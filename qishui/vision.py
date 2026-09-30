from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .device import BUNDLE, Layout, Node


@dataclass
class Observation:
    page: str = "unknown"
    action: Node | None = None
    close: Node | None = None
    confirmed_days: int | None = None
    note: str = ""
    texts: list[str] = field(default_factory=list)
    remaining: int | None = None
    target_day: int | None = None


def classify(nodes: list[Node], width: int, height: int, bundle: str = BUNDLE) -> Observation:
    """Pure recognition rules. Never matches a success claim in an ad's creative body."""
    nodes = [n for n in nodes if n.enabled and n.bundle == bundle]
    text = "\n".join(n.text for n in nodes)

    def find(pattern: str, zone=None):
        return next((n for n in nodes if re.search(pattern, n.text) and (zone is None or zone(n))), None)

    upper = lambda n: n.center[1] < height * .20
    lower = lambda n: n.center[1] > height * .52
    middle = lambda n: height * .28 < n.center[1] < height * .78
    obs = Observation(texts=[n.text for n in nodes if n.text])
    # Modal takes precedence over the dimmed success label behind it.
    leave = find(r"^坚持退出$", middle)
    if leave and find(r"再看.{0,8}(视频|提前|广告)", middle):
        obs.page, obs.action = "retention", leave
        return obs
    if find(r"(今日|今天).{0,10}(上限|用完)|暂无广告|暂时没有广告|明日再来|明天再来"):
        obs.page, obs.note = "exhausted", "当前没有可领取的广告"
        return obs
    # Only the known reward panel can launch an ad.
    entry = find(r"^(?:立即)?解锁\s*第\s*\d+\s*天畅听$", lower)
    title = find(r"再看\s*\d+\s*个提前享第\s*\d+\s*天畅听", lower)
    if entry and title:
        obs.page, obs.action = "entry", entry
        progress = re.search(r"再看\s*(\d+)\s*个提前享第\s*(\d+)\s*天畅听", title.text)
        obs.remaining, obs.target_day = map(int, progress.groups())
        confirmation = find(r"恭喜获得第\s*(\d+)\s*天免费时长畅听", lower)
        if confirmation:
            obs.confirmed_days = int(re.search(r"第\s*(\d+)", confirmation.text).group(1))
        return obs
    ad = find(r"^广告(?:[|丨].*)?$", upper) or find(r"^反馈$", lambda n: upper(n) and .35 * width < n.center[0] < .85 * width)
    success = find(r"^领取成功\s*[×xX✕✖]?\s*$", lambda n: upper(n) and n.center[0] > .7 * width)
    countdown = find(r"(\d+\s*[sS秒].{0,10}(奖励|领取)|\d+\s*秒后|奖励.{0,5}\d+\s*秒)", upper)
    if ad and success:
        obs.page = "ad_done"
        # Exact known top-right close symbol, if OCR exposes it independently.
        close = find(r"^[×xX✕✖]$", lambda n: upper(n) and n.center[0] > width * .85)
        obs.close = close
        return obs
    if ad and countdown:
        obs.page, obs.note = "ad_playing", countdown.text
        return obs
    if ad:
        obs.page, obs.note = "ad_loading", "等待广告状态"
        return obs
    if find(r"模式选择$") and find(r"^(免)?\d+天$", upper) and find(r"^我的$") and find(r"^会员$"):
        obs.page = "home"
        obs.action = find(r"^(免)?\d+天$", upper)
        obs.confirmed_days = int(re.search(r"\d+", obs.action.text).group())
    return obs


class LocalVision:
    def __init__(self):
        self._ocr = None

    def read(self, layout: Layout, screenshot: Path) -> Observation:
        if not layout.is_app:
            return Observation(note="当前前台不是汽水音乐")
        bundle = layout.target_bundle
        # Native selectors first. Empty/canvas overlays use bundled, offline OCR.
        root = layout.nodes[0].bounds if layout.nodes else (0, 0, 1084, 2412)
        width, height = root[2], root[3]
        native = classify(layout.nodes, width, height, bundle)
        if native.page in ("entry", "retention", "ad_playing", "exhausted") or (native.page == "ad_done" and native.close):
            return native
        import cv2
        import numpy as np
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1,
                                 det_use_cuda=False, cls_use_cuda=False, rec_use_cuda=False)
        img = cv2.imdecode(np.fromfile(str(screenshot), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return Observation(note="设备截图无法读取")
        height, width = img.shape[:2]
        results, _ = self._ocr(img, use_cls=False)
        nodes = []
        for box, text, score in results or []:
            if score < .80:
                continue
            xs, ys = [p[0] for p in box], [p[1] for p in box]
            nodes.append(Node(re.sub(r"\s+", "", text), "", "ocr",
                              (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))),
                              bundle, "OCR", True, True))
        obs = classify(nodes, width, height, bundle)
        # Locate the known close glyph by template, only after recognizing the reward label.
        if obs.page == "ad_done" and obs.close is None:
            template_path = Path(__file__).parent / "assets" / "ad_close.png"
            if template_path.exists():
                template = cv2.imdecode(np.fromfile(str(template_path), np.uint8), 0)
                scaled = cv2.resize(img, (1084, round(height * 1084 / width)))
                region = cv2.cvtColor(scaled[:round(scaled.shape[0] * .18), 920:1084], cv2.COLOR_BGR2GRAY)
                result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
                _, confidence, _, pos = cv2.minMaxLoc(result)
                if confidence >= .88:
                    x, y = pos[0] + 920, pos[1]
                    h, w = template.shape
                    factor = width / 1084
                    obs.close = Node("关闭广告", "", "local-template", tuple(round(v * factor) for v in (x, y, x+w, y+h)), bundle, "Template", True, True)
        return obs
