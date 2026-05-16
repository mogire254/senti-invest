import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from investments.models import InvestmentProduct

products = [
    # Level 1 - Bronze ($5 - $100)
    {
        'name': 'Dior Essentials Pack',
        'level': 'bronze',
        'min_investment': 5,
        'max_investment': 100,
        'daily_earnings_amount': 0.50,  # $0.50 per day = 10% return on $5
        'duration_days': 30,
        'description': 'Start your investment journey with Dior - earn $0.50 daily'
    },
    {
        'name': 'Chanel Beauty Fund',
        'level': 'bronze',
        'min_investment': 10,
        'max_investment': 100,
        'daily_earnings_amount': 1.00,  # $1 per day
        'duration_days': 30,
        'description': 'Invest in Chanel beauty products - $1 daily earnings'
    },
    
    # Level 2 - Silver ($100 - $500)
    {
        'name': 'Louis Vuitton Heritage',
        'level': 'silver',
        'min_investment': 100,
        'max_investment': 500,
        'daily_earnings_amount': 8.00,  # $8 per day
        'duration_days': 45,
        'description': 'Premium LV investment - $8 daily returns'
    },
    {
        'name': 'Gucci Signature Series',
        'level': 'silver',
        'min_investment': 200,
        'max_investment': 500,
        'daily_earnings_amount': 15.00,  # $15 per day
        'duration_days': 45,
        'description': 'Gucci luxury investment - earn $15 daily'
    },
    
    # Level 3 - Gold ($500 - $2,000)
    {
        'name': 'Rolex Presidential',
        'level': 'gold',
        'min_investment': 500,
        'max_investment': 2000,
        'daily_earnings_amount': 35.00,  # $35 per day
        'duration_days': 60,
        'description': 'Rolex watch investment - $35 daily earnings'
    },
    {
        'name': 'Cartier Love Collection',
        'level': 'gold',
        'min_investment': 1000,
        'max_investment': 2000,
        'daily_earnings_amount': 70.00,  # $70 per day
        'duration_days': 60,
        'description': 'Cartier jewelry investment - $70 daily'
    },
    
    # Level 4 - Platinum ($2,000 - $10,000)
    {
        'name': 'Patek Philippe Grand',
        'level': 'platinum',
        'min_investment': 2000,
        'max_investment': 10000,
        'daily_earnings_amount': 150.00,  # $150 per day
        'duration_days': 90,
        'description': 'Patek Philippe investment - $150 daily'
    },
    {
        'name': 'Hermes Birkin Collection',
        'level': 'platinum',
        'min_investment': 5000,
        'max_investment': 10000,
        'daily_earnings_amount': 350.00,  # $350 per day
        'duration_days': 90,
        'description': 'Hermes Birkin bag investment - $350 daily'
    },
    
    # Level 5 - Diamond ($10,000 - $50,000)
    {
        'name': 'Bentley Motors Fund',
        'level': 'diamond',
        'min_investment': 10000,
        'max_investment': 50000,
        'daily_earnings_amount': 800.00,  # $800 per day
        'duration_days': 120,
        'description': 'Bentley luxury car investment - $800 daily'
    },
    {
        'name': 'Ferrari Limited Edition',
        'level': 'diamond',
        'min_investment': 25000,
        'max_investment': 50000,
        'daily_earnings_amount': 2000.00,  # $2,000 per day
        'duration_days': 120,
        'description': 'Ferrari investment - $2,000 daily returns'
    },
    
    # Level 6 - VIP ($50,000+)
    {
        'name': 'Private Jet Portfolio',
        'level': 'vip',
        'min_investment': 50000,
        'max_investment': None,
        'daily_earnings_amount': 5000.00,  # $5,000 per day
        'duration_days': 180,
        'description': 'VIP private jet investment - $5,000 daily'
    },
    {
        'name': 'Luxury Yacht Fund',
        'level': 'vip',
        'min_investment': 100000,
        'max_investment': None,
        'daily_earnings_amount': 10000.00,  # $10,000 per day
        'duration_days': 180,
        'description': 'Super yacht investment - $10,000 daily'
    },
]

def add_products():
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
            print(f"✅ Added product: {product.name}")
        else:
            print(f"⚠️ Product already exists: {product.name}")

if __name__ == '__main__':
    add_products()
    print("\n🎉 All products added successfully!")