"""Recognize a user-selected local image. Optional dependencies are separate."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="识别本地图片，不连接或操作手机")
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error("图片不存在")
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        parser.error("请先安装 requirements-ocr.txt 中的可选依赖")
    import cv2
    import numpy as np
    image = cv2.imdecode(np.fromfile(str(args.image), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        parser.error("无法读取图片")
    results, _ = RapidOCR()(image)
    print(json.dumps([{"text": text, "confidence": score} for _, text, score in results or []],
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
