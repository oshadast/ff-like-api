from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
import json
import like_pb2
import uid_generator_pb2
import visit_count_pb2
from google.protobuf.message import DecodeError
from collections import OrderedDict
import concurrent.futures

app = Flask(__name__)

VALID_API_KEYS = {"ZEXXY"}

daily_limit = 200
used_count = 0


def load_tokens(region):
    try:
        if region == "IND":
            fname = "token_ind.json"
        elif region == "SG":
            fname = "token_sg.json"
        elif region in {"BR", "US", "SAC", "NA"}:
            fname = "token_br.json"
        else:
            fname = "token_bd.json"
        with open(fname, "r") as f:
            return json.load(f)
    except Exception as e:
        app.logger.error(f"Token load error {region}: {e}")
        return None


def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return binascii.hexlify(cipher.encrypt(pad(plaintext, AES.block_size))).decode()
    except Exception as e:
        app.logger.error(f"Encrypt error: {e}")
        return None


def create_like_proto(uid, region):
    try:
        m = like_pb2.like()
        m.uid = int(uid)
        m.region = region
        return m.SerializeToString()
    except Exception as e:
        app.logger.error(f"Like proto error: {e}")
        return None


def create_uid_proto(uid):
    try:
        m = uid_generator_pb2.uid_generator()
        m.saturn_ = int(uid)
        m.garena = 1
        return m.SerializeToString()
    except Exception as e:
        app.logger.error(f"UID proto error: {e}")
        return None


def get_url(region, endpoint):
    if region == "IND":
        base = "https://client.ind.freefiremobile.com"
    elif region == "SG":
        base = "https://client.sg.freefiremobile.com"
    elif region in {"BR", "US", "SAC", "NA"}:
        base = "https://client.us.freefiremobile.com"
    else:
        base = "https://clientbp.ggpolarbear.com"
    return f"{base}/{endpoint}"


def headers_for(token):
    return {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB55",
    }


def get_player_info(uid, region, token):
    """GetPlayerPersonalShow - synchronous"""
    try:
        proto = create_uid_proto(uid)
        if proto is None:
            return None
        enc = encrypt_message(proto)
        if enc is None:
            return None
        url = get_url(region, "GetPlayerPersonalShow")
        r = requests.post(
            url,
            data=bytes.fromhex(enc),
            headers=headers_for(token),
            verify=False,
            timeout=10,
        )
        if r.status_code != 200:
            return None
        decoded = visit_count_pb2.Info()
        decoded.ParseFromString(r.content)
        return decoded
    except DecodeError as e:
        app.logger.error(f"DecodeError: {e}")
        return None
    except Exception as e:
        app.logger.error(f"PlayerInfo error: {e}")
        return None


def send_like_once(uid, region, token):
    """LikeProfile - single request - synchronous"""
    try:
        proto = create_like_proto(uid, region)
        if proto is None:
            return False
        enc = encrypt_message(proto)
        if enc is None:
            return False
        url = get_url(region, "LikeProfile")
        r = requests.post(
            url,
            data=bytes.fromhex(enc),
            headers=headers_for(token),
            verify=False,
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        app.logger.error(f"Like error: {e}")
        return False


def send_likes_burst(uid, region, tokens, count=20):
    """Send likes from multiple tokens concurrently (thread pool)."""
    def worker(token):
        return send_like_once(uid, region, token)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(worker, t["token"]) for t in tokens for _ in range(count // max(1, len(tokens)) + 1)]
        for f in concurrent.futures.as_completed(futures):
            try:
                results.append(f.result())
            except Exception:
                results.append(False)
    return results


@app.route('/like', methods=['GET'])
def handle_requests():
    global used_count

    api_key = request.args.get("key")
    if api_key not in VALID_API_KEYS:
        result = OrderedDict([("error", "Invalid or missing API key"), ("status", 3)])
        return app.response_class(
            response=json.dumps(result, separators=(",", ":")),
            status=401,
            mimetype="application/json",
        )

    uid = request.args.get("uid")
    region = request.args.get("region", "").upper()
    if not uid or not region:
        return {"error": "UID and region are required"}, 400

    try:
        tokens = load_tokens(region)
        if not tokens:
            raise Exception("Failed to load tokens.")
        token = tokens[0]["token"]

        before = get_player_info(uid, region, token)
        if before is None:
            raise Exception("Failed to get initial info.")
        before_like = before.AccountInfo.Likes

        # Send likes
        send_likes_burst(uid, region, tokens, count=20)

        after = get_player_info(uid, region, token)
        if after is None:
            raise Exception("Failed to get final info.")
        after_like = after.AccountInfo.Likes

        like_given = after_like - before_like
        status = 1 if like_given > 0 else 2

        if status == 1:
            used_count += 1

        remaining = max(daily_limit - used_count, 0)

        result = OrderedDict([
            ("LikesGivenByAPI", like_given),
            ("LikesafterCommand", after_like),
            ("LikesbeforeCommand", before_like),
            ("PlayerNickname", after.AccountInfo.PlayerNickname),
            ("Level", after.AccountInfo.Levels),
            ("Region", after.AccountInfo.PlayerRegion),
            ("UID", after.AccountInfo.UID),
            ("status", status),
            ("daily_limit", daily_limit),
            ("used", used_count),
            ("remaining", remaining),
        ])

        return app.response_class(
            response=json.dumps(result, separators=(",", ":")),
            status=200,
            mimetype="application/json",
        )

    except Exception as e:
        app.logger.error(f"Error: {e}")
        return {"error": str(e)}, 500


@app.route('/remain', methods=['GET'])
def remain_info():
    global used_count
    remaining = max(daily_limit - used_count, 0)
    return jsonify({
        "daily_limit": daily_limit,
        "remaining": remaining,
        "used": used_count,
        "reset_info": "4:00 AM IST",
    })


if __name__ == '__main__':
    app.run(debug=False, use_reloader=False)