import os
import django
import json
import re
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth.models import User
from investments.models import UserProfile, Wallet, Deposit, UserInvestment, InvestmentProduct

print("="*60)
print("📊 LOADING BACKUP DATA TO LOCAL SQLITE")
print("="*60)

# ========== HELPER FUNCTION ==========
def extract_number(text):
    """Extract number from string like 'KES 2,000' or '2000.00'"""
    if not text:
        return 0
    # Remove KES, commas, and other characters
    cleaned = re.sub(r'[^0-9.]', '', str(text))
    try:
        return float(cleaned) if cleaned else 0
    except:
        return 0

def extract_username(text):
    """Extract username from various formats"""
    if not text:
        return ''
    # If it contains KES, it's not a username
    if 'KES' in text:
        return ''
    # Clean up
    username = text.strip()
    # Remove emojis and extra text
    if '✅' in username or '❌' in username:
        # It might be a status, not a username
        return ''
    return username

# ========== CHECK FILES ==========
files_to_check = ['users_backup.json', 'wallets_backup.json', 'investments_backup.json']
for f in files_to_check:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
            print(f"✅ {f}: {len(data)} items found")
    except FileNotFoundError:
        print(f"❌ {f}: NOT FOUND!")
    except Exception as e:
        print(f"⚠️ {f}: Error - {e}")

print("\n" + "-"*60)

# ========== CLEAR EXISTING DATA ==========
print("\n🧹 Clearing existing data (keeping admin)...")

# Keep admin user
try:
    admin = User.objects.get(username='admin')
    print("  ✅ Keeping admin user")
except User.DoesNotExist:
    print("  ⚠️ No admin user found")

# Delete all other users
deleted = User.objects.exclude(username='admin').delete()
print(f"  ✅ Deleted non-admin users")

# ========== LOAD USERS ==========
print("\n📥 Loading users...")
try:
    with open('users_backup.json', 'r', encoding='utf-8') as f:
        users_data = json.load(f)
    
    count = 0
    for item in users_data:
        username = item.get('username', '').strip()
        if not username or username == '-':
            continue
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                password='password123'
            )
            
            # Get name parts
            full_name = item.get('full_name', '')
            if full_name and full_name != '-':
                name_parts = full_name.split()
                user.first_name = name_parts[0]
                if len(name_parts) > 1:
                    user.last_name = ' '.join(name_parts[1:])
                user.save()
            
            # Create profile
            UserProfile.objects.create(
                user=user,
                phone_number=username,
                full_name=full_name if full_name != '-' else '',
                is_approved='Approved' in item.get('approval', ''),
                account_status='active' if 'Active' in item.get('status', '') else 'pending_kyc'
            )
            
            # Create wallet
            balance = extract_number(item.get('balance', '0'))
            deposited = extract_number(item.get('deposited', '0'))
            earned = extract_number(item.get('total_earned', '0'))
            
            Wallet.objects.create(
                user=user,
                balance=balance,
                total_deposited=deposited,
                total_earned=earned,
                total_withdrawn=0,
                total_invested=0
            )
            
            count += 1
            if balance > 0:
                print(f"  ✅ {username}: KES {balance:,.0f}")
            else:
                print(f"  ✅ {username}")
                
        except Exception as e:
            print(f"  ❌ {username}: {e}")
    
    print(f"\n✅ Loaded {count} users with wallets")

except FileNotFoundError:
    print("  ❌ users_backup.json not found!")
except Exception as e:
    print(f"  ❌ Error: {e}")

# ========== LOAD WALLETS (if needed - but we already created wallets with users) ==========
print("\n📥 Checking wallets data...")
try:
    with open('wallets_backup.json', 'r', encoding='utf-8') as f:
        wallets_data = json.load(f)
    print(f"  ✅ Found {len(wallets_data)} wallets in backup")
    
    # Update existing wallets with any missing data
    updated = 0
    for item in wallets_data:
        # Skip empty entries
        user_text = item.get('user', '')
        if not user_text or user_text == 'KES 0':
            continue
        
        # Try to find user by extracting from text
        for user in User.objects.all():
            if user.username in user_text or user_text in user.username:
                try:
                    wallet = Wallet.objects.get(user=user)
                    # Only update if balance is 0 and we have data
                    if wallet.balance == 0:
                        balance = extract_number(item.get('balance', '0'))
                        deposited = extract_number(item.get('deposited', '0'))
                        earned = extract_number(item.get('total_earned', '0'))
                        if balance > 0 or deposited > 0 or earned > 0:
                            wallet.balance = balance
                            wallet.total_deposited = deposited
                            wallet.total_earned = earned
                            wallet.save()
                            updated += 1
                            print(f"  ✅ Updated {user.username}: KES {balance:,.0f}")
                    break
                except Wallet.DoesNotExist:
                    pass
    
    print(f"✅ Updated {updated} wallets")

except FileNotFoundError:
    print("  ⚠️ wallets_backup.json not found")
except Exception as e:
    print(f"  ❌ Error: {e}")

# ========== LOAD INVESTMENTS ==========
print("\n📥 Loading investments...")
try:
    with open('investments_backup.json', 'r', encoding='utf-8') as f:
        inv_data = json.load(f)
    
    print(f"  ✅ Found {len(inv_data)} investments in backup")
    
    # Get or create default product
    product, created = InvestmentProduct.objects.get_or_create(
        name='Default Investment',
        defaults={
            'min_investment': 100,
            'daily_earnings_amount': 10,
            'duration_days': 20,
            'is_active': True,
            'level': 'bronze'
        }
    )
    
    count = 0
    for item in inv_data:
        try:
            # Extract username from the user field
            user_text = item.get('user', '').strip()
            if not user_text:
                continue
            
            # Try to find the user
            found_user = None
            for u in User.objects.all():
                if u.username in user_text or user_text in u.username:
                    found_user = u
                    break
            
            if not found_user:
                continue
            
            # Extract amount
            amount = extract_number(item.get('amount', '0'))
            status = item.get('status', 'Active')
            total_earned = extract_number(item.get('total_earned', '0'))
            
            if amount > 0:
                inv = UserInvestment.objects.create(
                    user=found_user,
                    product=product,
                    amount=amount,
                    status='active' if 'Active' in status else 'completed',
                    total_earned=total_earned,
                    invested_at=datetime.now()
                )
                count += 1
                print(f"  ✅ {found_user.username}: KES {amount:,.0f} investment restored")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print(f"✅ Loaded {count} investments")

except FileNotFoundError:
    print("  ⚠️ investments_backup.json not found")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n" + "="*60)
print("✅ COMPLETE!")
print("="*60)

# ========== SUMMARY ==========
print("\n📊 FINAL SUMMARY:")
print(f"  Users: {User.objects.count()}")
print(f"  Wallets: {Wallet.objects.count()}")
print(f"  Investments: {UserInvestment.objects.count()}")

print("\n💰 Users with balances:")
for w in Wallet.objects.filter(balance__gt=0):
    print(f"  {w.user.username}: KES {w.balance:,.0f}")