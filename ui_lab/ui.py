from pathlib import Path
import os
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QWidget, QLabel, QPushButton, QSpinBox, QProgressBar,
                              QVBoxLayout, QHBoxLayout, QFrame, QListWidget)
from .flow import DemoFlow
from .recognition import Frame, demo_frame
from .journal import Journal

STYLE = """
QWidget { background: #F6F8FB; color: #203043; font-family: 'Microsoft YaHei UI'; font-size: 13px; }
QFrame#card { background: white; border: 1px solid #E1E7EE; border-radius: 16px; }
QLabel { background: transparent; border: none; }
QLabel#muted { color: #768498; }
QLabel#badge { color: #007F83; background: #E4F6F4; border-radius: 6px; padding: 6px 12px; }
QPushButton { background: white; border: 1px solid #D5DEE8; border-radius: 8px; padding: 10px 18px; }
QPushButton:hover { background: #EEF5F7; }
QPushButton#primary { background: #008E92; color: white; border: none; }
QPushButton:disabled { color: #98A4B3; background: #EAF0F5; }
QSpinBox { background: white; border: 1px solid #D5DEE8; border-radius: 6px; padding: 7px; }
QProgressBar { background: #E7EDF2; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }
QProgressBar::chunk { background: #008E92; border-radius: 4px; }
QListWidget { background: white; border: none; font-size: 12px; }
QListWidget::item { padding: 6px 0; }
"""


def data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "USBInterfaceLab"
    return base


def text(value: str, size=13, muted=False):
    label = QLabel(value)
    label.setWordWrap(True)
    if muted:
        label.setObjectName("muted")
    label.setStyleSheet(f"font-size: {size}px;")
    return label


def card():
    widget = QFrame()
    widget.setObjectName("card")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)
    return widget, layout


