"""Tests for HorizonPicksModel and PicksUndoManager."""
import json

from geoviz_cross_well.picks_model import (
    HorizonPick,
    HorizonPicksModel,
    AddPickCmd,
    DeletePickCmd,
    MovePickCmd,
    ConnectPickCmd,
    PicksUndoManager,
)


def test_add_pick():
    model = HorizonPicksModel()
    pick_id = model.add_pick("Jurassic", "W1", 1250.0)
    assert pick_id is not None
    picks = model.all_picks()
    assert len(picks) == 1
    assert picks[0].formation_name == "Jurassic"
    assert picks[0].depth_for_well("W1") == 1250.0


def test_connect_picks():
    model = HorizonPicksModel()
    pick_id = model.add_pick("Jurassic", "W1", 1250.0)
    model.connect_picks(pick_id, "W2", 1280.0)
    pick = model.get_pick(pick_id)
    assert pick is not None
    assert pick.depth_for_well("W2") == 1280.0
    assert len(pick.connected_wells()) == 2


def test_delete_pick():
    model = HorizonPicksModel()
    pick_id = model.add_pick("F1", "W1", 100.0)
    model.delete_pick(pick_id)
    assert len(model.all_picks()) == 0


def test_undo_redo():
    model = HorizonPicksModel()
    pick_id = model.add_pick("F1", "W1", 100.0)
    assert len(model.all_picks()) == 1

    model.undo()
    assert len(model.all_picks()) == 0

    model.redo()
    assert len(model.all_picks()) == 1
    assert model.get_pick(pick_id) is not None


def test_undo_connect():
    model = HorizonPicksModel()
    pick_id = model.add_pick("F1", "W1", 100.0)
    model.connect_picks(pick_id, "W2", 200.0)
    pick = model.get_pick(pick_id)
    assert pick.depth_for_well("W2") == 200.0

    model.undo()  # undo connect
    pick = model.get_pick(pick_id)
    assert pick.depth_for_well("W2") is None


def test_undo_delete():
    model = HorizonPicksModel()
    pick_id = model.add_pick("F1", "W1", 100.0)
    model.delete_pick(pick_id)
    assert len(model.all_picks()) == 0

    model.undo()
    assert len(model.all_picks()) == 1
    assert model.get_pick(pick_id) is not None


def test_json_roundtrip():
    model = HorizonPicksModel()
    p1 = model.add_pick("Jurassic", "W1", 1250.0)
    model.connect_picks(p1, "W2", 1280.0)
    model.add_pick("Triassic", "W1", 1800.0)

    json_str = model.to_json()
    data = json.loads(json_str)
    assert len(data["picks"]) == 2

    model2 = HorizonPicksModel()
    model2.from_json(json_str)
    assert len(model2.all_picks()) == 2
    assert model2.get_pick(p1) is not None


def test_dtw_accept_reject():
    model = HorizonPicksModel()
    pick_id = model.add_pick("F1", "W1", 100.0, source="dtw")
    pick = model.get_pick(pick_id)
    assert pick.source == "dtw"

    model.accept_dtw_pick(pick_id)
    pick = model.get_pick(pick_id)
    assert pick.source == "manual"

    pick_id2 = model.add_pick("F2", "W1", 200.0, source="dtw")
    model.reject_dtw_pick(pick_id2)
    assert model.get_pick(pick_id2) is None


def test_picks_for_well():
    model = HorizonPicksModel()
    p1 = model.add_pick("F1", "W1", 100.0)
    model.connect_picks(p1, "W2", 200.0)
    model.add_pick("F2", "W1", 300.0)

    w1_picks = model.picks_for_well("W1")
    assert len(w1_picks) == 2
    w2_picks = model.picks_for_well("W2")
    assert len(w2_picks) == 1


def test_horizon_pick_none_depth():
    pick = HorizonPick(
        pick_id="abc",
        formation_name="F1",
        well_depths=[("W1", 100.0), ("W2", None), ("W3", 150.0)],
    )
    assert pick.depth_for_well("W2") is None
    assert pick.connected_wells() == ["W1", "W3"]

    json_data = {
        "picks": [
            {
                "pick_id": pick.pick_id,
                "formation_name": pick.formation_name,
                "well_depths": [[w, d] for w, d in pick.well_depths],
                "source": "manual",
            }
        ]
    }
    assert json_data["picks"][0]["well_depths"][1] == ["W2", None]

    model = HorizonPicksModel()
    model.from_dict(json_data)
    loaded = model.get_pick(pick.pick_id)
    assert loaded is not None
    assert loaded.depth_for_well("W2") is None


def test_clear():
    model = HorizonPicksModel()
    model.add_pick("F1", "W1", 100.0)
    model.clear()
    assert len(model.all_picks()) == 0
