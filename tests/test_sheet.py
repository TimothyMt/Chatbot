import pytest

from shopbot.ingest.sheet import parse_grid, to_csv_export_url


def test_edit_url_converted():
    url = "https://docs.google.com/spreadsheets/d/ABC123_x-y/edit#gid=42"
    assert to_csv_export_url(url) == (
        "https://docs.google.com/spreadsheets/d/ABC123_x-y/export?format=csv&gid=42"
    )


def test_edit_url_without_gid_defaults_to_0():
    url = "https://docs.google.com/spreadsheets/d/ABC123/edit"
    assert to_csv_export_url(url).endswith("gid=0")


def test_export_url_kept_as_is():
    url = "https://docs.google.com/spreadsheets/d/ABC/export?format=csv&gid=7"
    assert to_csv_export_url(url) == url


def test_invalid_url_raises():
    with pytest.raises(ValueError):
        to_csv_export_url("https://example.com/khong-phai-sheet")


def test_parse_grid_strips_cells():
    grid = parse_grid("a , b\n c ,d\n")
    assert grid[0] == ["a", "b"]
    assert grid[1] == ["c", "d"]
