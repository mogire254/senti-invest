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

# ========== EXTRACT TRANSACTION ID FROM M-PESA MESSAGE ==========
def extract_transaction_id(mpesa_message):
    """Extract the real transaction ID from M-Pesa confirmation message"""
    if not mpesa_message:
        return None
    
    txn_match = re.search(r'^([A-Z0-9]{8,12})\s+Confirmed', mpesa_message)
    if txn_match:
        return txn_match.group(1)
    
    txn_match = re.search(r'(?:Transaction|Txn)\s*ID:?\s*([A-Z0-9]{8,12})', mpesa_message, re.IGNORECASE)
    if txn_match:
        return txn_match.group(1)
    
    txn_match = re.match(r'^([A-Z0-9]{8,12})', mpesa_message.strip())
    if txn_match:
        return txn_match.group(1)
    
    txn_match = re.search(r'\b([A-Z0-9]{8,12})\b', mpesa_message)
    if txn_match:
        return txn_match.group(1)
    
    return None

# ========== VALIDATE M-PESA MESSAGE (Internal validation only - no till numbers) ==========
def validate_mpesa_message(mpesa_message, expected_amount=None):
    """Validate M-Pesa message - validates merchant names only, no till numbers"""
    if not mpesa_message:
        return {'valid': False, 'error': 'No message provided'}
    
    # List of valid merchant names (ONLY THESE - no till numbers)
    valid_merchants = [
        'MUTHONI MUTHOGA',
        'BRIAN MOGIRE NYABUTO',
        'DORCAS NJERI MWAI',
        'MUTHONI',
        'BRIAN MOGIRE',
        'DORCAS NJERI'
    ]
    
    # Extract transaction ID
    transaction_id = extract_transaction_id(mpesa_message)
    
    # Extract amount
    amount_match = re.search(r'Ksh([\d,]+\.?\d*)', mpesa_message, re.IGNORECASE)
    if not amount_match:
        return {'valid': False, 'error': 'Could not find amount in the message. Please paste the full M-Pesa confirmation message.'}
    
    paid_amount = Decimal(amount_match.group(1).replace(',', ''))
    
    # Check if amount matches expected
    if expected_amount and paid_amount != expected_amount:
        return {'valid': False, 'error': f'Amount mismatch. Expected KES {expected_amount:,.0f}, but paid KES {paid_amount:,.0f}'}
    
    if paid_amount < 100:
        return {'valid': False, 'error': f'Minimum deposit is KES 100. You paid KES {paid_amount:,.0f}'}
    
    # Check if paid to valid merchant name
    merchant_found = False
    for merchant in valid_merchants:
        if merchant.upper() in mpesa_message.upper():
            merchant_found = True
            break
    
    if not merchant_found:
        return {'valid': False, 'error': 'Payment verification failed. Please ensure you paid to the correct merchant. Contact admin for assistance.'}
    
    return {
        'valid': True,
        'transaction_id': transaction_id,
        'amount': paid_amount,
        'message': 'Message validated successfully'
    }

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

# ========== FORGOT PASSWORD FUNCTIONS ==========
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
        
        reset_token = str(uuid.uuid4()) + str(uuid.uuid4())
        
        reset_request = PasswordReset.objects.create(
            user=user,
            code=reset_token,
            is_used=False
        )
        
        profile.requires_password_reset = True
        profile.reset_token = reset_token
        profile.save()
        
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

@api_view(['POST'])
def reset_password_with_token(request):
    """Reset password using token from link"""
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
        
        user.set_password(new_password)
        user.save()
        
        reset.is_used = True
        reset.save()
        
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

