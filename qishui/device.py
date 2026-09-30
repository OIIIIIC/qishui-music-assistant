from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

BUNDLE = "com.luna.hm.music"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class DeviceError(RuntimeError):
    pass


def discover_hdc(configured: str = "") -> str:
    candidates = [configured, shutil.which("hdc")]
    for base in (os.environ.get("ProgramFiles", ""),
                 str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs")):
        candidates.append(str(Path(base) / "HoKit/resources/assets/tools/hdc/hdc.exe"))
    for path in candidates:
        if path and Path(path).is_file():
            return str(Path(path).resolve())
    raise DeviceError("未找到 HDC，请在设置中选择 HoKit 自带的 hdc.exe")


@dataclass(frozen=True)
class Node:
    text: str
    description: str
    identifier: str
    bounds: tuple[int, int, int, int]
    bundle: str
    kind: str
    clickable: bool
    enabled: bool

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bounds
        return (x1 + x2) // 2, (y1 + y2) // 2


class Layout:
    def __init__(self, raw: dict, target_bundle: str = BUNDLE, foreground_bundle: str | None = None):
        self.raw = raw
        self.target_bundle = target_bundle
        self.foreground_bundle = foreground_bundle
        self.nodes: list[Node] = []
        self._visit(raw)

    def _visit(self, value: dict, bundle: str = "", visible: bool = True):
        a = value.get("attributes", {})
        bundle = a.get("bundleName") or bundle
        visible = visible and str(a.get("visible", "true")).lower() != "false"
        bounds = tuple(int(x) for x in re.findall(r"-?\d+", a.get("bounds", "")))
        if visible and len(bounds) == 4 and bounds[2] > bounds[0] and bounds[3] > bounds[1]:
            self.nodes.append(Node(
                a.get("text", ""), a.get("description", ""), a.get("id", ""),
                bounds, bundle, a.get("type", ""),
                str(a.get("clickable", "false")).lower() == "true",
                str(a.get("enabled", "true")).lower() != "false",
            ))
        for child in value.get("children", []):
            self._visit(child, bundle, visible)

    @property
    def texts(self) -> list[str]:
        return [n.text for n in self.nodes if n.text and n.bundle == self.target_bundle]

    def find(self, pattern: str, *, full: bool = False) -> Node | None:
        match = re.fullmatch if full else re.search
        for n in self.nodes:
            if n.bundle == self.target_bundle and n.enabled and match(pattern, n.text):
                return n
        return None

    @property
    def is_app(self) -> bool:
        if self.foreground_bundle is not None:
            return self.foreground_bundle == self.target_bundle
        return any(n.bundle == self.target_bundle for n in self.nodes)


class HdcDevice:
    """A single serial-bound connection; never restarts HoKit's shared HDC server."""
    platform = "harmony"
    platform_label = "鸿蒙"
    bundle = BUNDLE
    def __init__(self, hdc: str = "", serial: str = ""):
        self.hdc = discover_hdc(hdc)
        self.serial = serial
        self.token = "qishui_" + uuid.uuid4().hex[:10]

    def run(self, *args: str, target: bool = True, timeout: int = 12) -> str:
        command = [self.hdc]
        if target:
            if not self.serial:
                raise DeviceError("尚未选择设备")
            command += ["-t", self.serial]
        command += list(args)
        try:
            p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=timeout, creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired as e:
            raise DeviceError("设备响应超时，请检查 USB 连接") from e
        except OSError as e:
            raise DeviceError(f"无法运行 HDC：{e}") from e
        text = p.stdout.decode("utf-8", errors="replace").strip()
        error = p.stderr.decode("utf-8", errors="replace").strip()
        if p.returncode or "[Fail]" in text or "[Fail]" in error:
            raise DeviceError((text or error or "HDC 命令失败")[:350])
        return text

    def targets(self) -> dict[str, str]:
        output = self.run("list", "targets", target=False)
        return {s.strip(): "device" for s in output.splitlines()
                if s.strip() and not s.strip().startswith("[")}

    def connect(self) -> str:
        devices = self.targets()
        if self.serial:
            if self.serial not in devices:
                raise DeviceError("已选择的设备未连接，请检查 USB 和调试授权")
        elif len(devices) == 1:
            self.serial = next(iter(devices))
        elif len(devices) > 1:
            raise DeviceError("检测到多台设备，请在设置中填写目标设备序列号")
        else:
            raise DeviceError("未发现手机，请连接 USB 并允许设备调试")
        name = self.run("shell", "param", "get", "const.product.marketname")
        if name and "fail" not in name.lower():
            return name
        model = self.run("shell", "param", "get", "const.product.model").strip()
        return {"PSN-AL00": "nova 15"}.get(model, model or "鸿蒙手机")

    def layout(self) -> Layout:
        remote = f"/data/local/tmp/{self.token}.json"
        output = self.run("shell", "uitest", "dumpLayout", "-p", remote)
        if "saved" not in output.lower():
            raise DeviceError(f"无法读取界面：{output[:200]}")
        with tempfile.TemporaryDirectory(prefix="qishui_") as folder:
            dest = Path(folder) / "layout.json"
            self.run("file", "recv", remote, str(dest))
            try:
                return Layout(json.loads(dest.read_text("utf-8")))
            except (OSError, ValueError) as e:
                raise DeviceError("设备返回的界面信息不完整") from e

    def screenshot(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        remote = f"/data/local/tmp/{self.token}.png"
        output = self.run("shell", "uitest", "screenCap", "-p", remote)
        if "saved" not in output.lower():
            raise DeviceError("无法截图")
        self.run("file", "recv", remote, str(path))

    def click(self, node: Node):
        x, y = node.center
        if x < 0 or y < 0 or not node.enabled:
            raise DeviceError("控件位置无效")
        result = self.run("shell", "uitest", "uiInput", "click", str(x), str(y))
        if "No Error" not in result:
            raise DeviceError(f"点击未成功：{result[:200]}")

    def open_app(self):
        result = self.run("shell", "aa", "start", "-b", BUNDLE, "-a", "MainAbility")
        if "successfully" not in result:
            raise DeviceError(f"无法打开汽水音乐：{result[:200]}")

    def cleanup(self):
        # Only the two files created by this connection, never a wildcard.
        if self.serial:
            try:
                self.run("shell", "rm", "-f", f"/data/local/tmp/{self.token}.json",
                         f"/data/local/tmp/{self.token}.png", timeout=3)
            except DeviceError:
                pass
