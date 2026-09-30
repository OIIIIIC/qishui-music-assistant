from qishui.device import BUNDLE, Node
from qishui.flow import Flow
from qishui.vision import Observation, classify


def node(text, x=500, y=1200):
    return Node(text,"","",(x-30,y-15,x+30,y+15),BUNDLE,"OCR",True,True)


def entry(days):
    return Observation("entry",action=node("立即解锁"),confirmed_days=days)


def test_count_requires_ad_success_and_return_not_day_increment():
    f = Flow(2)
    assert f.step(entry(4)).kind == "begin"
    assert f.step(Observation("ad_playing")).kind == "watching"
    assert f.step(entry(4)).kind == "wait"  # returning early is not a completed ad
    assert f.completed == 0
    done = Observation("ad_done",close=node("关闭"))
    assert f.step(done).kind == "wait"
    assert f.step(done).kind == "click"
    assert f.step(done).kind == "wait"  # no repeated close click
    result = f.step(entry(4))
    assert result.kind == "success"
    assert '暂无变化' in result.message  # don't claim that listening time was awarded
    assert f.completed == 1
    assert f.step(entry(5)).kind == "begin"  # new round, not duplicate success
    assert f.completed == 1


def test_target_stops_before_next_ad():
    f = Flow(1)
    f.step(entry(4))
    done = Observation("ad_done",close=node("关闭"))
    f.step(done)
    f.step(done)
    f.step(done)
    f.step(entry(5))
    assert f.step(entry(5)).kind == "finish"


def test_unknown_and_existing_ad_do_not_click():
    f = Flow(10)
    assert f.step(Observation()).kind == "wait"
    assert f.step(Observation("ad_done",close=node("关闭"))).kind == "pause"
    assert f.completed == 0


def test_retention_only_exits_after_our_confirmed_close():
    f = Flow(1)
    f.step(entry(4))
    assert f.step(Observation("retention",action=node("坚持退出"))).kind == "pause"


def test_ad_creative_success_text_is_not_reward():
    o = classify([node("反馈",720,150),node("领取成功",850,1500)],1084,2412)
    assert o.page != "ad_done"


def test_retention_overrides_dimmed_success_label():
    o = classify([node("反馈",720,150),node("领取成功×",950,150),
                  node("再看1个视频提前得",540,990),node("坚持退出",540,1440)],1084,2412)
    assert o.page == "retention"


def test_observed_reward_panel_and_payment_buttons():
    o = classify([node("再看1个提前享第5天畅听",540,1640),
                  node("恭喜获得第4天免费时长畅听",540,1730),
                  node("立即解锁第5天畅听",540,2280)],1084,2412)
    assert o.page == "entry" and o.confirmed_days == 4
    assert classify([node("4.8元开通",540,2200)],1084,2412).action is None


def test_feedback_can_shift_left_when_countdown_is_long():
    o = classify([node("反馈",560,150),node("04秒后可领取奖励×",850,150)],1084,2412)
    assert o.page == "ad_playing"


def test_success_needs_consecutive_observations():
    f=Flow(1)
    f.step(entry(4))
    f.step(Observation('ad_playing'))
    done=Observation('ad_done',close=node('关闭'))
    assert f.step(done).kind=='wait'
    f.step(Observation())
    assert f.step(done).kind=='wait'
    assert f.step(done).kind=='click'


def test_reward_increase_is_recorded_separately():
    f=Flow(1)
    f.step(entry(4))
    f.step(Observation('ad_playing'))
    done=Observation('ad_done',close=node('关闭'))
    f.step(done)
    f.step(done)
    assert '4 → 5' in f.step(entry(5)).message


def test_home_badge_launches_tracked_ad():
    f=Flow(1)
    assert f.step(Observation('home',action=node('5天'),confirmed_days=5)).kind=='begin'
    assert f.step(Observation('ad_playing')).kind=='watching'


def test_three_ad_panel_chooses_unlock_not_membership():
    o=classify([node('再看3个提前享第7天畅听',540,1640),
                node('恭喜获得第6天免费时长畅听',540,1730),
                node('4.8元开会员',260,2280),node('解锁第7天畅听',800,2280)],1084,2412)
    assert o.page=='entry'
    assert o.action.text=='解锁第7天畅听'
    assert (o.confirmed_days,o.remaining,o.target_day)==(6,3,7)