# ========== LEGACY MANUAL PAYMENT VERIFICATION ==========
@api_view(['POST'])
def verify_manual_payment(request):
    """Legacy manual payment verification - kept for compatibility"""
    try:
        user_id = request.data.get('user_id')
        amount = request.data.get('amount')
        phone_number = request.data.get('phone_number', '')
        mpesa_message = request.data.get('mpesa_message', '')
        
        if not mpesa_message:
            return Response({'error': 'Please paste your M-Pesa message'}, status=400)
        
        txn_match = re.search(r'^([A-Z0-9]+) Confirmed', mpesa_message)
        if not txn_match:
            return Response({'error': 'Could not find transaction ID in the message.'}, status=400)
        transaction_id = txn_match.group(1)
        
        amount_match = re.search(r'Ksh([\d,]+\.?\d*)', mpesa_message, re.IGNORECASE)
        if not amount_match:
            return Response({'error': 'Could not find amount in the message.'}, status=400)
        extracted_amount = Decimal(amount_match.group(1).replace(',', ''))
        
        if extracted_amount < 100:
            return Response({'error': f'Minimum deposit is KES 100. You paid KES {extracted_amount}'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        if Deposit.objects.filter(transaction_id=transaction_id).exists():
            return Response({'error': 'This transaction ID has already been used.'}, status=400)
        
        deposit = Deposit.objects.create(
            user=user,
            amount=extracted_amount,
            transaction_id=transaction_id,
            phone_number=phone_number,
            mpesa_message=mpesa_message,
            verification_status='pending_admin_approval',
            status='pending'
        )
        
        return Response({
            'success': True,
            'message': f'Payment recorded. Transaction ID: {transaction_id}. Admin will approve shortly.',
            'transaction_id': transaction_id,
            'pending_verification': True
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

# ========== NEW DEPOSIT SYSTEM (Step 1: Submit Request) ==========
@api_view(['POST'])
def submit_deposit_request(request):
    """Step 1: User submits deposit request - NO money added until admin approves"""
    try:
        maint_msg = check_maintenance()
        if maint_msg:
            return Response({
                'error': maint_msg,
                'maintenance': True,
                'code': 'MAINTENANCE_MODE'
            }, status=503)
        
        user_id = request.data.get('user_id')
        amount = request.data.get('amount')
        phone_number = request.data.get('phone_number', '')
        
        print("\n" + "="*60)
        print(f"📝 STEP 1: DEPOSIT REQUEST SUBMITTED")
        print("="*60)
        print(f"👤 User ID: {user_id}")
        print(f"💵 Amount: KES {amount}")
        print(f"📱 Phone: {phone_number}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        if not user_id or not amount:
            return Response({'error': 'User ID and amount required'}, status=400)
        
        amount = Decimal(str(amount))
        
        if amount < 100:
            return Response({'error': f'Minimum deposit is KES 100'}, status=400)
        
        if not phone_number or len(phone_number) < 10:
            return Response({'error': 'Please enter a valid M-Pesa phone number'}, status=400)
        
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
        
        request_id = str(uuid.uuid4())[:8].upper()
        
        deposit = Deposit.objects.create(
            user=user,
            amount=amount,
            transaction_id=request_id,
            phone_number=phone_number,
            verification_status='pending_approval',
            status='pending'
        )
        
        print(f"✅ Deposit request created: {user.username} - KES {amount:,.0f}")
        
        return Response({
            'success': True,
            'message': f'✅ Deposit request of KES {amount:,.0f} submitted. Check your phone to complete the M-PESA transaction, then paste the confirmation message.',
            'request_id': request_id,
            'amount': float(amount),
            'pending_approval': True
        })
        
    except Exception as e:
        print(f"❌ Submit deposit request error: {str(e)}")
        return Response({'error': str(e)}, status=500)


# ========== NEW DEPOSIT SYSTEM (Step 2: Verify Payment) ==========
@api_view(['POST'])
def verify_deposit_payment(request):
    """Step 2: User pastes M-Pesa message - validates and updates deposit (NO money added yet)"""
    try:
        maint_msg = check_maintenance()
        if maint_msg:
            return Response({
                'error': maint_msg,
                'maintenance': True,
                'code': 'MAINTENANCE_MODE'
            }, status=503)
        
        user_id = request.data.get('user_id')
        mpesa_message = request.data.get('mpesa_message', '')
        
        print("\n" + "="*60)
        print(f"📝 STEP 2: DEPOSIT VERIFICATION")
        print("="*60)
        print(f"👤 User ID: {user_id}")
        print(f"📝 Message: {mpesa_message[:100] if mpesa_message else 'No message'}...")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        if not user_id:
            return Response({'error': 'User ID required'}, status=400)
        
        if not mpesa_message or len(mpesa_message) < 20:
            return Response({'error': 'Please paste your full M-Pesa confirmation message'}, status=400)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        
        # Get the most recent pending deposit request for this user
        pending_deposit = Deposit.objects.filter(
            user=user,
            verification_status='pending_approval',
            status='pending'
        ).order_by('-created_at').first()
        
        if not pending_deposit:
            return Response({'error': 'No pending deposit request found. Please submit a deposit request first.'}, status=404)
        
        # Validate the M-Pesa message
        validation = validate_mpesa_message(mpesa_message, pending_deposit.amount)
        
        if not validation['valid']:
            print(f"❌ Message validation failed: {validation['error']}")
            return Response({'error': validation['error']}, status=400)
        
        # Extract transaction ID from message
        real_transaction_id = validation['transaction_id']
        
        # Check if transaction ID already used
        if Deposit.objects.filter(transaction_id=real_transaction_id).exists():
            return Response({'error': 'This transaction ID has already been used. Please check your deposit history.'}, status=400)
        
        # Update the deposit record with the message and real transaction ID
        pending_deposit.mpesa_message = mpesa_message
        pending_deposit.transaction_id = real_transaction_id
        pending_deposit.verification_status = 'pending_admin_approval'
        pending_deposit.save()
        
        print(f"✅ Deposit verified: {user.username} - KES {pending_deposit.amount:,.0f} - Transaction ID: {real_transaction_id} - Waiting for admin approval")
        
        # User-friendly response - NO till numbers or merchant names shown
        return Response({
            'success': True,
            'message': f'✅ Your M-Pesa payment has been recorded successfully.\n\n📋 Transaction ID: {real_transaction_id}\n💰 Amount: KES {pending_deposit.amount:,.0f}\n\n⏳ Please wait for admin approval. Funds will appear in your wallet after approval.',
            'deposit_id': pending_deposit.id,
            'amount': float(pending_deposit.amount),
            'transaction_id': real_transaction_id,
            'pending_admin_approval': True
        })
        
    except Exception as e:
        print(f"❌ Verify deposit error: {str(e)}")
        return Response({'error': str(e)}, status=500)


# ========== CHECK DEPOSIT STATUS ==========
@api_view(['GET'])
def check_deposit_status(request):
    """User checks if their deposit has been approved by admin"""
    try:
        user_id = request.GET.get('user_id')
        deposit_id = request.GET.get('deposit_id')
        
        if not user_id or not deposit_id:
            return Response({'error': 'User ID and deposit ID required'}, status=400)
        
        try:
            deposit = Deposit.objects.get(id=deposit_id, user_id=user_id)
        except Deposit.DoesNotExist:
            return Response({'error': 'Deposit not found'}, status=404)
        
        status_map = {
            'approved': 'approved',
            'pending_admin_approval': 'pending_admin_approval',
            'pending_approval': 'pending_approval',
            'rejected': 'rejected'
        }
        
        status_message = ''
        if deposit.verification_status == 'approved':
            status_message = '✅ Deposit approved! Money has been added to your wallet.'
        elif deposit.verification_status == 'pending_approval':
            status_message = '⏳ Please complete your M-Pesa transaction and paste the confirmation message.'
        elif deposit.verification_status == 'pending_admin_approval':
            status_message = '⏳ Deposit pending admin approval. Funds will appear after approval.'
        elif deposit.verification_status == 'rejected':
            status_message = f'❌ Deposit rejected. Reason: {deposit.rejection_reason or "Contact admin for details."}'
        
        return Response({
            'success': True,
            'status': status_map.get(deposit.verification_status, deposit.verification_status),
            'amount': float(deposit.amount),
            'message': status_message,
            'transaction_id': deposit.transaction_id
        })
        
    except Exception as e:
        print(f"❌ Check deposit status error: {str(e)}")
        return Response({'error': str(e)}, status=500)


# ========== ADMIN APPROVE DEPOSIT ==========
@api_view(['POST'])
def admin_approve_deposit(request):
    """Admin approves a deposit - ONLY THEN money is added to wallet"""
    try:
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != 'your-secret-admin-key':
            return Response({'error': 'Unauthorized'}, status=401)
        
        deposit_id = request.data.get('deposit_id')
        
        if not deposit_id:
            return Response({'error': 'Deposit ID required'}, status=400)
        
        try:
            deposit = Deposit.objects.get(id=deposit_id)
        except Deposit.DoesNotExist:
            return Response({'error': 'Deposit not found'}, status=404)
        
        if deposit.verification_status != 'pending_admin_approval':
            return Response({'error': f'Deposit already {deposit.verification_status}. Cannot approve again.'}, status=400)
        
        wallet, created = Wallet.objects.get_or_create(user=deposit.user)
        wallet.balance += deposit.amount
        wallet.total_deposited += deposit.amount
        wallet.save()
        
        deposit.verification_status = 'approved'
        deposit.status = 'approved'
        deposit.approved_at = timezone.now()
        deposit.approved_by = request.data.get('approved_by', 'admin')
        deposit.save()
        
        update_referral_status(deposit.user)
        
        FraudLog.objects.create(
            user=deposit.user,
            action='deposit_verified',
            amount=deposit.amount,
            reason=f'Deposit approved by admin. Transaction ID: {deposit.transaction_id}',
            performed_by=request.data.get('approved_by', 'admin')
        )
        
        print(f"✅ DEPOSIT APPROVED: {deposit.user.username} - KES {deposit.amount:,.0f} added to wallet")
        
        return Response({
            'success': True,
            'message': f'✅ Deposit of KES {deposit.amount:,.0f} approved and added to user balance.',
            'new_balance': float(wallet.balance)
        })
        
    except Exception as e:
        print(f"❌ Admin approve deposit error: {str(e)}")
        return Response({'error': str(e)}, status=500)


# ========== ADMIN REJECT DEPOSIT ==========
@api_view(['POST'])
def admin_reject_deposit(request):
    """Admin rejects a deposit - NO money added to wallet"""
    try:
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != 'your-secret-admin-key':
            return Response({'error': 'Unauthorized'}, status=401)
        
        deposit_id = request.data.get('deposit_id')
        reason = request.data.get('reason', 'No reason provided')
        
        if not deposit_id:
            return Response({'error': 'Deposit ID required'}, status=400)
        
        try:
            deposit = Deposit.objects.get(id=deposit_id)
        except Deposit.DoesNotExist:
            return Response({'error': 'Deposit not found'}, status=404)
        
        deposit.verification_status = 'rejected'
        deposit.status = 'rejected'
        deposit.rejection_reason = reason
        deposit.save()
        
        FraudLog.objects.create(
            user=deposit.user,
            action='deposit_rejected',
            amount=deposit.amount,
            reason=f'Deposit rejected by admin: {reason}',
            performed_by=request.data.get('rejected_by', 'admin')
        )
        
        print(f"❌ DEPOSIT REJECTED: {deposit.user.username} - KES {deposit.amount:,.0f}")
        
        return Response({
            'success': True,
            'message': f'❌ Deposit rejected. Reason: {reason}',
            'reason': reason
        })
        
    except Exception as e:
        print(f"❌ Admin reject deposit error: {str(e)}")
        return Response({'error': str(e)}, status=500)


# ========== GET PENDING DEPOSITS FOR ADMIN ==========
@api_view(['GET'])
def admin_get_pending_deposits(request):
    """Admin gets all pending deposit requests"""
    try:
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != 'your-secret-admin-key':
            return Response({'error': 'Unauthorized'}, status=401)
        
        pending_deposits = Deposit.objects.filter(
            verification_status='pending_admin_approval'
        ).order_by('-created_at')
        
        data = []
        for deposit in pending_deposits:
            data.append({
                'id': deposit.id,
                'user': deposit.user.username,
                'user_phone': deposit.user.profile.phone_number if hasattr(deposit.user, 'profile') else '',
                'amount': float(deposit.amount),
                'transaction_id': deposit.transaction_id,
                'phone_number': deposit.phone_number,
                'mpesa_message': deposit.mpesa_message,
                'created_at': deposit.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return Response({
            'success': True,
            'pending_deposits': data,
            'count': len(data)
        })
        
    except Exception as e:
        print(f"❌ Get pending deposits error: {str(e)}")
        return Response({'error': str(e)}, status=500)


# ========== ADMIN GET ALL WALLETS ==========
@api_view(['GET'])
def admin_get_all_wallets(request):
    """Admin can view all user wallets"""
    try:
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != 'your-secret-admin-key':
            return Response({'error': 'Unauthorized'}, status=401)
        
        wallets = Wallet.objects.select_related('user').all().order_by('-balance')
        
        data = []
        for wallet in wallets:
            data.append({
                'user_id': wallet.user.id,
                'username': wallet.user.username,
                'phone': wallet.user.profile.phone_number if hasattr(wallet.user, 'profile') else '',
                'balance': float(wallet.balance),
                'total_deposited': float(wallet.total_deposited),
                'total_withdrawn': float(wallet.total_withdrawn),
                'total_earned': float(wallet.total_earned),
                'total_invested': float(wallet.total_invested)
            })
        
        return Response({
            'success': True,
            'wallets': data,
            'count': len(data)
        })
        
    except Exception as e:
        print(f"❌ Get all wallets error: {str(e)}")
        return Response({'error': str(e)}, status=500)


# ========== LEGACY DEPOSIT FUNCTIONS (Keep for compatibility) ==========
@api_view(['POST'])
def request_mpesa_deposit(request):
    """Legacy deposit endpoint"""
    return Response({'error': 'Please use the new deposit system'}, status=400)

@api_view(['POST'])
def verify_mpesa_payment(request):
    """Legacy verify endpoint"""
    return Response({'error': 'Please use the new deposit system'}, status=400)


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
    user_id = request.data.get('user_id')
    product_id = request.data.get('product_id')
    amount = Decimal(str(request.data.get('amount', 0)))
    
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
        now = timezone.now()
        
        investments = UserInvestment.objects.filter(
            user=user, 
            status='active',
            expiry_date__gt=now
        ).select_related('product')
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except Exception as e:
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
    
    return Response({
        'success': True,
        'investments': data,
        'total_daily_earnings': float(total_daily),
        'count': len(data)
    })

@api_view(['POST'])
def request_withdrawal(request):
    """Request a withdrawal with admin notification - Minimum 300 KES"""
    user_id = request.data.get('user_id')
    amount = Decimal(str(request.data.get('amount', 0)))
    phone_number = request.data.get('phone_number')
    
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
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_withdrawal_history(request):
    """Get user's complete withdrawal history"""
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
        
# ========== DAILY EARNINGS API ==========
@api_view(['GET', 'POST'])
def process_daily_earnings_api(request):
    """API endpoint to trigger daily earnings"""
    print("\n" + "="*60)
    print(f"🔄 DAILY EARNINGS PROCESSING STARTED")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    now = timezone.localtime(timezone.now())
    today = now.date()
    
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
    
    for investment in active_investments:
        already_earned_today = False
        if investment.last_earning_date:
            last_earning_local = timezone.localtime(investment.last_earning_date)
            if last_earning_local.date() == today:
                already_earned_today = True
        
        if already_earned_today:
            continue
        
        daily_earnings = investment.product.daily_earnings_amount if investment.product.daily_earnings_amount else Decimal('0')
        
        if daily_earnings > 0:
            investment.total_earned += daily_earnings
            investment.last_earning_date = timezone.now()
            investment.save()
            
            try:
                wallet = Wallet.objects.get(user=investment.user)
                wallet.balance += daily_earnings
                wallet.total_earned += daily_earnings
                wallet.save()
                
                total_earnings += daily_earnings
                processed += 1
                users_affected.add(investment.user.id)
                
                print(f"✅ {investment.user.username} earned KES {daily_earnings:,.2f}")
                
            except Wallet.DoesNotExist:
                print(f"❌ No wallet found for {investment.user.username}")
        
        if investment.expiry_date <= timezone.now():
            investment.status = 'completed'
            investment.save()
    
    if processed > 0:
        DailyEarningsLog.objects.create(
            total_earnings=total_earnings,
            users_affected=len(users_affected),
            investments_processed=processed
        )
    
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

# ========== GET REFERRAL INFO - FIXED URL (NO /signup) ==========
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
        
        # ========== FIXED: Removed /signup from URL ==========
        site_url = "https://senti-earn.onrender.com"
        referral_link = f"{site_url}/?ref={referral_code}"
        # ====================================================
        
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