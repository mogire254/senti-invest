import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from investments.models import UserInvestment, Wallet

def process_daily_earnings():
    """
    Run this script daily to add earnings to user balances (10-day investment cycle)
    """
    print("="*60)
    print(f"🚀 SENTI INVEST - DAILY EARNINGS PROCESSOR")
    print(f"⏰ Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Get all active investments
    active_investments = UserInvestment.objects.filter(status='active')
    
    total_processed = 0
    total_earnings = Decimal('0')
    
    print(f"\n📊 Found {active_investments.count()} active investments")
    print("-"*60)
    
    for investment in active_investments:
        # Check if we already processed today
        today = datetime.now().date()
        if investment.last_earning_date and investment.last_earning_date.date() == today:
            print(f"⏭️  Already processed today: {investment.product.name} for {investment.user.username}")
            continue
        
        # Calculate daily earnings (in KES)
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
                total_processed += 1
                
                # Calculate days remaining
                days_remaining = (investment.expiry_date - datetime.now()).days
                
                print(f"✅ {investment.user.username} earned KES {daily_earnings:,.2f} from {investment.product.name}")
                print(f"   📈 Investment: KES {investment.amount:,.0f} | Days left: {days_remaining} | Total earned: KES {investment.total_earned:,.2f}")
                
            except Wallet.DoesNotExist:
                print(f"❌ No wallet found for {investment.user.username}")
        
        # Check if investment has expired (after 10 days)
        if investment.expiry_date <= datetime.now():
            investment.status = 'completed'
            investment.save()
            print(f"🎉 INVESTMENT COMPLETED: {investment.product.name} for {investment.user.username}")
            print(f"   💰 Final return: KES {investment.total_earned:,.2f}")
    
    print("-"*60)
    print(f"\n📊 SUMMARY REPORT")
    print("="*60)
    print(f"   ✅ Investments processed today: {total_processed}")
    print(f"   💰 Total earnings distributed: KES {total_earnings:,.2f}")
    print(f"   ⏰ Processing time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    return total_processed, total_earnings

if __name__ == '__main__':
    process_daily_earnings()