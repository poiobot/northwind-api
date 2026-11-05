"""?expand= on generated routes (HttpTools.parse_expand)."""
import pytest
from fastapi import HTTPException

from lib.httptools import HttpTools

EXPANDABLE = ("supplierID", "categoryID")


@pytest.mark.parametrize("expand", [None, "", " "])
def test_no_expansion_requested(expand):
    assert HttpTools.parse_expand(expand, EXPANDABLE) is None


def test_comma_separated_fields_in_request_order():
    assert HttpTools.parse_expand("categoryID,supplierID", EXPANDABLE) == ["categoryID", "supplierID"]


def test_spaces_and_repeats_are_tolerated():
    assert HttpTools.parse_expand(" supplierID , supplierID,", EXPANDABLE) == ["supplierID"]


def test_unknown_field_is_a_422_naming_the_expandable_ones():
    with pytest.raises(HTTPException) as error:
        HttpTools.parse_expand("supplierID,bogus", EXPANDABLE)
    assert error.value.status_code == 422
    (detail,) = error.value.detail
    assert detail["loc"] == ["query", "expand"] and detail["input"] == "bogus"
    assert "supplierID, categoryID" in detail["msg"]


def test_entity_without_references_rejects_any_expansion():
    with pytest.raises(HTTPException) as error:
        HttpTools.parse_expand("anything", ())
    assert "no reference fields" in error.value.detail[0]["msg"]
