from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import datetime, timedelta

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, unique=True)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    id_number = models.CharField(max_length=20, blank=True, null=True)
    is_kyc_verified = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.phone_number} ({'Approved' if self.is_approved else 'Pending'})"

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_deposited = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    def __str__(self):
        return f"{self.user.username}: KES {self.balance}"

class InvestmentProduct(models.Model):
    LEVEL_CHOICES = [
        ('bronze', 'Bronze Level (KES 520-800)'),
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
        return Decimal('0')
    
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
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name} (KES {self.amount})"

class Deposit(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    mpesa_receipt = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    
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