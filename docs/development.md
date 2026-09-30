# 开发说明

项目使用 Python 3.13、PySide6 和 RapidOCR。核心流程优先读取手机控件，对广告画面使用本地 OCR 与关闭图标匹配。

## 安装与测试

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
uv pip install --python .venv/Scripts/python.exe pytest
.venv/Scripts/python.exe -m pytest -q
```

`requirements.txt` 声明直接依赖，`requirements-lock.txt` 记录当前开发环境的完整依赖版本。需要复现该环境时可安装后者。

2026-09-30 本地测试结果：37 项通过。覆盖鸿蒙观看流程、Android 传输与控件解析、设备选择、轮数和记录持久化；不等同于 Android 真机验证。

## 项目结构

| 路径 | 作用 |
| --- | --- |
| `main.py` | 程序入口、预览与只读诊断 |
| `qishui/ui.py` | 界面、设置和运行记录 |
| `qishui/flow.py` | 观看流程与轮数判定 |
| `qishui/worker.py` | 后台设备检查与任务执行 |
| `qishui/device.py` | 鸿蒙 HDC 连接与控件读取 |
| `qishui/android.py` | Android ADB、UIAutomator 与截图 |
| `qishui/connection.py` | 手机系统与设备选择 |
| `qishui/vision.py` | OCR、页面及图标识别 |
| `qishui/storage.py` | 设置与 SQLite 记录 |
| `tests/` | 自动化测试 |
| `tools/` | 设备检查、真机联调与分享包生成 |

## 预览与诊断

只生成界面预览，不连接设备：

```powershell
.venv/Scripts/python.exe main.py --preview .local/preview.png
```

只读设备与本地 OCR 自检，不点击手机：

```powershell
.venv/Scripts/python.exe main.py --diagnose .local/diagnose.json
.venv/Scripts/python.exe main.py --platform android --diagnose .local/android-diagnose.json
```

限定一轮真机联调，**会真实操作手机**：

```powershell
.venv/Scripts/python.exe tools/verify_live.py --rounds 1 --seconds 240
.venv/Scripts/python.exe tools/verify_live.py --platform android --rounds 1 --seconds 240
```

多设备连接时须指定系统及序列号，不会自动选择第一台。鸿蒙控件通过 `hdc shell uitest` 读取，不安装手机端测试应用，也不重启 HoKit 使用的 HDC 服务。

## 计数规则

- 进入广告、确认完成、关闭广告、返回面板分别判定。
- 连续两次识别到广告顶部「领取成功」，并定位到关闭图标后，才尝试关闭。
- 返回面板后计为完成，听歌天数独立核对。未增加就记录「听歌天数暂无变化」。
- 继续观看提示会选择「坚持退出」，返回面板后再决定下一轮。
- 达到目标或时限就结束；持续无法识别、连接中断或单轮超时会暂停。
- 暂停时间计入最长运行时间；中断的未确认轮次保留为待确认。

## 构建与分享

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
.venv/Scripts/python.exe tools/package_release.py
```

`build.ps1` 会隔离构建 PATH，避免误收集其他工具的同名 DLL。分享包脚本会收集源码、文档、许可证、依赖声明和校验清单，并检查解压后的程序启动。

版本号位于 `tools/package_release.py`，同版本 ZIP 已存在时脚本会停止，避免覆盖。应先完成文档更新再生成分享包。

个人设置、SQLite 记录和异常截图不进入 Git。开发资料放在 `.local/`；若需独立运行数据目录，可设置 `QISHUI_DATA_DIR` 环境变量。
