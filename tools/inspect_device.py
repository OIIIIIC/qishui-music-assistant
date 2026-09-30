"""Explicit, read-only observation of a developer-authorized test application."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_lab.usb import UsbObserver


def main():
    parser = argparse.ArgumentParser(description="只读采集明确指定的测试应用控件，不点击手机")
    parser.add_argument("--platform", choices=("android", "harmony"), required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--output", type=Path, default=Path(".local/usb-observation"))
    args = parser.parse_args()
    nodes = UsbObserver(args.platform, args.tool, args.serial, args.package).capture(args.output)
    output = args.output / "nodes.json"
    output.write_text(json.dumps([{"text": n.text, "package": n.package, "bounds": n.bounds} for n in nodes],
                                ensure_ascii=False, indent=2), "utf-8")
    print(f"已采集 {len(nodes)} 个控件，保存在 {output}")


if __name__ == "__main__":
    main()
