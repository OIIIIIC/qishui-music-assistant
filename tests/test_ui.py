import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from ui_lab.ui import DemoWindow


def test_pause_unknown_page_and_complete_without_phone(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = DemoWindow(directory=tmp_path)
    window.start()
    window.timer.stop()
    window.tick()
    window.toggle_pause()
    sequence = window.sequence
    window.tick()
    assert window.sequence == sequence
    window.toggle_pause()
    window.timer.stop()
    window.inject_unknown = True
    window.tick()
    assert window.status == "paused"
    assert window.flow.completed == 0
    window.toggle_pause()
    window.timer.stop()
    for _ in range(15):
        window.tick()
    assert window.status == "complete"
    assert window.flow.completed == 2
    assert window.journal.db.execute("SELECT COUNT(*) FROM rounds").fetchone()[0] == 2
    window.close()
