from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pokequant.centering import measure_centering, parse_points
from pokequant.config import get_settings
from pokequant.db.models import (
    AlertDelivery,
    Decision,
    GradeCatalog,
    InventoryUnit,
    Listing,
    PrecisionSnapshot,
    Sale,
    Valuation,
    WatchlistItem,
)
from pokequant.db.session import get_session
from pokequant.expansion import plan_expansion
from pokequant.inventory.service import net_proceeds_ore
from pokequant.money import format_sek
from pokequant.services.decisions import record_decision
from pokequant.services.precision import latest_precision
from pokequant.web.auth import require_write_auth

_settings = get_settings()
_docs = None if _settings.app_env == "production" else "/api/docs"
app = FastAPI(title="PokeQuant", docs_url=_docs, redoc_url=None, openapi_url=None if _docs is None else "/openapi.json")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    watch_count = session.query(WatchlistItem).filter(WatchlistItem.active.is_(True)).count()
    open_alerts = (
        session.query(Listing).filter(Listing.workflow_state.in_(["alerted", "scored"])).count()
    )
    snap = latest_precision(session, source="tradera")
    expansion = plan_expansion(session)
    inventory = session.query(InventoryUnit).order_by(InventoryUnit.id.desc()).limit(20).all()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "watch_count": watch_count,
            "open_alerts": open_alerts,
            "snap": snap,
            "expansion": expansion,
            "inventory": inventory,
            "format_sek": format_sek,
        },
    )


@app.get("/review", response_class=HTMLResponse)
def review_queue(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    limit = get_settings().review_wip_limit
    listings = (
        session.query(Listing)
        .filter(Listing.workflow_state == "alerted")
        .order_by(Listing.last_seen_at.desc())
        .limit(limit)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "review.html",
        {"listings": listings, "format_sek": format_sek},
    )


@app.post("/review/{listing_id}")
def review_decide(
    listing_id: int,
    intent: str = Form(...),
    identity_label: str = Form("correct"),
    deal_label: str = Form(""),
    quality_label: str = Form(""),
    reason_code: str = Form(""),
    valuation_id: int = Form(0),
    session: Session = Depends(get_session),
    _: None = Depends(require_write_auth),
) -> RedirectResponse:
    listing = session.get(Listing, listing_id)
    if listing:
        valuation = None
        if valuation_id:
            valuation = session.get(Valuation, valuation_id)
        if valuation is None:
            alert = (
                session.query(AlertDelivery)
                .filter_by(listing_id=listing.id)
                .order_by(AlertDelivery.id.desc())
                .first()
            )
            if alert and alert.valuation_id:
                valuation = session.get(Valuation, alert.valuation_id)
        record_decision(
            session,
            listing,
            intent=intent,
            identity_label=identity_label,
            deal_label=deal_label or quality_label or "n/a",
            quality_label=deal_label or quality_label,
            reason_code=reason_code or None,
            false_match=identity_label == "wrong" or reason_code == "wrong_identity",
            valuation=valuation,
        )
        session.commit()
    return RedirectResponse("/review", status_code=303)


@app.get("/precision", response_class=HTMLResponse)
def precision_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    snap = latest_precision(session, source="tradera")
    history = session.query(PrecisionSnapshot).order_by(PrecisionSnapshot.id.desc()).limit(20).all()
    recent = session.query(Decision).order_by(Decision.id.desc()).limit(40).all()
    return templates.TemplateResponse(
        request,
        "precision.html",
        {"snap": snap, "history": history, "recent": recent},
    )


@app.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    units = session.query(InventoryUnit).order_by(InventoryUnit.id.desc()).limit(100).all()
    sales = session.query(Sale).order_by(Sale.id.desc()).limit(50).all()
    return templates.TemplateResponse(
        request,
        "inventory.html",
        {
            "units": units,
            "sales": sales,
            "format_sek": format_sek,
            "net_proceeds_ore": net_proceeds_ore,
        },
    )


@app.get("/watchlist", response_class=HTMLResponse)
def watchlist_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    items = (
        session.query(WatchlistItem)
        .filter(WatchlistItem.active.is_(True))
        .order_by(WatchlistItem.watch_id.asc())
        .all()
    )
    return templates.TemplateResponse(request, "watchlist.html", {"items": items})


@app.get("/grade-targets", response_class=HTMLResponse)
def grade_targets_page(
    request: Request,
    tier: str = "",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    q = session.query(GradeCatalog).filter(GradeCatalog.tier.is_not(None))
    if tier in {"workhorse", "hunt", "moonshot"}:
        q = q.filter(GradeCatalog.tier == tier)
    rows = q.order_by(GradeCatalog.ev_ore.desc()).limit(200).all()
    return templates.TemplateResponse(
        request,
        "grade_targets.html",
        {"rows": rows, "tier": tier, "format_sek": format_sek},
    )


@app.get("/centering", response_class=HTMLResponse)
def centering_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "centering.html", {})


class _PointIn(BaseModel):
    x: float
    y: float


class _MeasureIn(BaseModel):
    outer: list[_PointIn] = Field(min_length=4, max_length=4)
    inner: list[_PointIn] = Field(min_length=4, max_length=4)
    era: str = "modern"


@app.post("/centering/measure")
def centering_measure(body: _MeasureIn) -> JSONResponse:
    result = measure_centering(
        parse_points([{"x": p.x, "y": p.y} for p in body.outer]),
        parse_points([{"x": p.x, "y": p.y} for p in body.inner]),
        era=body.era if body.era == "vintage" else "modern",
    )
    band = f"{int(round(result.band * 100))}/{int(round((1 - result.band) * 100))}"
    side = "inside" if result.inside_psa10 else "outside"
    verdict = f"L/R {result.lr_label}, T/B {result.tb_label} — {side} {band}"
    return JSONResponse(
        {
            "left_pct": result.left_pct,
            "right_pct": result.right_pct,
            "top_pct": result.top_pct,
            "bottom_pct": result.bottom_pct,
            "lr_label": result.lr_label,
            "tb_label": result.tb_label,
            "inside_psa10": result.inside_psa10,
            "band": result.band,
            "confidence": result.confidence,
            "reason": result.reason,
            "verdict": verdict,
        }
    )
