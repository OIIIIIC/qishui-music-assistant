import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", type=Path, help="Render a disconnected design preview and exit")
    parser.add_argument("--diagnose", type=Path, help="Read-only device/OCR check; write a JSON report and exit")
    parser.add_argument("--platform", choices=("auto", "harmony", "android"), help="Device platform for diagnostics")
    parser.add_argument("--serial", help="Device serial for diagnostics")
    args = parser.parse_args()
    if args.diagnose:
        import json
        import traceback
        from qishui.connection import choose_device
        from qishui.storage import load_settings
        from qishui.vision import LocalVision
        device = None
        try:
            settings = load_settings()
            if args.platform:
                settings["platform"] = args.platform
            if args.serial:
                settings["serial"] = args.serial
            device = choose_device(settings)
            name = device.connect()
            layout = device.layout()
            image = args.diagnose.with_suffix(".png")
            device.screenshot(image)
            vision = LocalVision()
            observation = vision.read(layout, image)
            result = {"ok": True, "device": name, "page": observation.page,
                      "platform": device.platform, "is_app": layout.is_app,
                      "confirmed_days": observation.confirmed_days,
                      "local_ocr_used": vision._ocr is not None, "texts": observation.texts}
        except Exception:
            result = {"ok": False, "error": traceback.format_exc()}
        finally:
            if device:
                device.cleanup()
        args.diagnose.parent.mkdir(parents=True, exist_ok=True)
        args.diagnose.write_text(json.dumps(result,ensure_ascii=False,indent=2),"utf-8")
        return 0 if result["ok"] else 1
    if args.preview:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication, QMessageBox
    from qishui.storage import data_dir
    from qishui.ui import MainWindow
    app = QApplication(sys.argv[:1])
    if args.preview:
        # Qt's offscreen platform doesn't enumerate Windows fonts automatically.
        for filename in ("msyh.ttc", "msyhbd.ttc", "seguisb.ttf"):
            QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename))
    app.setApplicationName("汽水音乐助手")
    app.setOrganizationName("LocalTools")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    lock = QLockFile(str(data_dir() / "assistant.lock"))
    lock.setStaleLockTime(0)
    if not args.preview and not lock.tryLock(0):
        QMessageBox.information(None,"汽水音乐助手","助手已经在运行，请使用已打开的窗口。")
        return 0
    window = MainWindow(preview=bool(args.preview))
    window.show()
    if args.preview:
        def capture():
            args.preview.parent.mkdir(parents=True,exist_ok=True)
            window.grab().save(str(args.preview))
            app.quit()
        QTimer.singleShot(300,capture)
    result = app.exec()
    lock.unlock()
    return result


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        report = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "QishuiAssistant" / "startup-error.log"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(traceback.format_exc(), "utf-8")
        if sys.stderr is not None:
            sys.stderr.write(report.read_text("utf-8"))
        if not any(arg in sys.argv for arg in ("--preview", "--diagnose")):
            from PySide6.QtWidgets import QApplication, QMessageBox
            error_app = QApplication.instance() or QApplication([])
            QMessageBox.critical(None, "汽水音乐助手", f"启动遇到问题，详细记录已保存：\n{report}")
        sys.exit(1)
