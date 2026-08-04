"""Free graphics items — nine paper annotation kinds + record registry.

``records`` (pure Python, no Qt) is the frozen cross-repo record contract
(spec §3.5). ``ITEM_CLASSES`` maps kind -> item class; populated as the item
modules land (Tasks 3–6).
"""

from geoviz_paleo_map.cartography.items.free import records

ITEM_CLASSES: dict = {}

__all__ = ["records", "ITEM_CLASSES"]
