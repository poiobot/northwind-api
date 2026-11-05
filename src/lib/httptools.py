from fastapi import status, HTTPException, Body
from fastapi.responses import Response, HTMLResponse, JSONResponse
from fpdf import FPDF
from fpdf.fonts import FontFace

from json2xml.json2xml import Json2xml
from fastapi.encoders import jsonable_encoder
import json
import yaml
from typing import List, Literal, Union, get_args, get_origin
import re
import types

from pydantic import BaseModel

from lib.flatten_dict import FlattenDict

# Representations a client can request with ?format=
OutputFormat = Literal['json', 'xml', 'yaml', 'pdf']

# fpdf2 cannot split one table row across pages: a table cell shows at most TABLE_CELL_LIMIT
# characters, and a field/value block continues longer values on further rows of BLOCK_CHUNK
TABLE_CELL_LIMIT = 400
BLOCK_CHUNK = 2000
# Key sets of serialized fastapi-pagination pages (limit-offset and page-number)
PAGE_KEYS = ({"items", "total", "limit", "offset"}, {"items", "total", "page", "size", "pages"})


class HttpTools:

    @staticmethod
    def formatResponse(data, format: str='json', name: str='data'):
        """
        Render data (domain objects, dicts, lists or a pagination page) as json, xml, yaml or pdf,
        using the same field names as the JSON API (id, version... rather than _id, _version).
        :param name: collection or entity name: the xml root element, the pdf title and file name
        """
        content = jsonable_encoder(data, by_alias=False)
        if format == 'xml':
            # Json2xml returns None for empty data
            content = Json2xml(content, wrapper=name).to_xml() if content else f'<?xml version="1.0" encoding="UTF-8"?>\n<{name}/>\n'
            return Response(content=content, media_type="application/xml", status_code=status.HTTP_200_OK)
        if format == 'yaml':
            content = yaml.safe_dump(content, sort_keys=False, allow_unicode=True)
            return Response(content=content, media_type="application/yaml", status_code=status.HTTP_200_OK)
        if format == 'pdf':
            content = HttpTools._to_pdf(content, title=name)
            return Response(content=content, media_type="application/pdf", status_code=status.HTTP_200_OK,
                            headers={"Content-Disposition": f'inline; filename="{name}.pdf"'})
        return JSONResponse(content=content, status_code=status.HTTP_200_OK)

    @staticmethod
    def _to_pdf(content, title: str) -> bytes:
        """
        A collection becomes a table with a row per record (portrait, else landscape), or a
        field/value block per record when its columns can't fit; a single record is one block.
        A serialized pagination page gets its paging information under the title.
        """
        subtitle = None
        if isinstance(content, dict) and set(content) in PAGE_KEYS and isinstance(content["items"], list):
            subtitle = ", ".join(f"{k}={v}" for k, v in content.items() if k != "items")
            content = content["items"]
        single = not isinstance(content, list)
        records = [FlattenDict.flatten(r) if isinstance(r, dict) else {"value": r}
                   for r in ([content] if single else content)]
        header = list(dict.fromkeys(k for r in records for k in r))
        rows = [[HttpTools._pdf_text(r.get(k)) for k in header] for r in records]
        cells = [[HttpTools._shorten(text, TABLE_CELL_LIMIT) for text in row] for row in rows]

        pdf = FPDF(format="A4")
        pdf.set_title(title)
        pdf.set_auto_page_break(auto=True, margin=12)
        body_size = 9 if single else 7
        pdf.set_font("Helvetica", size=body_size)
        layout = None
        if not single and rows:
            for orientation, page_width in (("P", 210), ("L", 297)):
                widths = HttpTools._fit_columns(pdf, [header] + cells, page_width - pdf.l_margin - pdf.r_margin)
                if widths:
                    layout = (orientation, widths)
                    break

        pdf.add_page(orientation=layout[0] if layout else "P")
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(text=HttpTools._pdf_text(title), new_x="LMARGIN", new_y="NEXT")
        if subtitle:
            pdf.set_font("Helvetica", size=8)
            pdf.cell(text=HttpTools._pdf_text(subtitle), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("Helvetica", size=body_size)
        if not rows:
            pdf.cell(text="No records")
        elif layout:
            HttpTools._pdf_table(pdf, [header] + cells, layout[1])
        else:
            for row in rows:
                pairs = [[key if i == 0 else "", part]
                         for key, text in zip(header, row)
                         for i, part in enumerate(HttpTools._chunks(text, BLOCK_CHUNK))]
                HttpTools._pdf_table(pdf, pairs, HttpTools._fit_columns(pdf, pairs, pdf.epw))
                pdf.ln(4)
        return bytes(pdf.output())

    @staticmethod
    def _fit_columns(pdf, rows, room: float):
        """
        Column widths (mm) filling `room` for rows whose first row is the bold heading, or None
        when they don't fit. A column needs its longest word and at least 15mm of its text
        (40mm at most); the rest of the room goes in proportion to what is still wrapped.
        """
        pad = 2 * pdf.c_margin + pdf.line_width + 0.5  # cell margins and border, plus rounding room

        def width(text, bold):
            pdf.set_font(style="B" if bold else "")
            return pdf.get_string_width(text)

        try:
            columns = list(zip(*rows))
            words = [max(width(w, i == 0) for i, text in enumerate(col) for w in text.split() or [""]) for col in columns]
            texts = [max(width(text, i == 0) for i, text in enumerate(col)) for col in columns]
        finally:
            pdf.set_font(style="")
        need = [min(t, max(w, 15), 40) + pad for t, w in zip(texts, words)]
        want = [min(t, 60) + pad for t in texts]
        if sum(need) > room:
            return None
        slack = [max(w - n, 0) for w, n in zip(want, need)]
        spare = room - sum(need)
        if not sum(slack):
            return [n + spare / len(need) for n in need]
        return [n + spare * s / sum(slack) for n, s in zip(need, slack)]

    @staticmethod
    def _pdf_table(pdf, rows, widths):
        """Render text rows as a table; the first row is the bold heading, repeated on each page."""
        with pdf.table(col_widths=widths, line_height=pdf.font_size * 1.6, text_align="LEFT",
                       headings_style=FontFace(emphasis="BOLD", fill_color=(230, 230, 230))) as table:
            for row in rows:
                table_row = table.row()
                for text in row:
                    table_row.cell(text)

    @staticmethod
    def _shorten(text: str, limit: int) -> str:
        return text if len(text) <= limit else text[:limit - 3].rstrip() + "..."

    @staticmethod
    def _chunks(text: str, size: int) -> list:
        """Pieces of at most size characters, broken at spaces where possible."""
        pieces = []
        while len(text) > size:
            cut = text.rfind(" ", 0, size)
            cut = cut if cut > 0 else size
            pieces.append(text[:cut])
            text = text[cut:].lstrip()
        return pieces + [text]

    @staticmethod
    def _pdf_text(value) -> str:
        """Cell text: blank for null, lists joined, other values as JSON; core PDF fonts only cover latin-1."""
        if value is None:
            text = ""
        elif isinstance(value, str):
            text = value
        elif isinstance(value, list):
            text = ", ".join(HttpTools._pdf_text(v) for v in value)
        else:
            text = json.dumps(value, ensure_ascii=False)
        return text.encode("latin-1", "replace").decode("latin-1")

    @staticmethod
    def parse_expand(expand: str | None, expandable: tuple) -> List[str] | None:
        """
        Reference fields named by ?expand=field1,field2, in request order, for the DAO to replace
        with the referenced documents. A field that isn't one of `expandable` is a 422.
        """
        fields = list(dict.fromkeys(f.strip() for f in (expand or "").split(",") if f.strip()))
        unknown = [f for f in fields if f not in expandable]
        if unknown:
            allowed = ", ".join(expandable) if expandable else "none, this entity has no reference fields"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=[{
                "type": "enum", "loc": ["query", "expand"],
                "msg": f"Input should be one of: {allowed}", "input": unknown[0]}])
        return fields or None

    @staticmethod
    def parse_parameters(query_params, ignore_args: List[str]):
        defaults = {'keys': '*', 'format': 'json'}
        kvps = {key: query_params[key] for key in query_params.keys() if key not in ignore_args}
        # merge dictionaries priorising values from query
        # kvps = defaults | kvps
        kvps = {**defaults, **kvps}
        keys = '*' if kvps['keys'] == '*' else kvps['keys'].split(',')
        format = kvps['format']
        kvps.pop('keys')
        kvps.pop('format')
        kvps = [(key, kvps[key]) for key in kvps.keys()]
        if kvps == []: kvps = None
        return keys, format, kvps


