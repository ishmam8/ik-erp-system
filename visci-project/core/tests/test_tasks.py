from datetime import timedelta
from django.test import TestCase
from django.utils.timezone import now
from django.conf import settings
from visci.core.models import PendingTransaction, UserProfile, Transaction
from visci.core.tasks import check_expiry

# C O P I L O T E S T
# needs to be verified

class CheckExpiryTestCase(TestCase):
    def setUp(self):
        # Create a user and their profile
        self.user = settings.AUTH_USER_MODEL.objects.create_user(username="testuser", email="testuser@example.com", password="password")
        self.user_profile = UserProfile.objects.create(user=self.user, vgt_balance=100.00)

        # Create a pending transaction that is expired
        self.expired_transaction = PendingTransaction.objects.create(
            actor=self.user,
            target_email="recipient@example.com",
            vgt_amount=50.00,
            created_at=now() - timedelta(days=31),  # Expired by 1 day
            is_claimed=False,
        )

        # Create a pending transaction that is not expired
        self.valid_transaction = PendingTransaction.objects.create(
            actor=self.user,
            target_email="recipient2@example.com",
            vgt_amount=30.00,
            created_at=now() - timedelta(days=10),  # Not expired
            is_claimed=False,
        )

    def test_check_expiry(self):
        # Run the check_expiry function
        check_expiry()

        # Refresh user profile and check balance
        self.user_profile.refresh_from_db()
        self.assertEqual(self.user_profile.vgt_balance, 150.00)  # Balance should increase by 50.00

        # Check that the expired transaction is deleted
        self.assertFalse(PendingTransaction.objects.filter(id=self.expired_transaction.id).exists())

        # Check that the valid transaction is still present
        self.assertTrue(PendingTransaction.objects.filter(id=self.valid_transaction.id).exists())

        # Check that a new transaction is created
        transaction = Transaction.objects.get(transaction_type="GIFT_SEND_BACK")
        self.assertEqual(transaction.actor, self.user)
        self.assertEqual(transaction.vgt_amount, 50.00)
        self.assertEqual(
            transaction.notes,
            f"Pending transaction expired. Amount returned to {self.user.email}",
        )