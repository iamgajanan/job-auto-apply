import unittest

from app.features.payments.service import PaymentService


class PaymentQuotaUpgradeTests(unittest.TestCase):
    def test_quota_upgrade_replaces_previous_allocation(self):
        sql = PaymentService.quota_upgrade_sql()
        self.assertIn("update public.quota_allocations", sql)
        self.assertIn("ends_at = timezone('utc', now())", sql)
        self.assertIn("insert into public.quota_allocations", sql)
        self.assertNotIn("sum(granted_searches", sql)


if __name__ == "__main__":
    unittest.main()
