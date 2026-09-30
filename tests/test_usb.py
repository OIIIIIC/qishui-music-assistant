from pathlib import Path
import subprocess
import pytest
from ui_lab.usb import UsbObserver, parse_adb, parse_hdc


def test_parsers_keep_only_explicit_test_package():
    xml = '<hierarchy><node package="example.test" text="开始演示" bounds="[1,2][3,4]"/><node package="other.app" text="private"/></hierarchy>'
    nodes = parse_adb(xml, "example.test")
    assert [n.text for n in nodes] == ["开始演示"]
    raw = {"attributes": {"bundleName": "example.test", "text": "root"},
           "children": [{"attributes": {"text": "child"}},
                        {"attributes": {"bundleName": "other.app", "text": "private"}}]}
    assert [n.text for n in parse_hdc(raw, "example.test")] == ["root", "child"]


def test_observer_requires_serial_and_package(tmp_path):
    tool = tmp_path / "adb.exe"
    tool.touch()
    with pytest.raises(ValueError):
        UsbObserver("android", tool, "", "example.test")
    with pytest.raises(ValueError):
        UsbObserver("android", tool, "device", "")


def test_android_observer_reads_without_input_commands(tmp_path, monkeypatch):
    tool = tmp_path / "adb.exe"
    tool.touch()
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if command[3:5] == ["shell", "cat"]:
            output = b'<hierarchy><node package="example.test" text="Ready"/></hierarchy>'
        elif command[3:5] == ["exec-out", "screencap"]:
            output = b'\x89PNG\r\n\x1a\n'
        else:
            output = b''
        return subprocess.CompletedProcess(command, 0, output, b'')
    monkeypatch.setattr(subprocess, "run", run)
    observer = UsbObserver("android", tool, "test-device", "example.test")
    assert observer.capture(tmp_path / "capture")[0].text == "Ready"
    assert all(command[1:3] == ["-s", "test-device"] for command in calls)
    assert not any(word in {"input", "tap", "swipe", "start"} for command in calls for word in command[3:])
    assert (tmp_path / "capture/screen.png").read_bytes().startswith(b'\x89PNG')
