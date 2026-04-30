"""
认证模块 — 手机验证码登录 + JWT Token
腾讯云SMS免费100条/月，需设置环境变量：
  TENCENT_SMS_SECRET_ID, TENCENT_SMS_SECRET_KEY, TENCENT_SMS_SDK_APP_ID, TENCENT_SMS_SIGN_NAME, TENCENT_SMS_TEMPLATE_ID
未配置时自动降级为开发模式（ntfy.sh推送 + 控制台打印）
"""
import os
import random
import time
import hashlib
import hmac
import logging
import json
import requests as req_lib

logger = logging.getLogger(__name__)

# JWT配置
JWT_SECRET = os.getenv("JWT_SECRET", "stock-sentinel-secret-key-2026")
JWT_EXPIRE = 86400 * 30  # 30天

# 验证码配置
CODE_TTL = 300  # 5分钟有效
CODE_LENGTH = 6

# ntfy.sh推送地址（备用）
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "stock-sentinel-alerts")

# 腾讯云SMS配置
TENCENT_SECRET_ID = os.getenv("TENCENT_SMS_SECRET_ID", "")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SMS_SECRET_KEY", "")
TENCENT_SDK_APP_ID = os.getenv("TENCENT_SMS_SDK_APP_ID", "")
TENCENT_SIGN_NAME = os.getenv("TENCENT_SMS_SIGN_NAME", "")
TENCENT_TEMPLATE_ID = os.getenv("TENCENT_SMS_TEMPLATE_ID", "")

# 内存存储验证码 {phone: {code, expire_at, attempts}}
_codes: dict[str, dict] = {}


def _generate_code() -> str:
    """生成6位随机验证码"""
    return ''.join(random.choices('0123456789', k=CODE_LENGTH))


