"""
认证模块 — 手机验证码登录 + JWT Token
免费方案：验证码通过ntfy.sh推送（已集成），或开发模式直接返回
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

# ntfy.sh推送地址（已有）
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "stock-sentinel-alerts")

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


def send_code(phone: str) -> dict:
    """
    发送验证码到手机
    返回 {"success": bool, "message": str, "code": str(开发模式)}
    """
    if not phone or len(phone) < 11:
        return {"success": False, "message": "手机号格式不正确"}

    code = _generate_code()
    _codes[phone] = {
        "code": code,
        "expire_at": time.time() + CODE_TTL,
        "attempts": 0,
    }

    # 尝试通过ntfy.sh推送验证码
    sent_via_ntfy = False
    try:
        resp = req_lib.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=f"【金融哨兵】验证码：{code}，5分钟内有效。".encode(encoding="utf-8"),
            headers={
                "Title": "登录验证码",
                "Tags": "key",
                "Priority": "urgent",
            },
            timeout=5,
        )
        sent_via_ntfy = resp.status_code == 200
    except Exception as e:
        logger.warning(f"ntfy.sh推送失败: {e}")

    msg = "验证码已发送"
    if sent_via_ntfy:
        msg += "（请查看ntfy.sh通知）"
    else:
        msg += f"（开发模式：{code}）"

    logger.info(f"📱 验证码 → {phone}: {code}")
    return {"success": True, "message": msg, "code": code}


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
