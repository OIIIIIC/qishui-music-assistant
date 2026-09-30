# 开发说明

## 结构

```text
main.py                  桌面入口、离线回放和预览
ui_lab/recognition.py    自建演示标签与模拟帧
ui_lab/flow.py           无副作用的状态机
ui_lab/journal.py        SQLite 记录及幂等轮数写入
ui_lab/ui.py             模拟桌面界面
ui_lab/usb.py            指定测试应用的只读 USB 采集
tools/inspect_device.py  USB 读取命令行入口
tools/ocr_image.py       可选本地图片 OCR
tools/package_release.py 分享包及校验文件生成
tests/                  流程、存储、解析与界面集成测试
```

## 流程设计

状态机只消费 `Frame(sequence, page)`，输出描述下一步的 `Decision`。这里的决定只用于模拟页面，不会向手机发送操作。

每个观察帧有单调递增的序号。重复帧不能增加完成确认数；完成提示需连续出现两帧，回到起始页后才计为一轮。未知页面要求暂停，由用户恢复。界面的暂停操作不会推进模拟帧。

SQLite 以「任务 ID + 轮次」为唯一键，防止重复记录。模拟数据目录和真实设备采集目录独立。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe main.py --headless --target 2 --data-dir .local/replay
.\.venv\Scripts\python.exe main.py --preview .local/preview.png
```

测试覆盖连续确认、重复帧、目标停止、未知页面、暂停恢复、持久化、应用包名过滤和 USB 只读指令。USB 模拟测试不代表所有手机或工具版本已完成真机验证。

## 可选 USB 与 OCR

USB 采集只读取指定设备，不自动选择手机或启动应用。Android 使用 UIAutomator dump 与 screencap，鸿蒙使用 uitest dumpLayout。Android 采集脚本会清理自己创建的临时布局文件；鸿蒙布局文件由 uitest 创建，保留在设备上。

OCR 是独立脚本，依赖在 `requirements-ocr.txt` 中。桌面模拟演示不导入 OCR 组件，也不收集其模型。

## 构建与分享

构建脚本默认使用本项目 `.venv/Scripts/python.exe`，也允许通过 `-PythonExe` 显式指定环境。构建时隔离 PATH，排除未使用的 OCR 和图像处理运行库。

`tools/package_release.py` 收集完整桌面输出、公开源码、第三方声明与使用说明，生成 ZIP 和 SHA-256。脚本检查 ZIP 完整性，并在隔离数据目录中验证解压后的预览和两轮模拟回放。

ZIP 内的 `_internal` 是必要运行库，不能只分发 `.exe`。源码 ZIP 不包含运行记录、USB 截图、虚拟环境或构建产物。
