from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import datetime, timedelta
import random
import string

class UserProfile(models.Model):
    ACCOUNT_STATUS = [
        ('active', 'Active'),
        ('pending_kyc', 'Pending KYC Verification'),
        ('under_review', 'Under Review'),
        ('frozen', 'Frozen'),
        ('banned', 'Banned'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, unique=True)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    id_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Referral fields
    referral_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    
    is_kyc_verified = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    account_status = models.CharField(max_length=20, choices=ACCOUNT_STATUS, default='pending_kyc')
    suspension_reason = models.TextField(blank=True, null=True)
    suspended_by = models.CharField(max_length=100, blank=True, null=True)
    suspended_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Password reset fields
    requires_password_reset = models.BooleanField(default=False)
    reset_token = models.CharField(max_length=100, blank=True, null=True)
    
    def generate_referral_code(self):
        """Generate unique referral code from phone number"""
        if not self.referral_code:
            phone_suffix = self.phone_number[-6:] if len(self.phone_number) >= 6 else self.phone_number
            random_suffix = random.randint(100, 999)
            self.referral_code = f"REF{phone_suffix}{random_suffix}"
        return self.referral_code
    
    def is_banned(self):
        return self.account_status == 'banned'
    
    def is_frozen(self):
        return self.account_status == 'frozen'
    
    def __str__(self):
        return f"{self.user.username} - {self.phone_number} ({'Approved' if self.is_approved else 'Pending'})"

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_deposited = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_invested = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    def __str__(self):
        return f"{self.user.username}: KES {self.balance}"

class InvestmentProduct(models.Model):
    LEVEL_CHOICES = [
        ('bronze', 'Bronze Level (KES 100-800)'),
        ('silver', 'Silver Level (KES 1,000-1,500)'),
        ('gold', 'Gold Level (KES 2,000-3,000)'),
        ('platinum', 'Platinum Level (KES 5,000-8,000)'),
        ('diamond', 'Diamond Level (KES 10,000-12,000)'),
        ('vip', 'VIP Level (KES 15,000-70,000)'),
    ]
    
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    min_investment = models.DecimalField(max_digits=10, decimal_places=2)
    max_investment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    daily_earnings_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duration_days = models.IntegerField(default=10)
    description = models.TextField(blank=True)
    image_url = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    
    def get_daily_earnings(self, investment_amount):
        if self.daily_earnings_amount:
            return self.daily_earnings_amount
        # Calculate based on level if no fixed amount
        if self.level == 'platinum' or self.level == 'diamond':
            # 5000-10000 level: 20% daily
            return investment_amount * Decimal('0.20')
        else:
            # 1000-3000 level: 10% daily
            return investment_amount * Decimal('0.10')
    
    def get_duration(self):
        """Return duration based on product level"""
        if self.level in ['platinum', 'diamond']:
            return 16  # 16 days for 5000-10000
        else:
            return 20  # 20 days for 1000-3000
    
    def __str__(self):
        return f"{self.name} - {self.get_level_display()} (KES {self.min_investment})"

class UserInvestment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investments')
    product = models.ForeignKey(InvestmentProduct, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    invested_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    total_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_earning_date = models.DateTimeField(null=True, blank=True)
    
    def calculate_daily_earnings(self):
        if self.status != 'active':
            return Decimal('0')
        return self.product.get_daily_earnings(self.amount)
    
    def get_duration_days(self):
        """Get duration for this investment"""
        if self.product:
            return self.product.get_duration()
        return 10  # default
    
    def days_remaining(self):
        """Calculate days remaining in investment"""
        if self.status != 'active' or not self.expiry_date:
            return 0
        now = timezone.now()
        if now >= self.expiry_date:
            return 0
        return (self.expiry_date - now).days
    
    def check_expiry(self):
        """Auto-expire investment when duration ends"""
        if self.status == 'active' and self.expiry_date:
            if timezone.now() >= self.expiry_date:
                self.status = 'completed'
                self.save()
                return True
        return False
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name} (KES {self.amount})"

class Deposit(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    VERIFICATION_STATUS = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('disputed', 'Disputed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    mpesa_receipt = models.CharField(max_length=50, blank=True, null=True)
    mpesa_message = models.TextField(blank=True, null=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    verified_by = models.CharField(max_length=100, blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - KES {self.amount} ({self.status})"

class Withdrawal(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - KES {self.amount} ({self.status})"

class DailyEarningsLog(models.Model):
    """Track daily earnings processing for admin"""
    processed_at = models.DateTimeField(auto_now_add=True)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    users_affected = models.IntegerField(default=0)
    investments_processed = models.IntegerField(default=0)
    
    def __str__(self):
        return f"📊 {self.processed_at.date()} - KES {self.total_earnings:,.2f} to {self.users_affected} users"

class Referral(models.Model):
    """Tracks who referred whom with deposit/investment status"""
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referred_user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referred_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    has_deposited = models.BooleanField(default=False)
    has_invested = models.BooleanField(default=False)
    bonus_given = models.BooleanField(default=False)
    bonus_given_at = models.DateTimeField(null=True, blank=True)
    first_deposit_date = models.DateTimeField(null=True, blank=True)
    first_investment_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        status = "✅" if self.bonus_given else "⏳" if (self.has_deposited and self.has_invested) else "📌"
        return f"{status} {self.referrer.username} → {self.referred_user.username}"

class ReferralBonus(models.Model):
    """Bonuses given to users for referrals"""
    STATUS_CHOICES = [
        ('pending', '⏳ Pending'),
        ('claimed', '✅ Claimed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referral_bonuses')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    referred_count = models.IntegerField(default=0, help_text="How many referrals triggered this bonus")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    
    referral_ids = models.TextField(blank=True, help_text="Comma-separated IDs of referrals that triggered this bonus")
    bonus_type = models.CharField(max_length=20, default='referral')
    
    def __str__(self):
        return f"{self.user.username} - KES {self.amount} ({self.status})"

class BalanceAdjustmentLog(models.Model):
    """Track admin balance adjustments"""
    ACTION_CHOICES = [
        ('add', 'Added'),
        ('subtract', 'Subtracted'),
        ('bonus', 'Bonus Added'),
        ('refund', 'Refund'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='balance_adjustments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason = models.TextField()
    previous_balance = models.DecimalField(max_digits=12, decimal_places=2)
    new_balance = models.DecimalField(max_digits=12, decimal_places=2)
    performed_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.action} KES {self.amount}"

class FraudLog(models.Model):
    ACTION_CHOICES = [
        ('deposit_verified', 'Deposit Verified'),
        ('deposit_rejected', 'Deposit Rejected'),
        ('account_frozen', 'Account Frozen'),
        ('account_unfrozen', 'Account Unfrozen'),
        ('account_banned', 'Account Banned'),
        ('account_unbanned', 'Account Unbanned'),
        ('investment_cancelled', 'Investment Cancelled'),
        ('balance_adjusted', 'Balance Adjusted'),
        ('withdrawal_approved', 'Withdrawal Approved'),
        ('withdrawal_rejected', 'Withdrawal Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fraud_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reason = models.TextField()
    performed_by = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class PasswordReset(models.Model):
    """Track password reset codes/tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_resets')
    code = models.CharField(max_length=200)  # UUID tokens for admin-generated links
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    
    def is_valid(self):
        """Code expires after 24 hours"""
        return not self.is_used and (datetime.now() - self.created_at) < timedelta(hours=24)
    
    def __str__(self):
        return f"{self.user.username} - {self.code[:30]}... ({'Used' if self.is_used else 'Active'})"

# ========== MAINTENANCE MODE MODEL ==========
class MaintenanceMode(models.Model):
    """Control system maintenance mode - when enabled, users cannot login"""
    is_enabled = models.BooleanField(default=False)
    message = models.TextField(default="We are currently performing system maintenance. Please check back shortly. We apologize for the inconvenience.")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"Maintenance: {'ON' if self.is_enabled else 'OFF'}"
    
    class Meta:
        verbose_name = "Maintenance Mode"
        verbose_name_plural = "Maintenance Mode"