import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from investments.models import UserInvestment, Wallet, DailyEarningsLog

def process_daily_earnings():
    """Run this script every 24 hours to add earnings to user balances"""
    
    print("="*60)
    print(f"🚀 SENTI INVEST - DAILY EARNINGS PROCESSOR")
    print(f"⏰ Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Get all active investments
    active_investments = UserInvestment.objects.filter(status='active')
    
    total_earnings = Decimal('0')
    processed_investments = 0
    users_affected = set()
    
    print(f"\n📊 Found {active_investments.count()} active investments")
    print("-"*60)
    
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
                processed_investments += 1
                users_affected.add(investment.user.id)
                
                print(f"✅ {investment.user.username} earned KES {daily_earnings:,.2f} from {investment.product.name}")
                print(f"   📈 New balance: KES {wallet.balance:,.2f}")
                
            except Wallet.DoesNotExist:
                print(f"❌ No wallet found for {investment.user.username}")
        
        # Check if investment has expired
        if investment.expiry_date <= datetime.now():
            investment.status = 'completed'
            investment.save()
            print(f"🎉 INVESTMENT COMPLETED: {investment.product.name} for {investment.user.username}")
    
    # Create log entry
    log = DailyEarningsLog.objects.create(
        total_earnings=total_earnings,
        users_affected=len(users_affected),
        investments_processed=processed_investments
    )
    
    print("-"*60)
    print(f"\n📊 SUMMARY REPORT")
    print("="*60)
    print(f"   ✅ Investments processed today: {processed_investments}")
    print(f"   👥 Users affected: {len(users_affected)}")
    print(f"   💰 Total earnings distributed: KES {total_earnings:,.2f}")
    print(f"   📝 Log ID: {log.id}")
    print(f"   ⏰ Processing time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    return processed_investments, total_earnings

if __name__ == '__main__':
    process_daily_earnings()