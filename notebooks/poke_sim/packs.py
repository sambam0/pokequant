"""Load product YAML configs and related paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def products_dir() -> Path:
    return DATA_DIR / "products"


def load_product(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        # Allow product_id stem under data/products/
        candidate = products_dir() / f"{path.stem}.yaml"
        if candidate.is_file():
            path = candidate
        else:
            raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Product config must be a mapping: {path}")
    return data


def load_products(directory: str | Path | None = None) -> list[dict[str, Any]]:
    directory = Path(directory) if directory else products_dir()
    products = []
    for path in sorted(directory.glob("*.yaml")):
        products.append(load_product(path))
    return products
