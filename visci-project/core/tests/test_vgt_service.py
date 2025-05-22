import pytest
from core.services import vgt_service
from core.models import Vault, Transaction, UserProfile, PendingTransaction
from django.contrib.auth.models import User
from django.db import IntegrityError

def test_dummy():
    assert True

@pytest.fixture
def user():
    return User.objects.create_user(username='testuser', password='testpassword', email='test@example.com')

@pytest.fixture
def user_profile(user):
    return UserProfile.objects.create(user=user)

@pytest.fixture
def vault():
    return vgt_service.create_vault(initial_gold=100.00)

@pytest.mark.django_db
def test_create_vault():
    vault = vgt_service.create_vault(initial_gold=50.00)
    assert Vault.objects.count() == 1
    assert vault.vgt_balance == 50.00
    assert Transaction.objects.count() == 1
    transaction = Transaction.objects.first()
    assert transaction.transaction_type == 'MINT'
    assert transaction.vgt_amount == 50.00
    assert transaction.notes == 'Initial deposit'

@pytest.mark.django_db
def test_create_vault_with_serial_number():
    serial_number = "test_serial"
    vault = vgt_service.create_vault(initial_gold=50.00, serial_number=serial_number)
    assert Vault.objects.count() == 1
    assert vault.serial_number == serial_number

@pytest.mark.django_db
def test_add_vgt_to_vault(vault):
    vgt_service.add_vgt_to_vault(vault, amount=25.00, description='Test deposit')
    vault.refresh_from_db()
    assert vault.vgt_balance == 125.00
    assert Transaction.objects.count() == 2
    transaction = Transaction.objects.last()
    assert transaction.transaction_type == 'VAULT_DEPOSIT'
    assert transaction.vgt_amount == 25.00
    assert transaction.notes == 'Test deposit'

@pytest.mark.django_db
def test_remove_vgt_from_vault(vault):
    vgt_service.remove_vgt_from_vault(vault, amount=25.00, description='Test withdrawal')
    vault.refresh_from_db()
    assert vault.vgt_balance == 75.00
    assert Transaction.objects.count() == 2
    transaction = Transaction.objects.last()
    assert transaction.transaction_type == 'VAULT_WITHDRAWAL'
    assert transaction.vgt_amount == -25.00
    assert transaction.notes == 'Test withdrawal'

@pytest.mark.django_db
def test_remove_vgt_from_vault_insufficient_funds(vault):
    with pytest.raises(Exception, match="Insufficient gold in vault."):
        vgt_service.remove_vgt_from_vault(vault, amount=150.00)

@pytest.mark.django_db
def test_get_vault_balance(vault):
    # vgt_service.add_vgt_to_vault(vault, amount=25.00)
    vault.save()
    balance = vgt_service.get_vault_balance(vault)
    assert balance == 100.00

@pytest.mark.django_db
def test_user_buy_vgt(user, user_profile, vault):
    user_profile.is_active = True
    user_profile.save()
    
    initial_vault_balance = vault.vgt_balance
    
    result = vgt_service.user_buy_vgt(vault, user, amount=20.00)
    
    assert result is False #vault is not READY
    
    vault.status = 'READY'
    vault.save()
    
    result = vgt_service.user_buy_vgt(vault, user, amount=20.00)
    
    assert result is True
    user_profile.refresh_from_db()
    vault.refresh_from_db()
    assert user_profile.vgt_balance == 20.00
    assert vault.vgt_balance == initial_vault_balance - 20.00
    assert Transaction.objects.count() == 2
    transaction = Transaction.objects.last()
    assert transaction.transaction_type == 'BUY'
    assert transaction.vgt_amount == 20.00
    assert transaction.notes == 'User purchases 20.0 VGT'

@pytest.mark.django_db
def test_user_buy_vgt_inactive_profile(user, user_profile, vault):
    vault.status = 'READY'
    vault.save()
    user_profile.is_active = False
    user_profile.save()
    result = vgt_service.user_buy_vgt(vault, user, amount=20.00)
    assert result is False

@pytest.mark.django_db
def test_user_buy_vgt_insufficient_vault_balance(user, user_profile, vault):
    vault.status = 'READY'
    vault.save()
    result = vgt_service.user_buy_vgt(vault, user, amount=200.00)
    assert result is False

@pytest.mark.django_db
def test_user_send_vgt(user, user_profile):
    target_user = User.objects.create_user(username='targetuser', password='testpassword', email='target@example.com')
    target_profile = UserProfile.objects.create(user=target_user)
    user_profile.vgt_balance = 50.00
    user_profile.save()
    
    result = vgt_service.user_send_vgt(user, 'target@example.com', amount=20.00)
    
    user_profile.refresh_from_db()
    target_profile.refresh_from_db()

    assert result is True
    assert user_profile.vgt_balance == 30.00
    assert target_profile.vgt_balance == 20.00
    assert Transaction.objects.count() == 1
    transaction = Transaction.objects.last()
    assert transaction.transaction_type == 'GIFT_SENT'
    assert transaction.vgt_amount == 20.00
    assert transaction.notes == 'User sends 20.0 VGT to target@example.com'

@pytest.mark.django_db
def test_user_send_vgt_insufficient_balance(user, user_profile):
    with pytest.raises(Exception, match="Insufficient balance to send VGT."):
        vgt_service.user_send_vgt(user, 'target@example.com', amount=100.00)

@pytest.mark.django_db
def test_user_send_vgt_target_user_does_not_exist(user, user_profile):
    user_profile.vgt_balance = 50.00
    user_profile.save()
    
    result = vgt_service.user_send_vgt(user, 'target@example.com', amount=20.00)
    
    assert result is True
    assert PendingTransaction.objects.count() == 1
    pending_transaction = PendingTransaction.objects.first()
    assert pending_transaction.actor == user
    assert pending_transaction.target_email == 'target@example.com'
    assert pending_transaction.vgt_amount == 20.00
    assert pending_transaction.notes == 'User sends 20.0 VGT to target@example.com'
    user_profile.refresh_from_db()
    assert user_profile.vgt_balance == 30.00

@pytest.mark.django_db
def test_user_redeem_vgt(user, user_profile):
    user_profile.vgt_balance = 50.00
    user_profile.save()
    
    result = vgt_service.user_redeem_vgt(user, amount=20.00)
    
    assert result is True
    user_profile.refresh_from_db()
    assert user_profile.vgt_balance == 30.00
    assert Transaction.objects.count() == 1
    transaction = Transaction.objects.last()
    assert transaction.transaction_type == 'REDEEM'
    assert transaction.vgt_amount == -20.00
    assert transaction.notes == 'User redeems 20.0 VGT'

@pytest.mark.django_db
def test_user_redeem_vgt_insufficient_balance(user, user_profile):
    user_profile.vgt_balance = 10.00
    user_profile.save()
    
    result = vgt_service.user_redeem_vgt(user, amount=20.00)
    
    assert result is False
    user_profile.refresh_from_db()
    assert user_profile.vgt_balance == 10.00
    assert Transaction.objects.count() == 0