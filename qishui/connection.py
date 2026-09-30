from .android import AdbDevice
from .device import HdcDevice, DeviceError


def choose_device(settings: dict):
    """Select one transport without silently switching to another phone."""
    platform = settings.get("platform", "auto")
    serial = settings.get("serial", "")
    kinds = {"harmony": (HdcDevice, "hdc"), "android": (AdbDevice, "adb")}
    if platform in kinds:
        cls, key = kinds[platform]
        return cls(settings.get(key, ""), serial)
    if platform != "auto":
        raise DeviceError("未知设备类型，请在设置中重新选择")
    candidates, errors = [], []
    for cls, key in kinds.values():
        try:
            device = cls(settings.get(key, ""))
            for found in device.targets():
                if not serial or serial == found:
                    candidates.append((cls, key, found))
        except DeviceError as e:
            errors.append(str(e))
    if len(candidates) > 1:
        raise DeviceError("检测到多台设备，请在连接设置中选择手机系统并填写设备序列号")
    if candidates:
        cls, key, found = candidates[0]
        return cls(settings.get(key, ""), found)
    if serial:
        raise DeviceError("指定设备未连接；不会自动切换到其他手机")
    detail = "；".join(errors)
    raise DeviceError("未发现手机，请通过 USB 连接并允许调试" + ("；" + detail if detail else ""))
