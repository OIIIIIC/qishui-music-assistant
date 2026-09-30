"""Android transport using official ADB, platform UIAutomator dump and local OCR."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET

from .device import DeviceError, Layout, Node, NO_WINDOW

ANDROID_BUNDLE = "com.luna.music"


def discover_adb(configured: str = "") -> str:
    if configured:
        if Path(configured).is_file():
            return str(Path(configured).resolve())
        raise DeviceError("指定的 adb.exe 不存在，请检查连接设置")
    candidates = [shutil.which("adb")]
    scrcpy = shutil.which("scrcpy")
    if scrcpy:
        candidates.append(str(Path(scrcpy).parent / "adb.exe"))
    for root in (os.environ.get("ANDROID_SDK_ROOT"), os.environ.get("ANDROID_HOME"),
                 str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk")):
        if root:
            candidates.append(str(Path(root) / "platform-tools/adb.exe"))
    for path in candidates:
        if path and Path(path).is_file():
            return str(Path(path).resolve())
    raise DeviceError("未找到 ADB，请安装 Android SDK Platform-Tools，并在连接设置中选择 adb.exe")


def parse_targets(output: str) -> dict[str, str]:
    result = {}
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] in {"device", "unauthorized", "offline", "recovery", "sideload", "no"}:
            result[parts[0]] = parts[1]
    return result


def parse_android_layout(xml: str, foreground: str, bundle=ANDROID_BUNDLE) -> Layout:
    start = xml.find("<?xml")
    if start < 0:
        start = xml.find("<hierarchy")
    if start < 0:
        raise DeviceError("Android 未返回有效的控件布局")
    try:
        document = ET.fromstring(xml[start:].strip())
    except ET.ParseError as e:
        raise DeviceError("Android 控件布局不完整") from e

    def convert(element):
        a = element.attrib
        attributes = {"text": a.get("text", ""), "description": a.get("content-desc", ""),
                      "id": a.get("resource-id", ""), "type": a.get("class", ""),
                      "bundleName": a.get("package", ""), "bounds": a.get("bounds", ""),
                      "visible": a.get("visible-to-user", "true"),
                      "enabled": a.get("enabled", "true"), "clickable": a.get("clickable", "false")}
        return {"attributes": attributes, "children": [convert(c) for c in element]}

    raw = convert(document)
    # Root bounds must cover the entire device, not the first child/status bar.
    bounds = [tuple(map(int, re.findall(r"-?\d+", e.attrib.get("bounds", "")))) for e in document.iter()]
    bounds = [b for b in bounds if len(b) == 4]
    if bounds:
        raw["attributes"]["bounds"] = f"[0,0][{max(b[2] for b in bounds)},{max(b[3] for b in bounds)}]"
    raw["platform"] = "android"
    raw["foreground_bundle"] = foreground
    return Layout(raw, target_bundle=bundle, foreground_bundle=foreground)


class AdbDevice:
    platform = "android"
    platform_label = "Android"
    bundle = ANDROID_BUNDLE

    def __init__(self, adb: str = "", serial: str = ""):
        self.adb = discover_adb(adb)
        self.serial = serial
        self.token = "qishui_" + uuid.uuid4().hex[:10]

    def run(self, *args: str, target=True, binary=False, timeout=12):
        command = [self.adb]
        if target:
            if not self.serial:
                raise DeviceError("尚未选择 Android 设备")
            command += ["-s", self.serial]
        try:
            p = subprocess.run(command + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=timeout, creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired as e:
            raise DeviceError("Android 设备响应超时，请检查连接") from e
        except OSError as e:
            raise DeviceError(f"无法运行 ADB：{e}") from e
        if p.returncode:
            error = (p.stderr or p.stdout).decode("utf-8", errors="replace").strip()
            raise DeviceError(f"ADB 操作失败：{error[:300]}")
        return p.stdout if binary else p.stdout.decode("utf-8", errors="replace").strip()

    def targets(self) -> dict[str, str]:
        return parse_targets(self.run("devices", "-l", target=False))

    def connect(self) -> str:
        devices = self.targets()
        if not self.serial:
            if len(devices) != 1:
                raise DeviceError("检测到多台 Android 设备，请指定序列号" if devices else "未发现 Android 手机，请连接 USB 并开启 USB 调试")
            self.serial = next(iter(devices))
        status = devices.get(self.serial)
        if status == "unauthorized":
            raise DeviceError("请解锁 Android 手机，并在 USB 调试授权弹窗中点击允许")
        if status != "device":
            raise DeviceError("Android 设备离线或未连接，请检查 USB 连接")
        name = self.run("shell", "getprop", "ro.product.model")
        return name or "Android 手机"

    def foreground(self) -> str:
        # Current window focus takes precedence: do not operate through permission dialogs.
        text = self.run("shell", "dumpsys", "window", "windows")
        match = re.search(r"mCurrentFocus=Window\{[^\r\n]*?\s([A-Za-z0-9_.]+)/[^}\s]+", text)
        if match:
            return match.group(1)
        activities = self.run("shell", "dumpsys", "activity", "activities")
        match = re.search(r"(?:mResumedActivity|topResumedActivity)[^\r\n]*?\s([A-Za-z0-9_.]+)/[^}\s]+", activities)
        return match.group(1) if match else ""

    def layout(self) -> Layout:
        foreground = self.foreground()
        empty = {"attributes": {}, "children": [], "platform": "android", "foreground_bundle": foreground}
        if foreground != self.bundle:
            return Layout(empty, self.bundle, foreground)
        remote = f"/data/local/tmp/{self.token}.xml"
        try:
            output = self.run("shell", "uiautomator", "dump", "--compressed", remote, timeout=15)
            if "dumped" not in output.lower():
                raise DeviceError("Android 无法获取控件布局")
            xml = self.run("shell", "cat", remote)
            layout = parse_android_layout(xml, foreground, self.bundle)
            layout.foreground_bundle = self.foreground()
            return layout
        except DeviceError as e:
            # Video/WebView may never become idle. OCR is allowed only after rechecking focus.
            current = self.foreground()
            empty["foreground_bundle"] = current
            empty["layout_warning"] = str(e)
            return Layout(empty, self.bundle, current)

    def screenshot(self, path: Path):
        content = self.run("exec-out", "screencap", "-p", binary=True)
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise DeviceError("Android 截图失败，未收到 PNG 画面")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def click(self, node: Node):
        x, y = node.center
        if node.bundle != self.bundle or not node.enabled or min(x, y) < 0:
            raise DeviceError("Android 控件位置或应用归属无效")
        if self.foreground() != self.bundle:
            raise DeviceError("手机已离开汽水音乐，已取消点击")
        output = self.run("shell", "input", "tap", str(x), str(y))
        if output and re.search(r"error|exception|denied", output, re.I):
            raise DeviceError(f"Android 拒绝点击操作：{output[:180]}")

    def open_app(self):
        component = self.run("shell", "cmd", "package", "resolve-activity", "--brief", self.bundle).splitlines()[-1:]
        if not component or not component[0].startswith(self.bundle + "/"):
            raise DeviceError("未找到安卓版汽水音乐，请确认已安装应用")
        self.run("shell", "am", "start", "-n", component[0])

    def cleanup(self):
        if self.serial:
            try:
                self.run("shell", "rm", "-f", f"/data/local/tmp/{self.token}.xml", timeout=3)
            except DeviceError:
                pass
