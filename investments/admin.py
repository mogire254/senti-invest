from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.contrib import messages
from django.utils import timezone
from django.urls import path
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from .models import UserProfile, Wallet, InvestmentProduct, UserInvestment, Deposit, Withdrawal, DailyEarningsLog, Referral, ReferralBonus, FraudLog, PasswordReset, BalanceAdjustmentLog, MaintenanceMode
from datetime import datetime
from decimal import Decimal
import uuid

# ========== INLINE PROFILE ==========
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

# ========== CUSTOM USER ADMIN ==========
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'get_phone', 'get_full_name', 'get_balance', 'get_total_deposited', 
                   'get_total_earned', 'get_approval_status', 'get_account_status', 'get_active_investments', 'date_joined')
    list_filter = ('profile__is_approved', 'profile__account_status', 'profile__is_kyc_verified', 'date_joined')
    search_fields = ('username', 'profile__phone_number', 'profile__full_name')
    
    def get_phone(self, obj):
        return obj.profile.phone_number if hasattr(obj, 'profile') else '-'
    get_phone.short_description = '📱 Phone'
    
    def get_full_name(self, obj):
        return obj.profile.full_name if hasattr(obj, 'profile') else '-'
    get_full_name.short_description = '👤 Full Name'
    
    def get_balance(self, obj):
        if hasattr(obj, 'wallet') and obj.wallet:
            balance = obj.wallet.balance
            return f"KES {int(balance):,}" if balance else "KES 0"
        return "KES 0"
    get_balance.short_description = '💰 Balance'
    
    def get_total_deposited(self, obj):
        if hasattr(obj, 'wallet') and obj.wallet:
            deposited = obj.wallet.total_deposited
            return f"KES {int(deposited):,}" if deposited else "KES 0"
        return "KES 0"
    get_total_deposited.short_description = '🏦 Deposited'
    
    def get_total_earned(self, obj):
        if hasattr(obj, 'wallet') and obj.wallet:
            earned = obj.wallet.total_earned
            return f"KES {int(earned):,}" if earned else "KES 0"
        return "KES 0"
    get_total_earned.short_description = '💰 Total Earned'
    
    def get_active_investments(self, obj):
        count = UserInvestment.objects.filter(user=obj, status='active').count()
        return f"✅ {count}" if count > 0 else "0"
    get_active_investments.short_description = '📈 Active Investments'
    
    def get_approval_status(self, obj):
        if hasattr(obj, 'profile'):
            if obj.profile.is_approved:
                return "✅ Approved"
            else:
                return "⏳ Pending"
        return "-"
    get_approval_status.short_description = '✅ Approval'
    
    def get_account_status(self, obj):
        if hasattr(obj, 'profile'):
            status_map = {
                'active': '🟢 Active',
                'pending_kyc': '🟡 Pending KYC',
                'under_review': '🟠 Under Review',
                'frozen': '❄️ Frozen',
                'banned': '🚫 Banned',
            }
            return status_map.get(obj.profile.account_status, obj.profile.get_account_status_display())
        return '-'
    get_account_status.short_description = '🔒 Account Status'
    
    actions = ['approve_users', 'reject_users', 'freeze_users', 'unfreeze_users', 'ban_users', 'unban_users', 'delete_selected_users', 'force_password_reset']
    
    def approve_users(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile') and not user.profile.is_approved:
                user.profile.is_approved = True
                user.profile.account_status = 'active'
                user.profile.save()
                
                FraudLog.objects.create(
                    user=user,
                    action='account_unfrozen',
                    reason=f'Account approved by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"✅ {count} users approved successfully!", messages.SUCCESS)
    approve_users.short_description = "✅ Approve selected users"
    
    def reject_users(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile'):
                user.profile.is_approved = False
                user.profile.save()
                count += 1
        self.message_user(request, f"❌ {count} users rejected.", messages.WARNING)
    reject_users.short_description = "❌ Reject selected users"
    
    def freeze_users(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile') and user.profile.account_status != 'frozen':
                user.profile.account_status = 'frozen'
                user.profile.suspended_by = request.user.username
                user.profile.suspended_at = timezone.now()
                user.profile.save()
                
                FraudLog.objects.create(
                    user=user,
                    action='account_frozen',
                    reason=f'Account frozen by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"❄️ {count} users frozen!", messages.WARNING)
    freeze_users.short_description = "❄️ Freeze selected users"
    
    def unfreeze_users(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile') and user.profile.account_status == 'frozen':
                user.profile.account_status = 'active'
                user.profile.save()
                
                FraudLog.objects.create(
                    user=user,
                    action='account_unfrozen',
                    reason=f'Account unfrozen by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"✅ {count} users unfrozen!", messages.SUCCESS)
    unfreeze_users.short_description = "✅ Unfreeze selected users"
    
    def ban_users(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile') and user.profile.account_status != 'banned':
                user.profile.account_status = 'banned'
                user.profile.is_approved = False
                user.profile.suspended_by = request.user.username
                user.profile.suspended_at = timezone.now()
                user.profile.save()
                
                FraudLog.objects.create(
                    user=user,
                    action='account_banned',
                    reason=f'Account banned by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"🚫 {count} users banned!", messages.ERROR)
    ban_users.short_description = "🚫 Ban selected users"
    
    def unban_users(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile') and user.profile.account_status == 'banned':
                user.profile.account_status = 'active'
                user.profile.is_approved = True
                user.profile.save()
                
                FraudLog.objects.create(
                    user=user,
                    action='account_unbanned',
                    reason=f'Account unbanned by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"✅ {count} users unbanned!", messages.SUCCESS)
    unban_users.short_description = "✅ Unban selected users"
    
    def delete_selected_users(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile'):
                user.profile.delete()
            if hasattr(user, 'wallet'):
                user.wallet.delete()
            user.delete()
            count += 1
        self.message_user(request, f"🗑️ {count} users deleted permanently!", messages.ERROR)
    delete_selected_users.short_description = "🗑️ Delete selected users"
    
    def force_password_reset(self, request, queryset):
        for user in queryset:
            if hasattr(user, 'profile'):
                reset_token = str(uuid.uuid4()) + str(uuid.uuid4())
                
                PasswordReset.objects.create(
                    user=user,
                    code=reset_token,
                    is_used=False
                )
                
                profile = user.profile
                profile.requires_password_reset = True
                profile.reset_token = reset_token
                profile.save()
                
                reset_link = f"https://senti-invest.onrender.com/reset-password/{reset_token}/"
                
                self.message_user(
                    request,
                    f"🔑 Password reset for {user.username} - Link: {reset_link}",
                    messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    f"❌ No profile found for {user.username}",
                    messages.ERROR
                )
    force_password_reset.short_description = "🔑 Force password reset (generate link)"

# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# ========== USER PROFILE ADMIN ==========
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'full_name', 'is_approved', 'account_status', 'requires_password_reset', 'is_kyc_verified', 'referral_code', 'created_at')
    list_filter = ('is_approved', 'account_status', 'requires_password_reset', 'is_kyc_verified')
    search_fields = ('phone_number', 'full_name', 'user__username', 'referral_code')
    list_editable = ('is_approved', 'account_status')
    readonly_fields = ('referral_code', 'created_at', 'reset_token')
    actions = ['approve_profiles', 'reject_profiles', 'freeze_profiles', 'unfreeze_profiles', 'ban_profiles', 'unban_profiles', 'force_password_reset_profiles']
    
    def approve_profiles(self, request, queryset):
        count = queryset.update(is_approved=True, account_status='active')
        self.message_user(request, f"✅ {count} profiles approved!", messages.SUCCESS)
    approve_profiles.short_description = "✅ Approve selected profiles"
    
    def reject_profiles(self, request, queryset):
        count = queryset.update(is_approved=False)
        self.message_user(request, f"❌ {count} profiles rejected.", messages.WARNING)
    reject_profiles.short_description = "❌ Reject selected profiles"
    
    def freeze_profiles(self, request, queryset):
        count = 0
        for profile in queryset:
            if profile.account_status != 'frozen':
                profile.account_status = 'frozen'
                profile.suspended_by = request.user.username
                profile.suspended_at = timezone.now()
                profile.save()
                
                FraudLog.objects.create(
                    user=profile.user,
                    action='account_frozen',
                    reason=f'Account frozen by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"❄️ {count} profiles frozen!", messages.WARNING)
    freeze_profiles.short_description = "❄️ Freeze selected profiles"
    
    def unfreeze_profiles(self, request, queryset):
        count = 0
        for profile in queryset:
            if profile.account_status == 'frozen':
                profile.account_status = 'active'
                profile.save()
                
                FraudLog.objects.create(
                    user=profile.user,
                    action='account_unfrozen',
                    reason=f'Account unfrozen by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"✅ {count} profiles unfrozen!", messages.SUCCESS)
    unfreeze_profiles.short_description = "✅ Unfreeze selected profiles"
    
    def ban_profiles(self, request, queryset):
        count = 0
        for profile in queryset:
            if profile.account_status != 'banned':
                profile.account_status = 'banned'
                profile.is_approved = False
                profile.suspended_by = request.user.username
                profile.suspended_at = timezone.now()
                profile.save()
                
                FraudLog.objects.create(
                    user=profile.user,
                    action='account_banned',
                    reason=f'Account banned by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"🚫 {count} profiles banned!", messages.ERROR)
    ban_profiles.short_description = "🚫 Ban selected profiles"
    
    def unban_profiles(self, request, queryset):
        count = 0
        for profile in queryset:
            if profile.account_status == 'banned':
                profile.account_status = 'active'
                profile.is_approved = True
                profile.save()
                
                FraudLog.objects.create(
                    user=profile.user,
                    action='account_unbanned',
                    reason=f'Account unbanned by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"✅ {count} profiles unbanned!", messages.SUCCESS)
    unban_profiles.short_description = "✅ Unban selected profiles"
    
    def force_password_reset_profiles(self, request, queryset):
        for profile in queryset:
            reset_token = str(uuid.uuid4()) + str(uuid.uuid4())
            
            PasswordReset.objects.create(
                user=profile.user,
                code=reset_token,
                is_used=False
            )
            
            profile.requires_password_reset = True
            profile.reset_token = reset_token
            profile.save()
            
            reset_link = f"https://senti-invest.onrender.com/reset-password/{reset_token}/"
            
            self.message_user(
                request,
                f"🔑 Reset link for {profile.phone_number}: {reset_link}",
                messages.SUCCESS
            )
    force_password_reset_profiles.short_description = "🔑 Force password reset (generate link)"

# ========== WALLET ADMIN - FIXED TO ALLOW EDITING ==========
@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_balance_display', 'total_deposited', 'total_withdrawn', 'total_earned', 'total_invested')
    search_fields = ('user__username',)
    # REMOVED readonly_fields to allow editing of all fields
    fields = ('user', 'balance', 'total_deposited', 'total_withdrawn', 'total_earned', 'total_invested')
    
    def get_balance_display(self, obj):
        return f"KES {int(obj.balance):,}" if obj.balance else "KES 0"
    get_balance_display.short_description = '💰 Balance'

# ========== INVESTMENT PRODUCT ADMIN ==========
@admin.register(InvestmentProduct)
class InvestmentProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'min_investment', 'daily_earnings_amount', 'duration_days', 'is_active')
    list_filter = ('level', 'is_active')
    search_fields = ('name',)
    list_editable = ('daily_earnings_amount', 'duration_days', 'is_active')
    actions = ['activate_products', 'deactivate_products']
    
    def activate_products(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"✅ {count} products activated!")
    activate_products.short_description = "Activate selected products"
    
    def deactivate_products(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"❌ {count} products deactivated.")
    deactivate_products.short_description = "Deactivate selected products"

# ========== USER INVESTMENT ADMIN ==========
@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'amount_display', 'daily_earnings_display', 'total_earned_display', 'status', 'days_left', 'invested_at')
    list_filter = ('status', 'product__level')
    search_fields = ('user__username', 'product__name')
    actions = ['cancel_investments']
    
    def amount_display(self, obj):
        return f"KES {int(obj.amount):,}" if obj.amount else "KES 0"
    amount_display.short_description = '💰 Amount'
    
    def daily_earnings_display(self, obj):
        daily = obj.calculate_daily_earnings()
        return f"KES {int(daily):,}" if daily else "KES 0"
    daily_earnings_display.short_description = '📈 Daily Earnings'
    
    def total_earned_display(self, obj):
        return f"KES {int(obj.total_earned):,}" if obj.total_earned else "KES 0"
    total_earned_display.short_description = '💰 Total Earned'
    
    def days_left(self, obj):
        if obj.expiry_date and obj.status == 'active':
            now = timezone.now()
            if obj.expiry_date > now:
                days = (obj.expiry_date - now).days
                return f"✅ {days} days"
            return "❌ Expired"
        return "N/A"
    days_left.short_description = '⏰ Days Left'
    
    def cancel_investments(self, request, queryset):
        count = 0
        for investment in queryset:
            if investment.status == 'active':
                investment.status = 'cancelled'
                investment.save()
                
                wallet = Wallet.objects.get(user=investment.user)
                wallet.balance += investment.amount
                wallet.total_withdrawn += investment.amount
                wallet.save()
                
                FraudLog.objects.create(
                    user=investment.user,
                    action='investment_cancelled',
                    amount=investment.amount,
                    reason=f'Investment cancelled by admin {request.user.username}',
                    performed_by=request.user.username
                )
                count += 1
        self.message_user(request, f"🔄 {count} investments cancelled and refunded!")
    cancel_investments.short_description = "Cancel selected investments (refund to wallet)"

# ========== DEPOSIT ADMIN ==========
@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_display', 'transaction_id', 'verification_status', 'status', 'created_at')
    list_filter = ('verification_status', 'status', 'created_at')
    search_fields = ('user__username', 'transaction_id')
    actions = ['approve_deposits_action', 'reject_deposits_action']
    
    def amount_display(self, obj):
        return f"KES {int(obj.amount):,}" if obj.amount else "KES 0"
    amount_display.short_description = '💰 Amount'
    
    def approve_deposits_action(self, request, queryset):
        """Approve selected deposits - ADD MONEY to user wallet"""
        approved_count = 0
        for deposit in queryset.filter(verification_status='pending_admin_approval'):
            # Add money to wallet
            wallet, created = Wallet.objects.get_or_create(user=deposit.user)
            wallet.balance += deposit.amount
            wallet.total_deposited += deposit.amount
            wallet.save()
            
            deposit.verification_status = 'approved'
            deposit.status = 'approved'
            deposit.approved_at = timezone.now()
            deposit.approved_by = request.user.username
            deposit.save()
            
            FraudLog.objects.create(
                user=deposit.user,
                action='deposit_verified',
                amount=deposit.amount,
                reason=f'Deposit approved by admin {request.user.username}. Transaction ID: {deposit.transaction_id}',
                performed_by=request.user.username
            )
            approved_count += 1
            self.message_user(request, f"✅ Deposit of KES {deposit.amount} approved for {deposit.user.username} - Money added to wallet", messages.SUCCESS)
        
        if approved_count == 0:
            self.message_user(request, f"ℹ️ No deposits pending admin approval selected. Only deposits with 'pending_admin_approval' status can be approved.", messages.INFO)
        else:
            self.message_user(request, f"✅ {approved_count} deposit(s) approved successfully!", messages.SUCCESS)
    approve_deposits_action.short_description = "✅ Approve selected deposits (ADD MONEY to wallet)"
    
    def reject_deposits_action(self, request, queryset):
        """Reject selected deposits - NO MONEY added to wallet (or deduct if already approved)"""
        rejected_count = 0
        for deposit in queryset:
            # If deposit was already approved, deduct the amount
            if deposit.verification_status == 'approved':
                try:
                    wallet = Wallet.objects.get(user=deposit.user)
                    if wallet.balance >= deposit.amount:
                        wallet.balance -= deposit.amount
                        wallet.total_deposited -= deposit.amount
                        wallet.save()
                        self.message_user(request, f"💰 Reversed KES {deposit.amount} from {deposit.user.username}'s wallet", messages.WARNING)
                    else:
                        self.message_user(request, f"⚠️ Insufficient balance to deduct KES {deposit.amount} from {deposit.user.username}", messages.ERROR)
                except Wallet.DoesNotExist:
                    pass
            
            # Update deposit status to rejected
            deposit.verification_status = 'rejected'
            deposit.status = 'rejected'
            deposit.rejection_reason = f'Rejected by admin {request.user.username}'
            deposit.save()
            
            FraudLog.objects.create(
                user=deposit.user,
                action='deposit_rejected',
                amount=deposit.amount,
                reason=f'Deposit rejected by admin {request.user.username}. Transaction ID: {deposit.transaction_id}',
                performed_by=request.user.username
            )
            rejected_count += 1
            self.message_user(request, f"❌ Deposit of KES {deposit.amount} REJECTED for {deposit.user.username}", messages.WARNING)
        
        self.message_user(request, f"❌ {rejected_count} deposit(s) rejected!", messages.WARNING)
    reject_deposits_action.short_description = "❌ Reject selected deposits (NO money added or deduct if approved)"

# ========== WITHDRAWAL ADMIN ==========
@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_display', 'phone_number', 'status', 'created_at', 'approved_at', 'approved_by')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'phone_number')
    actions = ['approve_withdrawals', 'reject_withdrawals']
    
    def amount_display(self, obj):
        return f"KES {int(obj.amount):,}" if obj.amount else "KES 0"
    amount_display.short_description = '💰 Amount'
    
    def approve_withdrawals(self, request, queryset):
        pending_withdrawals = queryset.filter(status='pending')
        approved_count = 0
        skipped_count = queryset.count() - pending_withdrawals.count()
        
        for withdrawal in pending_withdrawals:
            withdrawal.status = 'approved'
            withdrawal.approved_at = timezone.now()
            withdrawal.approved_by = request.user.username
            withdrawal.save()
            
            FraudLog.objects.create(
                user=withdrawal.user,
                action='withdrawal_approved',
                amount=withdrawal.amount,
                reason=f'Withdrawal approved by admin {request.user.username}',
                performed_by=request.user.username
            )
            approved_count += 1
            self.message_user(request, f"✅ Withdrawal of KES {withdrawal.amount} approved for {withdrawal.user.username}", messages.SUCCESS)
        
        if skipped_count > 0:
            self.message_user(request, f"⚠️ Skipped {skipped_count} withdrawals (already approved/rejected)", messages.WARNING)
        
        if approved_count > 0:
            self.message_user(request, f"✅ {approved_count} withdrawals approved successfully!", messages.SUCCESS)
        else:
            self.message_user(request, f"ℹ️ No pending withdrawals selected. Only pending withdrawals can be approved.", messages.INFO)
    approve_withdrawals.short_description = "✅ Approve selected withdrawals (pending only)"
    
    def reject_withdrawals(self, request, queryset):
        pending_withdrawals = queryset.filter(status='pending')
        rejected_count = 0
        skipped_count = queryset.count() - pending_withdrawals.count()
        
        for withdrawal in pending_withdrawals:
            withdrawal.status = 'rejected'
            withdrawal.save()
            
            try:
                wallet = Wallet.objects.get(user=withdrawal.user)
                wallet.balance += withdrawal.amount
                wallet.total_withdrawn -= withdrawal.amount
                wallet.save()
                
                FraudLog.objects.create(
                    user=withdrawal.user,
                    action='withdrawal_rejected',
                    amount=withdrawal.amount,
                    reason=f'Withdrawal rejected by admin {request.user.username} - Money refunded',
                    performed_by=request.user.username
                )
                rejected_count += 1
                self.message_user(request, f"❌ Withdrawal of KES {withdrawal.amount} rejected and REFUNDED to {withdrawal.user.username}", messages.WARNING)
            except Wallet.DoesNotExist:
                self.message_user(request, f"⚠️ Wallet not found for {withdrawal.user.username}", messages.ERROR)
        
        if skipped_count > 0:
            self.message_user(request, f"⚠️ Skipped {skipped_count} withdrawals (already approved/rejected)", messages.WARNING)
        
        if rejected_count > 0:
            self.message_user(request, f"❌ {rejected_count} withdrawals rejected and refunded!", messages.WARNING)
        else:
            self.message_user(request, f"ℹ️ No pending withdrawals selected. Only pending withdrawals can be rejected.", messages.INFO)
    reject_withdrawals.short_description = "❌ Reject selected withdrawals (pending only - refunds money)"

# ========== DAILY EARNINGS LOG ADMIN ==========
@admin.register(DailyEarningsLog)
class DailyEarningsLogAdmin(admin.ModelAdmin):
    list_display = ('processed_at', 'users_affected', 'investments_processed', 'total_earnings_display')
    readonly_fields = ('processed_at', 'total_earnings', 'users_affected', 'investments_processed')
    
    def total_earnings_display(self, obj):
        return f"KES {int(obj.total_earnings):,}" if obj.total_earnings else "KES 0"
    total_earnings_display.short_description = '💰 Total Earnings'

# ========== REFERRAL ADMIN ==========
@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred_user', 'has_deposited', 'has_invested', 'bonus_given', 'created_at')
    list_filter = ('has_deposited', 'has_invested', 'bonus_given', 'created_at')
    search_fields = ('referrer__username', 'referred_user__username')

@admin.register(ReferralBonus)
class ReferralBonusAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'referred_count', 'status', 'bonus_type', 'created_at')
    list_filter = ('status', 'bonus_type', 'created_at')
    search_fields = ('user__username',)
    actions = ['approve_bonuses', 'check_qualification']
    
    def approve_bonuses(self, request, queryset):
        approved_count = 0
        for bonus in queryset.filter(status='pending'):
            bonus.status = 'claimed'
            bonus.claimed_at = timezone.now()
            bonus.approved_by = request.user.username
            bonus.save()
            
            if bonus.referral_ids:
                referral_ids = [int(x) for x in bonus.referral_ids.split(',') if x]
                Referral.objects.filter(id__in=referral_ids).update(
                    bonus_given=True,
                    bonus_given_at=timezone.now()
                )
            
            wallet, created = Wallet.objects.get_or_create(user=bonus.user)
            wallet.balance += bonus.amount
            wallet.save()
            
            approved_count += 1
        self.message_user(request, f"✅ {approved_count} bonuses approved and added to wallets!")
    approve_bonuses.short_description = "✅ Approve selected bonuses"
    
    def check_qualification(self, request, queryset):
        for user in queryset:
            qualified_count = Referral.objects.filter(
                referrer=user,
                has_deposited=True,
                has_invested=True,
                bonus_given=False
            ).count()
            self.message_user(request, f"{user.username} has {qualified_count} qualified referrals")
    check_qualification.short_description = "Check qualification for selected users"

# ========== BALANCE ADJUSTMENT LOG ADMIN ==========
@admin.register(BalanceAdjustmentLog)
class BalanceAdjustmentLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'action', 'performed_by', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'reason')
    readonly_fields = ('created_at',)

# ========== FRAUD LOG ADMIN ==========
@admin.register(FraudLog)
class FraudLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'amount_display', 'performed_by', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'reason')
    readonly_fields = ('created_at',)
    
    def amount_display(self, obj):
        return f"KES {int(obj.amount):,}" if obj.amount else "KES 0"
    amount_display.short_description = '💰 Amount'

# ========== PASSWORD RESET ADMIN ==========
@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'created_at', 'is_used')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__username', 'code')

# ========== MAINTENANCE MODE ADMIN ==========
@admin.register(MaintenanceMode)
class MaintenanceModeAdmin(admin.ModelAdmin):
    list_display = ('is_enabled', 'updated_at', 'updated_by')
    fields = ('is_enabled', 'message')
    readonly_fields = ('updated_at',)
    
    def save_model(self, request, obj, form, change):
        if obj.is_enabled:
            obj.updated_by = request.user.username
        obj.save()
        
    def has_add_permission(self, request):
        return not MaintenanceMode.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False