from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Wallet, InvestmentProduct, UserInvestment, Deposit, Withdrawal, DailyEarningsLog
from datetime import datetime

# ========== INLINE PROFILE ==========
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

# ========== CUSTOM USER ADMIN ==========
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'get_phone', 'get_full_name', 'get_balance', 'get_total_deposited', 
                   'get_total_earned', 'get_approval_status', 'get_active_investments', 'date_joined')
    list_filter = ('profile__is_approved', 'profile__is_kyc_verified', 'date_joined')
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
            if balance:
                return f"KES {int(balance):,}"
        return "KES 0"
    get_balance.short_description = '💰 Balance'
    
    def get_total_deposited(self, obj):
        if hasattr(obj, 'wallet') and obj.wallet:
            deposited = obj.wallet.total_deposited
            if deposited:
                return f"KES {int(deposited):,}"
        return "KES 0"
    get_total_deposited.short_description = '🏦 Deposited'
    
    def get_total_earned(self, obj):
        if hasattr(obj, 'wallet') and obj.wallet:
            earned = obj.wallet.total_earned
            if earned:
                return f"KES {int(earned):,}"
        return "KES 0"
    get_total_earned.short_description = '💰 Total Earned'
    
    def get_active_investments(self, obj):
        count = UserInvestment.objects.filter(user=obj, status='active').count()
        if count > 0:
            return f"✅ {count}"
        return "0"
    get_active_investments.short_description = '📈 Active Investments'
    
    def get_approval_status(self, obj):
        if hasattr(obj, 'profile'):
            if obj.profile.is_approved:
                return "✅ Approved"
            else:
                return "⏳ Pending"
        return "-"
    get_approval_status.short_description = '✅ Status'
    
    actions = ['approve_users', 'reject_users']
    
    def approve_users(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile'):
                user.profile.is_approved = True
                user.profile.save()
                count += 1
        self.message_user(request, f"✅ {count} users approved successfully!")
    approve_users.short_description = "Approve selected users"
    
    def reject_users(self, request, queryset):
        count = 0
        for user in queryset:
            if hasattr(user, 'profile'):
                user.profile.is_approved = False
                user.profile.save()
                count += 1
        self.message_user(request, f"❌ {count} users rejected.")
    reject_users.short_description = "Reject selected users"

# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# ========== USER PROFILE ADMIN ==========
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'full_name', 'is_approved', 'is_kyc_verified', 'created_at')
    list_filter = ('is_approved', 'is_kyc_verified')
    search_fields = ('phone_number', 'full_name', 'user__username')
    actions = ['approve_profiles', 'reject_profiles']
    
    def approve_profiles(self, request, queryset):
        count = queryset.update(is_approved=True)
        self.message_user(request, f"✅ {count} profiles approved!")
    approve_profiles.short_description = "Approve selected profiles"
    
    def reject_profiles(self, request, queryset):
        count = queryset.update(is_approved=False)
        self.message_user(request, f"❌ {count} profiles rejected.")
    reject_profiles.short_description = "Reject selected profiles"

# ========== WALLET ADMIN ==========
@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_balance_display', 'total_deposited', 'total_withdrawn', 'total_earned')
    search_fields = ('user__username',)
    readonly_fields = ('balance', 'total_deposited', 'total_withdrawn', 'total_earned')
    
    def get_balance_display(self, obj):
        if obj.balance:
            return f"KES {int(obj.balance):,}"
        return "KES 0"
    get_balance_display.short_description = '💰 Balance'

# ========== INVESTMENT PRODUCT ADMIN ==========
@admin.register(InvestmentProduct)
class InvestmentProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'min_investment', 'daily_earnings_amount', 'duration_days', 'is_active')
    list_filter = ('level', 'is_active')
    search_fields = ('name',)
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
    readonly_fields = ('total_earned', 'last_earning_date')
    
    def amount_display(self, obj):
        if obj.amount:
            return f"KES {int(obj.amount):,}"
        return "KES 0"
    amount_display.short_description = '💰 Amount'
    
    def daily_earnings_display(self, obj):
        daily = obj.calculate_daily_earnings()
        if daily:
            return f"KES {int(daily):,}"
        return "KES 0"
    daily_earnings_display.short_description = '📈 Daily Earnings'
    
    def total_earned_display(self, obj):
        if obj.total_earned:
            return f"KES {int(obj.total_earned):,}"
        return "KES 0"
    total_earned_display.short_description = '💰 Total Earned'
    
    def days_left(self, obj):
        days = (obj.expiry_date - datetime.now()).days
        if days > 0:
            return f"✅ {days} days"
        return "❌ Expired"
    days_left.short_description = '⏰ Days Left'

