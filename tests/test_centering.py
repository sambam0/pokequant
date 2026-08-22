from fastapi.testclient import TestClient

from pokequant.centering import Point, measure_centering, psa10_band
from pokequant.web.app import app


def test_psa10_band():
    assert psa10_band("modern") == 0.55
    assert psa10_band("vintage") == 0.60


def _rect(x0, y0, x1, y1) -> list[Point]:
    return [Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)]


def test_perfect_50_50_is_inside():
    outer = _rect(0, 0, 1000, 1400)
    inner = _rect(80, 80, 920, 1320)
    result = measure_centering(outer, inner)
    assert result.lr_label == "50/50"
    assert result.tb_label == "50/50"
    assert result.inside_psa10 is True
    assert result.confidence == "high"


def test_off_center_fails_modern_band():
    outer = _rect(0, 0, 1000, 1400)
    inner = _rect(40, 80, 880, 1320)
    result = measure_centering(outer, inner, era="modern")
    assert result.inside_psa10 is False
    assert result.left_pct < 0.40


def test_skewed_photo_lowers_confidence():
    outer = [Point(0, 0), Point(1000, 280), Point(620, 1400), Point(180, 980)]
    inner = [Point(80, 80), Point(880, 300), Point(580, 1260), Point(240, 900)]
    result = measure_centering(outer, inner)
    assert result.confidence in {"medium", "low"}
    assert result.reason != "clicked_inner_frame"


def test_centering_page_and_measure_api():
    client = TestClient(app)
    page = client.get("/centering")
    assert page.status_code == 200
    assert "Centering overlay" in page.text
    resp = client.post(
        "/centering/measure",
        json={
            "era": "modern",
            "outer": [
                {"x": 0, "y": 0},
                {"x": 1000, "y": 0},
                {"x": 1000, "y": 1400},
                {"x": 0, "y": 1400},
            ],
            "inner": [
                {"x": 80, "y": 80},
                {"x": 920, "y": 80},
                {"x": 920, "y": 1320},
                {"x": 80, "y": 1320},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["inside_psa10"] is True
    assert "50/50" in data["verdict"]
