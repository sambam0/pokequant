from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class BorderMeasure:
    left: float
    right: float
    top: float
    bottom: float
    left_pct: float
    right_pct: float
    top_pct: float
    bottom_pct: float
    lr_label: str
    tb_label: str
    inside_psa10: bool
    band: float
    confidence: str
    reason: str


def _gaussian_solve(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= scale
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            for j in range(col, n + 1):
                a[row][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]


def homography(src: list[Point], dst: list[Point]) -> list[float] | None:
    """Return h11..h32 (h33=1) mapping src → dst, or None if degenerate."""
    if len(src) != 4 or len(dst) != 4:
        return None
    matrix: list[list[float]] = []
    rhs: list[float] = []
    for s, d in zip(src, dst, strict=True):
        matrix.append([s.x, s.y, 1, 0, 0, 0, -d.x * s.x, -d.x * s.y])
        rhs.append(d.x)
        matrix.append([0, 0, 0, s.x, s.y, 1, -d.y * s.x, -d.y * s.y])
        rhs.append(d.y)
    return _gaussian_solve(matrix, rhs)


def apply_homography(h: list[float], p: Point) -> Point:
    x = h[0] * p.x + h[1] * p.y + h[2]
    y = h[3] * p.x + h[4] * p.y + h[5]
    w = h[6] * p.x + h[7] * p.y + 1.0
    if abs(w) < 1e-12:
        return Point(x, y)
    return Point(x / w, y / w)


def _quad_skew(points: list[Point]) -> float:
    """Mean absolute deviation of consecutive edge angles from 90°, in degrees."""
    if len(points) != 4:
        return 90.0
    edges = []
    for i in range(4):
        a, b = points[i], points[(i + 1) % 4]
        edges.append((b.x - a.x, b.y - a.y))

    def angle(u: tuple[float, float], v: tuple[float, float]) -> float:
        du = math.hypot(*u)
        dv = math.hypot(*v)
        if du < 1e-9 or dv < 1e-9:
            return 90.0
        cos = max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (du * dv)))
        return abs(abs(math.degrees(math.acos(cos))) - 90.0)

    return sum(angle(edges[i], edges[(i + 1) % 4]) for i in range(4)) / 4.0


def psa10_band(era: str = "modern") -> float:
    return 0.60 if era == "vintage" else 0.55


def measure_centering(
    outer: list[Point],
    inner: list[Point],
    *,
    era: str = "modern",
    width: float = 1000.0,
    height: float = 1400.0,
) -> BorderMeasure:
    band = psa10_band(era)
    dst = [Point(0, 0), Point(width, 0), Point(width, height), Point(0, height)]
    h = homography(outer, dst)
    if h is None:
        return BorderMeasure(
            0, 0, 0, 0, 0, 0, 0, 0, "—", "—", False, band, "low", "degenerate_quad"
        )

    warped = [apply_homography(h, p) for p in inner]
    xs = [p.x for p in warped]
    ys = [p.y for p in warped]
    left = min(xs)
    right = width - max(xs)
    top = min(ys)
    bottom = height - max(ys)
    if left <= 0 or right <= 0 or top <= 0 or bottom <= 0:
        return BorderMeasure(
            left,
            right,
            top,
            bottom,
            0,
            0,
            0,
            0,
            "—",
            "—",
            False,
            band,
            "low",
            "inner_outside_card",
        )

    lr = left + right
    tb = top + bottom
    left_pct = left / lr
    right_pct = right / lr
    top_pct = top / tb
    bottom_pct = bottom / tb
    lr_worse = max(left_pct, right_pct)
    tb_worse = max(top_pct, bottom_pct)
    inside = lr_worse <= band + 1e-9 and tb_worse <= band + 1e-9

    skew = _quad_skew(outer)
    if skew < 8:
        confidence = "high"
        reason = "clicked_inner_frame"
    elif skew < 18:
        confidence = "medium"
        reason = "photo_skewed"
    else:
        confidence = "low"
        reason = "strong_perspective_or_crop"

    def _pair(a: float, b: float) -> str:
        return f"{round(a * 100)}/{round(b * 100)}"

    return BorderMeasure(
        left=left,
        right=right,
        top=top,
        bottom=bottom,
        left_pct=left_pct,
        right_pct=right_pct,
        top_pct=top_pct,
        bottom_pct=bottom_pct,
        lr_label=_pair(left_pct, right_pct),
        tb_label=_pair(top_pct, bottom_pct),
        inside_psa10=inside,
        band=band,
        confidence=confidence,
        reason=reason,
    )


def parse_points(raw: list[dict] | list[list[float]]) -> list[Point]:
    points: list[Point] = []
    for item in raw:
        if isinstance(item, dict):
            points.append(Point(float(item["x"]), float(item["y"])))
        else:
            points.append(Point(float(item[0]), float(item[1])))
    return points
