from src.components.slider import TrackPolicy, analyze_track


def test_irregular_human_like_track_is_accepted():
    track = [(0, 0.0), (12, 0.04), (35, 0.11), (61, 0.17), (92, 0.29)]
    assert analyze_track(track)["result"] is True


def test_short_track_is_rejected_once_with_stable_message_type():
    result = analyze_track([(0, 0.0), (30, 0.2)])
    assert result == {"result": False, "msg": ["滑动轨迹过短"]}


def test_perfectly_linear_generated_track_is_rejected():
    track = [(index * 10, index * 0.05) for index in range(8)]
    result = analyze_track(track)
    assert result["result"] is False
    assert result["msg"] == ["滑动轨迹过于规律"]


def test_policy_can_disable_linear_track_rule():
    track = [(index * 10, index * 0.05) for index in range(8)]
    policy = TrackPolicy(reject_perfect_linear_tracks=False)
    assert analyze_track(track, policy)["result"] is True
