import pytest
from datetime import time, datetime
from zoneinfo import ZoneInfo
from kp_gateway_selector.gateway_selector.matchers.time_window import (
    _parse_hms,
    _parse_days,
    make_time_window,
    TimeWindow,
)


@pytest.fixture
def tz():
    return ZoneInfo("America/Sao_Paulo")


def test_parse_hms_valid(tz):
    assert _parse_hms("09:30", tz) == time(9, 30, tzinfo=tz)
    assert _parse_hms("23:59:59", tz) == time(23, 59, 59, tzinfo=tz)


def test_parse_hms_invalid_format(tz):
    with pytest.raises(ValueError, match="formato de hora inválido"):
        _parse_hms("9", tz)


def test_parse_hms_out_of_range(tz):
    with pytest.raises(ValueError, match="valores de hora/minuto/segundo fuera de rango"):
        _parse_hms("24:00", tz)


def test_parse_days_valid():
    assert _parse_days(["mon", "tuesday"]) == frozenset([0, 1])


def test_parse_days_invalid():
    with pytest.raises(ValueError, match="día inválido"):
        _parse_days(["invalid_day"])


def test_make_time_window_valid(tz):
    cond = {"type": "TIME_WINDOW", "tz": "America/Sao_Paulo", "start": "09:00", "end": "18:00"}
    matcher = make_time_window(cond)
    assert isinstance(matcher, TimeWindow)
    assert matcher.tz == tz


def test_make_time_window_with_days(tz):
    cond = {
        "type": "TIME_WINDOW",
        "tz": "America/Sao_Paulo",
        "start": "09:00",
        "end": "18:00",
        "days_of_week": ["mon", "fri"],
    }
    matcher = make_time_window(cond)
    assert isinstance(matcher, TimeWindow)
    assert matcher.days_of_week == frozenset([0, 4])

def test_make_time_window_missing_tz():
    with pytest.raises(ValueError, match="'tz' es obligatorio"):
        make_time_window({"start": "09:00", "end": "18:00"})


def test_make_time_window_missing_start_end():
    with pytest.raises(ValueError, match="'start' y 'end' deben ser strings"):
        make_time_window({"tz": "UTC"})


def test_make_time_window_invalid_days_of_week():
    with pytest.raises(ValueError, match="'days_of_week' debe ser lista"):
        make_time_window({"tz": "UTC", "start": "09:00", "end": "18:00", "days_of_week": "not-a-list"})


def test_time_window_daytime_inside(tz):
    matcher = TimeWindow(tz, time(9, 0, tzinfo=tz), time(18, 0, tzinfo=tz))
    ctx = {"now": datetime(2023, 1, 1, 10, 0, tzinfo=tz)}
    assert matcher(ctx) is True


def test_time_window_daytime_outside(tz):
    matcher = TimeWindow(tz, time(9, 0, tzinfo=tz), time(18, 0, tzinfo=tz))
    ctx = {"now": datetime(2023, 1, 1, 8, 0, tzinfo=tz)}
    assert matcher(ctx) is False


def test_time_window_overnight_inside(tz):
    matcher = TimeWindow(tz, time(22, 0, tzinfo=tz), time(6, 0, tzinfo=tz))
    ctx = {"now": datetime(2023, 1, 1, 23, 0, tzinfo=tz)}
    assert matcher(ctx) is True
    ctx = {"now": datetime(2023, 1, 1, 5, 0, tzinfo=tz)}
    assert matcher(ctx) is True


def test_time_window_overnight_outside(tz):
    matcher = TimeWindow(tz, time(22, 0, tzinfo=tz), time(6, 0, tzinfo=tz))
    ctx = {"now": datetime(2023, 1, 1, 21, 0, tzinfo=tz)}
    assert matcher(ctx) is False


def test_time_window_with_days_of_week_match(tz):
    # Monday is 0
    matcher = TimeWindow(tz, time(9, 0, tzinfo=tz), time(18, 0, tzinfo=tz), days_of_week=frozenset([0]))
    ctx = {"now": datetime(2023, 1, 2, 10, 0, tzinfo=tz)} # 2023-01-02 is a Monday
    assert matcher(ctx) is True


def test_time_window_with_days_of_week_no_match(tz):
    # Tuesday is 1
    matcher = TimeWindow(tz, time(9, 0, tzinfo=tz), time(18, 0, tzinfo=tz), days_of_week=frozenset([1]))
    ctx = {"now": datetime(2023, 1, 2, 10, 0, tzinfo=tz)} # 2023-01-02 is a Monday
    assert matcher(ctx) is False


def test_time_window_no_now_in_ctx(tz, monkeypatch):
    class MockDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2023, 1, 1, 10, 0, tzinfo=tz)
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.time_window.datetime", MockDateTime)
    matcher = TimeWindow(tz, time(9, 0, tzinfo=tz), time(18, 0, tzinfo=tz))
    assert matcher({}) is True


def test_time_window_now_naive_tz(tz):
    matcher = TimeWindow(tz, time(9, 0, tzinfo=tz), time(18, 0, tzinfo=tz))
    ctx = {"now": datetime(2023, 1, 1, 10, 0)}
    assert matcher(ctx) is True

def test_time_window_name_property(tz):
    """
    Tests the name property of the TimeWindow matcher.
    """
    matcher = TimeWindow(tz, time(9, 0, tzinfo=tz), time(18, 0, tzinfo=tz))
    assert matcher.name == "TIME_WINDOW"

def test_time_window_str_representation(tz):
    """
    Tests the __str__ representation of the TimeWindow matcher.
    """
    matcher = TimeWindow(tz, time(9, 0, tzinfo=tz), time(18, 0, tzinfo=tz), days_of_week=frozenset([0, 1]))
    expected_str = f"TIME_WINDOW(tz={tz}, start={time(9, 0, tzinfo=tz)}, end={time(18, 0, tzinfo=tz)}, days_of_week={frozenset([0, 1])})"
    assert str(matcher) == expected_str