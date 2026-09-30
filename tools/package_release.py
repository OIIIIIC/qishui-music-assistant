"""Package the verified build by allowlist; no settings, captures, or local shortcuts."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
APP = "汽水音乐助手"
VERSION = "0.2.0-alpha.1"
BUILD = ROOT / "dist" / APP
OUTPUT = ROOT / "release"
ARCHIVE = OUTPUT / f"{APP}-v{VERSION}-Windows-x64.zip"
PREFIX = f"{APP}-v{VERSION}"
DEPENDENCIES = {
    "pyside6", "pyside6-essentials", "pyside6-addons", "shiboken6",
    "rapidocr-onnxruntime", "onnxruntime", "opencv-python", "numpy", "pillow",
    "shapely", "pyclipper", "pyyaml", "protobuf", "flatbuffers", "six", "tqdm",
}

INSTRUCTIONS = f"""汽水音乐助手 v{VERSION} · Windows 便携版

一、如何打开
1. 将整个 ZIP 解压到一个文件夹。
2. 双击「汽水音乐助手.exe」。请勿直接在压缩包里运行。
3. 请保留同目录的 _internal 文件夹，不能只发送或移动 exe。
无需安装 Python，无需填写任何大模型 API Key。

二、连接手机
需要 Windows 64 位电脑，以及支持调试的鸿蒙或 Android 手机。
原有鸿蒙流程已在 Windows 11、nova 15、HarmonyOS 7.0、汽水音乐 21.1.1 上验证。
本次新增 Android 试验支持，仅完成本地模拟测试和 Windows 程序启动检查。
尚无 Android 真机验证，不能保证安卓版奖励页面和广告流程能够自动完成。
其他系统和广告页面尚未逐一验证。

鸿蒙：接收方需先安装 HoKit，或自行准备鸿蒙 HDC 工具。
HoKit 项目页面：https://github.com/yabi-zzh/HoKit
Android：准备官方 Android SDK Platform-Tools，也可使用 scrcpy 自带的 adb.exe。
官方下载：https://developer.android.com/tools/releases/platform-tools
本压缩包不包含 HoKit、HDC、ADB、scrcpy 或手机驱动。
开启手机的开发者选项和 USB 调试，使用 USB 数据线连接电脑，
在手机上允许本机调试。可以先用 HoKit 确认设备能连接。
助手会查找标准安装位置的 HoKit/HDC，也可在右上角设置的
「连接设置」中手动选择 hdc.exe。
Android 会查找 PATH 和标准 SDK 位置；scrcpy 在其他位置时，手动选择其中的 adb.exe，
并保留 adb.exe 同目录的 DLL。无需打开 HoKit 或 scrcpy 投屏窗口。
手机系统默认为自动识别，也可手动选择；只有一台设备时序列号留空。
检测到多台设备时需指定系统及序列号，助手不会随意选择一台。

三、开始使用
手机保持解锁、亮屏，打开汽水音乐免费听歌领取面板。
当前支持「立即解锁 第 N 天畅听」「解锁第 N 天畅听」的奖励流程。
在助手中选择目标轮数，然后点击「开始」。建议首次先设 1～2 轮。
运行中不要同时操作手机；电脑需要保持运行。
HoKit 投屏窗口的位置不影响操作，助手不占用电脑鼠标。

四、轮数怎么算
看完广告、连续确认「领取成功」、关闭广告并返回领取面板，计为一轮。
可能需要看多个广告才增加一天听歌时间，所以观看轮数与听歌天数分开记录。
达到目标自动结束；页面无法识别、断开连接或等待超时会暂停。
「暂停」停止自动操作，手机上的广告可能继续播放。
「结束」保存记录，不再开启下一轮。

五、数据和运行环境
程序及 OCR 均在本机运行，不调用联网大模型；手机加载广告仍需网络。
个人设置、记录和异常截图保存在当前 Windows 用户的：
%LOCALAPPDATA%\\QishuiAssistant
可通过「查看记录 → 打开记录文件夹」查看。
分享包不包含制作者的运行记录、手机截图、设备序列号或个人配置。

六、压缩包内容
汽水音乐助手.exe：启动程序
_internal：运行库和本地识别模型，请保留
使用说明.txt：本说明
第三方组件说明.txt / licenses：组件版本及随发行版附带的许可证文本
应用源码.zip：本工具源码、依赖清单及构建脚本（不含本机数据）
manifest.json：文件大小及 SHA-256 校验清单

