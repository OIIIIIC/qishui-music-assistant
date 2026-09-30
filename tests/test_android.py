from subprocess import CompletedProcess
from unittest.mock import Mock

import pytest

from qishui import android, connection
from qishui.android import AdbDevice, ANDROID_BUNDLE, parse_android_layout, parse_targets
from qishui.device import BUNDLE, DeviceError, HdcDevice, Layout, Node
from qishui.flow import Flow
from qishui.vision import LocalVision, classify


def node(text, x=540, y=1800, bundle=ANDROID_BUNDLE):
    return Node(text, "", "", (x-30, y-15, x+30, y+15), bundle, "TextView", True, True)


@pytest.fixture
def device(monkeypatch):
    monkeypatch.setattr(android, "discover_adb", lambda _: "adb.exe")
    return AdbDevice(serial="test-phone")


def test_targets_keep_authorization_and_offline_states():
    output = "* daemon started successfully\nList of devices attached\na device product:p model:m\nb unauthorized\nc offline\n"
    assert parse_targets(output) == {"a": "device", "b": "unauthorized", "c": "offline"}


@pytest.mark.parametrize("state,message", [("unauthorized", "授权"), ("offline", "离线")])
def test_connect_requires_ready_selected_device(device, state, message):
    device.run = Mock(return_value=f"test-phone {state}\nother device")
    with pytest.raises(DeviceError, match=message):
        device.connect()
    assert device.serial == "test-phone"


def test_connect_does_not_select_first_of_many(device):
    device.serial = ""
    device.run = Mock(return_value="one device\ntwo device")
    with pytest.raises(DeviceError, match="多台"):
        device.connect()


def test_screenshot_preserves_binary_and_pins_serial(device, monkeypatch, tmp_path):
    png = b"\x89PNG\r\n\x1a\n\x00\xff\x80\r\n"
    run = Mock(return_value=CompletedProcess([], 0, png, b""))
    monkeypatch.setattr(android.subprocess, "run", run)
    path = tmp_path / "phone.png"
    device.screenshot(path)
    assert path.read_bytes() == png
    assert run.call_args.args[0] == ["adb.exe", "-s", "test-phone", "exec-out", "screencap", "-p"]


def test_screenshot_error_is_not_saved_as_picture(device, tmp_path):
    device.run = Mock(return_value=b"error: device offline")
    path = tmp_path / "phone.png"
    with pytest.raises(DeviceError, match="截图失败"):
        device.screenshot(path)
    assert not path.exists()


def test_xml_normalizes_bounds_visibility_and_app_scope():
    xml = '''<?xml version="1.0"?><hierarchy>
      <node package="com.android.systemui" bounds="[0,0][1080,80]" text="其他通知"/>
      <node package="com.luna.music" bounds="[0,80][1080,2400]">
        <node text="解锁第7天畅听" bounds="[100,2200][980,2300]" clickable="true"/>
        <node text="隐藏按钮" bounds="[0,0][100,100]" visible-to-user="false"/>
      </node></hierarchy>'''
    layout = parse_android_layout(xml, ANDROID_BUNDLE)
    assert layout.nodes[0].bounds == (0, 0, 1080, 2400)
    assert layout.texts == ["解锁第7天畅听"]
    assert layout.find("解锁").center == (540, 2250)
    assert layout.is_app
    layout.foreground_bundle = "com.android.permissioncontroller"
    assert not layout.is_app


def test_invalid_xml_fails_explicitly():
    with pytest.raises(DeviceError):
        parse_android_layout("ERROR: could not get idle state", ANDROID_BUNDLE)


def test_video_dump_failure_uses_ocr_only_in_app(device):
    device.foreground = Mock(return_value=ANDROID_BUNDLE)
    device.run = Mock(side_effect=DeviceError("idle timeout"))
    layout = device.layout()
    assert layout.is_app and layout.nodes == []
    assert "layout_warning" in layout.raw
    device.foreground = Mock(side_effect=[ANDROID_BUNDLE, "com.android.launcher"])
    assert not device.layout().is_app


def test_focus_permission_dialog_overrides_resumed_app(device):
    device.run = Mock(return_value="mCurrentFocus=Window{123 u0 com.android.permissioncontroller/.GrantPermissionsActivity}")
    assert device.foreground() == "com.android.permissioncontroller"
    assert device.run.call_count == 1


