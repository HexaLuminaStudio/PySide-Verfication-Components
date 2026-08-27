from src.components.slider import TrackPolicy, analyze_track


def test_irregular_human_like_track_is_accepted():
    track = [(0, 0.0), (12, 0.04), (35, 0.11), (61, 0.17), (92, 0.29)]
    assert analyze_track(track)["result"] is True


def test_short_track_is_rejected_once_with_stable_message_type():
    result = analyze_track([(0, 0.0), (30, 0.2)])
    assert result["result"] is False
    assert result["msg"] == ["滑动轨迹过短"]
    assert result["riskScore"] == 100
    assert result["metrics"]["sampleCount"] == 2


def test_perfectly_linear_generated_track_is_rejected():
    track = [(index * 10, index * 0.05) for index in range(8)]
    result = analyze_track(track)
    assert result["result"] is False
    assert result["riskScore"] >= TrackPolicy().risk_threshold
    assert "滑动轨迹过于规律" in result["signals"]


def test_policy_can_disable_linear_track_rule():
    track = [(index * 10, index * 0.05) for index in range(8)]
    policy = TrackPolicy(reject_perfect_linear_tracks=False, risk_threshold=101)
    assert analyze_track(track, policy)["result"] is True


def test_non_monotonic_timestamps_are_rejected():
    track = [(0, 0.0), (12, 0.08), (30, 0.07), (60, 0.2)]
    result = analyze_track(track)
    assert result["result"] is False
    assert result["msg"] == ["轨迹时间戳异常"]


def test_equal_event_loop_timestamps_are_coalesced():
    track = [
        (0, 4, 0.0),
        (8, 4, 0.0),
        (25, 6, 0.05),
        (52, 3, 0.13),
        (91, 7, 0.28),
    ]
    result = analyze_track(track)
    assert result["result"] is True
    assert result["metrics"]["sampleCount"] == 4
    assert result["metrics"]["duplicateTimestampCount"] == 1


def test_non_finite_track_data_is_rejected_without_crashing():
    track = [(0, 0.0), (12, 0.04), (35, float("nan")), (61, 0.17)]
    result = analyze_track(track)
    assert result["result"] is False
    assert result["msg"] == ["轨迹数据异常"]


def test_keyboard_track_keeps_accessible_path_available():
    track = [(index * 8, index * 0.05) for index in range(8)]
    result = analyze_track(track, input_method="keyboard")
    assert result["result"] is True
    assert result["riskScore"] == 0


def test_unrealistically_fast_pointer_track_is_rejected():
    track = [(0, 0, 0.0), (40, 1, 0.008), (95, -1, 0.018), (150, 2, 0.03)]
    result = analyze_track(track)
    assert result["result"] is False
    assert "完成速度过快" in result["signals"]
    assert "持续速度异常" in result["signals"]


def test_single_clock_jitter_speed_spike_does_not_reject_human_track():
    track = [
        (0, 3, 0.0),
        (16, 4, 0.001),
        (42, 2, 0.07),
        (78, 6, 0.17),
        (118, 3, 0.31),
    ]
    result = analyze_track(track)
    assert result["metrics"]["maxSpeed"] > TrackPolicy().max_pointer_speed
    assert result["metrics"]["highSpeedRatio"] < 0.5
    assert result["result"] is True
