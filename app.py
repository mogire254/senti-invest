from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

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
    password = data.get('password')
    full_name = data.get('full_name', '')
    
    print(f"Signup attempt: {phone} - {full_name}")
    
    return jsonify({
        'success': True,
        'user_id': 1,
        'message': 'Account created! Awaiting admin approval.'
    })

@app.route('/api/login/', methods=['POST'])
def login():
    data = request.get_json()
    phone = data.get('phone_number')
    password = data.get('password')
    
    print(f"Login attempt: {phone}")
    
    return jsonify({
        'success': True,
        'user_id': 1,
        'balance': 10000,
        'message': 'Login successful'
    })

@app.route('/api/wallet/', methods=['GET'])
def wallet():
    user_id = request.args.get('user_id')
    print(f"Wallet request for user: {user_id}")
    
    return jsonify({
        'balance': 10000,
        'total_deposited': 5000,
        'total_withdrawn': 0,
        'total_earned': 500
    })

@app.route('/api/my-investments/', methods=['GET'])
def my_investments():
    user_id = request.args.get('user_id')
    print(f"Investments request for user: {user_id}")
    
    return jsonify({
        'investments': [],
        'total_daily_earnings': 0,
        'count': 0
    })

@app.route('/api/mpesa-deposit/', methods=['POST'])
def mpesa_deposit():
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    phone_number = data.get('phone_number')
    
    print(f"Deposit request: User {user_id}, Amount KES {amount}, Phone {phone_number}")
    
    return jsonify({
        'success': True,
        'message': f'Deposit of KES {amount:,.0f} successful!',
        'new_balance': 15000,
        'transaction_id': 'TEST12345'
    })

@app.route('/api/withdraw/', methods=['POST'])
def withdraw():
    data = request.get_json()
    user_id = data.get('user_id')
    amount = data.get('amount')
    phone_number = data.get('phone_number')
    
    print(f"Withdrawal request: User {user_id}, Amount KES {amount}, Phone {phone_number}")
    
    return jsonify({
        'success': True,
        'withdrawal_id': 1,
        'amount': amount,
        'message': 'Withdrawal request submitted for processing'
    })

@app.route('/api/invest/', methods=['POST'])
def invest():
    data = request.get_json()
    user_id = data.get('user_id')
    product_id = data.get('product_id')
    amount = data.get('amount')
    
    print(f"Investment request: User {user_id}, Product {product_id}, Amount KES {amount}")
    
    return jsonify({
        'success': True,
        'investment_id': 1,
        'new_balance': 5000,
        'daily_earnings': amount * 0.10,
        'message': f'Successfully invested KES {amount:,.0f}'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)