# ========== DEPOSIT ADMIN ==========
@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_display', 'phone_number', 'status_display', 'created_at', 'approved_at', 'approved_by')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'transaction_id', 'phone_number')
    actions = ['approve_deposits', 'reject_deposits']
    
    def amount_display(self, obj):
        if obj.amount:
            return f"KES {int(obj.amount):,}"
        return "KES 0"
    amount_display.short_description = '💰 Amount'
    
    def status_display(self, obj):
        status_map = {
            'pending': '⏳ Pending',
            'approved': '✅ Approved',
            'rejected': '❌ Rejected'
        }
        return status_map.get(obj.status, obj.status)
    status_display.short_description = '📌 Status'
    
    def approve_deposits(self, request, queryset):
        approved_count = 0
        for deposit in queryset:
            if deposit.status == 'pending':
                deposit.status = 'approved'
                deposit.approved_at = datetime.now()
                deposit.approved_by = request.user.username
                deposit.save()
                
                # Add to wallet
                wallet, created = Wallet.objects.get_or_create(user=deposit.user)
                wallet.balance += deposit.amount
                wallet.total_deposited += deposit.amount
                wallet.save()
                approved_count += 1
        self.message_user(request, f"✅ {approved_count} deposits approved! Funds added to wallets.")
    approve_deposits.short_description = "✅ Approve selected deposits"
    
    def reject_deposits(self, request, queryset):
        count = queryset.update(status='rejected')
        self.message_user(request, f"❌ {count} deposits rejected.")
    reject_deposits.short_description = "❌ Reject selected deposits"

# ========== WITHDRAWAL ADMIN ==========
@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_display', 'phone_number', 'status_display', 'created_at', 'approved_at', 'approved_by')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'phone_number')
    actions = ['approve_withdrawals', 'reject_withdrawals']
    
    def amount_display(self, obj):
        if obj.amount:
            return f"KES {int(obj.amount):,}"
        return "KES 0"
    amount_display.short_description = '💰 Amount'
    
    def status_display(self, obj):
        status_map = {
            'pending': '⏳ Pending',
            'approved': '✅ Approved',
            'rejected': '❌ Rejected'
        }
        return status_map.get(obj.status, obj.status)
    status_display.short_description = '📌 Status'
    
    def approve_withdrawals(self, request, queryset):
        approved_count = 0
        for withdrawal in queryset:
            if withdrawal.status == 'pending':
                withdrawal.status = 'approved'
                withdrawal.approved_at = datetime.now()
                withdrawal.approved_by = request.user.username
                withdrawal.save()
                
                # Deduct from wallet
                wallet = Wallet.objects.get(user=withdrawal.user)
                wallet.balance -= withdrawal.amount
                wallet.total_withdrawn += withdrawal.amount
                wallet.save()
                approved_count += 1
        self.message_user(request, f"✅ {approved_count} withdrawals approved! Amounts deducted from wallets.")
    approve_withdrawals.short_description = "✅ Approve selected withdrawals"
    
    def reject_withdrawals(self, request, queryset):
        count = 0
        for withdrawal in queryset:
            if withdrawal.status == 'pending':
                withdrawal.status = 'rejected'
                withdrawal.save()
                count += 1
        self.message_user(request, f"❌ {count} withdrawals rejected.")
    reject_withdrawals.short_description = "❌ Reject selected withdrawals"

# ========== DAILY EARNINGS LOG ADMIN ==========
@admin.register(DailyEarningsLog)
class DailyEarningsLogAdmin(admin.ModelAdmin):
    list_display = ('processed_at', 'users_affected', 'investments_processed', 'total_earnings_display')
    readonly_fields = ('processed_at', 'total_earnings', 'users_affected', 'investments_processed')
    
    def total_earnings_display(self, obj):
        if obj.total_earnings:
            return f"KES {int(obj.total_earnings):,}"
        return "KES 0"
    total_earnings_display.short_description = '💰 Total Earnings'