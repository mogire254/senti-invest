from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from decimal import Decimal
from datetime import datetime, timedelta
from .models import UserProfile, Wallet, InvestmentProduct, UserInvestment, Deposit, Withdrawal, DailyEarningsLog
import random
import hashlib
import base64
import requests
import uuid
import json

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
        
        # Create user
        user = User.objects.create_user(username=phone, password=password)
        
        # Create profile (NOT approved yet)
        profile = UserProfile.objects.create(
            user=user,
            phone_number=phone,
            full_name=full_name,
            is_approved=False
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

@api_view(['POST'])
def login_view(request):
    """User login - checks if approved"""
    try:
        phone = request.data.get('phone_number')
        password = request.data.get('password')
        
        print(f"=== LOGIN REQUEST ===")
        print(f"Phone: {phone}")
        
        if not phone or not password:
            return Response({'error': 'Phone and password required'}, status=400)
        
        user = authenticate(username=phone, password=password)
        
        if not user:
            print(f"❌ Authentication failed for {phone}")
            return Response({'error': 'Invalid phone number or password'}, status=401)
        
        # Check if user is approved
        try:
            profile = UserProfile.objects.get(user=user)
            if not profile.is_approved:
                print(f"⏳ User {phone} - PENDING APPROVAL")
                return Response({
                    'error': 'Account pending admin approval. Please wait.',
                    'pending_approval': True
                }, status=403)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)
        
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
            status='pending'
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
            'amount': float(deposit.amount),
            'message': 'Payment verified' if deposit.status == 'approved' else 'Payment pending approval'
        })
    except Deposit.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=404)

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