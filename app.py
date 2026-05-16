from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import requests
import base64
import uuid
import os

app = Flask(__name__)
CORS(app)

# M-Pesa Configuration - SANDBOX MODE
MPESA_CONSUMER_KEY = "A6ol1UBrTBuAhYXNhDyCnxt8a5dj8igP5hWsASBQVBJBiw3J"
MPESA_CONSUMER_SECRET = "XggoEqeUQyttVpMTDTDeBKC0w9peUEsqEo7WSR7JUjEUiVrRWsaujjaJoLOvaG67"
MPESA_PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
MPESA_SHORTCODE = "174379"
MPESA_ENVIRONMENT = "sandbox"
MPESA_CALLBACK_URL = "https://senti-invest.onrender.com/api/mpesa-callback/"

# Store pending deposits (in production, use a database)
pending_deposits = {}

@app.route('/')
def home():
    return jsonify({'message': 'Senti Invest API is running!'})

@app.route('/api/test/')
def test():
    return jsonify({
        'success': True,
        'message': 'API is working correctly!',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/products/')
def products():
    products_data = [
        {'id': 1, 'name': 'Level I - Starter Pack', 'min_investment': 520, 'daily_earnings': 52, 'level': 'bronze'},
        {'id': 2, 'name': 'Level II - Bronze Fund', 'min_investment': 800, 'daily_earnings': 80, 'level': 'bronze'},
        {'id': 3, 'name': 'Level III - Silver Starter', 'min_investment': 1000, 'daily_earnings': 100, 'level': 'silver'},
        {'id': 4, 'name': 'Level IV - Silver Plus', 'min_investment': 1500, 'daily_earnings': 150, 'level': 'silver'},
        {'id': 5, 'name': 'Level V - Gold Basic', 'min_investment': 2000, 'daily_earnings': 200, 'level': 'gold'},
        {'id': 6, 'name': 'Level VI - Gold Pro', 'min_investment': 3000, 'daily_earnings': 300, 'level': 'gold'},
        {'id': 7, 'name': 'Level VII - Platinum Entry', 'min_investment': 5000, 'daily_earnings': 500, 'level': 'platinum'},
        {'id': 8, 'name': 'Level VIII - Platinum Plus', 'min_investment': 8000, 'daily_earnings': 800, 'level': 'platinum'},
        {'id': 9, 'name': 'Level IX - Diamond Basic', 'min_investment': 10000, 'daily_earnings': 1000, 'level': 'diamond'},
        {'id': 10, 'name': 'Level X - Diamond Pro', 'min_investment': 12000, 'daily_earnings': 1200, 'level': 'diamond'},
        {'id': 11, 'name': 'Level XI - VIP Basic', 'min_investment': 15000, 'daily_earnings': 1500, 'level': 'vip'},
        {'id': 12, 'name': 'Level XII - VIP Plus', 'min_investment': 20000, 'daily_earnings': 2000, 'level': 'vip'},
        {'id': 13, 'name': 'Level XIII - VIP Elite', 'min_investment': 30000, 'daily_earnings': 3000, 'level': 'vip'},
        {'id': 14, 'name': 'Level XIV - VIP Premium', 'min_investment': 50000, 'daily_earnings': 5000, 'level': 'vip'},
        {'id': 15, 'name': 'Level XV - VIP Ultimate', 'min_investment': 70000, 'daily_earnings': 7000, 'level': 'vip'},
    ]
    return jsonify({'products': products_data})

@app.route('/api/signup/', methods=['POST'])
def signup():
    data = request.get_json()
    phone = data.get('phone_number')
    print(f"Signup: {phone}")
    return jsonify({'success': True, 'user_id': 1, 'message': 'Account created!'})

@app.route('/api/login/', methods=['POST'])
def login():
    data = request.get_json()
    phone = data.get('phone_number')
    print(f"Login: {phone}")
    return jsonify({'success': True, 'user_id': 1, 'balance': 10000, 'message': 'Login successful'})

@app.route('/api/wallet/', methods=['GET'])
def wallet():
    user_id = request.args.get('user_id')
    return jsonify({'balance': 10000, 'total_deposited': 5000, 'total_withdrawn': 0, 'total_earned': 500})

@app.route('/api/my-investments/', methods=['GET'])
def my_investments():
    return jsonify({'investments': [], 'total_daily_earnings': 0, 'count': 0})

@app.route('/api/mpesa-deposit/', methods=['POST'])
def mpesa_deposit():
    """Initiate M-Pesa STK Push - sends prompt to user's phone"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        phone_number = data.get('phone_number')
        
        print(f"💰 Deposit request: User {user_id}, Amount KES {amount}, Phone {phone_number}")
        
        # Validate amount
        if not amount or amount < 520:
            return jsonify({'error': 'Minimum deposit is KES 520'}), 400
        
        if not phone_number:
            return jsonify({'error': 'Phone number is required'}), 400
        
        # Format phone number for M-Pesa (254XXXXXXXXX)
        formatted_phone = phone_number
        if formatted_phone.startswith('0'):
            formatted_phone = '254' + formatted_phone[1:]
        elif formatted_phone.startswith('+'):
            formatted_phone = formatted_phone[1:]
        
        # Generate unique transaction ID
        transaction_id = str(uuid.uuid4())[:8].upper()
        
        # Store pending transaction
        pending_deposits[transaction_id] = {
            'user_id': user_id,
            'amount': amount,
            'phone': formatted_phone,
            'status': 'pending'
        }
        
        # Generate timestamp and password for M-Pesa API
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode((MPESA_SHORTCODE + MPESA_PASSKEY + timestamp).encode()).decode('utf-8')
        
        # Get access token from Safaricom
        auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        auth_response = requests.get(auth_url, auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET))
        
        if auth_response.status_code != 200:
            print(f"Auth failed: {auth_response.text}")
            return jsonify({'error': 'M-Pesa service unavailable. Please try again.'}), 503
        
        access_token = auth_response.json().get('access_token')
        
        # Prepare STK Push request
        api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": formatted_phone,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": formatted_phone,
            "CallBackURL": MPESA_CALLBACK_URL,
            "AccountReference": f"DEP{transaction_id}",
            "TransactionDesc": "Senti Invest Deposit"
        }
        
        # Send STK Push request
        response = requests.post(api_url, json=payload, headers=headers)
        result = response.json()
        
        print(f"📲 STK Push Response: {result}")
        
        if result.get('ResponseCode') == '0':
            print(f"✅ STK Push sent to {formatted_phone}")
            return jsonify({
                'success': True,
                'message': f'STK Push sent to {phone_number}. Please check your phone and enter PIN.',
                'transaction_id': transaction_id,
                'checkout_request_id': result.get('CheckoutRequestID')
            })
        else:
            print(f"❌ STK Push failed: {result}")
            return jsonify({
                'error': result.get('ResponseDescription', 'STK Push failed. Please try again.')
            }), 400
        
    except Exception as e:
        print(f"Error in deposit: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/mpesa-callback/', methods=['POST'])
def mpesa_callback():
    """M-Pesa callback - called when user completes payment on phone"""
    try:
        data = request.get_json()
        print(f"📲 Callback received: {data}")
        
        # Extract result details
        result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode', 1)
        checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
        amount = 0
        
        # Extract amount from metadata
        metadata = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {})
        if metadata:
            for item in metadata.get('Item', []):
                if item.get('Name') == 'Amount':
                    amount = item.get('Value', 0)
        
        if result_code == 0:
            # Payment successful
            print(f"✅ Payment successful! Amount: KES {amount}")
            
            # Find the transaction and mark as completed
            for txn_id, deposit in pending_deposits.items():
                if deposit['status'] == 'pending':
                    deposit['status'] = 'completed'
                    print(f"✅ Transaction {txn_id} completed")
                    break
        else:
            print(f"❌ Payment failed with result code: {result_code}")
        
        return jsonify({'ResultCode': 0, 'ResultDesc': 'Success'})
        
    except Exception as e:
        print(f"Callback error: {e}")
        return jsonify({'ResultCode': 1, 'ResultDesc': 'Failed'})

@app.route('/api/verify-payment/', methods=['POST'])
def verify_payment():
    """Check payment status"""
    try:
        data = request.get_json()
        transaction_id = data.get('transaction_id')
        
        if transaction_id in pending_deposits:
            status = pending_deposits[transaction_id]['status']
            amount = pending_deposits[transaction_id]['amount']
            return jsonify({
                'status': status,
                'amount': amount,
                'message': 'Payment completed!' if status == 'completed' else 'Payment pending'
            })
        else:
            return jsonify({'status': 'not_found', 'message': 'Transaction not found'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/withdraw/', methods=['POST'])
def withdraw():
    data = request.get_json()
    amount = data.get('amount')
    print(f"Withdrawal: KES {amount}")
    return jsonify({'success': True, 'withdrawal_id': 1, 'amount': amount, 'message': 'Withdrawal submitted'})

@app.route('/api/invest/', methods=['POST'])
def invest():
    data = request.get_json()
    amount = data.get('amount')
    print(f"Investment: KES {amount}")
    return jsonify({'success': True, 'investment_id': 1, 'new_balance': 5000, 'daily_earnings': amount * 0.1, 'message': 'Investment successful'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)