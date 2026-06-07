from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from investments.models import UserInvestment, Wallet

class Command(BaseCommand):
    help = 'Process daily earnings for all active investments'

    def handle(self, *args, **options):
        print("\n" + "="*60)
        print("🔄 PROCESSING DAILY EARNINGS")
        print("="*60)
        
        now = timezone.now()
        today = now.date()
        
        # Get all active investments that haven't earned today
        investments = UserInvestment.objects.filter(
            status='active',
            expiry_date__gt=now
        ).exclude(
            last_earning_date__date=today
        ).select_related('product', 'user')
        
        print(f"📊 Found {investments.count()} investments to process\n")
        
        total_processed = 0
        total_earnings = Decimal('0')
        users_affected = set()
        
        for investment in investments:
            daily_earnings = investment.product.daily_earnings_amount or Decimal('0')
            
            if daily_earnings > 0:
                # Update investment total earned
                investment.total_earned += daily_earnings
                investment.last_earning_date = now
                investment.save()
                
                # Add to user's wallet
                wallet, created = Wallet.objects.get_or_create(user=investment.user)
                wallet.balance += daily_earnings
                wallet.total_earned += daily_earnings
                wallet.save()
                
                total_earnings += daily_earnings
                total_processed += 1
                users_affected.add(investment.user.id)
                
                print(f"✅ {investment.user.username} earned KES {daily_earnings:,.2f} from {investment.product.name}")
        
        print("\n" + "="*60)
        print("📊 DAILY EARNINGS SUMMARY")
        print("="*60)
        print(f"   ✅ Investments processed: {total_processed}")
        print(f"   👥 Users affected: {len(users_affected)}")
        print(f"   💰 Total earnings distributed: KES {total_earnings:,.2f}")
        print("="*60)
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully processed {total_processed} investments"))