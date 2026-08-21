import unittest

from app.features.payments.service import PaymentService


class PaymentQuotaUpgradeTests(unittest.TestCase):
    def test_quota_upgrade_closes_active_allocation(self):
        sql = PaymentService.close_active_quota_sql()
        self.assertIn("update public.quota_allocations", sql)
        self.assertIn("set ends_at = timezone('utc', now())", sql)
        self.assertIn("ends_at is null or ends_at > timezone('utc', now())", sql)

    def test_free_to_paid_charges_full_price(self):
        self.assertEqual(PaymentService.calculate_upgrade_amount(0, 29900), 29900)

    def test_paid_upgrade_charges_only_difference(self):
        self.assertEqual(PaymentService.calculate_upgrade_amount(29900, 59900), 30000)

    def test_paid_upgrade_to_higher_plan_charges_difference(self):
        self.assertEqual(PaymentService.calculate_upgrade_amount(59900, 199900), 140000)

    def test_same_or_lower_plan_is_rejected(self):
        with self.assertRaises(ValueError):
            PaymentService.calculate_upgrade_amount(59900, 59900)
        with self.assertRaises(ValueError):
            PaymentService.calculate_upgrade_amount(59900, 29900)


if __name__ == "__main__":
    unittest.main()
