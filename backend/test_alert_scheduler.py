import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.features.saved_searches.alert_scheduler import next_run_at


IST = ZoneInfo("Asia/Kolkata")


class AlertSchedulerTests(unittest.TestCase):
    def test_daily_schedule_moves_to_next_day_after_9am(self):
        now = datetime(2026, 8, 16, 10, 0, tzinfo=IST)
        result = next_run_at("daily", now)
        self.assertEqual(result.astimezone(IST), datetime(2026, 8, 17, 9, 0, tzinfo=IST))

    def test_daily_schedule_uses_same_day_before_9am(self):
        now = datetime(2026, 8, 16, 8, 30, tzinfo=IST)
        result = next_run_at("daily", now)
        self.assertEqual(result.astimezone(IST), datetime(2026, 8, 16, 9, 0, tzinfo=IST))

    def test_weekly_schedule_targets_next_monday(self):
        now = datetime(2026, 8, 16, 8, 30, tzinfo=IST)
        result = next_run_at("weekly", now)
        self.assertEqual(result.astimezone(IST), datetime(2026, 8, 17, 9, 0, tzinfo=IST))

    def test_invalid_frequency_is_rejected(self):
        with self.assertRaises(ValueError):
            next_run_at("monthly", datetime(2026, 8, 16, 8, 30, tzinfo=IST))


if __name__ == "__main__":
    unittest.main()
