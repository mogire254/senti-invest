from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db import models
from django.db.models import Count, Q, Sum
from decimal import Decimal
from datetime import datetime, timedelta
from .models import UserProfile, Wallet, InvestmentProduct, UserInvestment, Deposit, Withdrawal, DailyEarningsLog, Referral, ReferralBonus, FraudLog, PasswordReset, BalanceAdjustmentLog, MaintenanceMode
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
import random
import hashlib
import base64
import requests
import uuid
import json
import re

# ========== MAINTENANCE MODE HELPER ==========
def check_maintenance():
    """Check if maintenance mode is enabled"""
    try:
        maintenance = MaintenanceMode.objects.first()
        if maintenance and maintenance.is_enabled:
            return maintenance.message
    except:
        pass
    return None

# ========== TEST ENDPOINT ==========
@api_view(['GET'])
def test_api(request):
    """Test endpoint to check if API is working"""
    return Response({
        'success': True,
        'message': 'API is working correctly!',
        'timestamp': datetime.now().isoformat()
    })

# ========== MAINTENANCE STATUS ENDPOINT ==========
@api_view(['GET'])
def check_maintenance_status(request):
    """Check if system is in maintenance mode"""
    maint_msg = check_maintenance()
    return Response({
        'maintenance': maint_msg is not None,
        'message': maint_msg or ''
    })

