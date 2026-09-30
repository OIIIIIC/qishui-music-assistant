from __future__ import annotations

import json
import threading
import time
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from .device import DeviceError
from .connection import choose_device
from .flow import Flow
from .storage import Journal, data_dir
from .vision import LocalVision, Observation


class Probe(QThread):
    result = Signal(bool, str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)

    def run(self):
        try:
            d = choose_device(self.settings)
            self.result.emit(True, f"{d.connect()} · {d.platform_label}")
        except Exception as e:
            self.result.emit(False, str(e))


class Runner(QThread):
    changed = Signal(dict)
    logged = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.session_id = None
        self.round_id = None
        self.flow = Flow(self.settings["target"])
        self.pause_reason = "已暂停，手机上的广告可能继续播放"

    def pause(self):
        self.pause_reason = "已暂停，手机上的广告可能继续播放"
        self.pause_event.set()

    def resume(self):
        self.pause_event.clear()

    def stop(self):
        self.stop_event.set()
        self.pause_event.clear()

    def state(self, status: str, detail: str, **extra):
        self.changed.emit({"status": status, "detail": detail, "completed": self.flow.completed,
                           "target": self.flow.target, **extra})

    def log(self, message):
        self.journal.event(self.session_id, message)
        self.logged.emit(message)

    def guarded_click(self, device, node):
        if self.stop_event.is_set() or self.pause_event.is_set():
            return False
        device.click(node)
        return True

    def pause_for(self, message: str, layout=None, screenshot=None):
        self.pause_reason = message
        self.pause_event.set()
        folder = data_dir() / "captures"
        folder.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if layout:
            (folder / f"{stamp}.json").write_text(json.dumps(layout.raw, ensure_ascii=False), "utf-8")
        if screenshot and screenshot.exists():
            import shutil
            shutil.copy2(screenshot, folder / f"{stamp}.png")
        self.log("已暂停：" + message)
        self.state("paused", message)

    def run(self):
        self.journal = Journal()
        device = None
        final_status = "stopped"
        final_message = "任务已结束"
        try:
            self.state("connecting", "正在连接手机")
            device = choose_device(self.settings)
            name = f"{device.connect()} · {device.platform_label}"
            self.session_id = self.journal.session(self.flow.target)
            self.log("任务开始，目标 " + str(self.flow.target) + " 轮")
            vision = LocalVision()
            start = time.monotonic()
            last_progress = start
            round_start = start
            screenshot = data_dir() / "current-screen.png"
            last_page = ""
            unknown_since = None
            self.state("running", "请在手机上打开听歌领取面板", device=name)
            while not self.stop_event.is_set():
                if time.monotonic() - start > self.settings["max_minutes"] * 60:
                    final_message = "已达到最长运行时间"
                    break
                if self.pause_event.is_set():
                    self.state("paused", self.pause_reason)
                    while self.pause_event.is_set() and not self.stop_event.wait(.2):
                        pass
                    last_progress = round_start = time.monotonic()
                    unknown_since = None
                    if self.stop_event.is_set():
                        break
                    # Do not retry a click whose delivery was interrupted; reconcile its result first.
                    self.state("running", "正在检查当前页面")
                    if time.monotonic() - start > self.settings["max_minutes"] * 60:
                        final_message = "已达到最长运行时间"
                        break
                layout = None
                try:
                    layout = device.layout()
                    if not layout.is_app:
                        self.pause_for("请切回汽水音乐的听歌领取面板", layout)
                        continue
                    device.screenshot(screenshot)
                    obs = vision.read(layout, screenshot)
                except DeviceError as e:
                    self.pause_for(str(e), layout)
                    continue
                if self.stop_event.is_set() or self.pause_event.is_set():
                    continue
                now = time.monotonic()
                if now - start > self.settings["max_minutes"] * 60:
                    final_message = "已达到最长运行时间"
                    break
                if obs.page in ("unknown", "home"):
                    if unknown_since is None:
                        unknown_since = now
                else:
                    unknown_since = None
                if obs.page != last_page:
                    last_page = obs.page
                    self.log("页面：" + {"entry": "听歌领取面板", "ad_playing": "广告播放中",
                                          "ad_loading": "广告加载中", "ad_done": "广告领取成功",
                                          "retention": "继续观看提示", "home": "播放首页",
                                          "unknown": "待识别", "exhausted": "暂无广告"}.get(obs.page, obs.page))
                decision = self.flow.step(obs)
                if decision.kind in ("begin", "click"):
                    if decision.kind == "begin":
                        self.round_id = self.journal.begin(self.session_id)
                        round_start = now
                    if not self.guarded_click(device, decision.node):
                        # The flow has already advanced; pausing here is ambiguous. Don't retry blindly.
                        self.pause_for("操作被暂停，请结束任务后从领取面板重新开始", layout, screenshot)
                        continue
                    self.log(decision.message)
                    last_progress = now
                elif decision.kind == "watching":
                    self.journal.watching(self.round_id)
                    self.log(decision.message)
                    last_progress = now
                elif decision.kind == "success":
                    self.journal.success(self.round_id, decision.message)
                    self.round_id = None
                    self.log(decision.message)
                    last_progress = now
                elif decision.kind == "pause":
                    self.pause_for(decision.message, layout, screenshot)
                    continue
                elif decision.kind == "finish":
                    final_status = "complete"
                    final_message = decision.message
                    break
                self.state("running", decision.message,
                           phase=obs.page, action=decision.kind, elapsed=int(now-start), session=self.session_id)
                if self.flow.active and now - round_start > self.settings["round_timeout"]:
                    self.pause_for("本轮等待超时，请检查手机页面", layout, screenshot)
                elif unknown_since is not None and now - unknown_since > 20:
                    self.pause_for("页面暂未适配，请打开记录查看截图", layout, screenshot)
                self.stop_event.wait(2)
        except Exception as e:
            final_status, final_message = "error", str(e)
        finally:
            if self.round_id:
                self.journal.uncertain(self.round_id, final_message)
                self.log("本轮结果未确认，未计入成功轮数")
            if self.session_id:
                self.journal.finish(self.session_id, final_status)
                self.log(final_message)
            self.journal.close()
            if device:
                device.cleanup()
            self.state(final_status, final_message)