遇到新广告或不支持的页面，请先结束任务，再检查手机页面。
本版本按已观察到的界面适配，不能保证所有广告样式都能自动处理。
"""


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    exe = BUILD / f"{APP}.exe"
    if not exe.is_file() or not (BUILD / "_internal").is_dir():
        raise SystemExit("请先运行 build.ps1")
    if ARCHIVE.exists():
        raise SystemExit(f"输出已存在，请使用新的版本号：{ARCHIVE}")
    OUTPUT.mkdir(exist_ok=True)
    entries = {}
    for path in BUILD.rglob("*"):
        if path.is_file():
            relative = path.relative_to(BUILD).as_posix()
            if relative != f"{APP}.exe" and not relative.startswith("_internal/"):
                raise RuntimeError(f"构建目录包含额外文件：{relative}")
            if path.suffix.lower() in {".log", ".sqlite3", ".lnk"} or path.name in {"settings.json", "current-screen.png"}:
                raise RuntimeError(f"构建目录包含个人数据：{relative}")
            entries[relative] = path
    entries["使用说明.txt"] = INSTRUCTIONS.replace("\n", "\r\n").encode("utf-8-sig")
    components = []
    for dist in importlib.metadata.distributions():
        name = canonical(dist.metadata["Name"])
        if name not in DEPENDENCIES:
            continue
        components.append(f"{dist.metadata['Name']} {dist.version}")
        for item in dist.files or []:
            normalized = str(item).replace("\\", "/")
            if re.search(r"license|licence|copying|notice", normalized, re.I):
                source = Path(dist.locate_file(item))
                if source.is_file() and source.suffix.lower() not in {".py", ".pyc", ".pyd"}:
                    dest = "licenses/" + name + "/" + normalized
                    if ".." not in Path(dest).parts:
                        entries[dest] = source
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        entries["licenses/python/LICENSE.txt"] = python_license
    entries["第三方组件说明.txt"] = (
        "本包包含以下第三方组件，其权利归相应作者所有。\r\n"
        "licenses 目录收录安装发行版自带的许可证与第三方声明；部分组件的声明也保留在 _internal 中。\r\n"
        "Qt / PySide6 使用动态链接，运行库位于 _internal；应用源代码附在应用源码.zip。\r\n\r\n"
        + "\r\n".join(sorted(components)) + f"\r\nPython {sys.version.split()[0]}\r\n"
    ).encode("utf-8-sig")
    import io
    source_buffer = io.BytesIO()
    with zipfile.ZipFile(source_buffer, "w", zipfile.ZIP_DEFLATED) as source_zip:
        paths = [ROOT / name for name in ("main.py", "README.md", "LICENSE", "requirements.txt", "requirements-lock.txt", "build.ps1", ".gitignore")]
        for directory in ("qishui", "tests", "tools", "docs"):
            paths.extend(p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for path in paths:
            source_zip.write(path, path.relative_to(ROOT).as_posix())
    entries["应用源码.zip"] = source_buffer.getvalue()
    manifest = {"name": APP, "version": VERSION, "platform": "Windows x64", "files": []}
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, source in sorted(entries.items()):
            content = source.read_bytes() if isinstance(source, Path) else source
            manifest["files"].append({"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
            archive.writestr(PREFIX + "/" + name, content)
        archive.writestr(PREFIX + "/manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"压缩包已生成：{ARCHIVE.name} ({ARCHIVE.stat().st_size / 1024**2:.1f} MiB)", flush=True)
    with zipfile.ZipFile(ARCHIVE) as archive:
        if archive.testzip():
            raise RuntimeError("压缩包 CRC 检查未通过")
        for item in manifest["files"]:
            if hashlib.sha256(archive.read(PREFIX + "/" + item["path"])).hexdigest() != item["sha256"]:
                raise RuntimeError("压缩包 SHA-256 检查未通过")
        local = ROOT / ".local"
        local.mkdir(exist_ok=True)
        # Fresh directory is explicitly constrained to this workspace before cleanup.
        with tempfile.TemporaryDirectory(prefix="share-check-", dir=local) as temp:
            temp_path = Path(temp).resolve()
            if not temp_path.is_relative_to(local.resolve()):
                raise RuntimeError("验证路径超出工作区")
            for member in archive.namelist():
                if not (temp_path / member).resolve().is_relative_to(temp_path):
                    raise RuntimeError("压缩包路径无效")
            archive.extractall(temp_path)
            preview = temp_path / "preview.png"
            env = dict(os.environ)
            env["QISHUI_DATA_DIR"] = str(temp_path / "data")
            env["PATH"] = str(Path(os.environ["WINDIR"]) / "System32")
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONHOME", None)
            result = subprocess.run([str(temp_path / PREFIX / f"{APP}.exe"), "--preview", str(preview)],
                                    env=env, cwd=temp_path, timeout=45,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode or not preview.exists():
                raise RuntimeError("解压后的界面启动检查失败")
    checksum = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    ARCHIVE.with_suffix(".zip.sha256").write_text(f"{checksum}  {ARCHIVE.name}\n", "utf-8")
    print(json.dumps({"archive": str(ARCHIVE), "bytes": ARCHIVE.stat().st_size,
                      "entries": len(manifest["files"]) + 1, "sha256": checksum,
                      "verified": ["CRC", "SHA-256", "extracted GUI startup with isolated PATH"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
