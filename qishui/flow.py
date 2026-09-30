from __future__ import annotations

from dataclasses import dataclass
from .device import Node
from .vision import Observation


@dataclass
class Decision:
    kind: str
    message: str
    node: Node | None = None


class Flow:
    """One session state machine; side effects live in the worker.

    Beginning, observing the ad, observing success twice, and returning to the
    reward panel are separate transitions. Watched ads and listening days differ.
    """
    def __init__(self, target: int):
        self.target = target
        self.completed = 0
        self.active = False
        self.watching = False
        self.before_days: int | None = None
        self.success_frames = 0
        self.closed = False
        self.exit_clicked = False
        self.home_clicked = False
        self.before_remaining = None

    def step(self, obs: Observation) -> Decision:
        if obs.page != "ad_done":
            self.success_frames = 0
        if obs.page == "exhausted":
            return Decision("finish", obs.note)
        if not self.active:
            if self.completed >= self.target:
                return Decision("finish", "目标已完成")
            if obs.page == "home" and obs.action and not self.home_clicked:
                self.home_clicked = True
                # On this app version the top free-days badge launches an ad directly.
                self.before_days = obs.confirmed_days
                self.before_remaining = obs.remaining
                self.active = True
                self.watching = self.closed = self.exit_clicked = False
                self.success_frames = 0
                return Decision("begin", f"准备观看第 {self.completed + 1} 轮", obs.action)
            if obs.page == "entry" and obs.action:
                self.before_days = obs.confirmed_days
                self.before_remaining = obs.remaining
                self.active = True
                self.watching = self.closed = self.exit_clicked = False
                self.success_frames = 0
                return Decision("begin", f"准备观看第 {self.completed + 1} 轮", obs.action)
            if obs.page.startswith("ad_") or obs.page == "retention":
                return Decision("pause", "请先手动返回听歌领取面板，再继续")
            return Decision("wait", "等待听歌领取面板")

        if obs.page in ("ad_playing", "ad_loading", "ad_done") and not self.watching:
            self.watching = True
            return Decision("watching", f"正在观看第 {self.completed + 1} 轮")
        if obs.page == "ad_done":
            self.success_frames += 1
            if self.success_frames >= 2 and not self.closed and obs.close:
                self.closed = True
                return Decision("click", "广告已完成，正在核对领取结果", obs.close)
            return Decision("wait", "正在确认广告完成状态" if obs.close else "等待识别广告关闭按钮")
        if obs.page in ("ad_playing", "ad_loading"):
            self.success_frames = 0
            return Decision("wait", "等待广告结束")
        if obs.page == "retention":
            if self.closed and not self.exit_clicked and obs.action:
                self.exit_clicked = True
                return Decision("click", "返回听歌领取面板", obs.action)
            if not self.closed:
                return Decision("pause", "广告状态发生变化，请检查手机页面")
        if obs.page == "entry" and self.watching and self.closed:
            self.completed += 1
            self.active = False
            self.home_clicked = False
            if self.before_days is not None and obs.confirmed_days is not None and obs.confirmed_days > self.before_days:
                reward = f"听歌天数：{self.before_days} → {obs.confirmed_days}"
            else:
                reward = "听歌天数暂无变化"
            if obs.remaining is not None:
                reward += f"；第 {obs.target_day} 天奖励还需看 {obs.remaining} 个"
            return Decision("success", f"第 {self.completed} 轮已看完，广告显示领取成功；{reward}")
        return Decision("wait", "等待页面更新")