# ========== AUTHENTICATION FUNCTIONS ==========
@api_view(['POST'])
def signup(request):
    """User signup - requires admin approval with referral tracking"""
    try:
        # Maintenance check
        maint_msg = check_maintenance()
        if maint_msg:
            return Response({
                'error': maint_msg,
                'maintenance': True,
                'code': 'MAINTENANCE_MODE'
            }, status=503)
        
        phone = request.data.get('phone_number')
        password = request.data.get('password')
        full_name = request.data.get('full_name', '')
        referral_code_param = request.data.get('referral_code', '')
        
        print("="*60)
        print(f"🔔 NEW USER REGISTRATION")
        print("="*60)
        print(f"📱 Phone: {phone}")
        print(f"👤 Name: {full_name if full_name else 'Not provided'}")
        if referral_code_param:
            print(f"🔗 Referred by code: {referral_code_param}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        if not phone or not password:
            return Response({'error': 'Phone and password required'}, status=400)
        
        if UserProfile.objects.filter(phone_number=phone).exists():
            return Response({'error': 'Phone number already registered'}, status=400)
        
        if User.objects.filter(username=phone).exists():
            return Response({'error': 'User already exists'}, status=400)
        
        user = User.objects.create_user(
            username=phone, 
            password=password,
            is_staff=False,
            is_superuser=False
        )
        
        profile = UserProfile.objects.create(
            user=user,
            phone_number=phone,
            full_name=full_name,
            is_approved=False,
            account_status='pending_kyc'
        )
        
        profile.generate_referral_code()
        profile.save()
        
        if referral_code_param:
            try:
                referrer_profile = UserProfile.objects.get(referral_code=referral_code_param)
                profile.referred_by = referrer_profile
                profile.save()
                
                Referral.objects.get_or_create(
                    referrer=referrer_profile.user,
                    referred_user=user
                )
                print(f"✅ Referral tracked: {referrer_profile.user.username} referred {phone}")
            except UserProfile.DoesNotExist:
                print(f"⚠️ Invalid referral code: {referral_code_param}")
        
        wallet = Wallet.objects.create(
            user=user, 
            balance=0.00,
            total_deposited=0,
            total_withdrawn=0,
            total_earned=0,
            total_invested=0
        )
        
        print("\n" + "="*60)
        print("⚠️ ADMIN ACTION REQUIRED!")
        print("="*60)
        print(f"New user needs approval:")
        print(f"   📱 Phone: {phone}")
        print(f"   👤 Name: {full_name if full_name else 'Not provided'}")
        print(f"   🔗 Referral Code: {profile.referral_code}")
        print(f"   🆔 User ID: {user.id}")
        print(f"   📅 Registered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        print(f"🔗 Approve here: https://senti-invest.onrender.com/admin/investments/userprofile/")
        print("="*60 + "\n")
        
        return Response({
            'success': True,
            'user_id': user.id,
            'referral_code': profile.referral_code,
            'message': 'Account created! Awaiting admin approval.'
        })
    except Exception as e:
        print(f"❌ Signup error: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
def login_view(request):
    """User login - checks if user exists, approved, and account status"""
    try:
        # ========== MAINTENANCE MODE CHECK - MUST BE FIRST ==========
        maint_msg = check_maintenance()
        if maint_msg:
            return Response({
                'success': False,
                'error': maint_msg,
                'maintenance': True,
                'code': 'MAINTENANCE_MODE'
            }, status=503)
        
        phone = request.data.get('phone_number')
        password = request.data.get('password')
        
        print(f"=== LOGIN REQUEST ===")
        print(f"Phone: {phone}")
        
        if not phone or not password:
            return Response({'error': 'Phone and password required'}, status=400)
        
        try:
            user = User.objects.get(username=phone)
        except User.DoesNotExist:
            print(f"❌ User not found: {phone}")
            return Response({
                'error': 'Account not found. Please sign up first.',
                'code': 'USER_NOT_FOUND'
            }, status=404)
        
        if not user.check_password(password):
            print(f"❌ Invalid password for {phone}")
            return Response({
                'error': 'Invalid password. Please try again.',
                'code': 'INVALID_PASSWORD'
            }, status=401)
        
        try:
            profile = UserProfile.objects.get(user=user)
            
            if profile.account_status in ['banned', 'frozen']:
                print(f"🚫 User {phone} - Account {profile.account_status}")
                return Response({
                    'error': f'Your account is {profile.account_status}. Please contact admin.',
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
        
        try:
            wallet = Wallet.objects.get(user=user)
            balance = float(wallet.balance)
        except Wallet.DoesNotExist:
            wallet = Wallet.objects.create(
                user=user, 
                balance=0.00,
                total_deposited=0,
                total_withdrawn=0,
                total_earned=0,
                total_invested=0
            )
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

# ========== FORGOT PASSWORD - REQUEST RESET (USER REQUESTS) ==========
@api_view(['POST'])
def forgot_password_request(request):
    """User requests password reset - admin notified to generate link"""
    try:
        phone = request.data.get('phone_number')
        
        print("\n" + "="*60)
        print(f"🔐 FORGOT PASSWORD REQUEST")
        print("="*60)
        print(f"📱 Phone: {phone}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        if not phone:
            return Response({'error': 'Phone number required'}, status=400)
        
        try:
            user = User.objects.get(username=phone)
            profile = UserProfile.objects.get(user=user)
        except User.DoesNotExist:
            return Response({'error': 'No account found with this phone number'}, status=404)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)
        
        # Generate reset token
        reset_token = str(uuid.uuid4()) + str(uuid.uuid4())
        
        # Store reset token
        reset_request = PasswordReset.objects.create(
            user=user,
            code=reset_token,
            is_used=False
        )
        
        # Update profile
        profile.requires_password_reset = True
        profile.reset_token = reset_token
        profile.save()
        
        # Generate reset link
        reset_link = f"https://senti-invest.onrender.com/reset-password/{reset_token}/"
        
        print("\n" + "="*60)
        print("⚠️ ADMIN ACTION REQUIRED - PASSWORD RESET REQUEST!")
        print("="*60)
        print(f"👤 User: {user.username}")
        print(f"📱 Phone: {phone}")
        print(f"👤 Name: {profile.full_name or 'Not provided'}")
        print("="*60)
        print(f"🔗 RESET LINK (Send to user):")
        print(f"{reset_link}")
        print("="*60)
        print("📝 Instructions:")
        print("1. Copy the link above")
        print("2. Send it to the user via WhatsApp/SMS")
        print("3. User clicks link and sets new password")
        print("="*60 + "\n")
        
        return Response({
            'success': True,
            'message': 'Password reset request sent to admin. You will receive a reset link shortly.',
            'request_id': reset_request.id
        })
        
    except Exception as e:
        print(f"❌ Forgot password error: {str(e)}")
        return Response({'error': str(e)}, status=500)

# ========== CHECK RESET TOKEN VALIDITY ==========
@api_view(['POST'])
def check_reset_token(request):
    """Check if reset token is valid before showing reset form"""
    try:
        token = request.data.get('token')
        
        if not token:
            return Response({'error': 'Token required'}, status=400)
        
        try:
            reset = PasswordReset.objects.get(code=token, is_used=False)
        except PasswordReset.DoesNotExist:
            return Response({'error': 'Invalid or expired reset link'}, status=404)
        
        if not reset.is_valid():
            reset.is_used = True
            reset.save()
            return Response({'error': 'Reset link has expired (24 hours). Please request a new one.'}, status=400)
        
        return Response({
            'success': True,
            'valid': True,
            'user_id': reset.user.id,
            'message': 'Token is valid. You can now reset your password.'
        })
        
    except Exception as e:
        print(f"❌ Check token error: {str(e)}")
        return Response({'error': str(e)}, status=500)

# ========== RESET PASSWORD WITH TOKEN ==========
@api_view(['POST'])
def reset_password_with_token(request):
    """Reset password using token from link (no code needed)"""
    try:
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        if not token:
            return Response({'error': 'Token required'}, status=400)
        
        if not new_password:
            return Response({'error': 'New password required'}, status=400)
        
        if new_password != confirm_password:
            return Response({'error': 'Passwords do not match'}, status=400)
        
        if len(new_password) < 4:
            return Response({'error': 'Password must be at least 4 characters'}, status=400)
        
        try:
            reset = PasswordReset.objects.get(code=token, is_used=False)
        except PasswordReset.DoesNotExist:
            return Response({'error': 'Invalid or expired reset link'}, status=404)
        
        if not reset.is_valid():
            reset.is_used = True
            reset.save()
            return Response({'error': 'Reset link has expired (24 hours). Please request a new one.'}, status=400)
        
        user = reset.user
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Mark token as used
        reset.is_used = True
        reset.save()
        
        # Clear reset flags from profile
        try:
            profile = UserProfile.objects.get(user=user)
            profile.requires_password_reset = False
            profile.reset_token = None
            profile.save()
        except UserProfile.DoesNotExist:
            pass
        
        print(f"✅ Password reset successful for {user.username}")
        
        return Response({
            'success': True,
            'message': 'Password has been reset successfully! You can now login with your new password.'
        })
        
    except Exception as e:
        print(f"❌ Reset password error: {str(e)}")
        return Response({'error': str(e)}, status=500)

# ========== ADMIN GENERATE RESET LINK ==========
@api_view(['POST'])
def admin_generate_reset_link(request):
    """Admin endpoint to generate password reset link for a user"""
    try:
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != 'your-secret-admin-key':
            return Response({'error': 'Unauthorized'}, status=401)
        
        phone = request.data.get('phone_number')
        
        if not phone:
            return Response({'error': 'Phone number required'}, status=400)
        
        try:
            user = User.objects.get(username=phone)
            profile = UserProfile.objects.get(user=user)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        
        reset_token = str(uuid.uuid4()) + str(uuid.uuid4())
        
        PasswordReset.objects.create(
            user=user,
            code=reset_token,
            is_used=False
        )
        
        profile.requires_password_reset = True
        profile.reset_token = reset_token
        profile.save()
        
        reset_link = f"https://senti-invest.onrender.com/reset-password/{reset_token}/"
        
        return Response({
            'success': True,
            'reset_link': reset_link,
            'message': f'Reset link generated for {user.username}'
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

# ========== PASSWORD RESET PAGE (NO CODE - ADMIN INITIATED) ==========
@csrf_protect
def password_reset_page(request, token):
    """Page where user can set new password using admin-provided token"""
    
    try:
        reset_request = PasswordReset.objects.get(code=token, is_used=False)
        
        if reset_request.created_at < timezone.now() - timedelta(hours=24):
            return render(request, 'password_reset.html', {
                'error': 'This reset link has expired (24 hours). Please contact admin for a new one.'
            })
        
        user = reset_request.user
        
    except PasswordReset.DoesNotExist:
        return render(request, 'password_reset.html', {
            'error': 'Invalid or already used reset link. Please contact admin.'
        })
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not new_password or len(new_password) < 4:
            return render(request, 'password_reset.html', {
                'token': token,
                'error': 'Password must be at least 4 characters long.'
            })
        
        if new_password != confirm_password:
            return render(request, 'password_reset.html', {
                'token': token,
                'error': 'Passwords do not match.'
            })
        
        user.set_password(new_password)
        user.save()
        
        reset_request.is_used = True
        reset_request.save()
        
        try:
            profile = UserProfile.objects.get(user=user)
            profile.requires_password_reset = False
            profile.reset_token = None
            profile.save()
        except UserProfile.DoesNotExist:
            pass
        
        return render(request, 'password_reset.html', {
            'success': 'Password has been reset successfully! You will be redirected to login page.'
        })
    
    return render(request, 'password_reset.html', {'token': token})

# ========== DEPOSIT FUNCTIONS ==========
@api_view(['POST'])
def request_mpesa_deposit(request):
    """Initiate M-Pesa deposit - Requires admin approval with notification"""
    # Maintenance check
    maint_msg = check_maintenance()
    if maint_msg:
        return Response({
            'error': maint_msg,
            'maintenance': True,
            'code': 'MAINTENANCE_MODE'
        }, status=503)
    
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
        
        if isinstance(amount, str):
            amount = Decimal(amount)
        else:
            amount = Decimal(amount)
        
        if not amount or amount < 100:
            return Response({'error': f'Minimum deposit is KES 100'}, status=400)
        
        if not phone_number:
            return Response({'error': 'Phone number is required'}, status=400)
        
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
        
        if phone_number.startswith('0'):
            formatted_phone = '254' + phone_number[1:]
        elif phone_number.startswith('+'):
            formatted_phone = phone_number[1:]
        else:
            formatted_phone = phone_number
        
        transaction_id = str(uuid.uuid4())[:8].upper()
        
        deposit = Deposit.objects.create(
            user=user,
            amount=amount,
            transaction_id=transaction_id,
            phone_number=phone_number,
            status='pending',
            verification_status='pending'
        )
        
        print("\n" + "="*60)
        print("⚠️ ADMIN ACTION REQUIRED - DEPOSIT PENDING!")
        print("="*60)
        print(f"💰 Deposit Request:")
        print(f"   👤 User: {user.username} ({profile.full_name or 'No name'})")
        print(f"   💵 Amount: KES {amount:,.0f}")
        print(f"   📱 Phone: {phone_number}")
        print(f"   🆔 Transaction ID: {transaction_id}")
        print("="*60)
        print(f"🔗 Approve here: https://senti-invest.onrender.com/admin/investments/deposit/")
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

@api_view(['POST'])
def verify_manual_payment(request):
    """Verify manual M-Pesa payment by parsing the SMS message"""
    # Maintenance check
    maint_msg = check_maintenance()
    if maint_msg:
        return Response({
            'error': maint_msg,
            'maintenance': True,
            'code': 'MAINTENANCE_MODE'
        }, status=503)
    
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
        
        try:
            profile = UserProfile.objects.get(user_id=user_id)
            if profile.account_status in ['banned', 'frozen']:
                return Response({
                    'error': f'Your account is {profile.account_status}. Please contact admin for assistance.'
                }, status=403)
        except UserProfile.DoesNotExist:
            pass
        
        txn_match = re.search(r'^([A-Z0-9]+) Confirmed', mpesa_message)
        if not txn_match:
            return Response({'error': 'Could not find transaction ID in the message. Please paste the full M-Pesa confirmation message.'}, status=400)
        transaction_id = txn_match.group(1)
        
        if Deposit.objects.filter(transaction_id=transaction_id).exists():
            return Response({'error': 'This transaction has already been used. Please check your deposit history.'}, status=400)
        
        amount_match = re.search(r'Ksh([\d,]+\.?\d*)', mpesa_message)
        if not amount_match:
            return Response({'error': 'Could not find amount in the message. Please paste the full M-Pesa confirmation message.'}, status=400)
        extracted_amount = Decimal(amount_match.group(1).replace(',', ''))
        
        amount = extracted_amount
        
        if amount < 100:
            return Response({'error': f'Minimum deposit is KES 100. You paid KES {amount}'}, status=400)
        
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
        
        wallet, created = Wallet.objects.get_or_create(user=user, defaults={
            'balance': 0,
            'total_deposited': 0,
            'total_withdrawn': 0,
            'total_earned': 0,
            'total_invested': 0
        })
        wallet.balance += amount
        wallet.total_deposited += amount
        wallet.save()
        
        update_referral_status(user)
        
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
        
        print("\n" + "="*60)
        print(f"📧 ACCOUNT UNBAN REQUEST")
        print("="*60)
        print(f"User: {user.username}")
        print(f"Phone: {profile.phone_number}")
        print(f"Reason: {reason}")
        print("="*60)
        print(f"🔗 Approve here: https://senti-invest.onrender.com/admin/investments/userprofile/")
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
    # Maintenance check
    maint_msg = check_maintenance()
    if maint_msg:
        return Response({
            'error': maint_msg,
            'maintenance': True,
            'code': 'MAINTENANCE_MODE'
        }, status=503)
    
    user_id = request.data.get('user_id')
    product_id = request.data.get('product_id')
    amount = Decimal(str(request.data.get('amount', 0)))
    
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
        
        profile = UserProfile.objects.get(user=user)
        if profile.account_status in ['banned', 'frozen']:
            return Response({'error': f'Your account is {profile.account_status}. Cannot make investments.'}, status=403)
            
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except InvestmentProduct.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)
    except Wallet.DoesNotExist:
        return Response({'error': 'Wallet not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=404)
    
    if amount != product.min_investment:
        return Response({'error': f'Investment amount must be exactly KES {product.min_investment}'}, status=400)
    
    if amount > wallet.balance:
        return Response({'error': f'Insufficient balance. Available: KES {wallet.balance:,.0f}'}, status=400)
    
    wallet.balance -= amount
    wallet.total_invested = (wallet.total_invested or 0) + amount
    wallet.save()
    
    expiry = timezone.now() + timedelta(days=product.duration_days)
    investment = UserInvestment.objects.create(
        user=user,
        product=product,
        amount=amount,
        expiry_date=expiry,
        status='active',
        total_earned=Decimal('0')
    )
    
    update_referral_status(user)
    
    print(f"✅ Investment successful! New balance: KES {wallet.balance:,.0f}")
    print(f"📊 Investment ID: {investment.id}, Expires: {expiry}")
    
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
    
    print(f"📊 Getting investments for user: {user_id}")
    
    try:
        user = User.objects.get(id=user_id)
        now = timezone.now()
        
        investments = UserInvestment.objects.filter(
            user=user, 
            status='active',
            expiry_date__gt=now
        ).select_related('product')
        
        print(f"Found {investments.count()} active investments")
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except Exception as e:
        print(f"Error: {str(e)}")
        return Response({'error': str(e)}, status=500)
    
    data = []
    total_daily = Decimal('0')
    
    for inv in investments:
        daily = inv.product.daily_earnings_amount if inv.product.daily_earnings_amount else Decimal('0')
        total_daily += daily
        
        days_left = (inv.expiry_date - now).days
        if days_left < 0:
            days_left = 0
        
        total_earned = inv.total_earned if inv.total_earned else Decimal('0')
        
        data.append({
            'id': inv.id,
            'product_name': inv.product.name,
            'product_level': inv.product.level,
            'amount': float(inv.amount),
            'daily_earnings': float(daily),
            'total_earned': float(total_earned),
            'invested_at': inv.invested_at.strftime('%Y-%m-%d'),
            'expiry_date': inv.expiry_date.strftime('%Y-%m-%d'),
            'days_left': max(0, days_left),
            'duration_days': inv.product.duration_days
        })
    
    print(f"Returning {len(data)} investments, total daily: KES {float(total_daily):,.2f}")
    
    return Response({
        'success': True,
        'investments': data,
        'total_daily_earnings': float(total_daily),
        'count': len(data)
    })

@api_view(['POST'])
def request_withdrawal(request):
    """Request a withdrawal with admin notification - Minimum 300 KES"""
    # Maintenance check
    maint_msg = check_maintenance()
    if maint_msg:
        return Response({
            'error': maint_msg,
            'maintenance': True,
            'code': 'MAINTENANCE_MODE'
        }, status=503)
    
    user_id = request.data.get('user_id')
    amount = Decimal(str(request.data.get('amount', 0)))
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
        
        if profile.account_status in ['banned', 'frozen']:
            return Response({'error': f'Your account is {profile.account_status}. Cannot process withdrawals.'}, status=403)
            
    except Wallet.DoesNotExist:
        return Response({'error': 'Wallet not found'}, status=404)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except UserProfile.DoesNotExist:
        return Response({'error': 'Profile not found'}, status=404)
    
    if amount < 300:
        return Response({'error': 'Minimum withdrawal is KES 300'}, status=400)
    
    if amount > wallet.balance:
        return Response({'error': f'Insufficient balance. Available: KES {wallet.balance:,.0f}'}, status=400)
    
    wallet.balance -= amount
    wallet.total_withdrawn += amount
    wallet.save()
    
    withdrawal = Withdrawal.objects.create(
        user=user,
        amount=amount,
        phone_number=phone_number,
        status='pending'
    )
    
    print("\n" + "="*60)
    print("⚠️ ADMIN ACTION REQUIRED - WITHDRAWAL PENDING!")
    print("="*60)
    print(f"💸 Withdrawal Request:")
    print(f"   👤 User: {user.username} ({profile.full_name or 'No name'})")
    print(f"   💵 Amount: KES {amount:,.0f}")
    print(f"   📱 Phone: {phone_number}")
    print(f"   🆔 Withdrawal ID: {withdrawal.id}")
    print(f"   💰 New Balance: KES {wallet.balance:,.0f}")
    print("="*60)
    print(f"🔗 Approve here: https://senti-invest.onrender.com/admin/investments/withdrawal/")
    print("="*60 + "\n")
    
    return Response({
        'success': True,
        'withdrawal_id': withdrawal.id,
        'amount': float(amount),
        'new_balance': float(wallet.balance),
        'message': 'Withdrawal request submitted. Money deducted from your balance. Admin will review within 8-12 hours.'
    })

@api_view(['GET'])
def get_wallet(request):
    """Get wallet details"""
    user_id = request.GET.get('user_id')
    
    print(f"💰 Getting wallet for user: {user_id}")
    
    try:
        wallet = Wallet.objects.get(user_id=user_id)
        
        investments = UserInvestment.objects.filter(user_id=user_id, status='active')
        total_earned_from_investments = sum(float(inv.total_earned or 0) for inv in investments)
        
        referral_earned = ReferralBonus.objects.filter(
            user_id=user_id, 
            status='claimed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total_earned = total_earned_from_investments + float(referral_earned)
        
        return Response({
            'balance': float(wallet.balance or 0),
            'total_deposited': float(wallet.total_deposited or 0),
            'total_withdrawn': float(wallet.total_withdrawn or 0),
            'total_invested': float(wallet.total_invested or 0),
            'total_earned': total_earned
        })
    except Wallet.DoesNotExist:
        return Response({
            'balance': 0,
            'total_deposited': 0,
            'total_withdrawn': 0,
            'total_invested': 0,
            'total_earned': 0
        })
    except Exception as e:
        print(f"❌ Wallet error: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_withdrawal_history(request):
    """Get user's complete withdrawal history (all statuses)"""
    user_id = request.GET.get('user_id')
    
    try:
        user = User.objects.get(id=user_id)
        withdrawals = Withdrawal.objects.filter(user=user).order_by('-created_at')
        
        history = []
        for w in withdrawals:
            history.append({
                'id': w.id,
                'amount': float(w.amount),
                'phone_number': w.phone_number,
                'status': w.status,
                'created_at': w.created_at.isoformat(),
                'approved_at': w.approved_at.isoformat() if w.approved_at else None
            })
        
        return Response({
            'success': True,
            'withdrawals': history
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except Exception as e:
        print(f"❌ Withdrawal history error: {str(e)}")
        return Response({'error': str(e)}, status=500)

# ========== REFERRAL STATUS UPDATE FUNCTIONS ==========
def update_referral_status(user):
    """Update referral status when user deposits or invests"""
    try:
        referral = Referral.objects.filter(referred_user=user).first()
        if not referral:
            return
        
        wallet = Wallet.objects.get(user=user)
        if wallet.total_deposited > 0 and not referral.has_deposited:
            referral.has_deposited = True
            referral.first_deposit_date = timezone.now()
            referral.save()
            print(f"📢 Referral updated: {referral.referrer.username}'s referral {user.username} has deposited")
        
        investments = UserInvestment.objects.filter(user=user, status='active')
        if investments.exists() and not referral.has_invested:
            referral.has_invested = True
            referral.first_investment_date = timezone.now()
            referral.save()
            print(f"📢 Referral updated: {referral.referrer.username}'s referral {user.username} has invested")
            
            check_referral_qualification_for_user(referral.referrer)
            
    except Exception as e:
        print(f"Error updating referral status: {e}")

def check_referral_qualification_for_user(user):
    """Check if user qualifies for bonus based on their referrals"""
    qualified_count = Referral.objects.filter(
        referrer=user,
        has_deposited=True,
        has_invested=True,
        bonus_given=False
    ).count()
    
    if qualified_count >= 5:
        qualified = Referral.objects.filter(
            referrer=user,
            has_deposited=True,
            has_invested=True,
            bonus_given=False
        )[:5]
        
        referral_ids = ','.join([str(r.id) for r in qualified])
        
        existing = ReferralBonus.objects.filter(
            user=user,
            status='pending',
            bonus_type='referral'
        ).first()
        
        if not existing:
            bonus = ReferralBonus.objects.create(
                user=user,
                amount=Decimal('500'),
                referred_count=qualified_count,
                status='pending',
                bonus_type='referral',
                referral_ids=referral_ids
            )
            print(f"🎁 Auto-created bonus for {user.username} with {qualified_count} qualified referrals")

# ========== REFERRAL WITH STATUS ENDPOINTS ==========
@api_view(['GET'])
def get_referral_list_with_status(request):
    """Get user's referral list with investment status"""
    try:
        user_id = request.GET.get('user_id')
        user = User.objects.get(id=user_id)
        referrals = Referral.objects.filter(referrer=user).select_related('referred_user')
        
        referral_data = []
        for ref in referrals:
            try:
                wallet = Wallet.objects.get(user=ref.referred_user)
                has_deposit = wallet.total_deposited > 0
            except:
                has_deposit = False
            
            investments = UserInvestment.objects.filter(user=ref.referred_user, status='active')
            has_investment = investments.exists()
            
            if has_deposit and not ref.has_deposited:
                ref.has_deposited = True
                ref.first_deposit_date = timezone.now()
                ref.save()
            
            if has_investment and not ref.has_invested:
                ref.has_invested = True
                ref.first_investment_date = timezone.now()
                ref.save()
            
            referral_data.append({
                'id': ref.id,
                'phone': ref.referred_user.username,
                'has_deposited': ref.has_deposited,
                'has_invested': ref.has_invested,
                'bonus_given': ref.bonus_given,
                'joined_date': ref.created_at.strftime('%Y-%m-%d'),
                'status': 'qualified' if (ref.has_deposited and ref.has_invested and not ref.bonus_given) else 
                          'invested' if (ref.has_deposited and ref.has_invested) else
                          'deposited' if ref.has_deposited else
                          'pending'
            })
        
        qualified = [r for r in referral_data if r['status'] == 'qualified']
        invested = [r for r in referral_data if r['status'] == 'invested' and not r['bonus_given']]
        deposited = [r for r in referral_data if r['status'] == 'deposited']
        pending = [r for r in referral_data if r['status'] == 'pending']
        
        return Response({
            'success': True,
            'total_referrals': len(referral_data),
            'qualified_count': len(qualified),
            'referrals': {
                'qualified': qualified,
                'invested': invested,
                'deposited': deposited,
                'pending': pending
            }
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_bonus_history(request):
    """Get user's bonus claim history"""
    try:
        user_id = request.GET.get('user_id')
        user = User.objects.get(id=user_id)
        bonuses = ReferralBonus.objects.filter(user=user).order_by('-created_at')
        
        history = []
        for bonus in bonuses:
            history.append({
                'id': bonus.id,
                'amount': float(bonus.amount),
                'referred_count': bonus.referred_count,
                'status': bonus.status,
                'created_at': bonus.created_at.strftime('%Y-%m-%d %H:%M'),
                'claimed_at': bonus.claimed_at.strftime('%Y-%m-%d %H:%M') if bonus.claimed_at else None,
                'bonus_type': getattr(bonus, 'bonus_type', 'referral')
            })
        
        total_claimed = sum(b.amount for b in bonuses if b.status == 'claimed')
        
        return Response({
            'success': True,
            'history': history,
            'total_claimed': float(total_claimed)
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
        
# ========== FIXED DAILY EARNINGS - USES NAIROBI TIMEZONE ==========
@api_view(['GET', 'POST'])
def process_daily_earnings_api(request):
    """API endpoint to trigger daily earnings - USES NAIROBI TIMEZONE for ALL users"""
    print("\n" + "="*60)
    print(f"🔄 DAILY EARNINGS PROCESSING STARTED")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # IMPORTANT: Use Africa/Nairobi timezone for correct date
    from django.utils import timezone
    now = timezone.localtime(timezone.now())
    today = now.date()
    
    print(f"📅 Nairobi date: {today}")
    print(f"⏰ Nairobi time: {now.strftime('%H:%M:%S')}")
    
    # Only get active investments from users who are NOT frozen or banned
    active_investments = UserInvestment.objects.filter(
        status='active', 
        expiry_date__gt=timezone.now(),
        user__profile__account_status='active',
        user__profile__is_approved=True
    )
    
    total_earnings = Decimal('0')
    processed = 0
    users_affected = set()
    skipped_frozen = 0
    
    print(f"📊 Found {active_investments.count()} active investments from active users")
    
    for investment in active_investments:
        # Check if already earned today in NAIROBI timezone
        already_earned_today = False
        if investment.last_earning_date:
            # Convert last_earning_date to Nairobi timezone for comparison
            last_earning_local = timezone.localtime(investment.last_earning_date)
            if last_earning_local.date() == today:
                already_earned_today = True
        
        if already_earned_today:
            print(f"⏭️ Skipping {investment.user.username} - Already earned today in Nairobi time")
            continue
        
        daily_earnings = investment.product.daily_earnings_amount if investment.product.daily_earnings_amount else Decimal('0')
        
        if daily_earnings > 0:
            investment.total_earned += daily_earnings
            investment.last_earning_date = timezone.now()  # Store in UTC
            investment.save()
            
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
        
        if investment.expiry_date <= timezone.now():
            investment.status = 'completed'
            investment.save()
            print(f"🎉 Investment completed: {investment.product.name} for {investment.user.username}")
    
    if processed > 0:
        log = DailyEarningsLog.objects.create(
            total_earnings=total_earnings,
            users_affected=len(users_affected),
            investments_processed=processed
        )
    
    print("\n" + "="*60)
    print("📊 DAILY EARNINGS SUMMARY")
    print("="*60)
    print(f"   📅 Date (Nairobi): {today}")
    print(f"   ✅ Investments processed: {processed}")
    print(f"   👥 Users affected: {len(users_affected)}")
    print(f"   💰 Total earnings distributed: KES {total_earnings:,.2f}")
    print(f"   ⏭️ Skipped (frozen/banned): {skipped_frozen}")
    print("="*60)
    
    return Response({
        'success': True,
        'processed': processed,
        'total_earnings': float(total_earnings),
        'users_affected': len(users_affected),
        'skipped_frozen': skipped_frozen,
        'date': str(today),
        'message': f'Processed {processed} investments, distributed KES {total_earnings:,.0f} to {len(users_affected)} users'
    })

# ========== ADMIN BALANCE MANAGEMENT ==========
@api_view(['POST'])
def admin_adjust_balance(request):
    """Admin endpoint to manually adjust user balance"""
    try:
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != 'your-secret-admin-key':
            return Response({'error': 'Unauthorized'}, status=401)
        
        user_id = request.data.get('user_id')
        amount = Decimal(str(request.data.get('amount', 0)))
        action = request.data.get('action')
        reason = request.data.get('reason', '')
        performed_by = request.data.get('performed_by', 'admin')
        
        user = User.objects.get(id=user_id)
        wallet = Wallet.objects.get(user=user)
        
        previous_balance = wallet.balance
        
        if action == 'add':
            wallet.balance += amount
            message = f"Added KES {amount:,.0f} to {user.username}'s balance"
        elif action == 'subtract':
            if amount > wallet.balance:
                return Response({'error': 'Insufficient balance'}, status=400)
            wallet.balance -= amount
            message = f"Subtracted KES {amount:,.0f} from {user.username}'s balance"
        else:
            return Response({'error': 'Invalid action'}, status=400)
        
        wallet.save()
        
        BalanceAdjustmentLog.objects.create(
            user=user,
            amount=amount,
            action=action,
            reason=reason,
            previous_balance=previous_balance,
            new_balance=wallet.balance,
            performed_by=performed_by
        )
        
        FraudLog.objects.create(
            user=user,
            action='balance_adjusted',
            amount=amount,
            reason=f"Balance {action} by {performed_by}: {reason}",
            performed_by=performed_by
        )
        
        return Response({
            'success': True,
            'message': message,
            'new_balance': float(wallet.balance),
            'previous_balance': float(previous_balance)
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except Wallet.DoesNotExist:
        return Response({'error': 'Wallet not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def admin_referral_stats(request):
    """Get referral statistics for admin dashboard"""
    try:
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != 'your-secret-admin-key':
            return Response({'error': 'Unauthorized'}, status=401)
        
        top_referrers = UserProfile.objects.annotate(
            referral_count=Count('referrals')
        ).filter(referral_count__gt=0).order_by('-referral_count')[:10]
        
        pending_bonuses = ReferralBonus.objects.filter(status='pending').count()
        
        qualified_users = User.objects.annotate(
            qualified_count=Count('referrals_made', filter=Q(
                referrals_made__has_deposited=True,
                referrals_made__has_invested=True,
                referrals_made__bonus_given=False
            ))
        ).filter(qualified_count__gte=5)
        
        return Response({
            'success': True,
            'top_referrers': [{
                'username': p.user.username,
                'phone': p.phone_number,
                'referral_count': p.referral_count
            } for p in top_referrers],
            'pending_bonuses': pending_bonuses,
            'qualified_users': [{
                'id': u.id,
                'username': u.username,
                'qualified_count': u.qualified_count
            } for u in qualified_users]
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

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
            referrer_profile = UserProfile.objects.get(referral_code=referrer_code)
            referrer = referrer_profile.user
        except UserProfile.DoesNotExist:
            return Response({'success': True})
        
        try:
            referred_user = User.objects.get(username=referred_phone)
        except User.DoesNotExist:
            return Response({'success': True})
        
        if referrer.username == referred_phone:
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
        profile = UserProfile.objects.get(user=user)
        
        if not profile.referral_code:
            profile.generate_referral_code()
            profile.save()
        
        referral_code = profile.referral_code
        referral_count = UserProfile.objects.filter(referred_by=profile).count()
        
        pending_bonuses = ReferralBonus.objects.filter(user=user, status='pending')
        claimed_bonuses = ReferralBonus.objects.filter(user=user, status='claimed')
        
        pending_total = sum(b.amount for b in pending_bonuses)
        claimed_total = sum(b.amount for b in claimed_bonuses)
        
        site_url = "https://senti-earn.netlify.app"
        referral_link = f"{site_url}/signup?ref={referral_code}"
        
        referrer_name = None
        if profile.referred_by:
            referrer_name = profile.referred_by.user.username
        
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
        bonus.claimed_at = timezone.now()
        bonus.save()
        
        if bonus.referral_ids:
            referral_ids = [int(x) for x in bonus.referral_ids.split(',') if x]
            Referral.objects.filter(id__in=referral_ids).update(
                bonus_given=True,
                bonus_given_at=timezone.now()
            )
        
        wallet, created = Wallet.objects.get_or_create(user_id=user_id, defaults={
            'balance': 0,
            'total_deposited': 0,
            'total_withdrawn': 0,
            'total_invested': 0,
            'total_earned': 0
        })
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

# ========== INVESTMENT UPGRADE ENDPOINT ==========
@api_view(['POST'])
def upgrade_investment(request):
    """Upgrade an existing investment to a higher product"""
    # Maintenance check
    maint_msg = check_maintenance()
    if maint_msg:
        return Response({
            'error': maint_msg,
            'maintenance': True,
            'code': 'MAINTENANCE_MODE'
        }, status=503)
    
    try:
        user_id = request.data.get('user_id')
        investment_id = request.data.get('investment_id')
        new_product_id = request.data.get('new_product_id')
        
        if not user_id or not investment_id or not new_product_id:
            return Response({'error': 'user_id, investment_id, and new_product_id are required'}, status=400)
        
        user = User.objects.get(id=user_id)
        old_investment = UserInvestment.objects.get(id=investment_id, user=user, status='active')
        old_product = old_investment.product
        
        new_product = InvestmentProduct.objects.get(id=new_product_id, is_active=True)
        
        if new_product.min_investment <= old_investment.amount:
            return Response({
                'error': f'New product must have higher investment amount. Current: KES {old_investment.amount:,.0f}, New: KES {new_product.min_investment:,.0f}'
            }, status=400)
        
        difference = new_product.min_investment - old_investment.amount
        
        try:
            wallet = Wallet.objects.get(user=user)
        except Wallet.DoesNotExist:
            return Response({'error': 'Wallet not found'}, status=404)
        
        if wallet.balance < difference:
            return Response({
                'error': f'Insufficient balance. Need KES {difference:,.0f} to upgrade. Available: KES {wallet.balance:,.0f}'
            }, status=400)
        
        if difference > 0:
            wallet.balance -= difference
            wallet.save()
        
        now = timezone.now()
        days_remaining = max(0, (old_investment.expiry_date - now).days)
        days_used = old_product.duration_days - days_remaining
        remaining_days = new_product.duration_days - days_used
        if remaining_days < 0:
            remaining_days = 0
        
        new_expiry = now + timedelta(days=remaining_days)
        
        old_investment.status = 'cancelled'
        old_investment.save()
        
        new_investment = UserInvestment.objects.create(
            user=user,
            product=new_product,
            amount=new_product.min_investment,
            expiry_date=new_expiry,
            status='active',
            total_earned=Decimal('0')
        )
        
        FraudLog.objects.create(
            user=user,
            action='balance_adjusted',
            amount=difference,
            reason=f'Investment upgrade from {old_product.name} (KES {old_investment.amount:,.0f}) to {new_product.name} (KES {new_product.min_investment:,.0f})',
            performed_by='system'
        )
        
        return Response({
            'success': True,
            'message': f'Successfully upgraded from {old_product.name} to {new_product.name}',
            'new_investment_id': new_investment.id,
            'amount_paid': float(difference),
            'new_balance': float(wallet.balance),
            'daily_earnings': float(new_product.daily_earnings_amount or 0),
            'expiry_date': new_expiry.strftime('%Y-%m-%d'),
            'days_left': remaining_days
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except UserInvestment.DoesNotExist:
        return Response({'error': 'Investment not found or already completed/cancelled'}, status=404)
    except InvestmentProduct.DoesNotExist:
        return Response({'error': 'New product not found'}, status=404)
    except Exception as e:
        print(f"Upgrade error: {str(e)}")
        return Response({'error': str(e)}, status=500)