def test_foreground_activity_fallback(device):
    device.run = Mock(side_effect=["", "topResumedActivity=ActivityRecord{123 u0 com.luna.music/.MainActivity t3}"])
    assert device.foreground() == ANDROID_BUNDLE


def test_click_rechecks_foreground_and_does_not_touch_other_app(device):
    device.foreground = Mock(return_value="com.android.launcher")
    device.run = Mock()
    with pytest.raises(DeviceError, match="取消点击"):
        device.click(node("解锁第7天畅听"))
    device.run.assert_not_called()


def test_click_refuses_wrong_bundle(device):
    device.run = Mock()
    with pytest.raises(DeviceError, match="归属"):
        device.click(node("解锁第7天畅听", bundle=BUNDLE))
    device.run.assert_not_called()


def test_android_round_counts_only_after_return_and_stops_at_target():
    panel = [node("再看2个提前享第7天畅听"), node("解锁第7天畅听", y=2280)]
    ad = [node("反馈", 600, 150), node("领取成功", 950, 150), node("×", 1040, 150)]
    entry = classify(panel, 1080, 2400, ANDROID_BUNDLE)
    done = classify(ad, 1080, 2400, ANDROID_BUNDLE)
    assert entry.page == "entry" and done.page == "ad_done"
    assert classify(panel, 1080, 2400).page == "unknown"
    flow = Flow(1)
    assert flow.step(entry).kind == "begin"
    assert flow.step(done).kind == "watching"
    assert flow.step(done).kind == "wait"
    decision = flow.step(done)
    assert decision.kind == "click" and decision.node.bundle == ANDROID_BUNDLE
    assert flow.completed == 0
    assert flow.step(entry).kind == "success"
    assert flow.step(entry).kind == "finish"


def test_local_ocr_is_not_used_over_other_apps(tmp_path):
    layout = Layout({}, ANDROID_BUNDLE, "com.android.launcher")
    vision = LocalVision()
    assert vision.read(layout, tmp_path / "missing.png").page == "unknown"
    assert vision._ocr is None


def test_local_ocr_emits_android_nodes_for_canvas_panel(tmp_path):
    import cv2
    import numpy as np
    image = tmp_path / "canvas.png"
    cv2.imencode(".png", np.zeros((2400, 1080, 3), dtype=np.uint8))[1].tofile(str(image))
    vision = LocalVision()
    vision._ocr = Mock(return_value=([
        ([[100,1700],[980,1700],[980,1800],[100,1800]], "再看2个提前享第7天畅听", .99),
        ([[100,2200],[980,2200],[980,2300],[100,2300]], "解锁第7天畅听", .99),
    ], 0))
    obs = vision.read(Layout({}, ANDROID_BUNDLE, ANDROID_BUNDLE), image)
    assert obs.page == "entry" and obs.action.bundle == ANDROID_BUNDLE
    assert obs.remaining == 2 and obs.target_day == 7


def backends(monkeypatch, harmony, android_targets):
    for name, targets in (("HdcDevice", harmony), ("AdbDevice", android_targets)):
        cls = Mock()
        cls.return_value.targets.return_value = targets
        monkeypatch.setattr(connection, name, cls)


def test_auto_selects_android_with_serial(monkeypatch):
    backends(monkeypatch, {}, {"phone": "device"})
    connection.choose_device({})
    connection.AdbDevice.assert_called_with("", "phone")


def test_auto_keeps_unauthorized_device_for_clear_error(monkeypatch):
    backends(monkeypatch, {}, {"phone": "unauthorized"})
    connection.choose_device({})
    connection.AdbDevice.assert_called_with("", "phone")


def test_auto_never_picks_between_platforms(monkeypatch):
    backends(monkeypatch, {"h": "device"}, {"a": "device"})
    with pytest.raises(DeviceError, match="多台"):
        connection.choose_device({})
    connection.choose_device({"platform": "android", "serial": "a"})
    connection.AdbDevice.assert_called_with("", "a")


def test_auto_never_switches_missing_selected_phone(monkeypatch):
    backends(monkeypatch, {}, {"other": "device"})
    with pytest.raises(DeviceError, match="不会自动切换"):
        connection.choose_device({"serial": "missing"})


def test_harmony_single_device_still_connects(monkeypatch):
    monkeypatch.setattr("qishui.device.discover_hdc", lambda _: "hdc.exe")
    d = HdcDevice()
    d.run = Mock(side_effect=["harmony-phone", "nova 15"])
    assert d.connect() == "nova 15"
    assert d.serial == "harmony-phone"
