from ui_lab.flow import DemoFlow
from ui_lab.recognition import Frame, demo_frame, classify_texts
from ui_lab.journal import Journal


def test_requires_two_distinct_consecutive_frames_and_return():
    flow = DemoFlow(1)
    assert flow.step(Frame(0, "ready")).kind == "begin"
    assert flow.step(Frame(1, "done")).kind == "wait"
    assert flow.step(Frame(1, "done")).kind == "wait"
    assert flow.completed == 0
    assert flow.step(Frame(2, "done")).kind == "return"
    assert flow.completed == 0
    assert flow.step(Frame(3, "ready")).kind == "success"
    assert flow.step(Frame(4, "ready")).kind == "finish"
    assert flow.completed == 1


def test_intervening_page_resets_confirmation():
    flow = DemoFlow(1)
    for frame in (Frame(0, "ready"), Frame(1, "done"), Frame(2, "busy")):
        flow.step(frame)
    assert flow.step(Frame(3, "done")).kind == "wait"
    assert flow.step(Frame(4, "done")).kind == "return"


def test_unknown_page_pauses_instead_of_counting():
    flow = DemoFlow(1)
    flow.step(Frame(0, "ready"))
    assert flow.step(Frame(1, "unknown")).kind == "pause"
    assert flow.completed == 0


def test_replay_stops_exactly_at_target():
    flow = DemoFlow(3)
    decisions = [flow.step(demo_frame(i)) for i in range(40)]
    assert flow.completed == 3
    assert sum(d.kind == "begin" for d in decisions) == 3
    assert sum(d.kind == "success" for d in decisions) == 3


def test_recognition_uses_only_demo_labels():
    assert classify_texts(["领取成功", "关闭广告"]) == "unknown"
    assert classify_texts(["演示完成"]) == "done"


def test_round_record_is_idempotent_and_persistent(tmp_path):
    path = tmp_path / "history.sqlite3"
    journal = Journal(path)
    session = journal.session(2)
    assert journal.record_round(session, 1)
    assert not journal.record_round(session, 1)
    journal.close()
    reopened = Journal(path)
    assert reopened.db.execute("SELECT COUNT(*) FROM rounds").fetchone()[0] == 1
    reopened.close()
