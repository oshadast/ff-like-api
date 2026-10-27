import requests
import json
import hashlib

def hash_password(password):
    """Password එක hash කරනවා (Garena style)"""
    return hashlib.sha256(password.encode()).hexdigest().upper()

def get_token_from_guest(uid, password, region="SG"):
    """
    Guest account එකෙන් JWT token එකක් ගන්නවා.
    """
    # Garena guest login endpoint (OB55)
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    
    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        "Content-Type": "application/x-www-form-urlencoded",
        "ReleaseVersion": "OB55",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
    }
    
    # Garena ගේ client credentials (public, game client එකේ තියෙනවා)
    data = {
        "uid": uid,
        "password": hash_password(password),  # hashed password
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1d547ef16dae6",
        "client_id": "100067",
    }
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=15)
        result = response.json()
        
        if "access_token" in result:
            return result["access_token"]
        else:
            print(f"❌ Error for {uid}: {result}")
            return None
    except Exception as e:
        print(f"❌ Exception for {uid}: {e}")
        return None


def main():
    # ඔබගේ SG guest accounts
    accounts = [
        {"uid": "8360180454", "password": "ANURAG"},
        {"uid": "8360180827", "password": "ANURAG"},
    ]
    
    tokens = []
    
    for acc in accounts:
        print(f"🔄 Getting token for UID: {acc['uid']}...")
        token = get_token_from_guest(acc["uid"], acc["password"])
        
        if token:
            tokens.append({"token": token})
            print(f"✅ Token received for {acc['uid']}")
        else:
            print(f"❌ Failed for {acc['uid']}")
    
    if tokens:
        with open("token_sg.json", "w") as f:
            json.dump(tokens, f, indent=2)
        print(f"\n✅ Saved {len(tokens)} tokens to token_sg.json")
    else:
        print("\n❌ No tokens generated. Check your credentials.")


if __name__ == "__main__":
    main()