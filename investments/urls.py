from django.urls import path
from . import views

urlpatterns = [
    # Test endpoint
    path('api/test/', views.test_api, name='test-api'),
    
    # Authentication
    path('api/signup/', views.signup, name='signup'),
    path('api/login/', views.login_view, name='login'),
    
    # Products and Investments
    path('api/products/', views.get_products, name='products'),
    path('api/invest/', views.invest_product, name='invest'),
    path('api/my-investments/', views.get_user_investments, name='my-investments'),
    
    # Wallet and Transactions
    path('api/wallet/', views.get_wallet, name='wallet'),
    path('api/withdraw/', views.request_withdrawal, name='withdraw'),
    
    # M-Pesa Deposit
    path('api/mpesa-deposit/', views.request_mpesa_deposit, name='mpesa-deposit'),
    path('api/verify-payment/', views.verify_mpesa_payment, name='verify-payment'),
    
    # Daily Earnings
    path('api/process-daily-earnings/', views.process_daily_earnings_api, name='process-daily'),
]