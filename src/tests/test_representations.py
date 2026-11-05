"""Multi-representation responses (lib/representation.py)."""
import io
import xml.etree.ElementTree as ET

import pytest
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route

from lib.representation import InvalidFormat, RepresentationMiddleware, install_representations, negotiate

BROWSER = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"


class TestNegotiate:

    @pytest.mark.parametrize("fmt", ["json", "xml", "yaml", "pdf"])
    def test_format_parameter_selects_the_representation(self, fmt):
        assert negotiate(fmt, None) == fmt

    def test_format_parameter_is_case_insensitive(self):
        assert negotiate("XML", None) == "xml"

    def test_unknown_format_parameter_is_rejected(self):
        with pytest.raises(InvalidFormat):
            negotiate("csv", None)

    def test_format_parameter_overrides_accept(self):
        assert negotiate("json", "application/xml") == "json"

    @pytest.mark.parametrize("accept, expected", [
        ("application/json", "json"),
        ("application/xml", "xml"),
        ("text/xml", "xml"),
        ("application/yaml", "yaml"),
        ("application/x-yaml", "yaml"),
        ("text/yaml", "yaml"),
        ("application/pdf", "pdf"),
    ])
    def test_accept_selects_each_served_media_type(self, accept, expected):
        assert negotiate(None, accept) == expected

    def test_highest_q_wins(self):
        assert negotiate(None, "application/json;q=0.5, application/xml") == "xml"

    def test_equal_q_prefers_json_then_xml_yaml_pdf(self):
        assert negotiate(None, "application/pdf, application/yaml") == "yaml"

    def test_q_zero_is_not_acceptable(self):
        assert negotiate(None, "application/xml;q=0") == "json"

    @pytest.mark.parametrize("accept", [None, "", "*/*", "application/*", "text/*", "text/csv"])
    def test_json_when_nothing_explicit_is_served(self, accept):
        assert negotiate(None, accept) == "json"

    def test_browsers_get_json(self):
        assert negotiate(None, BROWSER) == "json"

    @pytest.mark.parametrize("accept, expected", [
        ("Application/XML; charset=UTF-8", "xml"),
        (" application/yaml ;q=0.9 , application/json;q=0.1", "yaml"),
        ("application/xml;q=abc", "json"),
    ])
    def test_accept_parsing_tolerates_case_parameters_and_bad_q(self, accept, expected):
        assert negotiate(None, accept) == expected


def _pdf_text(content: bytes) -> str:
    pypdf = pytest.importorskip("pypdf")
    return "\n".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(content)).pages)


def _shop() -> FastAPI:
    """A small API shaped like a generated one, with the middleware inside CORS as the app template does."""
    app = FastAPI()

    @app.get("/shop/products")
    def list_products():
        return {"items": [{"id": 1, "name": "Chai"}, {"id": 2, "name": "Chang"}], "total": 2, "limit": 50, "offset": 0}

    @app.get("/shop/products/{id}")
    def find_product(id: int):
        if id == 999:
            raise HTTPException(status_code=404, detail="product 999 not found")
        return {"id": id, "name": "Chai"}

    @app.post("/shop/products", status_code=201)
    def create_product(data: dict):
        return data

    @app.delete("/shop/products/{id}")
    def delete_product(id: int):
        return JSONResponse({"product": id, "status": "DELETED"})

    @app.get("/shop/api/describe")
    def describe():
        return {"service": {"name": "shop"}}

    @app.get("/shop/greeting")
    def greeting():
        return PlainTextResponse("hello")

    @app.get("/shop/stream")
    def stream():
        chunks = [b'{"items": [{"id": 1}', b', {"id": 2}], "total": 2}']
        return StreamingResponse(iter(chunks), media_type="application/json")

    @app.get("/shop/broken")
    def broken():
        return Response(content=b"{not json", media_type="application/json")

    @app.get("/shop/odd")
    def odd():
        return {"a:b": 1}  # valid JSON, but not a valid XML element name

    @app.delete("/shop/carts/{id}", status_code=204)
    def delete_cart(id: int):
        return None

    async def mcp_endpoint(request):
        return JSONResponse({"jsonrpc": "2.0"})

    app.mount("/mcp", Starlette(routes=[Route("/", mcp_endpoint)]))
    app.add_middleware(RepresentationMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=["*"])
    return app


client = TestClient(_shop())


