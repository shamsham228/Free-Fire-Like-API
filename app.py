from flask import Flask, request, jsonify
import json
import time
import base64
import requests
import logging
import asyncio
import aiohttp
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError
from google.protobuf.json_format import MessageToJson
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN_FILE = "tokens.json"

def load_tokens():
    try:
        if not os.path.exists(TOKEN_FILE):
            logger.warning(f"⚠️ {TOKEN_FILE} not found")
            return []
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            logger.info(f"✅ Loaded {len(data)} tokens")
            return data
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
        return []

def get_token_info(token):
    """Decode JWT token to get account info"""
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
        return json.loads(decoded)
    except:
        return None

def is_token_expired(token):
    """Check if token is expired"""
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
        
        logger.info(f"📤 Request to: {url}")
        
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'ReleaseVersion': "OB53"
        }
        
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=15)
        
        logger.info(f"📊 Response: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"❌ Status {response.status_code}")
            return None
        
        binary = bytes.fromhex(response.content.hex())
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        
        logger.info(f"✅ Success")
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
        logger.error(f"Like error: {e}")
        return False

# ============ ROUTES ============

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "credit": "https://t.me/paglu_dev",
        "message": "Welcome to the Free Fire Like API",
        "status": "API is running",
        "endpoints": "/like?uid=<uid> or /like?uid=<uid>&server_name=<server_name>",
        "example": "/like?uid=123456789 or /like?uid=123456789&server_name=bd"
    })

@app.route('/health', methods=['GET'])
def health():
    tokens = load_tokens()
    valid_count = sum(1 for t in tokens if not is_token_expired(t.get('token', '')))
    return jsonify({
        'status': 'healthy' if valid_count > 0 else 'unhealthy',
        'total_tokens': len(tokens),
        'valid_tokens': valid_count
    }), 200 if valid_count > 0 else 500

