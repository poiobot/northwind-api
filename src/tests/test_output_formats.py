"""Representations served by ?format=json|xml|yaml|pdf (HttpTools.formatResponse)."""
import io
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional, Union

import pytest
import yaml
from fastapi_pagination import LimitOffsetPage
from pydantic import BaseModel, ConfigDict, Field
from fastapi.encoders import jsonable_encoder

from lib.httptools import HttpTools

CREATED = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)


class Address(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    city: str = None
    postalCode: Union[float, str] = None


class Customer(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[str] = Field(default=None, alias="_id")
    companyName: str = None
    address: Address = None
    version: int = Field(default=1, alias="_version")
    created: datetime = Field(default=CREATED, alias="_created")


ALFKI = Customer(_id="ALFKI", companyName="Alfreds Futterkiste", address=Address(city="Berlin", postalCode=12209.0))
AROUT = Customer(_id="AROUT", companyName="Around the Horn", address=Address(city="London", postalCode="WA1 1DP"))
PAGE = LimitOffsetPage[Customer](items=[ALFKI, AROUT], total=91, limit=2, offset=0)


def _pdf_text(response):
    pypdf = pytest.importorskip("pypdf")
    return "\n".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(response.body)).pages)


class TestYaml:

    def test_single_record_uses_api_field_names(self):
        response = HttpTools.formatResponse(ALFKI, "yaml", name="customer")
        assert response.media_type == "application/yaml"
        assert yaml.safe_load(response.body) == {
            "id": "ALFKI", "companyName": "Alfreds Futterkiste",
            "address": {"city": "Berlin", "postalCode": 12209.0},
            "version": 1, "created": "2026-10-01T10:00:00Z",
        }

    def test_page_keeps_pagination_metadata(self):
        loaded = yaml.safe_load(HttpTools.formatResponse(PAGE, "yaml", name="customers").body)
        assert [c["id"] for c in loaded["items"]] == ["ALFKI", "AROUT"]
        assert (loaded["total"], loaded["limit"], loaded["offset"]) == (91, 2, 0)


class TestXml:

    def test_page_is_wrapped_in_the_collection_element(self):
        response = HttpTools.formatResponse(PAGE, "xml", name="customers")
        assert response.media_type == "application/xml"
        root = ET.fromstring(response.body)
        assert root.tag == "customers"
        assert [item.findtext("id") for item in root.find("items")] == ["ALFKI", "AROUT"]
        assert root.findtext("total") == "91"

    def test_single_record_keeps_nested_values(self):
        root = ET.fromstring(HttpTools.formatResponse(AROUT, "xml", name="customer").body)
        assert root.tag == "customer"
        assert root.findtext("address/postalCode") == "WA1 1DP"

    def test_empty_list_is_an_empty_document(self):
        root = ET.fromstring(HttpTools.formatResponse([], "xml", name="customers").body)
        assert root.tag == "customers" and len(root) == 0


class TestPdf:

    def test_single_record_lists_each_field(self):
        response = HttpTools.formatResponse(ALFKI, "pdf", name="customer")
        assert response.media_type == "application/pdf"
        assert response.headers["content-disposition"] == 'inline; filename="customer.pdf"'
        text = _pdf_text(response)
        for expected in ("companyName", "Alfreds Futterkiste", "address.city", "Berlin", "12209.0"):
            assert expected in text

    def test_page_has_a_row_per_record_and_its_metadata(self):
        text = _pdf_text(HttpTools.formatResponse(PAGE, "pdf", name="customers"))
        for expected in ("customers", "total=91", "Alfreds Futterkiste", "Around the Horn", "WA1 1DP"):
            assert expected in text

    def test_serialized_page_keeps_its_metadata(self):
        # The representation middleware sees the JSON a route produced, not the Page object
        text = _pdf_text(HttpTools.formatResponse(jsonable_encoder(PAGE), "pdf", name="customers"))
        assert "total=91" in text and text.count("companyName") == 1

    def test_record_with_items_and_total_is_one_record_not_a_page(self):
        order = {"id": 1, "customer": "Łódź Foods", "items": [{"product": "Chai", "qty": 2}], "total": 12.5}
        text = _pdf_text(HttpTools.formatResponse(order, "pdf", name="order"))
        assert "?ód? Foods" in text and "total=" not in text

    def test_document_with_a_very_long_field_renders_whole(self):
        # Like /api/describe, whose entities list becomes one long cell
        describe = {"service": {"name": "northwind"},
                    "entities": [{"name": f"Entity{i}", "fields": [f"field{j}" for j in range(60)]} for i in range(20)]}
        text = _pdf_text(HttpTools.formatResponse(describe, "pdf", name="describe"))
        assert "Entity0" in text and "Entity19" in text

    def test_table_cell_too_long_for_a_page_is_shortened(self):
        notes = [{"id": i, "notes": "lorem ipsum " * 1500} for i in range(3)]
        text = _pdf_text(HttpTools.formatResponse(notes, "pdf", name="notes"))
        assert "lorem ipsum" in text and "..." in text

    def test_collection_that_fits_is_one_table(self):
        text = _pdf_text(HttpTools.formatResponse(PAGE, "pdf", name="customers"))
        assert text.count("companyName") == 1

    def test_collection_too_wide_for_a_table_gets_a_block_per_record(self):
        wide = [{"id": i, **{f"field{n}": f"value number {n} of record {i}" for n in range(20)}} for i in range(3)]
        text = _pdf_text(HttpTools.formatResponse(wide, "pdf", name="wide"))
        assert text.count("field19") == 3
        assert "value number 19 of record 2" in text

    def test_characters_outside_latin1_do_not_break_rendering(self):
        lodz = Customer(_id="LODZ", companyName="Łódź Foods")
        assert "?ód? Foods" in _pdf_text(HttpTools.formatResponse(lodz, "pdf", name="customer"))


def test_json_is_plain_json():
    response = HttpTools.formatResponse([{"_id": "ALFKI", "created": CREATED}], "json", name="customers")
    assert response.media_type == "application/json"
    assert response.body == b'[{"_id":"ALFKI","created":"2026-10-01T10:00:00+00:00"}]'


def test_non_ascii_text_survives_xml_and_yaml():
    lodz = Customer(_id="LODZ", companyName="Łódź Foods", address=Address(city="México D.F."))
    root = ET.fromstring(HttpTools.formatResponse(lodz, "xml", name="customer").body)
    assert (root.findtext("companyName"), root.findtext("address/city")) == ("Łódź Foods", "México D.F.")
    loaded = yaml.safe_load(HttpTools.formatResponse(lodz, "yaml", name="customer").body)
    assert loaded["companyName"] == "Łódź Foods"
