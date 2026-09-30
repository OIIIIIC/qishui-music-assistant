from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    sequence: int
    page: str


def classify_texts(texts: list[str]) -> str:
    """Only recognize our own demonstration page's explicit labels."""
    labels = {text.strip() for text in texts}
    if "演示完成" in labels:
        return "done"
    if "处理中" in labels:
        return "busy"
    if "开始演示" in labels:
        return "ready"
    return "unknown"


DEMO_LABELS = ("开始演示", "处理中", "演示完成", "演示完成", "开始演示")


def demo_frame(sequence: int) -> Frame:
    # Each cycle contains two independently observed completion frames.
    return Frame(sequence, classify_texts([DEMO_LABELS[sequence % len(DEMO_LABELS)]]))