@app.route('/token-info', methods=['GET'])
def token_info():
    """Check token validity and details"""
    try:
        tokens = load_tokens()
        if not tokens:
            return jsonify({"error": "No tokens loaded"}), 500
        
        info_list = []
        valid_count = 0
        
        for idx, token_obj in enumerate(tokens):
            token = token_obj.get('token', '')
            
            if not token:
                info_list.append({
                    "index": idx,
                    "status": "❌ EMPTY",
                    "expired": True
                })
                continue
            
            try:
                # Decode token
                payload = token.split('.')[1]
                payload += '=' * (-len(payload) % 4)
                decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
                info = json.loads(decoded)
                
                exp_time = info.get('exp', 0)
                current_time = int(time.time())
                is_expired = current_time > exp_time
                hours_left = (exp_time - current_time) / 3600
                
                token_info_item = {
                    "index": idx,
                    "account_id": info.get('account_id'),
                    "nickname": info.get('nickname'),
                    "region": info.get('lock_region'),
                    "expired": is_expired,
                    "hours_left": round(hours_left, 2),
                    "status": "❌ EXPIRED" if is_expired else "✅ VALID"
                }
                
                if not is_expired:
                    valid_count += 1
                    
            except Exception as e:
                token_info_item = {
                    "index": idx,
                    "status": "❌ INVALID",
                    "error": str(e)[:50],
                    "expired": True
                }
            
            info_list.append(token_info_item)
        
        return jsonify({
            "total_tokens": len(tokens),
            "valid_tokens": valid_count,
            "expired_tokens": len(tokens) - valid_count,
            "tokens": info_list,
            "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "UID is required"}), 400

    try:
        tokens = load_tokens()
        if tokens is None or not tokens:
            return jsonify({
                "error": "No tokens available. Please contact admin.",
                "status": 0
            }), 500
        
        # Get server_name from query or detect from token
        server_name = request.args.get("server_name", "").upper()
        
        # Try to get token with matching region
        selected_token = None
        token_region = None
        
        if server_name:
            # Find token with matching region
            for token_obj in tokens:
                token = token_obj.get('token', '')
                try:
                    payload = token.split('.')[1]
                    payload += '=' * (-len(payload) % 4)
                    decoded_payload = base64.urlsafe_b64decode(payload).decode('utf-8')
                    parsed_payload = json.loads(decoded_payload)
                    region = parsed_payload.get('lock_region', '').upper()
                    
                    if region == server_name:
                        selected_token = token
                        token_region = region
                        break
                except:
                    continue
        
        # If no matching token found, use first available
        if not selected_token:
            selected_token = tokens[0]['token']
            try:
                payload = selected_token.split('.')[1]
                payload += '=' * (-len(payload) % 4)
                decoded_payload = base64.urlsafe_b64decode(payload).decode('utf-8')
                parsed_payload = json.loads(decoded_payload)
                token_region = parsed_payload.get('lock_region', 'IND').upper()
            except:
                token_region = 'IND'
        
        # Use detected region if not provided
        if not server_name:
            server_name = token_region
        
        app.logger.info(f"🎯 Request: UID={uid}, Server={server_name}, Token Region={token_region}")
        
        # Check region compatibility
        if server_name != token_region:
            return jsonify({
                "error": f"Region mismatch: Token is {token_region}, requested {server_name}. Use /like {token_region} {uid}",
                "status": 0,
                "suggestion": f"Try: /like {token_region} {uid}"
            }), 400
        
        encrypted_uid = enc(uid)
        if encrypted_uid is None:
            return jsonify({"error": "Encryption of UID failed.", "status": 0}), 500

        # Get before likes count
        app.logger.info(f"📖 Fetching player info...")
        before = make_request(encrypted_uid, server_name, selected_token)
        
        if before is None:
            return jsonify({
                "error": f"Cannot fetch player info. Possible reasons:\n• UID {uid} doesn't exist\n• UID is not in {server_name} region\n• Try different region",
                "status": 0,
                "uid": uid,
                "region": server_name
            }), 500
        
        data_before = json.loads(MessageToJson(before))
        account_info = data_before.get('AccountInfo', {})
        
        if not account_info:
            return jsonify({
                "error": f"Invalid UID or UID not found in {server_name} region",
                "status": 0,
                "uid": uid,
                "region": server_name
            }), 404
        
        before_like = int(account_info.get('Likes', 0) or 0)
        player_uid = int(account_info.get('UID', 0) or 0)
        player_name = str(account_info.get('PlayerNickname', 'Unknown'))
        player_level = int(account_info.get('Level', 0) or 0)
        
        app.logger.info(f"👤 Player: {player_name}, Level: {player_level}, Likes: {before_like}")

        # Determine URL based on server
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/LikeProfile"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/LikeProfile"
        else:
            url = "https://clientbp.ggpolarbear.com/LikeProfile"

        # Send like requests
        app.logger.info(f"💌 Sending likes...")
        requests_sent = asyncio.run(send_multiple_requests(uid, server_name, url))
        app.logger.info(f"📨 Requests completed")

        # Get after likes count
        time.sleep(2)  # Wait for likes to process
        after = make_request(encrypted_uid, server_name, selected_token)
        
        if after is None:
            return jsonify({
                "error": "Failed to verify likes. But likes may have been sent.",
                "status": 2
            }), 500
        
        data_after = json.loads(MessageToJson(after))
        after_account_info = data_after.get('AccountInfo', {})
        after_like = int(after_account_info.get('Likes', 0) or 0)
        
        like_given = after_like - before_like
        status = 1 if like_given > 0 else 2
        
        app.logger.info(f"✅ Result: Before={before_like}, After={after_like}, Given={like_given}")
        
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
            "message": "✅ Likes sent successfully!" if status == 1 else "⚠️ No likes added (may already have max)"
        })
        
    except Exception as e:
        app.logger.error(f"❌ Error processing request: {e}", exc_info=True)
        return jsonify({
            "error": str(e)[:200],
            "status": 0
        }), 500
if __name__ == '__main__':
    app.run()
