"""
环境变量配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# ── AI 分析 ──
AI_API_KEY: str = os.getenv("AI_API_KEY", "")
AI_API_URL: str = os.getenv("AI_API_URL", "https://api.tokex.top/v1")
AI_MODEL: str = os.getenv("AI_MODEL", "mimo-v2.5-pro")

# ── ntfy.sh 推送 ──
NTFY_TOPIC: str = os.getenv("NTFY_TOPIC", "stock-sentinel")
NTFY_SERVER: str = os.getenv("NTFY_SERVER", "https://ntfy.sh")

# ── 数据库 ──
DB_PATH: str = os.getenv("DB_PATH", "data/stock_sentinel.db")

# ── 轮询间隔（秒） ──
POLL_REALTIME: int = int(os.getenv("POLL_REALTIME", "30"))
POLL_NEWS: int = int(os.getenv("POLL_NEWS", "300"))

# ── 检测阈值 ──
THRESHOLD_PRICE_CHANGE: float = float(os.getenv("THRESHOLD_PRICE_CHANGE", "3.0"))
THRESHOLD_VOLUME_RATIO: float = float(os.getenv("THRESHOLD_VOLUME_RATIO", "3.0"))

# 确保数据库目录存在
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
