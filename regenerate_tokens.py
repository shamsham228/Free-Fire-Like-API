import requests
import json
import time
import sys

UIDPASS_FILE = "uidpass.json"
TOKEN_FILE = "tokens.json"
AUTH_API = "https://xtytdtyj-jwt.up.railway.app/token"

def load_uidpass():
    try:
        with open(UIDPASS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading uidpass: {e}")
        return []

def fetch_token(uid, password):
    """Fetch token from auth API"""
    url = f"{AUTH_API}?uid={uid}&password={password}"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        token = data.get("token")
        
        if token:
            print(f"✅ Token {uid}: SUCCESS")
            return token
        else:
            print(f"❌ Token {uid}: No token returned")
            return None
    except Exception as e:
        print(f"❌ Token {uid}: {str(e)[:50]}")
        return None

def main():
    print("=" * 70)
    print("🔄 REGENERATING FREE FIRE TOKENS")
    print("=" * 70)
    
    uidpass_list = load_uidpass()
    
    if not uidpass_list:
        print("❌ No UID/Password entries found!")
        return
    
    print(f"📊 Found {len(uidpass_list)} accounts\n")
    
    new_tokens = []
    success_count = 0
    
    for idx, item in enumerate(uidpass_list, 1):
        uid = item.get("uid")
        password = item.get("password")
        
        print(f"[{idx}/{len(uidpass_list)}] Processing UID: {uid}")
        
        token = fetch_token(uid, password)
        if token:
            new_tokens.append({"token": token})
            success_count += 1
        
        time.sleep(1)  # Rate limiting
    
    print("\n" + "=" * 70)
    
    if success_count == 0:
        print("❌ Failed to fetch any tokens!")
        sys.exit(1)
    
    # Save tokens
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(new_tokens, f, indent=2)
        print(f"✅ Successfully generated {success_count}/{len(uidpass_list)} tokens")
        print(f"💾 Saved to {TOKEN_FILE}")
    except Exception as e:
        print(f"❌ Error saving tokens: {e}")
        sys.exit(1)
    
    print("=" * 70)

if __name__ == "__main__":
    main()
