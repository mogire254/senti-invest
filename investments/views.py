from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from decimal import Decimal
from datetime import datetime, timedelta
from .models import UserProfile, Wallet, InvestmentProduct, UserInvestment, Deposit, Withdrawal, DailyEarningsLog, Referral, ReferralBonus, FraudLog
import random
import hashlib
import base64
import requests
import uuid
import json
import re

# ========== TEST ENDPOINT ==========
@api_view(['GET'])
def test_api(request):
    """Test endpoint to check if API is working"""
    return Response({
        'success': True,
        'message': 'API is working correctly!',
        'timestamp': datetime.now().isoformat()
    })

# ========== AUTHENTICATION FUNCTIONS ==========
@api_view(['POST'])
def signup(request):
    """User signup - requires admin approval with enhanced notification"""
    try:
        phone = request.data.get('phone_number')
        password = request.data.get('password')
        full_name = request.data.get('full_name', '')
        
        print("="*60)
        print(f"🔔 NEW USER REGISTRATION")
        print("="*60)
        print(f"📱 Phone: {phone}")
        print(f"👤 Name: {full_name if full_name else 'Not provided'}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        if not phone or not password:
            return Response({'error': 'Phone and password required'}, status=400)
        
        if UserProfile.objects.filter(phone_number=phone).exists():
            return Response({'error': 'Phone number already registered'}, status=400)
        
        if User.objects.filter(username=phone).exists():
            return Response({'error': 'User already exists'}, status=400)
        
        # Create user - NEVER as staff or superuser
        user = User.objects.create_user(
            username=phone, 
            password=password,
            is_staff=False,
            is_superuser=False
        )
        
        # Create profile (NOT approved yet)
        profile = UserProfile.objects.create(
            user=user,
            phone_number=phone,
            full_name=full_name,
            is_approved=False,
            account_status='pending_kyc'
        )
        
        # Create wallet
        wallet = Wallet.objects.create(user=user, balance=0.00)
        
        # Enhanced admin notification
        print("\n" + "="*60)
        print("⚠️ ADMIN ACTION REQUIRED!")
        print("="*60)
        print(f"New user needs approval:")
        print(f"   📱 Phone: {phone}")
        print(f"   👤 Name: {full_name if full_name else 'Not provided'}")
        print(f"   🆔 User ID: {user.id}")
        print(f"   📅 Registered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        print(f"🔗 Approve here: http://localhost:8000/admin/investments/userprofile/")
        print("="*60 + "\n")
        
        return Response({
            'success': True,
            'user_id': user.id,
            'message': 'Account created! Awaiting admin approval.'
        })
    except Exception as e:
        print(f"❌ Signup error: {str(e)}")
        return Response({'error': str(e)}, status=500)

# ========== FIXED LOGIN VIEW ==========
@api_view(['POST'])
def login_view(request):
    """User login - checks if user exists, approved, and account status"""
    try:
        phone = request.data.get('phone_number')
        password = request.data.get('password')
        
        print(f"=== LOGIN REQUEST ===")
        print(f"Phone: {phone}")
        
        if not phone or not password:
            return Response({'error': 'Phone and password required'}, status=400)
        
        # FIRST: Check if user exists in database
        try:
            user = User.objects.get(username=phone)
        except User.DoesNotExist:
            print(f"❌ User not found: {phone}")
            return Response({
                'error': 'Account not found. Please sign up first.',
                'code': 'USER_NOT_FOUND'
            }, status=404)
        
        # SECOND: Authenticate with password
        user = authenticate(username=phone, password=password)
        
        if not user:
            print(f"❌ Authentication failed for {phone}")
            return Response({
                'error': 'Invalid password. Please try again.',
                'code': 'INVALID_PASSWORD'
            }, status=401)
        
        # THIRD: Check if user is approved
        try:
            profile = UserProfile.objects.get(user=user)
            
            # Check account status
            if profile.account_status in ['banned', 'frozen']:
                print(f"🚫 User {phone} - Account {profile.account_status}")
                return Response({
                    'error': f'Your account is {profile.account_status}. Please contact admin for assistance.',
                    'account_status': profile.account_status,
                    'is_banned': profile.account_status == 'banned',
                    'is_frozen': profile.account_status == 'frozen',
                    'code': 'ACCOUNT_BLOCKED'
                }, status=403)
            
            if not profile.is_approved:
                print(f"⏳ User {phone} - PENDING APPROVAL")
                return Response({
                    'error': 'Account pending admin approval. Please wait.',
                    'pending_approval': True,
                    'code': 'PENDING_APPROVAL'
                }, status=403)
                
        except UserProfile.DoesNotExist:
            print(f"❌ Profile not found for {phone}")
            return Response({
                'error': 'Account setup incomplete. Please contact support.',
                'code': 'PROFILE_MISSING'
            }, status=404)
        
        # Get wallet
        try:
            wallet = Wallet.objects.get(user=user)
            balance = float(wallet.balance)
        except Wallet.DoesNotExist:
            wallet = Wallet.objects.create(user=user, balance=0.00)
            balance = 0.00
        
        print(f"✅ Login successful: {phone} (ID: {user.id})")
        
        return Response({
            'success': True,
            'user_id': user.id,
            'balance': balance,
            'account_status': profile.account_status,
            'message': f'Welcome back {profile.full_name or phone}!'
        })
        
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        return Response({'error': str(e)}, status=500)


# ========== DEPOSIT FUNCTIONS ==========
@api_view(['POST'])
def request_mpesa_deposit(request):
    """Initiate M-Pesa deposit - Requires admin approval with notification"""
    try:
        user_id = request.data.get('user_id')
        amount = request.data.get('amount')
        phone_number = request.data.get('phone_number', '')
        
        print("\n" + "="*60)
        print(f"💰 NEW DEPOSIT REQUEST")
        print("="*60)
        print(f"👤 User ID: {user_id}")
        print(f"💵 Amount: KES {amount}")
        print(f"📱 Phone: {phone_number}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Convert amount to Decimal
        if isinstance(amount, str):
            amount = Decimal(amount)
        else:
            amount = Decimal(amount)
        
        # Validation
        if not amount or amount < 520:
            return Response({'error': f'Minimum deposit is KES 520'}, status=400)
        
        if not phone_number:
            return Response({'error': 'Phone number is required'}, status=400)
        
        # Check if user exists and is approved
        try:
            user = User.objects.get(id=user_id)
            profile = UserProfile.objects.get(user=user)
            
            if not profile.is_approved:
                return Response({'error': 'Account not approved yet. Please wait for admin approval.'}, status=403)
            
            if profile.account_status in ['banned', 'frozen']:
                return Response({'error': f'Your account is {profile.account_status}. Cannot process deposit.'}, status=403)
                
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)
        
        # Format phone number
        if phone_number.startswith('0'):
            formatted_phone = '254' + phone_number[1:]
        elif phone_number.startswith('+'):
            formatted_phone = phone_number[1:]
        else:
            formatted_phone = phone_number
        
        # Generate unique transaction ID
        transaction_id = str(uuid.uuid4())[:8].upper()
        
        # Create deposit record (PENDING approval)
        deposit = Deposit.objects.create(
            user=user,
            amount=amount,
            transaction_id=transaction_id,
            phone_number=phone_number,
            status='pending',
            verification_status='pending'
        )
        
        # Enhanced admin notification
        print("\n" + "="*60)
        print("⚠️ ADMIN ACTION REQUIRED - DEPOSIT PENDING!")
        print("="*60)
        print(f"💰 Deposit Request:")
        print(f"   👤 User: {user.username} ({profile.full_name or 'No name'})")
        print(f"   💵 Amount: KES {amount:,.0f}")
        print(f"   📱 Phone: {phone_number}")
        print(f"   🆔 Transaction ID: {transaction_id}")
        print("="*60)
        print(f"🔗 Approve here: http://localhost:8000/admin/investments/deposit/")
        print("="*60 + "\n")
        
        return Response({
            'success': True,
            'message': f'Deposit request of KES {amount:,.0f} submitted for admin approval.',
            'transaction_id': transaction_id,
            'pending': True
        })
        
    except Exception as e:
        print(f"❌ Error in deposit: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
def verify_mpesa_payment(request):
    """Verify M-Pesa payment status"""
    transaction_id = request.data.get('transaction_id')
    
    try:
        deposit = Deposit.objects.get(transaction_id=transaction_id)
        return Response({
            'status': deposit.status,
            'verification_status': deposit.verification_status,
            'amount': float(deposit.amount),
            'message': 'Payment verified' if deposit.status == 'approved' else 'Payment pending approval'
        })
    except Deposit.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=404)


# ========== MANUAL PAYMENT VERIFICATION ==========
@api_view(['POST'])
def verify_manual_payment(request):
    """Verify manual M-Pesa payment by parsing the SMS message"""
    try:
        user_id = request.data.get('user_id')
        amount = request.data.get('amount')
        phone_number = request.data.get('phone_number', '')
        mpesa_message = request.data.get('mpesa_message', '')
        
        print("\n" + "="*60)
        print(f"📱 MANUAL PAYMENT VERIFICATION")
        print("="*60)
        print(f"👤 User ID: {user_id}")
        print(f"💵 Amount: KES {amount}")
        print(f"📱 Phone: {phone_number}")
        print(f"📝 Message: {mpesa_message[:100]}...")
        print("="*60)
        
        if not mpesa_message:
            return Response({'error': 'Please paste your M-Pesa message'}, status=400)
        
        # Check if user is banned or frozen
        try:
            profile = UserProfile.objects.get(user_id=user_id)
            if profile.account_status in ['banned', 'frozen']:
                return Response({
                    'error': f'Your account is {profile.account_status}. Please contact admin for assistance.'
                }, status=403)
        except UserProfile.DoesNotExist:
            pass
        
        # Extract transaction ID from message
        txn_match = re.search(r'^([A-Z0-9]+) Confirmed', mpesa_message)
        if not txn_match:
            return Response({'error': 'Could not find transaction ID in the message. Please paste the full M-Pesa confirmation message.'}, status=400)
        transaction_id = txn_match.group(1)
        
        # Check for duplicate transaction
        if Deposit.objects.filter(transaction_id=transaction_id).exists():
            return Response({'error': 'This transaction has already been used. Please check your deposit history.'}, status=400)
        
        # Extract amount from message
        amount_match = re.search(r'Ksh([\d,]+\.?\d*)', mpesa_message)
        if not amount_match:
            return Response({'error': 'Could not find amount in the message. Please paste the full M-Pesa confirmation message.'}, status=400)
        extracted_amount = Decimal(amount_match.group(1).replace(',', ''))
        
        # Use the amount from the message (not user input) for security
        amount = extracted_amount
        
        if amount < 520:
            return Response({'error': f'Minimum deposit is KES 520. You paid KES {amount}'}, status=400)
        
        # Create deposit record
        user = User.objects.get(id=user_id)
        deposit = Deposit.objects.create(
            user=user,
            amount=amount,
            transaction_id=transaction_id,
            phone_number=phone_number,
            mpesa_message=mpesa_message,
            verification_status='pending',
            status='pending'
        )
        
        # Add to wallet temporarily (pending verification)
        wallet, created = Wallet.objects.get_or_create(user=user)
        wallet.balance += amount
        wallet.save()
        
        # Create fraud log entry
        FraudLog.objects.create(
            user=user,
            action='deposit_verified',
            amount=amount,
            reason=f'Manual deposit via SMS verification. Transaction: {transaction_id}',
            performed_by='system'
        )
        
        print(f"✅ Manual payment recorded: {user.username} - KES {amount}")
        print(f"⚠️ Pending admin verification - Transaction ID: {transaction_id}")
        
        return Response({
            'success': True,
            'message': f'Payment of KES {amount:,.0f} recorded! Funds are available now. Admin will verify within 24-48 hours.',
            'new_balance': float(wallet.balance),
            'transaction_id': transaction_id,
            'pending_verification': True
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except Exception as e:
        print(f"❌ Manual payment error: {str(e)}")
        return Response({'error': str(e)}, status=500)


# ========== ACCOUNT STATUS FUNCTIONS ==========
@api_view(['GET'])
def check_account_status(request):
    """Check if user account is active, frozen, or banned"""
    user_id = request.GET.get('user_id')
    
    try:
        profile = UserProfile.objects.get(user_id=user_id)
        
        status_info = {
            'account_status': profile.account_status,
            'is_active': profile.account_status == 'active',
            'is_frozen': profile.account_status == 'frozen',
            'is_banned': profile.account_status == 'banned',
            'is_approved': profile.is_approved,
        }
        
        if profile.account_status in ['frozen', 'banned']:
            status_info['message'] = f'Your account is {profile.account_status}. Please contact admin for assistance.'
            status_info['contact'] = 'support@senti-earn.com'
        
        return Response(status_info)
        
    except UserProfile.DoesNotExist:
        return Response({'account_status': 'active', 'is_active': True, 'is_approved': False})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def request_unban(request):
    """Allow banned users to request account reinstatement"""
    try:
        user_id = request.data.get('user_id')
        reason = request.data.get('reason', '')
        
        user = User.objects.get(id=user_id)
        profile = UserProfile.objects.get(user=user)
        
        if profile.account_status != 'banned':
            return Response({'error': 'Your account is not banned'}, status=400)
        
        # Create notification for admin
        print("\n" + "="*60)
        print(f"📧 ACCOUNT UNBAN REQUEST")
        print("="*60)
        print(f"User: {user.username}")
        print(f"Phone: {profile.phone_number}")
        print(f"Reason: {reason}")
        print("="*60)
        print(f"🔗 Approve here: http://localhost:8000/admin/investments/userprofile/")
        print("="*60 + "\n")
        
        return Response({
            'success': True,
            'message': 'Your request has been sent to admin. They will contact you if approved.'
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except UserProfile.DoesNotExist:
        return Response({'error': 'Profile not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# ========== PRODUCT FUNCTIONS ==========
@api_view(['GET'])
def get_products(request):
    """Get all available investment products"""
    level = request.GET.get('level', None)
    products = InvestmentProduct.objects.filter(is_active=True)
    
    if level:
        products = products.filter(level=level)
    
    data = []
    for p in products:
        data.append({
            'id': p.id,
            'name': p.name,
            'level': p.level,
            'level_display': p.get_level_display(),
            'min_investment': float(p.min_investment),
            'max_investment': float(p.max_investment) if p.max_investment else None,
            'daily_earnings': float(p.daily_earnings_amount) if p.daily_earnings_amount else 0,
            'duration_days': p.duration_days,
            'description': p.description,
            'image_url': p.image_url
        })
    
    return Response({'products': data})

@api_view(['POST'])
def invest_product(request):
    """Invest in a product"""
    user_id = request.data.get('user_id')
    product_id = request.data.get('product_id')
    amount = Decimal(request.data.get('amount', 0))
    
    print("\n" + "="*60)
    print(f"📈 NEW INVESTMENT")
    print("="*60)
    print(f"👤 User ID: {user_id}")
    print(f"📦 Product ID: {product_id}")
    print(f"💵 Amount: KES {amount}")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        user = User.objects.get(id=user_id)
        product = InvestmentProduct.objects.get(id=product_id)
        wallet = Wallet.objects.get(user=user)
        
        # Check if user is banned or frozen
        profile = UserProfile.objects.get(user=user)
        if profile.account_status in ['banned', 'frozen']:
            return Response({'error': f'Your account is {profile.account_status}. Cannot make investments.'}, status=403)
            
    except Exception as e:
        return Response({'error': str(e)}, status=404)
    
    # Validate
    if amount < product.min_investment:
        return Response({'error': f'Minimum investment is KES {product.min_investment}'}, status=400)
    
    if product.max_investment and amount > product.max_investment:
        return Response({'error': f'Maximum investment is KES {product.max_investment}'}, status=400)
    
    if amount > wallet.balance:
        return Response({'error': 'Insufficient balance'}, status=400)
    
    # Deduct from wallet
    wallet.balance -= amount
    wallet.total_invested += amount
    wallet.save()
    
    # Create investment
    expiry = datetime.now() + timedelta(days=product.duration_days)
    investment = UserInvestment.objects.create(
        user=user,
        product=product,
        amount=amount,
        expiry_date=expiry,
        status='active'
    )
    
    print(f"✅ Investment successful! New balance: KES {wallet.balance:,.0f}")
    
    return Response({
        'success': True,
        'investment_id': investment.id,
        'new_balance': float(wallet.balance),
        'daily_earnings': float(product.daily_earnings_amount) if product.daily_earnings_amount else 0,
        'message': f'Successfully invested KES {amount:,.0f} in {product.name}'
    })

@api_view(['GET'])
def get_user_investments(request):
    """Get user's active investments"""
    user_id = request.GET.get('user_id')
    
    try:
        user = User.objects.get(id=user_id)
        investments = UserInvestment.objects.filter(user=user, status='active')
    except Exception:
        return Response({'error': 'User not found'}, status=404)
    
    data = []
    total_daily = Decimal('0')
    
    for inv in investments:
        daily = inv.calculate_daily_earnings()
        total_daily += daily
        days_left = (inv.expiry_date - datetime.now()).days
        
        data.append({
            'id': inv.id,
            'product_name': inv.product.name,
            'product_level': inv.product.get_level_display(),
            'amount': float(inv.amount),
            'daily_earnings': float(daily),
            'invested_at': inv.invested_at.strftime('%Y-%m-%d'),
            'expiry_date': inv.expiry_date.strftime('%Y-%m-%d'),
            'days_left': max(0, days_left),
            'total_earned': float(inv.total_earned)
        })
    
    return Response({
        'investments': data,
        'total_daily_earnings': float(total_daily),
        'count': len(data)
    })

# ========== WITHDRAWAL FUNCTIONS ==========
@api_view(['POST'])
def request_withdrawal(request):
    """Request a withdrawal with admin notification"""
    user_id = request.data.get('user_id')
    amount = Decimal(request.data.get('amount', 0))
    phone_number = request.data.get('phone_number')
    
    print("\n" + "="*60)
    print(f"💸 NEW WITHDRAWAL REQUEST")
    print("="*60)
    print(f"👤 User ID: {user_id}")
    print(f"💵 Amount: KES {amount}")
    print(f"📱 Phone: {phone_number}")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        wallet = Wallet.objects.get(user_id=user_id)
        user = User.objects.get(id=user_id)
        profile = UserProfile.objects.get(user=user)
        
        # Check if user is banned or frozen
        if profile.account_status in ['banned', 'frozen']:
            return Response({'error': f'Your account is {profile.account_status}. Cannot process withdrawals.'}, status=403)
            
    except Wallet.DoesNotExist:
        return Response({'error': 'Wallet not found'}, status=404)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except UserProfile.DoesNotExist:
        return Response({'error': 'Profile not found'}, status=404)
    
    if amount < 500:
        return Response({'error': 'Minimum withdrawal is KES 500'}, status=400)
    
    if amount > wallet.balance:
        return Response({'error': f'Insufficient balance. Available: KES {wallet.balance:,.0f}'}, status=400)
    
    withdrawal = Withdrawal.objects.create(
        user=user,
        amount=amount,
        phone_number=phone_number,
        status='pending'
    )
    
    # Enhanced admin notification
    print("\n" + "="*60)
    print("⚠️ ADMIN ACTION REQUIRED - WITHDRAWAL PENDING!")
    print("="*60)
    print(f"💸 Withdrawal Request:")
    print(f"   👤 User: {user.username} ({profile.full_name or 'No name'})")
    print(f"   💵 Amount: KES {amount:,.0f}")
    print(f"   📱 Phone: {phone_number}")
    print(f"   🆔 Withdrawal ID: {withdrawal.id}")
    print(f"   💰 Current Balance: KES {wallet.balance:,.0f}")
    print("="*60)
    print(f"🔗 Approve here: http://localhost:8000/admin/investments/withdrawal/")
    print("="*60 + "\n")
    
    return Response({
        'success': True,
        'withdrawal_id': withdrawal.id,
        'amount': float(amount),
        'message': 'Withdrawal request submitted for processing. Admin will review and approve within 8-12 hours.'
    })

@api_view(['GET'])
def get_wallet(request):
    """Get wallet details"""
    user_id = request.GET.get('user_id')
    
    try:
        wallet = Wallet.objects.get(user_id=user_id)
        return Response({
            'balance': float(wallet.balance),
            'total_deposited': float(wallet.total_deposited),
            'total_withdrawn': float(wallet.total_withdrawn),
            'total_earned': float(wallet.total_earned)
        })
    except:
        return Response({'error': 'Wallet not found'}, status=404)

# ========== DAILY EARNINGS API ==========
@api_view(['POST'])
def process_daily_earnings_api(request):
    """API endpoint to trigger daily earnings with logging"""
    print("\n" + "="*60)
    print(f"🔄 DAILY EARNINGS PROCESSING STARTED")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    active_investments = UserInvestment.objects.filter(status='active')
    total_earnings = Decimal('0')
    processed = 0
    users_affected = set()
    
    print(f"📊 Found {active_investments.count()} active investments")
    
    for investment in active_investments:
        # Check if we already processed today
        today = datetime.now().date()
        if investment.last_earning_date and investment.last_earning_date.date() == today:
            continue
        
        # Calculate daily earnings
        daily_earnings = investment.calculate_daily_earnings()
        
        if daily_earnings > 0:
            # Update investment total earned
            investment.total_earned += daily_earnings
            investment.last_earning_date = datetime.now()
            investment.save()
            
            # Add to user's wallet balance
            try:
                wallet = Wallet.objects.get(user=investment.user)
                wallet.balance += daily_earnings
                wallet.total_earned += daily_earnings
                wallet.save()
                
                total_earnings += daily_earnings
                processed += 1
                users_affected.add(investment.user.id)
                
                print(f"✅ {investment.user.username} earned KES {daily_earnings:,.2f} from {investment.product.name}")
                
            except Wallet.DoesNotExist:
                print(f"❌ No wallet found for {investment.user.username}")
        
        # Check if investment has expired
        if investment.expiry_date <= datetime.now():
            investment.status = 'completed'
            investment.save()
            print(f"🎉 Investment completed: {investment.product.name} for {investment.user.username}")
    
    # Create log entry
    log = DailyEarningsLog.objects.create(
        total_earnings=total_earnings,
        users_affected=len(users_affected),
        investments_processed=processed
    )
    
    print("\n" + "="*60)
    print("📊 DAILY EARNINGS SUMMARY")
    print("="*60)
    print(f"   ✅ Investments processed: {processed}")
    print(f"   👥 Users affected: {len(users_affected)}")
    print(f"   💰 Total earnings distributed: KES {total_earnings:,.2f}")
    print(f"   📝 Log ID: {log.id}")
    print("="*60)
    
    return Response({
        'success': True,
        'processed': processed,
        'total_earnings': float(total_earnings),
        'users_affected': len(users_affected),
        'message': f'Processed {processed} investments, distributed KES {total_earnings:,.0f} to {len(users_affected)} users'
    })

# ========== REFERRAL SYSTEM API ==========

@api_view(['POST'])
def track_referral(request):
    """Track when someone signs up using a referral link"""
    try:
        referrer_code = request.data.get('referral_code')
        referred_phone = request.data.get('phone_number')
        
        if not referrer_code:
            return Response({'success': True})
        
        try:
            referrer = User.objects.get(username=referrer_code)
        except User.DoesNotExist:
            return Response({'success': True})
        
        if referrer.username == referred_phone:
            return Response({'success': True})
        
        try:
            referred_user = User.objects.get(username=referred_phone)
        except User.DoesNotExist:
            return Response({'success': True})
        
        referral, created = Referral.objects.get_or_create(
            referrer=referrer,
            referred_user=referred_user
        )
        
        referral_count = Referral.objects.filter(referrer=referrer).count()
        
        print(f"📢 REFERRAL: {referrer.username} referred {referred_user.username} (Total: {referral_count})")
        
        return Response({
            'success': True, 
            'referral_count': referral_count,
            'is_new_referral': created
        })
        
    except Exception as e:
        print(f"Referral tracking error: {e}")
        return Response({'success': True})

@api_view(['GET'])
def get_referral_info(request):
    """Get user's referral link, stats, and bonuses"""
    user_id = request.GET.get('user_id')
    
    try:
        user = User.objects.get(id=user_id)
        
        referral_code = user.username
        referral_count = Referral.objects.filter(referrer=user).count()
        
        pending_bonuses = ReferralBonus.objects.filter(user=user, status='pending')
        claimed_bonuses = ReferralBonus.objects.filter(user=user, status='claimed')
        
        pending_total = sum(b.amount for b in pending_bonuses)
        claimed_total = sum(b.amount for b in claimed_bonuses)
        
        referral_link = f"https://senti-earn.netlify.app/signup?ref={referral_code}"
        
        try:
            referred_by = Referral.objects.get(referred_user=user)
            referrer_name = referred_by.referrer.username
        except Referral.DoesNotExist:
            referrer_name = None
        
        return Response({
            'success': True,
            'referral_code': referral_code,
            'referral_link': referral_link,
            'referral_count': referral_count,
            'referrer_name': referrer_name,
            'pending_bonuses': [{
                'id': b.id, 
                'amount': float(b.amount), 
                'referred_count': b.referred_count,
                'created_at': b.created_at.strftime('%Y-%m-%d')
            } for b in pending_bonuses],
            'claimed_bonuses': [{
                'id': b.id, 
                'amount': float(b.amount), 
                'claimed_at': b.claimed_at.strftime('%Y-%m-%d %H:%M') if b.claimed_at else 'N/A'
            } for b in claimed_bonuses],
            'pending_total': float(pending_total),
            'claimed_total': float(claimed_total)
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
def claim_bonus(request):
    """User claims a pending bonus (adds to wallet immediately)"""
    try:
        user_id = request.data.get('user_id')
        bonus_id = request.data.get('bonus_id')
        
        if not user_id or not bonus_id:
            return Response({'error': 'User ID and Bonus ID required'}, status=400)
        
        bonus = ReferralBonus.objects.get(id=bonus_id, user_id=user_id, status='pending')
        
        bonus.status = 'claimed'
        bonus.claimed_at = datetime.now()
        bonus.save()
        
        wallet, created = Wallet.objects.get_or_create(user_id=user_id)
        wallet.balance += bonus.amount
        wallet.save()
        
        print(f"🎁 BONUS CLAIMED: User {user_id} claimed KES {bonus.amount}")
        
        return Response({
            'success': True,
            'message': f'KES {bonus.amount:,.0f} added to your balance!',
            'new_balance': float(wallet.balance)
        })
        
    except ReferralBonus.DoesNotExist:
        return Response({'error': 'Bonus not found or already claimed'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)