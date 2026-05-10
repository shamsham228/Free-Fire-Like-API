from flask import Flask, request, jsonify
import json
import time
import base64
import requests
import logging
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import DecodeError

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN_FILE = "tokens.json"

def load_tokens():
    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except:
        return None

@app.route('/token-info', methods=['GET'])
def token_info():
    tokens = load_tokens()
    if not tokens:
        return jsonify({"error": "No tokens"}), 500
    
    info_list = []
    valid_count = 0
    
    for idx, token_obj in enumerate(tokens):
        token = token_obj.get('token', '')
        
        # Skip empty tokens
        if not token or token.strip() == "":
            info_list.append({
                "index": idx,
                "error": "Empty token",
                "expired": True
            })
            continue
        
        # Get token info
        info = get_token_info(token)
        if not info:
            info_list.append({
                "index": idx,
                "error": "Cannot decode token",
                "expired": True
            })
            continue
        
        # Check expiration
        exp_time = info.get('exp', 0)
        current_time = int(time.time())
        is_expired = current_time > exp_time
        hours_left = (exp_time - current_time) / 3600
        
        # Add to list
        token_info_item = {
            "index": idx,
            "account_id": info.get('account_id'),
            "nickname": info.get('nickname'),
            "region": info.get('lock_region'),
            "expired": is_expired,  # TRUE if expired, FALSE if valid
            "hours_left": round(hours_left, 2),
            "exp_timestamp": exp_time,
            "current_timestamp": current_time,
            "status": "❌ EXPIRED" if is_expired else "✅ VALID"
        }
        
        info_list.append(token_info_item)
        
        # Count valid tokens
        if not is_expired:
            valid_count += 1
    
    return jsonify({
        "total_tokens": len(tokens),
        "valid_tokens": valid_count,
        "expired_tokens": len(tokens) - valid_count,
        "tokens": info_list,
        "message": f"{valid_count} token(s) are VALID and ready to use"
    })

def is_token_expired(token):
    info = get_token_info(token)
    if not info:
        return True
    exp_time = info.get('exp', 0)
    return int(time.time()) > exp_time

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded = pad(plaintext, AES.block_size)
        encrypted = cipher.encrypt(padded)
        return binascii.hexlify(encrypted).decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return None

def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        logger.error(f"Protobuf error: {e}")
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        logger.error(f"UID protobuf error: {e}")
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
        logger.error(f"Request error: {e}")
        return None

def send_like_request(encrypted_uid, token, url):
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
        logger.error(f"Like request error: {e}")
        return False

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "API running", "credit": "https://t.me/paglu_dev"})

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
            hours_left = (exp_time - int(time.time())) / 3600
            
            info_list.append({
                "index": idx,
                "account_id": info.get('account_id'),
                "nickname": info.get('nickname'),
                "region": info.get('lock_region'),
                "expired": is_token_expired(token),
                "hours_left": round(hours_left, 2)
            })
    
    valid = sum(1 for t in info_list if not t['expired'])
    return jsonify({"total": len(tokens), "valid": valid, "tokens": info_list})

@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "UID required"}), 400

    try:
        tokens = load_tokens()
        if not tokens:
            return jsonify({"error": "No tokens", "status": 0}), 500
        
        # Find first valid token
        valid_token = None
        for t in tokens:
            if not is_token_expired(t.get('token', '')):
                valid_token = t.get('token')
                break
        
        if not valid_token:
            return jsonify({"error": "All tokens expired", "status": 0}), 400
        
        token_info = get_token_info(valid_token)
        server_name = request.args.get("server_name", "").upper()
        if not server_name:
            server_name = token_info.get('lock_region', 'IND').upper()
        
        encrypted_uid = enc(uid)
        if not encrypted_uid:
            return jsonify({"error": "Encryption failed", "status": 0}), 500

        # Get before
        before = make_request(encrypted_uid, server_name, valid_token)
        if before is None:
            return jsonify({"error": "Failed to fetch player info", "status": 0}), 500
        
        data_before = json.loads(MessageToJson(before))
        account_info = data_before.get('AccountInfo', {})
        before_like = int(account_info.get('Likes', 0) or 0)
        player_uid = int(account_info.get('UID', 0) or 0)
        player_name = str(account_info.get('PlayerNickname', 'Unknown'))
        player_level = int(account_info.get('Level', 0) or 0)

        # Send like
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/LikeProfile"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/LikeProfile"
        else:
            url = "https://clientbp.ggpolarbear.com/LikeProfile"

        time.sleep(1)
        success = send_like_request(encrypted_uid, valid_token, url)
        
        if not success:
            return jsonify({
                "LikesGivenByAPI": 0,
                "status": 2,
                "message": "Failed to send like"
            })
        
        time.sleep(2)
        
        # Get after
        after = make_request(encrypted_uid, server_name, valid_token)
        if after is None:
            return jsonify({"status": 2, "message": "Failed to check likes"}), 500
        
        data_after = json.loads(MessageToJson(after))
        after_like = int(data_after.get('AccountInfo', {}).get('Likes', 0) or 0)
        
        like_given = after_like - before_like
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
            "message": "✅ Like sent!" if status == 1 else "❌ Failed to send like"
        })
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"error": str(e), "status": 0}), 500

if __name__ == '__main__':
    app.run()
