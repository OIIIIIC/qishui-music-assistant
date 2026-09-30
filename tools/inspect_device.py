"""Read-only capture for adapting selectors. Data stays in .local/captures."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qishui.connection import choose_device
from qishui.storage import load_settings

sys.stdout.reconfigure(encoding="utf-8")
p = argparse.ArgumentParser()
p.add_argument("name", nargs="?", default="current")
p.add_argument("--screenshot", action="store_true")
p.add_argument("--platform", choices=("auto", "harmony", "android"), default="auto")
p.add_argument("--serial", default="")
a = p.parse_args()
d = choose_device(load_settings() | {"platform": a.platform, "serial": a.serial})
try:
    print("设备:", d.connect())
    layout = d.layout()
    folder = Path(".local/captures")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{a.name}.json").write_text(json.dumps(layout.raw, ensure_ascii=False, indent=2), "utf-8")
    for n in layout.nodes:
        if n.text and n.bundle == d.bundle:
            print(n.text, n.bounds, n.identifier, "click" if n.clickable else "")
    if a.screenshot:
        d.screenshot(folder / f"{a.name}.png")
finally:
    d.cleanup()
