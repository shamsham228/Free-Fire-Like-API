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

# ===== TOKEN MANAGEMENT =====

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

# ===== ENCRYPTION =====

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

# ===== API REQUESTS (UPDATED WITH OB53 HEADERS) =====

def make_request(encrypt, server_name, token):
    """Fetch player info with updated OB53 headers"""
    try:
        # Select endpoint based on region
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
            host = "client.ind.freefiremobile.com"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
            host = "client.us.freefiremobile.com"
        else:
            url = "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
            host = "clientbp.ggpolarbear.com"
        
        edata = bytes.fromhex(encrypt)
        
        # ✅ UPDATED HEADERS - OB53 (May 2026)
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'deflate, gzip',
            'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': host,
            'ReleaseVersion': 'OB53',
            'X-GA': 'v1 1',
            'X-Unity-Version': '2022.3.47f1',
            'Connection': 'Keep-Alive'
        }
        
        logger.info(f"🔗 Request: {url}")
        logger.info(f"📦 Body: {len(edata)} bytes")
        
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=15)
        
        logger.info(f"📊 Status: {response.status_code}")
        logger.info(f"📦 Response: {len(response.content)} bytes")
        
        if response.status_code != 200:
            logger.error(f"❌ HTTP {response.status_code}")
            logger.error(f"Response: {response.text[:200]}")
            return None
        
        binary = bytes.fromhex(response.content.hex())
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        
        logger.info(f"✅ Success")
        return items
        
    except Exception as e:
        logger.error(f"Request error: {e}", exc_info=True)
        return None

async def send_request(encrypted_uid, token, url):
    """Send async like request with updated headers"""
    try:
        edata = bytes.fromhex(encrypted_uid)
        
        # ✅ UPDATED HEADERS - OB53
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'deflate, gzip',
            'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Unity-Version': '2022.3.47f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': 'OB53'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers, ssl=False) as response:
                return response.status == 200
                
    except Exception as e:
        logger.error(f"Async request error: {e}")
        return False

async def send_multiple_requests(uid, server_name, url):
    """Send 100 like requests asynchronously"""
    try:
        region = server_name
        
        # Create protobuf for like (different from profile fetch)
        message = like_pb2.like()
        message.uid = int(uid)
        message.region = region
        protobuf_message = message.SerializeToString()
        
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            logger.error("Like encryption failed")
            return None
        
        tokens = load_tokens()
        if not tokens:
            return None
        
        tasks = []
        for i in range(100):
            token = tokens[i % len(tokens)]["token"]
            tasks.append(send_request(encrypted_uid, token, url))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
        
        logger.info(f"📨 Sent {success_count}/100 like requests")
        return results
        
    except Exception as e:
        logger.error(f"Multi-request error: {e}")
        return None

# ===== ROUTES =====

@app.route('/')
def index():
    return jsonify({
        "credit": "https://t.me/paglu_dev",
        "message": "Free Fire Like API - OB53 Updated",
        "status": "✅ Running",
        "version": "2.1 (May 2026)",
        "endpoints": {
            "/like": "Send likes - ?uid=<uid>&server_name=<region>",
            "/token-info": "Check token status",
            "/health": "Health check",
            "/test-encryption": "Test encryption output"
        }
    })


# Add to app.py
@app.route('/test-account-ids')
def test_account_ids():
    """Test with 11-digit account IDs instead of external UIDs"""
    
    account_ids = [
        "15624989316", "15646271815", "15644204732", "15644271911",
        "15646632857", "15646715513", "15647208313", "15647246530",
        "15647283555", "15647323557", "15647561606", "15651198005"
    ]
    
    results = []
    tokens = load_tokens()
    
    if not tokens:
        return jsonify({"error": "No tokens"}), 500
    
    token = tokens[0]['token']
    
    for acc_id in account_ids:
        try:
            encrypted = enc(acc_id)
            if not encrypted:
                results.append({"account_id": acc_id, "status": "❌ Encryption failed"})
                continue
                
            response = make_request(encrypted, "IND", token)
            
            if response:
                data = json.loads(MessageToJson(response))
                account_info = data.get('AccountInfo', {})
                
                results.append({
                    "account_id": acc_id,
                    "status": "✅ WORKING",
                    "name": account_info.get('PlayerNickname', 'Unknown'),
                    "level": account_info.get('Level', 0),
                    "likes": account_info.get('Likes', 0)
                })
            else:
                results.append({
                    "account_id": acc_id,
                    "status": "❌ FAILED"
                })
        except Exception as e:
            results.append({
                "account_id": acc_id,
                "status": "❌ ERROR",
                "error": str(e)[:50]
            })
    
    working = [r for r in results if r.get('status') == "✅ WORKING"]
    
    return jsonify({
        "note": "Testing with 11-digit Account IDs",
        "total_tested": len(account_ids),
        "working_count": len(working),
        "results": results
    })
    

