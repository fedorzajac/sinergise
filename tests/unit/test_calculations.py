import pytest
from cli_tool.calculations import (
    calculate_bbox_area,
    needs_splitting,
    split_bbox,
    add_to_filename,
    convert_polygon_to_utm
)

def test_calculate_bbox_area():
    bbox = [0,0,1000,2000]
    area = calculate_bbox_area(bbox=bbox)
    assert area == 2_000_000

def test_needs_splitting_false():
    bbox = [0,0,1000,1000]
    assert needs_splitting(bbox=bbox) == False


def test_needs_splitting_true():
    bbox = [0,0,1000,2000]
    assert needs_splitting(bbox=bbox) == True

def test_split_bbox():
    bbox = [0,0,100,100]
    res = split_bbox(bbox=bbox)
    assert len(res) == 4
    assert res[0] == [0, 0, 50, 50]  # bottom-left
    assert res[1] == [50, 0, 100, 50]  # bottom-right
    assert res[2] == [0, 50, 50, 100]  # top-left
    assert res[3] == [50, 50, 100, 100]  # top-right

def test_add_to_filename():
    """Test filename modification."""
    res = add_to_filename("output.tif", "_2024-01-01")
    assert res == "output_2024-01-01.tif"

def test_convert_polygon_to_utm():
    """Test polygon conversion to UTM coordinates."""
    bbox = convert_polygon_to_utm("AOI_test.geojson")
    assert len(bbox) == 4
    assert all(isinstance(x, (int, float)) for x in bbox)