class QueryParser:
    # Mapping of operators
    operator_map = {
        'EQ': '==', 'NEQ': '!=', 'GT': '>', 'GTE': '>=', 'LT': '<', 'LTE': '<=',
        'LIKE': 'like', 'IN': 'in', 'NOT-IN': 'not-in'
    }
    # OPERATOR(field,value): operators may contain a hyphen (NOT-IN), fields may be dotted (address.city)
    pattern = re.compile(r'([A-Za-z-]+)\(([\w.]+),(.*)\)')

    @staticmethod
    def transform_query_conditions(conditions, entity: type[BaseModel] = None):
        """
        ?q=OPERATOR(field,value) conditions as (field, operator, value) tuples for the DAO; IN and
        NOT-IN take values separated by |. Given the entity model, fields map to their stored names
        (id -> _id) and values convert to the field's type, so EQ(OrderID,10248) matches a number;
        LIKE patterns stay text. A condition that cannot be used is a 422, never silently dropped.
        """
        result = []
        for condition in conditions or []:
            match = QueryParser.pattern.fullmatch(condition.strip())
            operator = QueryParser.operator_map.get(match.group(1).upper()) if match else None
            try:
                if operator is None:
                    raise ValueError("Expected OPERATOR(field,value) with OPERATOR one of "
                                     + ", ".join(QueryParser.operator_map))
                field, accepted = QueryParser._field(entity, match.group(2))
                if operator == "like":
                    value = match.group(3)
                elif operator in ("in", "not-in"):
                    value = [QueryParser._convert(v, accepted, field) for v in match.group(3).split("|")]
                else:
                    value = QueryParser._convert(match.group(3), accepted, field)
            except ValueError as error:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=[{
                    "type": "value_error", "loc": ["query", "q"], "msg": str(error), "input": condition}])
            result.append((field, operator, value))
        return result

    @staticmethod
    def _field(entity, path: str):
        """
        Stored name and accepted scalar types of a dotted field path in the entity model. Paths go
        into embedded models but not through references; a name the model lacks keeps its spelling
        and accepts text.
        """
        parts, stored, model, accepted = path.split("."), [], entity, set()
        for part in parts:
            info = None
            if model is not None:
                info = model.model_fields.get(part) or next(
                    (f for f in model.model_fields.values() if f.alias == part), None)
            if info is None:
                return ".".join(stored + parts[len(stored):]), set()
            stored.append(info.alias or part)
            extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
            model = None if "table" in extra else QueryParser._embedded_model(info.annotation)
            accepted = QueryParser._scalar_types(info.annotation)
        return ".".join(stored), accepted

    @staticmethod
    def _embedded_model(annotation):
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return annotation
        return next((m for m in map(QueryParser._embedded_model, get_args(annotation)) if m), None)

    @staticmethod
    def _scalar_types(annotation) -> set:
        """bool, int, float and str among a field's types; a list contributes its element type."""
        if get_origin(annotation) in (Union, types.UnionType, list, set, tuple):
            return set().union(*map(QueryParser._scalar_types, get_args(annotation)))
        return {annotation} & {bool, int, float, str}

    @staticmethod
    def _convert(value: str, accepted: set, field: str):
        """The value as the field's type; numbers win when a field also accepts text."""
        if not accepted & {bool, int, float}:
            return value
        if bool in accepted and value.lower() in ("true", "false"):
            return value.lower() == "true"
        for number in (int, float):
            if number in accepted:
                try:
                    return number(value)
                except ValueError:
                    pass
        if str in accepted:
            return value
        expected = " or ".join(t.__name__ for t in (bool, int, float) if t in accepted)
        raise ValueError(f"{field} expects {expected}, not {value!r}")
