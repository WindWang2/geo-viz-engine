from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal


@dataclass
class HorizonPick:
    pick_id: str
    formation_name: str
    well_depths: list[tuple[str, float | None]]
    source: str = "manual"
    confidence: dict[str, float] = field(default_factory=dict)

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:12]

    def depth_for_well(self, well: str) -> float | None:
        for w, d in self.well_depths:
            if w == well:
                return d
        return None

    def set_depth(self, well: str, depth: float | None) -> None:
        for i, (w, _) in enumerate(self.well_depths):
            if w == well:
                self.well_depths[i] = (w, depth)
                return
        self.well_depths.append((well, depth))

    def connected_wells(self) -> list[str]:
        return [w for w, d in self.well_depths if d is not None]


class PickCommand(ABC):
    @abstractmethod
    def execute(self, model: HorizonPicksModel) -> None: ...

    @abstractmethod
    def undo(self, model: HorizonPicksModel) -> None: ...


class AddPickCmd(PickCommand):
    def __init__(self, pick: HorizonPick):
        self.pick = pick

    def execute(self, model: HorizonPicksModel) -> None:
        model._picks[self.pick.pick_id] = self.pick

    def undo(self, model: HorizonPicksModel) -> None:
        model._picks.pop(self.pick.pick_id, None)


class DeletePickCmd(PickCommand):
    def __init__(self, pick_id: str):
        self.pick_id = pick_id
        self._snapshot: HorizonPick | None = None

    def execute(self, model: HorizonPicksModel) -> None:
        self._snapshot = model._picks.pop(self.pick_id, None)

    def undo(self, model: HorizonPicksModel) -> None:
        if self._snapshot is not None:
            model._picks[self.pick_id] = self._snapshot


class MovePickCmd(PickCommand):
    def __init__(self, pick_id: str, well: str, new_depth: float):
        self.pick_id = pick_id
        self.well = well
        self.new_depth = new_depth
        self._old_depth: float | None = None

    def execute(self, model: HorizonPicksModel) -> None:
        pick = model._picks.get(self.pick_id)
        if pick is None:
            return
        self._old_depth = pick.depth_for_well(self.well)
        pick.set_depth(self.well, self.new_depth)

    def undo(self, model: HorizonPicksModel) -> None:
        pick = model._picks.get(self.pick_id)
        if pick is None:
            return
        pick.set_depth(self.well, self._old_depth)


class ConnectPickCmd(PickCommand):
    def __init__(self, pick_id: str, well: str, depth: float):
        self.pick_id = pick_id
        self.well = well
        self.depth = depth

    def execute(self, model: HorizonPicksModel) -> None:
        pick = model._picks.get(self.pick_id)
        if pick is not None:
            pick.set_depth(self.well, self.depth)

    def undo(self, model: HorizonPicksModel) -> None:
        pick = model._picks.get(self.pick_id)
        if pick is not None:
            pick.set_depth(self.well, None)


class CompositePickCmd(PickCommand):
    def __init__(self, commands: list[PickCommand]):
        self._commands = commands

    def execute(self, model: HorizonPicksModel) -> None:
        for cmd in self._commands:
            cmd.execute(model)

    def undo(self, model: HorizonPicksModel) -> None:
        for cmd in reversed(self._commands):
            cmd.undo(model)


class PicksUndoManager:
    def __init__(self, max_depth: int = 100):
        self._undo_stack: list[PickCommand] = []
        self._redo_stack: list[PickCommand] = []
        self._max_depth = max_depth

    def execute(self, cmd: PickCommand, model: HorizonPicksModel) -> None:
        cmd.execute(model)
        self._undo_stack.append(cmd)
        if len(self._undo_stack) > self._max_depth:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self, model: HorizonPicksModel) -> bool:
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo(model)
        self._redo_stack.append(cmd)
        return True

    def redo(self, model: HorizonPicksModel) -> bool:
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.execute(model)
        self._undo_stack.append(cmd)
        return True

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()


class HorizonPicksModel(QObject):
    picks_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._picks: dict[str, HorizonPick] = {}
        self.undo_manager = PicksUndoManager()

    def add_pick(self, formation: str, well: str, depth: float, source: str = "manual") -> str:
        pick_id = HorizonPick.new_id()
        pick = HorizonPick(
            pick_id=pick_id,
            formation_name=formation,
            well_depths=[(well, depth)],
            source=source,
        )
        cmd = AddPickCmd(pick)
        self.undo_manager.execute(cmd, self)
        self.picks_changed.emit()
        return pick_id

    def connect_picks(self, pick_id: str, well: str, depth: float) -> None:
        cmd = ConnectPickCmd(pick_id, well, depth)
        self.undo_manager.execute(cmd, self)
        self.picks_changed.emit()

    def delete_pick(self, pick_id: str) -> None:
        cmd = DeletePickCmd(pick_id)
        self.undo_manager.execute(cmd, self)
        self.picks_changed.emit()

    def move_pick(self, pick_id: str, well: str, new_depth: float) -> None:
        cmd = MovePickCmd(pick_id, well, new_depth)
        self.undo_manager.execute(cmd, self)
        self.picks_changed.emit()

    def accept_dtw_pick(self, pick_id: str) -> None:
        pick = self._picks.get(pick_id)
        if pick is not None and pick.source == "dtw":
            pick.source = "manual"
            pick.confidence.clear()
            self.picks_changed.emit()

    def reject_dtw_pick(self, pick_id: str) -> None:
        pick = self._picks.get(pick_id)
        if pick is not None and pick.source == "dtw":
            self.delete_pick(pick_id)

    def picks_for_well(self, well: str) -> list[HorizonPick]:
        return [p for p in self._picks.values() if p.depth_for_well(well) is not None]

    def all_picks(self) -> list[HorizonPick]:
        return list(self._picks.values())

    def get_pick(self, pick_id: str) -> HorizonPick | None:
        return self._picks.get(pick_id)

    def undo(self) -> bool:
        result = self.undo_manager.undo(self)
        if result:
            self.picks_changed.emit()
        return result

    def redo(self) -> bool:
        result = self.undo_manager.redo(self)
        if result:
            self.picks_changed.emit()
        return result

    def clear(self) -> None:
        self._picks.clear()
        self.undo_manager.clear()
        self.picks_changed.emit()

    def to_dict(self) -> dict:
        return {
            "picks": [
                {
                    "pick_id": p.pick_id,
                    "formation_name": p.formation_name,
                    "well_depths": [[w, d] for w, d in p.well_depths],
                    "source": p.source,
                    "confidence": p.confidence,
                }
                for p in self._picks.values()
            ]
        }

    def from_dict(self, data: dict) -> None:
        self._picks.clear()
        for item in data.get("picks", []):
            pick = HorizonPick(
                pick_id=item["pick_id"],
                formation_name=item["formation_name"],
                well_depths=[(wd[0], wd[1]) for wd in item["well_depths"]],
                source=item.get("source", "manual"),
                confidence=item.get("confidence", {}),
            )
            self._picks[pick.pick_id] = pick
        self.undo_manager.clear()
        self.picks_changed.emit()

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def from_json(self, text: str) -> None:
        self.from_dict(json.loads(text))
