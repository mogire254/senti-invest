from django.urls import path
from . import views

urlpatterns = [
    # Test endpoint
    path('api/test/', views.test_api, name='test-api'),
    
    # Maintenance Mode
    path('api/check-maintenance/', views.check_maintenance_status, name='check-maintenance'),
    
    # Authentication
    path('api/signup/', views.signup, name='signup'),
    path('api/login/', views.login_view, name='login'),
    
    # Forgot Password - TWO WAYS (User requests, Admin generates)
    path('api/forgot-password-request/', views.forgot_password_request, name='forgot-password-request'),
    path('api/check-reset-token/', views.check_reset_token, name='check-reset-token'),
    path('api/reset-password-with-token/', views.reset_password_with_token, name='reset-password-with-token'),
    path('api/admin-generate-reset-link/', views.admin_generate_reset_link, name='admin-generate-reset-link'),
    
    # Password Reset Page (Admin initiated - no code)
    path('reset-password/<str:token>/', views.password_reset_page, name='password-reset-page'),
    
    # Account Status
    path('api/check-account-status/', views.check_account_status, name='check-account-status'),
    path('api/request-unban/', views.request_unban, name='request-unban'),
    
    # Products and Investments
    path('api/products/', views.get_products, name='products'),
    path('api/invest/', views.invest_product, name='invest'),
    path('api/my-investments/', views.get_user_investments, name='my-investments'),
    
    # Wallet and Transactions
    path('api/wallet/', views.get_wallet, name='wallet'),
    path('api/withdraw/', views.request_withdrawal, name='withdraw'),
    path('api/withdrawal-history/', views.get_withdrawal_history, name='withdrawal-history'),
    
    # M-Pesa Deposit (Old - Keep for compatibility)
    path('api/mpesa-deposit/', views.request_mpesa_deposit, name='mpesa-deposit'),
    path('api/verify-payment/', views.verify_mpesa_payment, name='verify-payment'),
    path('api/verify-manual-payment/', views.verify_manual_payment, name='verify-manual-payment'),
    
    # ========== NEW DEPOSIT APPROVAL SYSTEM (Admin Approval Required) ==========
    path('api/submit-deposit-request/', views.submit_deposit_request, name='submit-deposit-request'),
    path('api/check-deposit-status/', views.check_deposit_status, name='check-deposit-status'),
    path('api/admin-approve-deposit/', views.admin_approve_deposit, name='admin-approve-deposit'),
    path('api/admin-reject-deposit/', views.admin_reject_deposit, name='admin-reject-deposit'),
    path('api/admin-pending-deposits/', views.admin_get_pending_deposits, name='admin-pending-deposits'),
    
    # Daily Earnings
    path('api/process-daily-earnings/', views.process_daily_earnings_api, name='process-daily'),
    
    # Referral System
    path('api/track-referral/', views.track_referral, name='track-referral'),
    path('api/referral-info/', views.get_referral_info, name='referral-info'),
    path('api/claim-bonus/', views.claim_bonus, name='claim-bonus'),
    
    # Referral endpoints with status tracking
    path('api/referral-list-status/', views.get_referral_list_with_status, name='referral-list-status'),
    path('api/bonus-history/', views.get_bonus_history, name='bonus-history'),
    
    # Admin endpoints
    path('api/admin-adjust-balance/', views.admin_adjust_balance, name='admin-adjust-balance'),
    path('api/admin-referral-stats/', views.admin_referral_stats, name='admin-referral-stats'),
    
    # Investment Upgrade endpoint
    path('api/upgrade-investment/', views.upgrade_investment, name='upgrade-investment'),
]