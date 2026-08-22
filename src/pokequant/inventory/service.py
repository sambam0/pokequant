from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from pokequant.audit import audit
from pokequant.db.models import (
    Inspection,
    InventoryUnit,
    Lot,
    Purchase,
    ReturnRecord,
    Sale,
)
from pokequant.workflow.states import transition_inventory


def create_purchase(
    session: Session,
    *,
    purchase_code: str,
    purchase_price_ore: int,
    inbound_shipping_ore: int = 0,
    buyer_fee_ore: int = 0,
    import_cost_ore: int = 0,
    listing_id: int | None = None,
    watchlist_item_id: int | None = None,
    seller_type: str = "private",
    vat_code: str = "UNSET",
    approved_by: str = "domain",
    evidence_refs: str = "",
) -> Purchase:
    landed = purchase_price_ore + inbound_shipping_ore + buyer_fee_ore + import_cost_ore
    purchase = Purchase(
        purchase_code=purchase_code,
        listing_id=listing_id,
        watchlist_item_id=watchlist_item_id,
        seller_type=seller_type,
        purchase_price_ore=purchase_price_ore,
        buyer_fee_ore=buyer_fee_ore,
        inbound_shipping_ore=inbound_shipping_ore,
        import_cost_ore=import_cost_ore,
        landed_cost_ore=landed,
        vat_code=vat_code,
        approved_by=approved_by,
        evidence_refs=evidence_refs,
        purchased_at=datetime.now(timezone.utc),
    )
    session.add(purchase)
    audit(session, action="purchase.create", entity_type="purchase", entity_id=purchase_code, actor=approved_by)
    return purchase


def receive_unit(
    session: Session,
    *,
    inventory_code: str,
    purchase: Purchase,
    identity_name: str,
    allocated_cost_ore: int | None = None,
    condition: str = "NM",
    location: str = "RECEIVING",
    lot: Lot | None = None,
) -> InventoryUnit:
    unit = InventoryUnit(
        inventory_code=inventory_code,
        purchase_id=purchase.id,
        lot_id=lot.id if lot else None,
        watchlist_item_id=purchase.watchlist_item_id,
        identity_name=identity_name,
        condition=condition,
        allocated_cost_ore=allocated_cost_ore if allocated_cost_ore is not None else purchase.landed_cost_ore,
        vat_code=purchase.vat_code,
        location=location,
        state="receiving",
    )
    session.add(unit)
    session.flush()
    if purchase.arrived_at is None:
        purchase.arrived_at = datetime.now(timezone.utc)
        purchase.workflow_state = "received"
    audit(session, action="inventory.receive", entity_type="inventory_unit", entity_id=inventory_code)
    return unit


def allocate_lot_equal(session: Session, *, lot_code: str, purchase: Purchase, names: list[str]) -> Lot:
    if not names:
        raise ValueError("names required")
    lot = Lot(
        lot_code=lot_code,
        purchase_id=purchase.id,
        total_landed_cost_ore=purchase.landed_cost_ore,
        allocation_method="equal",
    )
    session.add(lot)
    session.flush()
    each = purchase.landed_cost_ore // len(names)
    remainder = purchase.landed_cost_ore - each * len(names)
    for i, name in enumerate(names):
        cost = each + (remainder if i == 0 else 0)
        receive_unit(
            session,
            inventory_code=f"{lot_code}-{i+1:02d}",
            purchase=purchase,
            identity_name=name,
            allocated_cost_ore=cost,
            lot=lot,
        )
    audit(session, action="lot.allocate_equal", entity_type="lot", entity_id=lot_code, details=f"n={len(names)}")
    return lot


def inspect_unit(
    session: Session,
    unit: InventoryUnit,
    *,
    inspector: str,
    observed_condition: str,
    authenticity_ok: bool = True,
    mismatch: bool = False,
    predicted_condition: str | None = None,
    blind: bool = False,
    notes: str = "",
) -> Inspection:
    unit.state = transition_inventory(unit.state, "inspecting")
    inspection = Inspection(
        inventory_unit_id=unit.id,
        inspector=inspector,
        blind=blind,
        predicted_condition=predicted_condition,
        observed_condition=observed_condition,
        authenticity_ok=authenticity_ok,
        mismatch=mismatch,
        notes=notes,
    )
    session.add(inspection)
    unit.condition = observed_condition
    if mismatch or not authenticity_ok:
        unit.state = transition_inventory(unit.state, "quarantine")
        unit.location = "QUARANTINE"
        unit.authenticity_status = "failed" if not authenticity_ok else "mismatch"
    else:
        unit.state = transition_inventory(unit.state, "ready")
        unit.location = "READY"
        unit.authenticity_status = "ok"
    audit(session, action="inventory.inspect", entity_type="inventory_unit", entity_id=unit.inventory_code, actor=inspector)
    return inspection


def record_sale(
    session: Session,
    unit: InventoryUnit,
    *,
    sale_code: str,
    channel: str,
    gross_ore: int,
    marketplace_fee_ore: int = 0,
    payment_fee_ore: int = 0,
    postage_ore: int = 0,
    packaging_ore: int = 0,
    shipping_charged_ore: int = 0,
    vat_code: str | None = None,
) -> Sale:
    if unit.state == "ready":
        unit.state = transition_inventory(unit.state, "listed")
    if unit.state == "listed":
        unit.state = transition_inventory(unit.state, "reserved")
    unit.state = transition_inventory(unit.state, "sold")
    unit.location = "SOLD"
    sale = Sale(
        sale_code=sale_code,
        inventory_unit_id=unit.id,
        channel=channel,
        gross_ore=gross_ore,
        shipping_charged_ore=shipping_charged_ore,
        marketplace_fee_ore=marketplace_fee_ore,
        payment_fee_ore=payment_fee_ore,
        postage_ore=postage_ore,
        packaging_ore=packaging_ore,
        vat_code=vat_code or unit.vat_code,
        settlement_state="provisional",
    )
    session.add(sale)
    audit(session, action="sale.record", entity_type="sale", entity_id=sale_code)
    return sale


def net_proceeds_ore(sale: Sale) -> int:
    return (
        sale.gross_ore
        + sale.shipping_charged_ore
        - sale.marketplace_fee_ore
        - sale.payment_fee_ore
        - sale.postage_ore
        - sale.packaging_ore
    )


def record_return(
    session: Session,
    sale: Sale,
    unit: InventoryUnit,
    *,
    return_code: str,
    refund_ore: int,
    reason: str = "",
    added_shipping_ore: int = 0,
) -> ReturnRecord:
    unit.state = transition_inventory(unit.state, "returned")
    unit.state = transition_inventory(unit.state, "quarantine")
    unit.location = "QUARANTINE"
    rec = ReturnRecord(
        return_code=return_code,
        sale_id=sale.id,
        inventory_unit_id=unit.id,
        reason=reason,
        refund_ore=refund_ore,
        added_shipping_ore=added_shipping_ore,
    )
    session.add(rec)
    sale.settlement_state = "returned"
    audit(session, action="return.record", entity_type="return", entity_id=return_code)
    return rec
