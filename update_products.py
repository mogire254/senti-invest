import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from investments.models import InvestmentProduct

# Clear existing products
InvestmentProduct.objects.all().delete()

# New products with no gaps between levels
products = [
    # Level 1: Premium Watches ($520 - $1,000)
    {
        'name': 'Rolex Oyster Perpetual',
        'level': 'bronze',
        'min_investment': 520,
        'max_investment': 1000,
        'daily_earnings_amount': 15,  # $15 per day
        'duration_days': 30,
        'description': 'Luxury Rolex watch investment - earn $15 daily'
    },
    {
        'name': 'Omega Seamaster',
        'level': 'bronze',
        'min_investment': 650,
        'max_investment': 1000,
        'daily_earnings_amount': 18,
        'duration_days': 30,
        'description': 'Premium Omega watch - $18 daily returns'
    },
    {
        'name': 'Tag Heuer Carrera',
        'level': 'bronze',
        'min_investment': 800,
        'max_investment': 1000,
        'daily_earnings_amount': 22,
        'duration_days': 30,
        'description': 'Swiss luxury watch - $22 daily'
    },
    
    # Level 2: Luxury Handbags ($1,001 - $5,000)
    {
        'name': 'Hermès Birkin 35',
        'level': 'silver',
        'min_investment': 1001,
        'max_investment': 5000,
        'daily_earnings_amount': 50,
        'duration_days': 45,
        'description': 'Iconic Birkin bag - earn $50 daily'
    },
    {
        'name': 'Chanel Classic Flap',
        'level': 'silver',
        'min_investment': 1500,
        'max_investment': 5000,
        'daily_earnings_amount': 75,
        'duration_days': 45,
        'description': 'Timeless Chanel - $75 daily returns'
    },
    {
        'name': 'Louis Vuitton Capucines',
        'level': 'silver',
        'min_investment': 2000,
        'max_investment': 5000,
        'daily_earnings_amount': 100,
        'duration_days': 45,
        'description': 'LV masterpiece - $100 daily'
    },
    
    # Level 3: Luxury Cars ($5,001 - $25,000)
    {
        'name': 'Porsche 911 Turbo',
        'level': 'gold',
        'min_investment': 5001,
        'max_investment': 25000,
        'daily_earnings_amount': 300,
        'duration_days': 60,
        'description': 'German engineering - earn $300 daily'
    },
    {
        'name': 'Ferrari F8 Tributo',
        'level': 'gold',
        'min_investment': 10000,
        'max_investment': 25000,
        'daily_earnings_amount': 600,
        'duration_days': 60,
        'description': 'Italian supercar - $600 daily'
    },
    {
        'name': 'Lamborghini Huracan',
        'level': 'gold',
        'min_investment': 15000,
        'max_investment': 25000,
        'daily_earnings_amount': 900,
        'duration_days': 60,
        'description': 'Exotic Lamborghini - $900 daily'
    },
    
    # Level 4: Private Jets ($25,001 - $100,000)
    {
        'name': 'Gulfstream G650',
        'level': 'platinum',
        'min_investment': 25001,
        'max_investment': 100000,
        'daily_earnings_amount': 1500,
        'duration_days': 90,
        'description': 'Ultra-luxury jet - earn $1,500 daily'
    },
    {
        'name': 'Bombardier Global 7500',
        'level': 'platinum',
        'min_investment': 40000,
        'max_investment': 100000,
        'daily_earnings_amount': 2500,
        'duration_days': 90,
        'description': 'Long-range business jet - $2,500 daily'
    },
    {
        'name': 'Cessna Citation Longitude',
        'level': 'platinum',
        'min_investment': 60000,
        'max_investment': 100000,
        'daily_earnings_amount': 3500,
        'duration_days': 90,
        'description': 'Super-midsize jet - $3,500 daily'
    },
    
    # Level 5: Super Yachts ($100,001 - $500,000)
    {
        'name': 'Benetti Oasis 40M',
        'level': 'diamond',
        'min_investment': 100001,
        'max_investment': 500000,
        'daily_earnings_amount': 5000,
        'duration_days': 120,
        'description': 'Luxury superyacht - earn $5,000 daily'
    },
    {
        'name': 'Sunseeker 131 Yacht',
        'level': 'diamond',
        'min_investment': 200000,
        'max_investment': 500000,
        'daily_earnings_amount': 10000,
        'duration_days': 120,
        'description': 'British luxury yacht - $10,000 daily'
    },
    {
        'name': 'Lürssen Nordic',
        'level': 'diamond',
        'min_investment': 350000,
        'max_investment': 500000,
        'daily_earnings_amount': 17500,
        'duration_days': 120,
        'description': 'German mega yacht - $17,500 daily'
    },
    
    # Level 6: Private Islands ($500,001 - $2,000,000)
    {
        'name': 'Musha Cay Bahamas',
        'level': 'vip',
        'min_investment': 500001,
        'max_investment': 2000000,
        'daily_earnings_amount': 25000,
        'duration_days': 180,
        'description': 'Caribbean private island - earn $25,000 daily'
    },
    {
        'name': 'Necker Island',
        'level': 'vip',
        'min_investment': 1000000,
        'max_investment': 2000000,
        'daily_earnings_amount': 50000,
        'duration_days': 180,
        'description': 'Richard Branson\'s island - $50,000 daily'
    },
    {
        'name': 'Soneva Fushi',
        'level': 'vip',
        'min_investment': 1500000,
        'max_investment': 2000000,
        'daily_earnings_amount': 75000,
        'duration_days': 180,
        'description': 'Maldives paradise - $75,000 daily'
    },
]

def update_products():
    for product_data in products:
        product, created = InvestmentProduct.objects.get_or_create(
            name=product_data['name'],
            defaults={
                'level': product_data['level'],
                'min_investment': product_data['min_investment'],
                'max_investment': product_data['max_investment'],
                'daily_earnings_amount': product_data['daily_earnings_amount'],
                'duration_days': product_data['duration_days'],
                'description': product_data['description'],
                'is_active': True
            }
        )
        if created:
            print(f"✅ Added: {product.name} (${product.min_investment} - ${product.max_investment})")
        else:
            print(f"⚠️ Updated: {product.name}")

if __name__ == '__main__':
    update_products()
    print("\n" + "="*50)
    print("🎉 PRODUCTS UPDATED SUCCESSFULLY!")
    print("="*50)
    
    # Show summary by level
    levels = ['bronze', 'silver', 'gold', 'platinum', 'diamond', 'vip']
    level_names = {
        'bronze': '💎 Premium Watches ($520 - $1,000)',
        'silver': '👛 Luxury Handbags ($1,001 - $5,000)',
        'gold': '🏎️ Luxury Cars ($5,001 - $25,000)',
        'platinum': '✈️ Private Jets ($25,001 - $100,000)',
        'diamond': '⛵ Super Yachts ($100,001 - $500,000)',
        'vip': '🏝️ Private Islands ($500,001 - $2,000,000)'
    }
    
    for level in levels:
        count = InvestmentProduct.objects.filter(level=level).count()
        print(f"\n{level_names[level]}: {count} products")