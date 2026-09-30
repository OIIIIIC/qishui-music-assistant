from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl, QSize
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                              QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
                              QListWidget, QListWidgetItem, QMessageBox, QProgressBar,
                              QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

from .storage import Journal, data_dir, load_settings, save_settings
from .worker import Probe, Runner

TEAL = "#008F92"
STYLE = """
QWidget { background: #FCFDFD; color: #1C2934; font-family: 'Microsoft YaHei UI'; font-size: 13px; }
QLabel { background: transparent; }
QLabel#muted { color: #929BA5; }
QPushButton { border: 1px solid #D9DFE3; border-radius: 9px; padding: 8px 16px; background: #FFFFFF; }
QPushButton:hover { background: #F0F5F5; border-color: #ABBBC0; }
QPushButton:pressed { background: #E6EEEE; }
QPushButton:disabled { color: #A4ADB4; background: #F3F5F5; border-color: #E7EBED; }
QPushButton#primary { background: #008F92; border: none; color: white; font-size: 16px; font-weight: 600; }
QPushButton#primary:hover { background: #007F82; }
QPushButton#primary:pressed { background: #006F72; }
QPushButton#primary:disabled { background: #A2CACB; color: #F6FFFF; }
QPushButton#link { border: none; background: transparent; color: #77838F; padding: 4px; }
QPushButton#link:hover { color: #008F92; background: #EDF7F6; }
QPushButton#settings { border: none; background: transparent; padding: 4px; color: #788590; }
QPushButton#settings:hover { background: #EDF3F3; }
QFrame#divider { background: #EDF0F2; border: none; max-height: 1px; }
QProgressBar { background: #E8ECEF; border: none; border-radius: 4px; min-height: 7px; max-height: 7px; }
QProgressBar::chunk { background: #008F92; border-radius: 4px; }
QSpinBox, QLineEdit, QComboBox { background: #FFFFFF; border: 1px solid #D9E0E4; border-radius: 6px; padding: 7px; selection-background-color: #008F92; }
QListWidget { border: 1px solid #E4E9EC; border-radius: 8px; padding: 8px; background: #FFFFFF; }
QListWidget::item { padding: 9px 4px; border-bottom: 1px solid #F0F3F4; }
QToolTip { background: #FFFFFF; color: #26343D; border: 1px solid #D8E2E4; padding: 6px; }
"""