def _base64url_encode(data: bytes) -> str:
    """Base64url编码（不依赖PyJWT）"""
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _base64url_decode(s: str) -> bytes:
    """Base64url解码"""
    import base64
    s += '=' * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_token(user_id: int, phone: str) -> str:
    """创建JWT Token（纯实现，不依赖PyJWT）"""
    import time as _time
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _base64url_encode(json.dumps({
        "user_id": user_id,
        "phone": phone,
        "exp": int(_time.time()) + JWT_EXPIRE,
        "iat": int(_time.time()),
    }).encode())
    signature = _base64url_encode(
        hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def verify_token(token: str) -> dict | None:
    """验证JWT Token，返回payload或None"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header, payload, signature = parts
        # 验证签名
        expected = _base64url_encode(
            hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_base64url_decode(payload))
        # 验证过期
        if data.get('exp', 0) < time.time():
            return None
        return data
    except Exception:
        return None


def _send_via_tencent_sms(phone: str, code: str) -> bool:
    """通过腾讯云SMS发送验证码"""
    if not all([TENCENT_SECRET_ID, TENCENT_SECRET_KEY, TENCENT_SDK_APP_ID,
                TENCENT_SIGN_NAME, TENCENT_TEMPLATE_ID]):
        return False

    try:
        # 腾讯云SMS API v3 (TC3-HMAC-SHA256签名)
        import time as _time
        import datetime as _dt
        import hashlib as _hash
        import hmac as _hmac
        import json as _json

        service = "sms"
        host = "sms.tencentcloudapi.com"
        endpoint = f"https://{host}"
        action = "SendSms"
        version = "2021-01-11"
        region = "ap-guangzhou"
        algorithm = "TC3-HMAC-SHA256"

        # 请求体
        payload = _json.dumps({
            "PhoneNumberSet": [f"+86{phone}"],
            "SmsSdkAppId": TENCENT_SDK_APP_ID,
            "SignName": TENCENT_SIGN_NAME,
            "TemplateId": TENCENT_TEMPLATE_ID,
            "TemplateParamSet": [code],
        })

        # TC3签名
        timestamp = int(_time.time())
        date = _dt.datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')

        # Step 1: CanonicalRequest
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        canonical_headers = f"content-type:application/json\nhost:{host}\n"
        signed_headers = "content-type;host"
        hashed_payload = _hash.sha256(payload.encode('utf-8')).hexdigest()
        canonical_request = (f"{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n"
                           f"{canonical_headers}\n{signed_headers}\n{hashed_payload}")

        # Step 2: StringToSign
        credential_scope = f"{date}/{service}/tc3_request"
        hashed_canonical_request = _hash.sha256(canonical_request.encode('utf-8')).hexdigest()
        string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical_request}"

        # Step 3: Signature
        def _hmac_sha256(key, msg):
            return _hmac.new(key, msg.encode('utf-8'), _hash.sha256).digest()

        secret_date = _hmac_sha256(f"TC3{TENCENT_SECRET_KEY}".encode('utf-8'), date)
        secret_service = _hmac_sha256(secret_date, service)
        secret_signing = _hmac_sha256(secret_service, "tc3_request")
        signature = _hmac.new(secret_signing, string_to_sign.encode('utf-8'), _hash.sha256).hexdigest()

        # Authorization header
        authorization = (f"{algorithm} "
                        f"Credential={TENCENT_SECRET_ID}/{credential_scope}, "
                        f"SignedHeaders={signed_headers}, "
                        f"Signature={signature}")

        # 发送请求
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Version": version,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": region,
        }

        resp = req_lib.post(endpoint, data=payload, headers=headers, timeout=10)
        result = resp.json()

        if result.get("Response", {}).get("SendStatusSet", [{}])[0].get("Code") == "Ok":
            logger.info(f"📱 腾讯云SMS发送成功 → {phone}")
            return True
        else:
            err = result.get("Response", {}).get("Error", {})
            logger.error(f"腾讯云SMS发送失败: {err}")
            return False

    except Exception as e:
        logger.error(f"腾讯云SMS异常: {e}")
        return False


def _send_via_ntfy(phone: str, code: str) -> bool:
    """通过ntfy.sh推送验证码（备用方案）"""
    try:
        resp = req_lib.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=f"【金融哨兵】验证码：{code}，5分钟内有效。".encode(encoding="utf-8"),
            headers={"Title": "登录验证码", "Tags": "key", "Priority": "urgent"},
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"ntfy.sh推送失败: {e}")
        return False


def send_code(phone: str) -> dict:
    """
    发送验证码到手机
    优先级：腾讯云SMS → ntfy.sh → 开发模式（直接返回）
    """
    if not phone or len(phone) < 11:
        return {"success": False, "message": "手机号格式不正确"}

    code = _generate_code()
    _codes[phone] = {
        "code": code,
        "expire_at": time.time() + CODE_TTL,
        "attempts": 0,
    }

    # 1. 尝试腾讯云SMS（真实短信）
    if _send_via_tencent_sms(phone, code):
        return {"success": True, "message": "验证码已发送到手机"}

    # 2. 尝试ntfy.sh推送
    if _send_via_ntfy(phone, code):
        return {"success": True, "message": "验证码已发送（请查看ntfy通知）"}

    # 3. 开发模式
    logger.info(f"📱 验证码(开发模式) → {phone}: {code}")
    return {"success": True, "message": f"验证码已发送（开发模式：{code}）", "code": code}


def verify_code(phone: str, code: str) -> bool:
    """验证手机验证码"""
    record = _codes.get(phone)
    if not record:
        return False

    record["attempts"] += 1

    # 超过5次尝试，作废
    if record["attempts"] > 5:
        _codes.pop(phone, None)
        return False

    # 过期
    if time.time() > record["expire_at"]:
        _codes.pop(phone, None)
        return False

    # 验证
    if hmac.compare_digest(record["code"], code):
        _codes.pop(phone, None)
        return True

    return False
