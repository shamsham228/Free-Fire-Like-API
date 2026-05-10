from flask import Flask, request, jsonify
import os
import json
import time
import base64
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN_FILE = "tokens.json"

def load_tokens():
    try:
        if not os.path.exists(TOKEN_FILE):
            return None
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except:
        return None

def get_token_info(token):
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
        return json.loads(decoded)
    except:
        return None

def is_token_expired(token):
    info = get_token_info(token)
    if not info:
        return True
    exp_time = info.get('exp', 0)
    current_time = int(time.time())
    return current_time > exp_time

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "API running"})

@app.route('/health', methods=['GET'])
def health():
    tokens = load_tokens()
    if tokens:
        return jsonify({'status': 'healthy', 'tokens': len(tokens)})
    return jsonify({'status': 'unhealthy'}), 500

@app.route('/token-info', methods=['GET'])
def token_info():
    tokens = load_tokens()
    if not tokens:
        return jsonify({"error": "No tokens"}), 500
    
    info_list = []
    for idx, token_obj in enumerate(tokens):
        token = token_obj.get('token', '')
        if not token:
            continue
        
        info = get_token_info(token)
        if info:
            exp_time = info.get('exp', 0)
            current_time = int(time.time())
            hours_left = (exp_time - current_time) / 3600
            
            info_list.append({
                "index": idx,
                "account_id": info.get('account_id'),
                "nickname": info.get('nickname'),
                "region": info.get('lock_region'),
                "expired": is_token_expired(token),
                "hours_left": round(hours_left, 2),
                "exp": exp_time,
                "current_time": current_time
            })
    
    valid_count = sum(1 for t in info_list if not t['expired'])
    
    return jsonify({
        "total_tokens": len(tokens),
        "valid_tokens": valid_count,
        "tokens": info_list
    })

@app.route('/like', methods=['GET'])
def like():
    tokens = load_tokens()
    if not tokens:
        return jsonify({"error": "No tokens", "status": 0}), 500
    
    # Find valid token
    valid_token = None
    for t in tokens:
        if not is_token_expired(t.get('token', '')):
            valid_token = t.get('token')
            break
    
    if not valid_token:
        return jsonify({
            "error": "All tokens expired",
            "status": 0,
            "message": "No valid tokens available"
        }), 400
    
    uid = request.args.get("uid")
    server_name = request.args.get("server_name", "IND")
    
    if not uid:
        return jsonify({"error": "UID required"}), 400
    
    # Placeholder response
    return jsonify({
        "status": 2,
        "message": "Like service under development",
        "LikesGivenByAPI": 0,
        "UID": uid,
        "Region": server_name,
        "PlayerLevel": 0,
        "PlayerNickname": "Unknown"
    })

if __name__ == '__main__':
    app.run()
