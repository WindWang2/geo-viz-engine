"""Free graphics items — nine paper annotation kinds + record registry.

``records`` (pure Python, no Qt) is the frozen cross-repo record contract
(spec §3.5). ``ITEM_CLASSES`` maps kind -> item class; ``item_from_record``
is the window's restore path (unknown/malformed records -> None, the host
counts and reports them).
"""

from geoviz_paleo_map.cartography.items.free import records
from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem
from geoviz_paleo_map.cartography.items.free.box_items import (
    FreeEllipseItem,
    FreeRectItem,
)

ITEM_CLASSES: dict[str, type[FreeGraphicsItem]] = {
    cls.kind: cls
    for cls in (FreeRectItem, FreeEllipseItem)
}


def item_from_record(record: dict) -> FreeGraphicsItem | None:
    """Validate ``record`` (frozen contract) and build the item; None when
    the kind is unknown or the record is malformed."""
    norm = records.parse_record(record)
    if norm is None:
        return None
    cls = ITEM_CLASSES.get(norm["kind"])
    if cls is None:
        return None
    try:
        return cls.from_normalized(norm)
    except Exception:
        return None


__all__ = [
    "records",
    "FreeGraphicsItem",
    "FreeRectItem",
    "FreeEllipseItem",
    "ITEM_CLASSES",
    "item_from_record",
]
