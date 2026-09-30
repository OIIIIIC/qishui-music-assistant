import argparse
import json
import os
from pathlib import Path
import sys


def replay(target: int, directory: Path):
    from ui_lab.flow import DemoFlow
    from ui_lab.journal import Journal
    from ui_lab.recognition import demo_frame
    flow = DemoFlow(target)
    journal = Journal(directory / "demo.sqlite3")
    session = journal.session(target)
    try:
        for sequence in range(target * 5 + 2):
            decision = flow.step(demo_frame(sequence))
            journal.log(session, decision.message)
            if decision.kind == "success":
                journal.record_round(session, flow.completed)
            if decision.kind == "finish":
                break
        result = {"mode": "simulation", "completed": flow.completed, "target": target}
        print(json.dumps(result, ensure_ascii=False))
        return 0 if flow.completed == target else 1
    finally:
        journal.close()


def main():
    parser = argparse.ArgumentParser(description="内置模拟页面的界面自动化技术演示")
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--target", type=int, default=2)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    if not 1 <= args.target <= 20:
        parser.error("目标轮数应为 1～20")
    if args.headless:
        directory = args.data_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "USBInterfaceLab"
        return replay(args.target, directory)
    if args.preview:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication
    from ui_lab.ui import DemoWindow
    app = QApplication(sys.argv[:1])
    if args.preview:
        for name in ("msyh.ttc", "msyhbd.ttc", "seguisb.ttf"):
            QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name))
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = DemoWindow(preview=bool(args.preview), directory=args.data_dir)
    window.show()
    if args.preview:
        def capture():
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.preview)):
                app.exit(1)
            else:
                app.quit()
        QTimer.singleShot(300, capture)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
