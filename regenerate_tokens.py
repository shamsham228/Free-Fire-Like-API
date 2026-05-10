import requests
import json
import time

UIDPASS_FILE = "uidpass.json"
TOKEN_FILE = "tokens.json"
API_URL = "https://xtytdtyj-jwt.up.railway.app/token"

def read_uidpass():
    with open(UIDPASS_FILE, "r") as f:
        return json.load(f)

def fetch_token(uid, password):
    url = f"{API_URL}?uid={uid}&password={password}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        token = data.get("token")
        if token:
            print(f"✅ Token {uid}: OK")
            return token
        else:
            print(f"❌ Token {uid}: No token returned")
            return None
    except Exception as e:
        print(f"❌ Token {uid}: {e}")
        return None

def main():
    print("=" * 60)
    print("REGENERATING TOKENS")
    print("=" * 60)
    
    uidpass_list = read_uidpass()
    new_tokens = []
    
    for item in uidpass_list:
        uid = item.get("uid")
        password = item.get("password")
        
        token = fetch_token(uid, password)
        if token:
            new_tokens.append({"token": token})
        
        time.sleep(0.5)
    
    print(f"\n✅ Generated {len(new_tokens)} tokens")
    
    with open(TOKEN_FILE, "w") as f:
        json.dump(new_tokens, f, indent=2)
    
    print(f"✅ Saved to {TOKEN_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    main()
