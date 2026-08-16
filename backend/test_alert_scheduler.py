from datetime import datetime
from zoneinfo import ZoneInfo

from app.features.saved_searches.alert_scheduler import next_run_at


IST = ZoneInfo("Asia/Kolkata")


def test_daily_schedule_moves_to_next_day_after_9am():
    now = datetime(2026, 8, 16, 10, 0, tzinfo=IST)
    result = next_run_at("daily", now)
    assert result.astimezone(IST) == datetime(2026, 8, 17, 9, 0, tzinfo=IST)


def test_daily_schedule_uses_same_day_before_9am():
    now = datetime(2026, 8, 16, 8, 30, tzinfo=IST)
    result = next_run_at("daily", now)
    assert result.astimezone(IST) == datetime(2026, 8, 16, 9, 0, tzinfo=IST)


def test_weekly_schedule_targets_next_monday():
    # Sunday morning should schedule the following Monday at 09:00 IST.
    now = datetime(2026, 8, 16, 8, 30, tzinfo=IST)
    result = next_run_at("weekly", now)
    assert result.astimezone(IST) == datetime(2026, 8, 17, 9, 0, tzinfo=IST)


def test_invalid_frequency_is_rejected():
    try:
        next_run_at("monthly", datetime(2026, 8, 16, 8, 30, tzinfo=IST))
    except ValueError:
        return
    raise AssertionError("Unsupported frequency should raise ValueError")
