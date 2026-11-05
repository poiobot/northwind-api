"""
Multi-representation responses: every JSON response of a Spore API can be served as json, xml,
yaml or pdf, chosen by ?format= or the Accept header. install_representations(app) wires it in.
"""
import json
import logging

import inflection
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse

from lib.httptools import HttpTools

logger = logging.getLogger(__name__)

# Served representations, in order of preference when Accept gives them the same q
FORMATS = ("json", "xml", "yaml", "pdf")

MEDIA_TYPES = {
    "application/json": "json",
    "application/xml": "xml",
    "text/xml": "xml",
    "application/yaml": "yaml",
    "application/x-yaml": "yaml",
    "text/yaml": "yaml",
    "application/pdf": "pdf",
}

# Always served as they are: the API docs and the MCP sub-app
EXCLUDED_PATHS = ("/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json")
EXCLUDED_PREFIX = "/mcp"


class InvalidFormat(ValueError):
    """?format= names something other than FORMATS."""


def negotiate(format_param: str | None, accept: str | None) -> str:
    """
    ?format= when present, else the best explicitly accepted media type by q-value, else json.
    Wildcards never select a representation, and browsers (Accept with text/html) get json:
    they rank application/xml above */*, which would turn every opened link into XML.
    """
    if format_param is not None:
        fmt = format_param.strip().lower()
        if fmt not in FORMATS:
            raise InvalidFormat(format_param)
        return fmt
    accepted = list(_accepted(accept or ""))
    if any(media_type == "text/html" for media_type, _ in accepted):
        return "json"
    best, best_q = "json", 0.0
    for media_type, q in accepted:
        fmt = MEDIA_TYPES.get(media_type)
        if fmt and (q > best_q or (q == best_q and FORMATS.index(fmt) < FORMATS.index(best))):
            best, best_q = fmt, q
    return best


def _accepted(header: str):
    """(media type, q) for each entry of an Accept header, leaving out the q=0 ones."""
    for entry in header.split(","):
        media_type, _, params = entry.partition(";")
        media_type = media_type.strip().lower()
        q = 1.0
        for param in params.split(";"):
            key, _, value = param.partition("=")
            if key.strip().lower() == "q":
                try:
                    q = float(value)
                except ValueError:
                    q = 0.0
        if media_type and q > 0:
            yield media_type, q


def representation_name(scope: dict, status: int) -> str:
    """
    XML root element and PDF title/filename: error for failures, the entity for an item route
    (/shop/products/{id} -> product), otherwise the route's last path segment.
    """
    if status >= 400:
        return "error"
    route = scope.get("route")
    segments = [s for s in getattr(route, "path", scope.get("path", "")).split("/") if s]
    if not segments:
        return "data"
    if segments[-1].startswith("{"):
        return inflection.singularize(segments[-2]) if len(segments) > 1 else "data"
    return segments[-1]


def _excluded(path: str) -> bool:
    return path in EXCLUDED_PATHS or path == EXCLUDED_PREFIX or path.startswith(EXCLUDED_PREFIX + "/")


def _convertible(status: int, headers: MutableHeaders) -> bool:
    """A JSON response that may carry a body (not 1xx, 204 No Content or 304 Not Modified)."""
    content_type = headers.get("content-type", "").split(";")[0].strip()
    return content_type == "application/json" and status >= 200 and status not in (204, 304)


class RepresentationMiddleware:
    """Serves each JSON response in the representation the request negotiated (see negotiate)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or _excluded(scope["path"]):
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        try:
            fmt = negotiate(request.query_params.get("format"), request.headers.get("accept"))
        except InvalidFormat as error:
            response = JSONResponse(status_code=422, headers={"Vary": "Accept"}, content={"detail": [{
                "type": "enum", "loc": ["query", "format"],
                "msg": "Input should be 'json', 'xml', 'yaml' or 'pdf'", "input": str(error)}]})
            await response(scope, receive, send)
            return
        await self.app(scope, receive, _Representation(scope, send, fmt).send)


class _Representation:
    """Wraps send(): adds Vary, and holds back a JSON response to send it re-rendered."""

    def __init__(self, scope, send, fmt: str):
        self.scope, self.downstream, self.fmt = scope, send, fmt
        self.start = None
        self.body = bytearray()

    async def send(self, message):
        if message["type"] == "http.response.start":
            headers = MutableHeaders(scope=message)
            headers.add_vary_header("Accept")
            if self.fmt != "json" and _convertible(message["status"], headers):
                self.start = message
                return
        elif message["type"] == "http.response.body" and self.start is not None:
            self.body += message.get("body", b"")
            if not message.get("more_body", False):
                await self._send_rendered()
            return
        await self.downstream(message)

    async def _send_rendered(self):
        try:
            data = json.loads(self.body) if self.body else None
            name = representation_name(self.scope, self.start["status"])
            rendered = HttpTools.formatResponse(data, self.fmt, name=name)
        except Exception:
            # Not JSON after all, or not renderable (an XML-invalid key, say): send it as it came
            logger.warning("Sending %s as JSON: it could not be rendered as %s",
                           self.scope["path"], self.fmt, exc_info=True)
            await self.downstream(self.start)
            await self.downstream({"type": "http.response.body", "body": bytes(self.body)})
            return
        headers = MutableHeaders(scope=self.start)
        for key in ("content-type", "content-length", "content-disposition"):
            del headers[key]
            if key in rendered.headers:
                headers.append(key, rendered.headers[key])
        await self.downstream(self.start)
        await self.downstream({"type": "http.response.body", "body": rendered.body})


# Documented on every operation, so Swagger's "Try it out" can request each representation
FORMAT_PARAMETER = {
    "name": "format",
    "in": "query",
    "required": False,
    "description": "Representation of the response: json, xml, yaml or pdf. Without it, the Accept header decides.",
    "schema": {"type": "string", "enum": list(FORMATS), "default": "json"},
}
_OPERATIONS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}


def install_representations(app) -> None:
    """Serves every JSON response of app as json, xml, yaml or pdf and documents ?format= on every operation."""
    app.add_middleware(RepresentationMiddleware)
    build_openapi = app.openapi

    def openapi():
        if app.openapi_schema is None:
            for path_item in build_openapi().get("paths", {}).values():
                for method, operation in path_item.items():
                    if method not in _OPERATIONS:
                        continue
                    params = operation.setdefault("parameters", [])
                    if not any(p.get("in") == "query" and p.get("name") == "format" for p in params):
                        params.append(dict(FORMAT_PARAMETER))
        return app.openapi_schema

    app.openapi = openapi
