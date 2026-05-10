from flask import Flask, request, jsonify
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError
import base64
import time
import logging
from datetime import datetime
import random

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN_FILE = "tokens.json"
CACHE_FILE = "like_cache.json"

LIKE_LIMITS = {
    "level_1_2": {"daily_likes": 20, "requests_per_call": 1},
    "level_3_10": {"daily_likes": 50, "requests_per_call": 1},
    "level_11_30": {"daily_likes": 150, "requests_per_call": 1},
    "level_30_plus": {"daily_likes": 300, "requests_per_call": 1}
}

def load_tokens():
    try:
        if not os.path.exists(TOKEN_FILE):
            return None
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
        return None

def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

def get_token_info(token):
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        decoded_payload = base64.urlsafe_b64decode(payload).decode('utf-8')
        return json.loads(decoded_payload)
    except:
        return None

def is_token_expired(token):
    info = get_token_info(token)
    if not info:
        return True
    exp_time = info.get('exp', 0)
    if int(time.time()) > exp_time:
        return True
    return False

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encrypting: {e}")
        return None

def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        logger.error(f"Error creating protobuf: {e}")
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    return encrypt_message(protobuf_data)

def make_request(encrypt, server_name, token):
    try:
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        else:
            url = "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
        
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'ReleaseVersion': "OB53"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=15)
        binary = bytes.fromhex(response.content.hex())
        
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except Exception as e:
        logger.error(f"Error in make_request: {e}")
        return None

def send_like(encrypted_uid, token, url):
    """Send single like request"""
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'ReleaseVersion': "OB53"
        }
        
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=15)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending like: {e}")
        return False

def has_liked_today(token_id, target_uid):
    cache = load_cache()
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{token_id}_{target_uid}_{today}"
    return cache.get(key, False)

def mark_liked(token_id, target_uid):
    cache = load_cache()
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{token_id}_{target_uid}_{today}"
    cache[key] = True
    save_cache(cache)

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "API running",
        "endpoints": "/like?uid=<uid>&server_name=<server_name>"
    })

@app.route('/health', methods=['GET'])
def health():
    tokens = load_tokens()
    if not tokens:
        return jsonify({'status': 'unhealthy'}), 500
    valid = [t for t in tokens if not is_token_expired(t.get('token', ''))]
    return jsonify({'status': 'healthy', 'valid_tokens': len(valid)})

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
            info_list.append({
                "index": idx,
                "account_id": info.get('account_id'),
                "expired": is_token_expired(token)
            })
    return jsonify({"total": len(tokens), "valid": len(info_list), "tokens": info_list})

@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "UID required"}), 400
    
    try:
        tokens = load_tokens()
        if not tokens:
            return jsonify({"error": "No tokens", "status": 0}), 500
        
        valid_tokens = [t for t in tokens if not is_token_expired(t.get('token', ''))]
        if not valid_tokens:
            return jsonify({"error": "All tokens expired", "status": 0}), 400
        
        # Pick random token
        token = random.choice(valid_tokens)['token']
        token_info = get_token_info(token)
        
        if not token_info:
            return jsonify({"error": "Cannot decode token", "status": 0}), 500
        
        server_name = request.args.get("server_name", "IND").upper()
        
        # Encrypt UID
        encrypted_uid = enc(uid)
        if encrypted_uid is None:
            return jsonify({"error": "Encryption failed", "status": 0}), 500

        # Get before likes
        before = make_request(encrypted_uid, server_name, token)
        if before is None:
            return jsonify({"error": "Failed to fetch player info", "status": 0}), 500
        
        data_before = json.loads(MessageToJson(before))
        account_info_before = data_before.get('AccountInfo', {})
        before_like = int(account_info_before.get('Likes', 0) or 0)
        player_level = int(account_info_before.get('Level', 0) or 0)
        player_uid = int(account_info_before.get('UID', 0) or 0)
        player_name = str(account_info_before.get('PlayerNickname', 'Unknown'))
        
        token_account_id = token_info.get('account_id')
        
        # Check if already liked
        if has_liked_today(token_account_id, player_uid):
            return jsonify({
                "error": "Already liked",
                "status": 0
            }), 429
        
        # Check daily limit
        cache = load_cache()
        today = datetime.now().strftime("%Y-%m-%d")
        daily_count_key = f"daily_{token_account_id}_{today}"
        current_daily_likes = cache.get(daily_count_key, 0)
        
        limit_config = get_like_limit(player_level)
        max_daily_likes = limit_config['daily_likes']
        
        if current_daily_likes >= max_daily_likes:
            return jsonify({
                "error": "Daily limit reached",
                "status": 0
            }), 429
        
        # Send like
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/LikeProfile"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/LikeProfile"
        else:
            url = "https://clientbp.ggpolarbear.com/LikeProfile"
        
        # Send like with delay
        time.sleep(1)
        success = send_like(encrypted_uid, token, url)
        
        if not success:
            return jsonify({
                "LikesGivenByAPI": 0,
                "status": 2,
                "message": "Failed to send like"
            })
        
        # Wait and check
        time.sleep(2)
        after = make_request(encrypted_uid, server_name, token)
        
        if after is None:
            return jsonify({
                "LikesGivenByAPI": 0,
                "status": 2,
                "message": "Failed to check likes"
            })
        
        data_after = json.loads(MessageToJson(after))
        account_info_after = data_after.get('AccountInfo', {})
        after_like = int(account_info_after.get('Likes', 0) or 0)
        
        like_given = after_like - before_like
        
        if like_given > 0:
            mark_liked(token_account_id, player_uid)
            cache[daily_count_key] = current_daily_likes + like_given
            save_cache(cache)
        
        status = 1 if like_given > 0 else 2
        
        return jsonify({
            "credit": "https://t.me/paglu_dev",
            "LikesGivenByAPI": like_given,
            "LikesafterCommand": after_like,
            "LikesbeforeCommand": before_like,
            "PlayerNickname": player_name,
            "PlayerLevel": player_level,
            "Region": server_name,
            "UID": player_uid,
            "status": status,
            "message": "✅ Like sent!" if status == 1 else "❌ Failed to send like",
            "guest_account": {
                "id": token_account_id,
                "likes_sent_today": current_daily_likes + like_given,
                "daily_limit": max_daily_likes
            }
        })
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"error": str(e), "status": 0}), 500

def get_like_limit(level):
    if level <= 2:
        return LIKE_LIMITS["level_1_2"]
    elif level <= 10:
        return LIKE_LIMITS["level_3_10"]
    elif level <= 30:
        return LIKE_LIMITS["level_11_30"]
    else:
        return LIKE_LIMITS["level_30_plus"]

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