class TestMiddleware:

    def test_list_as_xml_is_wrapped_in_the_collection(self):
        response = client.get("/shop/products?format=xml")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/xml")
        root = ET.fromstring(response.content)
        assert root.tag == "products" and root.findtext("total") == "2"

    def test_accept_header_selects_yaml(self):
        response = client.get("/shop/products/1", headers={"Accept": "application/yaml"})
        assert response.headers["content-type"].startswith("application/yaml")
        assert yaml.safe_load(response.content) == {"id": 1, "name": "Chai"}

    def test_item_pdf_is_named_after_the_entity(self):
        response = client.get("/shop/products/1?format=pdf")
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"] == 'inline; filename="product.pdf"'

    def test_pdf_list_shows_paging(self):
        text = _pdf_text(client.get("/shop/products?format=pdf").content)
        assert "total=2" in text and "Chang" in text

    def test_errors_keep_their_status_and_are_named_error(self):
        response = client.get("/shop/products/999?format=xml")
        assert response.status_code == 404
        root = ET.fromstring(response.content)
        assert root.tag == "error" and root.findtext("detail") == "product 999 not found"

    def test_validation_errors_are_converted_too(self):
        response = client.get("/shop/products/abc?format=yaml")
        assert response.status_code == 422
        assert yaml.safe_load(response.content)["detail"][0]["loc"] == ["path", "id"]

    def test_write_responses_are_converted(self):
        created = client.post("/shop/products?format=yaml", json={"id": 3, "name": "Aniseed Syrup"})
        assert created.status_code == 201
        assert yaml.safe_load(created.content) == {"id": 3, "name": "Aniseed Syrup"}
        deleted = client.delete("/shop/products/3", headers={"Accept": "application/xml"})
        assert ET.fromstring(deleted.content).findtext("status") == "DELETED"

    def test_other_routes_are_named_after_their_last_segment(self):
        assert ET.fromstring(client.get("/shop/api/describe?format=xml").content).tag == "describe"

    def test_unknown_format_is_a_422_naming_the_allowed_values(self):
        response = client.get("/shop/products?format=csv")
        assert response.status_code == 422
        assert response.headers["content-type"] == "application/json"
        assert "'json', 'xml', 'yaml' or 'pdf'" in response.json()["detail"][0]["msg"]

    def test_json_responses_pass_through_with_vary(self):
        response = client.get("/shop/products/1")
        assert response.json() == {"id": 1, "name": "Chai"}
        assert response.headers["vary"] == "Accept"

    def test_browsers_get_json(self):
        response = client.get("/shop/products/1", headers={"Accept": BROWSER})
        assert response.headers["content-type"] == "application/json"

    def test_non_json_responses_pass_through(self):
        response = client.get("/shop/greeting?format=xml")
        assert response.text == "hello" and response.headers["vary"] == "Accept"

    @pytest.mark.parametrize("path", ["/openapi.json?format=xml", "/mcp/?format=xml"])
    def test_excluded_paths_are_untouched(self, path):
        response = client.get(path)
        assert response.headers["content-type"] == "application/json"
        assert "vary" not in response.headers

    def test_docs_are_untouched(self):
        assert client.get("/docs?format=xml").headers["content-type"].startswith("text/html")

    def test_json_streamed_in_chunks_is_converted_whole(self):
        root = ET.fromstring(client.get("/shop/stream?format=xml").content)
        assert [item.findtext("id") for item in root.find("items")] == ["1", "2"]

    def test_body_that_is_not_json_is_sent_unchanged(self):
        assert client.get("/shop/broken?format=xml").content == b"{not json"

    def test_cors_headers_survive_conversion(self):
        response = client.get("/shop/products?format=yaml", headers={"Origin": "https://example.com"})
        assert response.headers["access-control-allow-origin"] == "*"

    def test_a_response_that_cannot_be_rendered_is_sent_as_json(self):
        response = client.get("/shop/odd?format=xml", headers={"Origin": "https://example.com"})
        assert (response.status_code, response.headers["content-type"]) == (200, "application/json")
        assert response.json() == {"a:b": 1}
        assert response.headers["access-control-allow-origin"] == "*"

    def test_no_content_responses_stay_empty(self):
        response = client.delete("/shop/carts/1?format=xml")
        assert (response.status_code, response.content) == (204, b"")


class TestInstall:

    def setup_method(self):
        app = FastAPI()

        @app.get("/shop/products")
        def list_products():
            return {"items": [], "total": 0}

        @app.get("/shop/legacy")
        def legacy(format: str = "json"):
            return {"format": format}

        install_representations(app)
        self.client = TestClient(app)

    def test_every_operation_documents_the_format_parameter(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        (param,) = [p for p in paths["/shop/products"]["get"]["parameters"] if p["name"] == "format"]
        assert (param["in"], param["schema"]["enum"]) == ("query", ["json", "xml", "yaml", "pdf"])

    def test_a_route_declaring_format_is_documented_once(self):
        params = self.client.get("/openapi.json").json()["paths"]["/shop/legacy"]["get"]["parameters"]
        assert [p["name"] for p in params].count("format") == 1

    def test_the_app_serves_representations(self):
        response = self.client.get("/shop/products?format=yaml")
        assert response.headers["content-type"].startswith("application/yaml")
