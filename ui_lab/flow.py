from dataclasses import dataclass
from .recognition import Frame


@dataclass(frozen=True)
class Decision:
    kind: str
    message: str


class DemoFlow:
    """Pure state machine. Decisions affect only a simulated page."""
    def __init__(self, target: int):
        if not 1 <= target <= 20:
            raise ValueError("目标轮数应为 1～20")
        self.target = target
        self.completed = 0
        self.phase = "idle"
        self.confirmations = 0
        self.last_sequence = -1

    def step(self, frame: Frame) -> Decision:
        if self.completed >= self.target:
            return Decision("finish", "演示已完成")
        if frame.sequence <= self.last_sequence:
            return Decision("wait", "忽略重复或过期画面")
        self.last_sequence = frame.sequence
        if frame.page == "unknown":
            self.confirmations = 0
            return Decision("pause", "遇到未知模拟页面，请检查后继续")
        if self.phase == "idle":
            if frame.page == "ready":
                self.phase = "working"
                return Decision("begin", f"开始第 {self.completed + 1} 轮模拟任务")
            return Decision("wait", "等待模拟起始页面")
        if self.phase == "working":
            if frame.page == "done":
                self.confirmations += 1
                if self.confirmations >= 2:
                    self.phase = "returning"
                    return Decision("return", "连续确认完成，模拟返回起始页")
                return Decision("wait", "第一次确认完成，等待另一帧")
            self.confirmations = 0
            return Decision("wait", "模拟任务处理中")
        if frame.page == "ready":
            self.completed += 1
            self.phase = "idle"
            self.confirmations = 0
            return Decision("success", f"第 {self.completed} 轮已确认并记录")
        return Decision("wait", "等待模拟起始页")