def icon(kind: str, color=TEAL, size=24) -> QIcon:
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24 * 2, size / 24 * 2)
    p.setPen(QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == "music":
        p.setBrush(QColor(color))
        p.drawEllipse(4, 14, 7, 6)
        p.drawEllipse(15, 11, 7, 6)
        p.drawLine(11, 17, 11, 5)
        p.drawLine(22, 14, 22, 2)
        p.drawLine(11, 5, 22, 2)
    elif kind == "settings":
        p.drawEllipse(5, 5, 14, 14)
        p.drawEllipse(9, 9, 6, 6)
        for x1, y1, x2, y2 in ((12,2,12,5),(12,19,12,22),(2,12,5,12),(19,12,22,12),(5,5,7,7),(17,17,19,19),(5,19,7,17),(17,7,19,5)):
            p.drawLine(x1,y1,x2,y2)
    elif kind == "record":
        p.drawRoundedRect(5, 3, 14, 18, 2, 2)
        for y in (8, 12, 16):
            p.drawLine(9, y, 15, y)
    elif kind == "edit":
        p.drawLine(6, 17, 16, 7)
        p.drawLine(9, 20, 19, 10)
        p.drawLine(16, 7, 19, 10)
        p.drawLine(6, 17, 5, 21)
        p.drawLine(5, 21, 9, 20)
    p.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


def divider():
    f = QFrame()
    f.setObjectName("divider")
    f.setFixedHeight(1)
    return f


def label(text, size=13, color=None, bold=False):
    w = QLabel(text)
    font = QFont("Microsoft YaHei UI", size)
    font.setBold(bold)
    w.setFont(font)
    w.setStyleSheet(f"font-size: {round(size * 1.25)}px; font-weight: {'600' if bold else '400'}; color: {color or '#1C2934'};")
    return w


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("任务设置")
        self.resize(440, 320)
        self.values = dict(settings)
        root = QVBoxLayout(self)
        root.setContentsMargins(24,24,24,20)
        root.setSpacing(18)
        form = QFormLayout()
        form.setVerticalSpacing(14)
        self.target = QSpinBox()
        self.target.setRange(1,100)
        self.target.setSuffix(" 轮")
        self.target.setValue(settings["target"])
        self.minutes = QSpinBox()
        self.minutes.setRange(1,240)
        self.minutes.setSuffix(" 分钟")
        self.minutes.setValue(settings["max_minutes"])
        self.timeout = QSpinBox()
        self.timeout.setRange(60,600)
        self.timeout.setSuffix(" 秒")
        self.timeout.setValue(settings["round_timeout"])
        form.addRow("目标轮数", self.target)
        form.addRow("最长运行时间", self.minutes)
        form.addRow("单轮等待上限", self.timeout)
        root.addLayout(form)
        advanced = QPushButton("连接设置")
        advanced.setObjectName("link")
        root.addWidget(advanced, alignment=Qt.AlignmentFlag.AlignLeft)
        self.connection = QWidget()
        f = QFormLayout(self.connection)
        f.setContentsMargins(0,0,0,0)
        self.platform = QComboBox()
        for title, value in (("自动识别", "auto"), ("鸿蒙 · HDC", "harmony"), ("Android · 试验支持", "android")):
            self.platform.addItem(title, value)
        self.platform.setCurrentIndex(max(0, self.platform.findData(settings.get("platform", "auto"))))
        f.addRow("手机系统", self.platform)
        self.hdc = QLineEdit(settings["hdc"])
        self.hdc.setPlaceholderText("自动查找 HoKit 内的 HDC")
        pick = QPushButton("选择")
        pick.clicked.connect(self.choose_hdc)
        row = QHBoxLayout()
        row.addWidget(self.hdc)
        row.addWidget(pick)
        self.serial = QLineEdit(settings["serial"])
        self.serial.setPlaceholderText("只有一台手机时留空")
        f.addRow("HDC 路径", row)
        self.adb = QLineEdit(settings.get("adb", ""))
        self.adb.setPlaceholderText("自动查找 Android SDK 内的 ADB")
        pick_adb = QPushButton("选择")
        pick_adb.clicked.connect(self.choose_adb)
        adb_row = QHBoxLayout()
        adb_row.addWidget(self.adb)
        adb_row.addWidget(pick_adb)
        f.addRow("ADB 路径", adb_row)
        f.addRow("设备序列号", self.serial)
        root.addWidget(self.connection)
        self.connection.hide()
        advanced.clicked.connect(lambda: self.connection.setVisible(not self.connection.isVisible()))
        hint = label("达到目标自动结束；遇到未知页面自动暂停。", 10, "#8B969F")
        hint.setWordWrap(True)
        root.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def choose_hdc(self):
        path, _ = QFileDialog.getOpenFileName(self,"选择 hdc.exe", "", "HDC (hdc.exe)")
        if path:
            self.hdc.setText(path)

    def accept(self):
        self.values.update(target=self.target.value(), max_minutes=self.minutes.value(),
                           round_timeout=self.timeout.value(), hdc=self.hdc.text().strip(),
                           platform=self.platform.currentData(), adb=self.adb.text().strip(),
                           serial=self.serial.text().strip())
        super().accept()

    def choose_adb(self):
        path, _ = QFileDialog.getOpenFileName(self,"选择 adb.exe", "", "ADB (adb.exe)")
        if path:
            self.adb.setText(path)


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("运行记录")
        self.resize(580,480)
        root = QVBoxLayout(self)
        root.setContentsMargins(20,20,20,20)
        journal = Journal()
        latest = journal.latest()
        if latest:
            counts = journal.counts(latest[0])
            root.addWidget(label(f"最近任务 · 已看完 {counts['success']} 轮 · 已开始 {counts['started']} 轮 · 待确认 {counts['uncertain']} 轮", 10, "#788590"))
        view = QListWidget()
        for stamp, message in journal.history():
            view.addItem(QListWidgetItem(f"{stamp.replace('T', ' ')}\n{message}"))
        journal.close()
        if not view.count():
            view.addItem("还没有运行记录")
        root.addWidget(view)
        open_folder = QPushButton("打开记录文件夹")
        open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
        root.addWidget(open_folder, alignment=Qt.AlignmentFlag.AlignRight)


class MainWindow(QWidget):
    def __init__(self, *, preview=False):
        super().__init__()
        self.preview = preview
        self.settings = load_settings()
        self.runner = None
        self.probe = None
        self.closing = False
        self.status = "idle"
        self.completed = 0
        self.setWindowTitle("汽水音乐助手")
        self.setWindowIcon(icon("music"))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.resize(480,580)
        self.setMinimumSize(420,550)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(26,18,24,18)
        head.setSpacing(10)
        self.dot = label("●", 11, "#C0C8CE")
        self.device_label = label("正在检查设备", 11, "#61707E")
        head.addWidget(self.dot)
        head.addWidget(self.device_label,1)
        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("settings")
        self.settings_btn.setIcon(icon("settings", "#7D8996"))
        self.settings_btn.setIconSize(QSize(22,22))
        self.settings_btn.setFixedSize(30,30)
        self.settings_btn.setToolTip("任务设置")
        self.settings_btn.setAccessibleName("任务设置")
        self.settings_btn.clicked.connect(self.edit_settings)
        head.addWidget(self.settings_btn)
        root.addLayout(head)
        root.addWidget(divider())
        body = QVBoxLayout()
        body.setContentsMargins(38,24,38,24)
        body.setSpacing(0)
        body.addStretch(2)
        heading = label("已完成", 13, "#818D99")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setToolTip("看完广告、显示领取成功并返回听歌面板后计数；听歌天数另记在详情中")
        body.addWidget(heading)
        body.addSpacing(3)
        numbers = QHBoxLayout()
        numbers.setSpacing(8)
        numbers.addStretch()
        self.number = label("0", 72, "#1C2934", True)
        self.number.setStyleSheet("font-family: 'Segoe UI'; font-size: 100px; font-weight: 600; color: #1C2934;")
        numbers.addWidget(self.number)
        unit = label("轮", 20, "#7E8996")
        unit.setStyleSheet("font-size: 25px; color: #7E8996; padding-top: 34px;")
        numbers.addWidget(unit, alignment=Qt.AlignmentFlag.AlignVCenter)
        numbers.addStretch()
        body.addLayout(numbers)
        body.addSpacing(8)
        self.target_btn = QPushButton(f"目标 {self.settings['target']} 轮")
        self.target_btn.setObjectName("link")
        self.target_btn.setIcon(icon("edit", "#8E99A4", 16))
        self.target_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.target_btn.clicked.connect(self.edit_settings)
        body.addWidget(self.target_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        body.addStretch(2)
        self.progress = QProgressBar()
        self.progress.setRange(0,self.settings["target"])
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        body.addWidget(self.progress)
        body.addSpacing(22)
        self.state_label = label("准备就绪", 14, "#293846", True)
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self.state_label)
        body.addSpacing(6)
        self.detail_label = label("打开听歌领取面板，然后开始", 10, "#8A96A1")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setWordWrap(True)
        self.detail_label.setMinimumHeight(38)
        body.addWidget(self.detail_label)
        body.addStretch(1)
        body.addSpacing(12)
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.primary = QPushButton("开始")
        self.primary.setObjectName("primary")
        self.primary.setMinimumHeight(48)
        self.primary.clicked.connect(self.primary_action)
        self.end_btn = QPushButton("结束")
        self.end_btn.setMinimumHeight(48)
        self.end_btn.setFixedWidth(100)
        self.end_btn.setEnabled(False)
        self.end_btn.clicked.connect(self.end_task)
        buttons.addWidget(self.primary,1)
        buttons.addWidget(self.end_btn)
        body.addLayout(buttons)
        root.addLayout(body,1)
        root.addWidget(divider())
        foot = QHBoxLayout()
        foot.setContentsMargins(24,12,26,12)
        record = QPushButton("查看记录")
        record.setObjectName("link")
        record.setIcon(icon("record", TEAL,18))
        record.setStyleSheet("color: #008F92;")
        record.clicked.connect(lambda: HistoryDialog(self).exec())
        foot.addWidget(record)
        foot.addStretch()
        foot.addWidget(label("本地运行",10,"#9AA3AC"))
        root.addLayout(foot)
        self.probe_timer = QTimer(self)
        self.probe_timer.setInterval(10000)
        self.probe_timer.timeout.connect(self.check_device)
        if preview:
            self.device_result(True,"nova 15")
            self.update_state({"status":"running","detail":"等待广告结束","completed":7,"target":20,"phase":"ad_playing"})
            self.end_btn.setEnabled(True)
        else:
            journal = Journal()
            journal.recover()
            latest = journal.latest()
            if latest:
                self.completed = journal.counts(latest[0])["success"]
                self.number.setText(str(self.completed))
                self.progress.setRange(0,latest[1])
                self.progress.setValue(self.completed)
                self.target_btn.setText(f"目标 {latest[1]} 轮")
                self.state_label.setText("上次已完成" if latest[2] != "interrupted" else "上次任务已中断")
                self.detail_label.setText("观看轮数已保存，点击开始创建新任务")
            journal.close()
            QTimer.singleShot(150,self.check_device)
            self.probe_timer.start()

    def check_device(self):
        if self.closing or (self.runner and self.runner.isRunning()) or (self.probe and self.probe.isRunning()):
            return
        if self.probe:
            self.probe.deleteLater()
        self.probe = Probe(self.settings, self)
        self.probe.result.connect(self.device_result)
        self.probe.finished.connect(self.maybe_close)
        self.probe.start()

    def device_result(self, connected, name):
        self.dot.setStyleSheet("color: #24BD6C;" if connected else "color: #C0C8CE;")
        self.device_label.setText(name + " 已连接" if connected else "等待连接手机")
        self.device_label.setToolTip("USB 连接正常" if connected else name)

    def edit_settings(self):
        if self.runner and self.runner.isRunning():
            return
        dialog = SettingsDialog(self.settings,self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.values
            save_settings(self.settings)
            self.target_btn.setText(f"目标 {self.settings['target']} 轮")
            self.progress.setRange(0,self.settings["target"])
            self.check_device()

    def primary_action(self):
        if self.preview:
            return
        if self.runner and self.runner.isRunning():
            if self.runner.pause_event.is_set():
                self.runner.resume()
                self.primary.setText("暂停")
                self.state_label.setText("正在继续")
            else:
                self.runner.pause()
                self.primary.setText("继续")
                self.state_label.setText("已暂停")
                self.detail_label.setText("手机上的广告可能继续播放")
            return
        if self.runner:
            self.runner.deleteLater()
        self.runner = Runner(self.settings,self)
        self.runner.changed.connect(self.update_state)
        self.runner.finished.connect(self.runner_finished)
        self.completed = 0
        self.number.setText("0")
        self.progress.setRange(0,self.settings["target"])
        self.progress.setValue(0)
        self.target_btn.setText(f"目标 {self.settings['target']} 轮")
        self.settings_btn.setEnabled(False)
        self.target_btn.setEnabled(False)
        self.end_btn.setEnabled(True)
        self.primary.setText("暂停")
        self.runner.start()

    def update_state(self, value):
        self.status = value["status"]
        self.completed = value["completed"]
        self.number.setText(str(self.completed))
        self.progress.setRange(0,value["target"])
        self.progress.setValue(self.completed)
        if value.get("device"):
            self.device_result(True,value["device"])
        names = {"idle":"准备就绪", "connecting":"正在连接", "paused":"已暂停",
                 "stopped":"任务已结束", "complete":"任务已完成", "error":"需要检查"}
        if self.status == "running":
            if value.get("action") == "success":
                title = f"第 {self.completed} 轮已完成"
            elif value.get("action") == "begin":
                title = f"准备观看第 {self.completed+1} 轮"
            else:
                title = "正在核对领取结果" if value.get("phase") in ("ad_done","retention","entry") else f"正在观看第 {self.completed+1} 轮"
        else:
            title = names.get(self.status,"准备就绪")
        self.state_label.setText(title)
        self.detail_label.setText(value["detail"])
        self.detail_label.setToolTip(value["detail"])
        if self.status == "paused":
            self.primary.setText("继续")
        elif self.status in ("running","connecting"):
            self.primary.setText("暂停")
        else:
            self.primary.setText("重新开始" if self.completed else "开始")
        if self.status == "error":
            self.state_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #AD6B37;")
        else:
            self.state_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #293846;")

    def end_task(self):
        if self.runner and self.runner.isRunning():
            self.runner.stop()
            self.primary.setEnabled(False)
            self.end_btn.setEnabled(False)
            self.state_label.setText("正在结束")
            self.detail_label.setText("正在保存记录，请稍候")

    def runner_finished(self):
        self.primary.setEnabled(True)
        self.end_btn.setEnabled(False)
        self.settings_btn.setEnabled(True)
        self.target_btn.setEnabled(True)
        self.maybe_close()

    def maybe_close(self):
        if self.closing and not any(t and t.isRunning() for t in (self.runner,self.probe)):
            QTimer.singleShot(0,self.close)

    def closeEvent(self, event):
        if any(t and t.isRunning() for t in (self.runner,self.probe)):
            self.closing = True
            self.probe_timer.stop()
            self.end_task()
            self.hide()
            event.ignore()
        else:
            event.accept()
