"""Package only the public demonstration and verify its extracted executable."""
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ui_lab import __version__

APP = "USBInterfaceLab"
PREFIX = f"{APP}-v{__version__}"
ARCHIVE = ROOT / "release" / f"{PREFIX}-Windows-x64.zip"
COMPONENTS = {"pyside6", "pyside6-addons", "pyside6-essentials", "shiboken6"}


def main():
    build = ROOT / "dist" / APP
    if not (build / f"{APP}.exe").is_file():
        raise SystemExit("请先运行 build.ps1")
    if ARCHIVE.exists():
        raise SystemExit("相同版本的分享包已存在，请修改版本后重新生成")
    entries = {}
    for path in build.rglob("*"):
        if path.is_file():
            relative = path.relative_to(build).as_posix()
            if relative != f"{APP}.exe" and not relative.startswith("_internal/"):
                raise RuntimeError("构建目录存在额外文件")
            entries[relative] = path.read_bytes()
    source = io.BytesIO()
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        files = [ROOT / name for name in ("main.py", "README.md", "LICENSE", ".gitignore", "build.ps1",
                                          "requirements.txt", "requirements-dev.txt", "requirements-ocr.txt")]
        for directory in ("ui_lab", "tools", "tests", "docs"):
            files.extend(p for p in (ROOT / directory).rglob("*")
                         if p.is_file() and "__pycache__" not in p.parts)
        for file in files:
            archive.write(file, file.relative_to(ROOT).as_posix())
    entries["public-source.zip"] = source.getvalue()
    entries["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    entries["使用说明.txt"] = (
        "USB 界面自动化实验室 · 模拟演示\r\n\r\n"
        "完整解压后打开 USBInterfaceLab.exe，保留 _internal 文件夹。\r\n"
        "主程序使用自建模拟页面，不连接或操作手机，无需安装 Python。\r\n"
        "选择 1～2 轮，点击开始；可暂停、继续，或模拟未知页面。\r\n"
        "记录位于 %LOCALAPPDATA%\\USBInterfaceLab，包内不含个人记录。\r\n"
        "public-source.zip 包含源码、测试和开发文档。\r\n"
        "只读 USB 与可选 OCR 脚本需要在源码环境运行，OCR 库和模型未随此包分发。\r\n"
        "本包不包含任何第三方活动领取或广告自动操作流程。\r\n"
    ).encode("utf-8-sig")
    components = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"].lower()
        if name not in COMPONENTS:
            continue
        components.append(f"{dist.metadata['Name']} {dist.version}")
        for item in dist.files or []:
            normalized = str(item).replace("\\", "/")
            if any(word in normalized.lower() for word in ("license", "licence", "copying", "notice")):
                path = Path(dist.locate_file(item))
                if path.is_file() and path.suffix.lower() not in {".py", ".pyc", ".pyd"} and ".." not in Path(normalized).parts:
                    entries[f"licenses/{name}/{normalized}"] = path.read_bytes()
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        entries["licenses/python/LICENSE.txt"] = python_license.read_bytes()
    entries["第三方组件说明.txt"] = (
        "本演示包包含 Python 和以下动态链接的 Qt/PySide6 组件。\r\n"
        "组件权利属于各自作者；licenses 和 _internal 中保留随发行版附带的声明。\r\n"
        "应用源码采用 MIT，附在 public-source.zip 中。\r\n\r\n"
        + "\r\n".join(sorted(components)) + f"\r\nPython {sys.version.split()[0]}\r\n"
    ).encode("utf-8-sig")
    manifest = {"name": APP, "version": __version__, "mode": "simulation", "files": [
        {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in sorted(entries.items())]}
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    ARCHIVE.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(entries.items()):
            archive.writestr(f"{PREFIX}/{name}", data)
    with zipfile.ZipFile(ARCHIVE) as archive:
        if archive.testzip():
            raise RuntimeError("ZIP 完整性检查失败")
        local = ROOT / ".local"
        local.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="release-check-", dir=local) as temp:
            target = Path(temp).resolve()
            assert target.is_relative_to(local.resolve())
            assert all((target / name).resolve().is_relative_to(target) for name in archive.namelist())
            archive.extractall(target)
            exe = target / PREFIX / f"{APP}.exe"
            environment = dict(os.environ, PATH=str(Path(os.environ["WINDIR"]) / "System32"))
            environment.pop("PYTHONPATH", None)
            environment.pop("PYTHONHOME", None)
            for args in (("--preview", str(target / "preview.png")),
                         ("--headless", "--target", "2", "--data-dir", str(target / "data"))):
                result = subprocess.run([str(exe), *args], cwd=target, env=environment, timeout=45,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if result.returncode:
                    raise RuntimeError("解压后的演示程序检查失败")
            if not (target / "preview.png").is_file() or not (target / "data/demo.sqlite3").is_file():
                raise RuntimeError("演示检查未生成预期文件")
            import sqlite3
            with sqlite3.connect(target / "data/demo.sqlite3") as db:
                assert db.execute("SELECT COUNT(*) FROM rounds").fetchone()[0] == 2
    checksum = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    ARCHIVE.with_suffix(".zip.sha256").write_text(f"{checksum}  {ARCHIVE.name}\n", "utf-8")
    print(json.dumps({"archive": ARCHIVE.name, "bytes": ARCHIVE.stat().st_size, "sha256": checksum,
                      "verified": ["ZIP CRC", "extracted GUI preview", "two-round simulated replay"]}))


if __name__ == "__main__":
    main()
