import requests
import json
import time
import sys
from datetime import datetime
import base64

UIDPASS_FILE = "uidpass.json"
TOKEN_FILE = "tokens.json"
AUTH_API = "https://xtytdtyj-jwt.up.railway.app/token"

def load_uidpass():
    try:
        with open(UIDPASS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {UIDPASS_FILE}: {e}")
        return []

def validate_token(token):
    """Validate token structure and expiration"""
    try:
        if not token or len(token) < 50:
            return False, "Token too short"
        
        parts = token.split('.')
        if len(parts) != 3:
            return False, "Invalid JWT format"
        
        # Decode payload
        payload = parts[1]
        payload += '=' * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
        info = json.loads(decoded)
        
        # Check expiration
        exp_time = info.get('exp', 0)
        current_time = int(time.time())
        
        if current_time >= exp_time:
            return False, "Token expired"
        
        hours_left = (exp_time - current_time) / 3600
        
        if hours_left < 1:
            return False, f"Token expires in {hours_left:.1f}h"
        
        return True, f"Valid for {hours_left:.1f}h"
        
    except Exception as e:
        return False, f"Validation error: {str(e)[:50]}"

def fetch_token(uid, password):
    """Fetch and validate token"""
    url = f"{AUTH_API}?uid={uid}&password={password}"
    
    try:
        print(f"  📡 Fetching token for UID {uid}...")
        
        response = requests.get(url, timeout=20)
        
        if response.status_code != 200:
            print(f"  ❌ HTTP {response.status_code}")
            return None
        
        data = response.json()
        token = data.get("token")
        
        if not token:
            print(f"  ❌ No token in response")
            return None
        
        # Validate token
        is_valid, message = validate_token(token)
        
        if is_valid:
            print(f"  ✅ {message}")
            return token
        else:
            print(f"  ⚠️ Invalid: {message}")
            return None
            
    except requests.Timeout:
        print(f"  ⏱️ Request timeout")
        return None
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:100]}")
        return None

def main():
    print("=" * 70)
    print("🔄 FREE FIRE TOKEN REGENERATION")
    print(f"⏰ Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 70)
    
    uidpass_list = load_uidpass()
    
    if not uidpass_list:
        print("❌ No UID/Password found in uidpass.json")
        sys.exit(1)
    
    print(f"📊 Processing {len(uidpass_list)} accounts...\n")
    
    new_tokens = []
    success_count = 0
    
    for idx, item in enumerate(uidpass_list, 1):
        uid = item.get("uid")
        password = item.get("password")
        
        if not uid or not password:
            print(f"[{idx}/{len(uidpass_list)}] ⚠️ Missing UID or password")
            continue
        
        print(f"[{idx}/{len(uidpass_list)}] UID: {uid}")
        
        token = fetch_token(uid, password)
        
        if token:
            new_tokens.append({"token": token})
            success_count += 1
        
        # Rate limiting
        if idx < len(uidpass_list):
            time.sleep(2)
        
        print()
    
    print("=" * 70)
    
    if success_count == 0:
        print("❌ FAILED: No valid tokens generated!")
        print(f"🔍 Check if {AUTH_API} is working")
        sys.exit(1)
    
    # Save tokens
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(new_tokens, f, indent=2)
        
        print(f"✅ SUCCESS: {success_count}/{len(uidpass_list)} tokens saved")
        print(f"💾 File: {TOKEN_FILE}")
        print(f"⏰ Completed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
    except Exception as e:
        print(f"❌ Save error: {e}")
        sys.exit(1)
    
    print("=" * 70)

if __name__ == "__main__":
    main()
