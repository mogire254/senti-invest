from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import json

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
    ]
    return jsonify({'products': products_data})

@app.route('/api/signup/', methods=['POST'])
def signup():
    data = request.get_json()
    return jsonify({
        'success': True,
        'user_id': 1,
        'message': 'Account created! Awaiting admin approval.'
    })

@app.route('/api/login/', methods=['POST'])
def login():
    data = request.get_json()
    return jsonify({
        'success': True,
        'user_id': 1,
        'balance': 10000,
        'message': 'Login successful'
    })

@app.route('/api/wallet/', methods=['GET'])
def wallet():
    return jsonify({
        'balance': 10000,
        'total_deposited': 5000,
        'total_withdrawn': 0,
        'total_earned': 500
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)