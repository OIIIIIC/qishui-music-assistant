"""Read-only USB observations for an explicitly chosen authorized test app."""
from dataclasses import dataclass
from pathlib import Path
import json
import re
import subprocess
import uuid
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class Node:
    text: str
    package: str
    bounds: tuple[int, ...]


def parse_adb(xml: str, package: str) -> list[Node]:
    nodes = []
    for element in ET.fromstring(xml).iter():
        attrs = element.attrib
        if attrs.get("package") == package:
            nodes.append(Node(attrs.get("text", ""), package,
                              tuple(map(int, re.findall(r"-?\d+", attrs.get("bounds", ""))))))
    return nodes


def parse_hdc(raw: dict, package: str) -> list[Node]:
    nodes = []
    def visit(value, inherited=""):
        attrs = value.get("attributes", {})
        current = attrs.get("bundleName") or inherited
        if current == package and str(attrs.get("visible", "true")).lower() != "false":
            nodes.append(Node(attrs.get("text", ""), current,
                              tuple(map(int, re.findall(r"-?\d+", attrs.get("bounds", ""))))))
        for child in value.get("children", []):
            visit(child, current)
    visit(raw)
    return nodes


class UsbObserver:
    """Read layout and a screenshot; no tap, swipe or activity-launch interface."""
    def __init__(self, platform: str, tool: Path, serial: str, package: str):
        if platform not in {"android", "harmony"}:
            raise ValueError("未知手机系统")
        if not tool.is_file() or not serial.strip() or not package.strip():
            raise ValueError("需要明确指定调试工具、设备序列号和获授权测试应用的包名")
        self.platform, self.tool, self.serial, self.package = platform, tool.resolve(), serial, package

    def _run(self, *args: str, binary=False):
        selector = "-s" if self.platform == "android" else "-t"
        result = subprocess.run([str(self.tool), selector, self.serial, *args], capture_output=True,
                                timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode:
            raise RuntimeError("设备读取失败，请检查调试授权、工具版本与指定序列号")
        return result.stdout if binary else result.stdout.decode("utf-8", errors="replace")

    def capture(self, output: Path) -> list[Node]:
        output.mkdir(parents=True, exist_ok=True)
        if self.platform == "android":
            remote = f"/data/local/tmp/ui_lab_{uuid.uuid4().hex}.xml"
            try:
                self._run("shell", "uiautomator", "dump", remote)
                xml = self._run("shell", "cat", remote)
                nodes = parse_adb(xml, self.package)
                screenshot = self._run("exec-out", "screencap", "-p", binary=True)
            finally:
                self._run("shell", "rm", "-f", remote)
            (output / "layout.xml").write_text(xml, "utf-8")
            (output / "screen.png").write_bytes(screenshot)
            return nodes
        # HDC uitest reports the created JSON path; only retrieve that exact file.
        text = self._run("shell", "uitest", "dumpLayout")
        match = re.search(r"(/data/local/tmp/[A-Za-z0-9_./-]+\.json)", text)
        if not match:
            raise RuntimeError("当前 HDC 未返回可读取的控件文件路径")
        remote = match.group(1)
        raw = json.loads(self._run("shell", "cat", remote))
        (output / "layout.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), "utf-8")
        return parse_hdc(raw, self.package)