class DemoWindow(QWidget):
    def __init__(self, *, preview=False, directory: Path | None = None):
        super().__init__()
        self.preview = preview
        self.directory = directory or data_dir()
        self.journal = None if preview else Journal(self.directory / "demo.sqlite3")
        self.flow = DemoFlow(2)
        self.sequence = 0
        self.observation_sequence = 0
        self.session = None
        self.status = "idle"
        self.inject_unknown = False
        self.setWindowTitle("USB 界面自动化实验室 · 模拟演示")
        self.resize(940, 660)
        self.setMinimumSize(860, 620)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 22)
        root.setSpacing(20)
        heading = QHBoxLayout()
        title = text("USB 界面自动化实验室", 26)
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        heading.addWidget(title, 1)
        badge = text("模拟环境 · 无需手机", 12)
        badge.setObjectName("badge")
        heading.addWidget(badge)
        root.addLayout(heading)
        root.addWidget(text("观察页面 → 确认状态 → 返回起始页 → 记录结果", 13, True))
        columns = QHBoxLayout()
        columns.setSpacing(20)
        left, progress = card()
        progress.addWidget(text("任务进度", 15, True))
        self.counter = text("0 / 2", 54)
        self.counter.setStyleSheet("font-size: 54px; font-weight: 600;")
        progress.addWidget(self.counter)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 2)
        progress.addWidget(self.bar)
        self.detail = text("点击开始，观察一次完整的模拟流程", 15)
        progress.addWidget(self.detail)
        target = QHBoxLayout()
        target.addWidget(text("目标轮数", 13, True))
        self.target = QSpinBox()
        self.target.setRange(1, 20)
        self.target.setValue(2)
        self.target.setSuffix(" 轮")
        target.addWidget(self.target)
        progress.addLayout(target)
        actions = QHBoxLayout()
        self.start_button = QPushButton("开始演示")
        self.start_button.setObjectName("primary")
        self.pause_button = QPushButton("暂停")
        self.pause_button.setEnabled(False)
        actions.addWidget(self.start_button)
        actions.addWidget(self.pause_button)
        progress.addLayout(actions)
        self.stop_button = QPushButton("结束")
        self.stop_button.setEnabled(False)
        progress.addWidget(self.stop_button)
        progress.addStretch()
        progress.addWidget(text("所有自动状态推进均发生在内置模拟页面中。", 12, True))
        columns.addWidget(left, 1)
        right, mock = card()
        mock.addWidget(text("内置模拟页面", 15, True))
        self.page_title = text("准备就绪", 30)
        self.page_title.setStyleSheet("font-size: 30px; font-weight: 600; color: #007F83;")
        mock.addWidget(self.page_title)
        self.page_description = text("开始演示", 16)
        mock.addWidget(self.page_description)
        mock.addWidget(text("识别来自演示标签，不包含第三方活动页面规则。", 12, True))
        self.unknown_button = QPushButton("模拟未知页面")
        self.unknown_button.setEnabled(False)
        mock.addWidget(self.unknown_button)
        mock.addWidget(text("运行记录", 14))
        self.logs = QListWidget()
        mock.addWidget(self.logs, 1)
        columns.addWidget(right, 1)
        root.addLayout(columns, 1)
        root.addWidget(text("技术示例：状态确认 · 重复帧过滤 · 幂等计数 · SQLite 本地记录", 12, True))
        self.timer = QTimer(self)
        self.timer.setInterval(850)
        self.timer.timeout.connect(self.tick)
        self.start_button.clicked.connect(self.start)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.stop_button.clicked.connect(self.stop)
        self.unknown_button.clicked.connect(lambda: setattr(self, "inject_unknown", True))
        if preview:
            self.flow.completed = 1
            self.counter.setText("1 / 2")
            self.bar.setValue(1)
            self.detail.setText("正在确认第 2 轮模拟任务的完成状态")
            self.page_title.setText("状态待确认")
            self.page_description.setText("演示完成 · 等待另一帧确认")
            for message in ("开始第 1 轮模拟任务", "连续两帧确认完成", "返回起始页，第 1 轮已记录", "开始第 2 轮模拟任务"):
                self.logs.addItem(message)

    def log(self, message: str):
        self.logs.addItem(message)
        self.logs.scrollToBottom()
        if self.journal and self.session is not None:
            self.journal.log(self.session, message)

    def start(self):
        self.flow = DemoFlow(self.target.value())
        self.sequence = 0
        self.observation_sequence = 0
        self.inject_unknown = False
        self.session = self.journal.session(self.flow.target) if self.journal else None
        self.status = "running"
        self.counter.setText(f"0 / {self.flow.target}")
        self.bar.setRange(0, self.flow.target)
        self.bar.setValue(0)
        self.logs.clear()
        self.start_button.setEnabled(False)
        self.target.setEnabled(False)
        self.pause_button.setText("暂停")
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.unknown_button.setEnabled(True)
        self.log("演示开始，使用内置模拟数据")
        self.timer.start()

    def tick(self):
        if self.status != "running":
            return
        page = "unknown" if self.inject_unknown else demo_frame(self.sequence).page
        frame = Frame(self.observation_sequence, page)
        self.observation_sequence += 1
        if self.inject_unknown:
            self.inject_unknown = False
        else:
            self.sequence += 1
        decision = self.flow.step(frame)
        self.page_title.setText({"ready": "准备就绪", "busy": "处理中", "done": "状态待确认",
                                 "unknown": "未知页面"}[frame.page])
        self.page_description.setText({"ready": "开始演示", "busy": "处理中",
                                       "done": "演示完成", "unknown": "无法识别的演示标签"}[frame.page])
        self.detail.setText(decision.message)
        self.counter.setText(f"{self.flow.completed} / {self.flow.target}")
        self.bar.setValue(self.flow.completed)
        self.log(decision.message)
        if decision.kind == "success" and self.journal:
            self.journal.record_round(self.session, self.flow.completed)
        if decision.kind == "pause":
            self.status = "paused"
            self.timer.stop()
            self.pause_button.setText("继续")
        elif decision.kind == "finish":
            self.stop(finished=True)

    def toggle_pause(self):
        if self.status == "running":
            self.status = "paused"
            self.timer.stop()
            self.pause_button.setText("继续")
            self.detail.setText("演示已暂停")
        elif self.status == "paused":
            self.status = "running"
            self.pause_button.setText("暂停")
            self.timer.start()

    def stop(self, *, finished=False):
        self.timer.stop()
        self.status = "complete" if finished else "stopped"
        self.start_button.setEnabled(True)
        self.target.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.unknown_button.setEnabled(False)
        self.detail.setText("演示已完成" if finished else "演示已结束")

    def closeEvent(self, event):
        self.timer.stop()
        if self.journal:
            self.journal.close()
        event.accept()
