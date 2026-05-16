import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth.models import User
from investments.models import UserProfile, Wallet

def create_permanent_superuser():
    """Create a permanent superuser account"""
    
    # Superuser credentials - YOU CAN CHANGE THESE
    SUPERUSER_PHONE = "admin@sentiinvest.com"  # Login username
    SUPERUSER_PASSWORD = "SentiAdmin2024!"  # Strong password
    SUPERUSER_NAME = "Senti Invest Admin"
    SUPERUSER_EMAIL = "admin@sentiinvest.com"
    
    # Check if superuser already exists
    if User.objects.filter(username=SUPERUSER_PHONE).exists():
        print("⚠️ Superuser already exists!")
        user = User.objects.get(username=SUPERUSER_PHONE)
        print(f"📱 Username: {user.username}")
        print(f"🔐 Password: {SUPERUSER_PASSWORD} (if you haven't changed it)")
        return
    
    # Create superuser
    user = User.objects.create_superuser(
        username=SUPERUSER_PHONE,
        email=SUPERUSER_EMAIL,
        password=SUPERUSER_PASSWORD
    )
    
    # Create profile for superuser
    profile = UserProfile.objects.create(
        user=user,
        phone_number=SUPERUSER_PHONE,
        full_name=SUPERUSER_NAME,
        is_approved=True,
        is_kyc_verified=True
    )
    
    # Create wallet for superuser
    wallet = Wallet.objects.create(
        user=user,
        balance=0,
        total_deposited=0,
        total_withdrawn=0,
        total_earned=0
    )
    
    print("="*60)
    print("✅ PERMANENT SUPERUSER CREATED SUCCESSFULLY!")
    print("="*60)
    print(f"📱 Username: {SUPERUSER_PHONE}")
    print(f"🔐 Password: {SUPERUSER_PASSWORD}")
    print(f"👤 Name: {SUPERUSER_NAME}")
    print(f"📧 Email: {SUPERUSER_EMAIL}")
    print("="*60)
    print("🔐 You can now login to admin panel anytime at:")
    print("   http://localhost:8000/admin")
    print("="*60)

if __name__ == '__main__':
    create_permanent_superuser()