# Add to app.py for testing
@app.route('/test-all-guests')
def test_all_guests():
    """Test which guest accounts work"""
    
    guest_uids = [
        "4791121514", "4801190221", "4800217784", "4800253941",
        "4801420983", "4801452310", "4801618821", "4801629659",
        "4801640033", "4801651164", "4801725579", "4803358978"
    ]
    
    results = []
    tokens = load_tokens()
    
    if not tokens:
        return jsonify({"error": "No tokens"}), 500
    
    token = tokens[0]['token']
    
    for uid in guest_uids:
        try:
            encrypted = enc(uid)
            response = make_request(encrypted, "IND", token)
            
            if response:
                data = json.loads(MessageToJson(response))
                account_info = data.get('AccountInfo', {})
                
                results.append({
                    "uid": uid,
                    "status": "✅ WORKING",
                    "name": account_info.get('PlayerNickname', 'Unknown'),
                    "level": account_info.get('Level', 0),
                    "likes": account_info.get('Likes', 0)
                })
            else:
                results.append({
                    "uid": uid,
                    "status": "❌ FAILED"
                })
        except Exception as e:
            results.append({
                "uid": uid,
                "status": "❌ ERROR",
                "error": str(e)[:50]
            })
    
    working = [r for r in results if r['status'] == "✅ WORKING"]
    
    return jsonify({
        "total_tested": len(guest_uids),
        "working_count": len(working),
        "results": results,
        "recommendation": "Use working UIDs for testing"
    })

@app.route('/find-account-id')
def find_account_id():
    """Try to find account ID from profile UID"""
    profile_uid = request.args.get("uid", "1457219434")
    
    try:
        tokens = load_tokens()
        if not tokens:
            return jsonify({"error": "No tokens"}), 500
        
        token = tokens[0]['token']
        
        # Try multiple conversions
        test_uids = [
            profile_uid,                          # Original
            str(int(profile_uid) * 10 + 8),      # Common conversion 1
            str(int(profile_uid) + 14217275304), # Based on pattern
            "1" + profile_uid,                   # Add leading 1
        ]
        
        results = []
        
        for test_uid in test_uids:
            encrypted = enc(test_uid)
            if not encrypted:
                continue
            
            response = make_request(encrypted, "IND", token)
            
            results.append({
                "test_uid": test_uid,
                "found": response is not None,
                "status": "✅ FOUND" if response else "❌ Not found"
            })
        
        # Also check all our token account IDs
        token_accounts = []
        for token_obj in tokens[:5]:  # First 5 only
            info = get_token_info(token_obj.get('token', ''))
            if info:
                token_accounts.append({
                    "account_id": info.get('account_id'),
                    "external_uid": info.get('external_uid'),
                    "nickname": info.get('nickname')
                })
        
        return jsonify({
            "searched_profile_uid": profile_uid,
            "test_results": results,
            "our_token_accounts": token_accounts,
            "recommendation": "Try UIDs that returned ✅ FOUND"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/decode-uid')
def decode_uid():
    """Help users find their real account ID"""
    
    try:
        tokens = load_tokens()
        if not tokens:
            return jsonify({"error": "No tokens"}), 500
        
        # Try to find the UID in our tokens
        uid_search = request.args.get("search", "")
        
        results = []
        
        for token_obj in tokens:
            token = token_obj.get('token', '')
            info = get_token_info(token)
            
            if info:
                account_id = info.get('account_id')
                external_uid = info.get('external_uid')
                nickname = info.get('nickname')
                
                results.append({
                    "account_id": account_id,
                    "external_uid": external_uid,
                    "nickname": nickname,
                    "account_id_str": str(account_id),
                    "external_uid_str": str(external_uid)
                })
        
        return jsonify({
            "message": "Free Fire has multiple ID types",
            "explanation": {
                "account_id": "Used by API (10-11 digits)",
                "external_uid": "Guest login ID (10 digits)",
                "profile_uid": "Shown in game (may differ)"
            },
            "your_tokens": results,
            "note": "Use 'account_id' for API calls"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    tokens = load_tokens()
    valid_count = sum(1 for t in tokens if not is_token_expired(t.get('token', '')))
    return jsonify({
        'status': 'healthy' if valid_count > 0 else 'unhealthy',
        'total_tokens': len(tokens),
        'valid_tokens': valid_count,
        'timestamp': datetime.utcnow().isoformat()
    }), 200 if valid_count > 0 else 500

@app.route('/token-info')
def token_info():
    """Check all tokens status"""
    try:
        tokens = load_tokens()
        if not tokens:
            return jsonify({"error": "No tokens"}), 500
        
        info_list = []
        valid_count = 0
        
        for idx, token_obj in enumerate(tokens):
            token = token_obj.get('token', '')
            
            if not token:
                info_list.append({"index": idx, "status": "❌ EMPTY", "expired": True})
                continue
            
            try:
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
                    "client_version": info.get('client_version'),
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

@app.route('/test-encryption')
def test_encryption():
    """Test encryption output"""
    uid = request.args.get("uid", "1457219434")
    
    try:
        encrypted = enc(uid)
        
        return jsonify({
            "uid": uid,
            "encrypted_hex": encrypted,
            "encrypted_length": len(encrypted) // 2 if encrypted else 0,
            "note": "Compare with captured traffic",
            "expected_length": 16
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/like')
def handle_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "UID required"}), 400

    try:
        # Validate UID
        if not uid.isdigit():
            return jsonify({"error": "UID must be numeric", "status": 0}), 400
        
        # Accept both 10 and 11 digit UIDs
        if len(uid) not in [10, 11]:
            return jsonify({
                "error": f"UID must be 10 or 11 digits. Got {len(uid)} digits",
                "status": 0
            }), 400
        
        tokens = load_tokens()
        if not tokens:
            return jsonify({"error": "No tokens", "status": 0}), 500
        
        # Find token for account 4801618821 (the working one)
        selected_token = None
        
        for token_obj in tokens:
            token = token_obj.get('token', '')
            info = get_token_info(token)
            
            if info and info.get('external_uid') == 4801618821:
                selected_token = token
                logger.info("✅ Using working account token")
                break
        
        # Fallback to first token
        if not selected_token:
            selected_token = tokens[0]['token']
        
        server_name = request.args.get("server_name", "IND").upper()
        
        logger.info(f"🎯 Request: UID={uid}, Server={server_name}")
        
        # Rest of your existing code...
        encrypted_uid = enc(uid)
        if not encrypted_uid:
            return jsonify({"error": "Encryption failed", "status": 0}), 500

        # Get before likes
        before = make_request(encrypted_uid, server_name, selected_token)
        
        if before is None:
            return jsonify({
                "error": f"Cannot fetch player info for UID {uid}",
                "status": 0,
                "note": "This UID may not exist or is in wrong region"
            }), 500
        
        # ... rest of existing code
        
        data_before = json.loads(MessageToJson(before))
        account_info = data_before.get('AccountInfo', {})
        
        if not account_info:
            return jsonify({
                "error": f"UID {uid} not found in {server_name} region",
                "status": 0
            }), 404
        
        before_like = int(account_info.get('Likes', 0) or 0)
        player_uid = int(account_info.get('UID', 0) or 0)
        player_name = str(account_info.get('PlayerNickname', 'Unknown'))
        player_level = int(account_info.get('Level', 0) or 0)
        
        logger.info(f"👤 {player_name} (Lv.{player_level}) - Likes: {before_like}")

        # Send likes
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/LikeProfile"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/LikeProfile"
        else:
            url = "https://clientbp.ggpolarbear.com/LikeProfile"

        logger.info(f"💌 Sending likes...")
        await_result = asyncio.run(send_multiple_requests(uid, server_name, url))
        
        # Get after likes
        time.sleep(2)
        after = make_request(encrypted_uid, server_name, selected_token)
        
        if after is None:
            return jsonify({
                "message": "Likes sent but verification failed",
                "status": 2
            }), 500
        
        data_after = json.loads(MessageToJson(after))
        after_like = int(data_after.get('AccountInfo', {}).get('Likes', 0) or 0)
        
        like_given = after_like - before_like
        status = 1 if like_given > 0 else 2
        
        logger.info(f"✅ Before={before_like}, After={after_like}, Given={like_given}")
        
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
            "message": "✅ Success!" if status == 1 else "⚠️ No likes added"
        })
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return jsonify({"error": str(e)[:200], "status": 0}), 500

if __name__ == '__main__':
    app.run(debug=True)
