# 🛡️ Stock Sentinel — AI 盯盘哨兵

> 手机添加自选股 → AI自动盯盘 → 异常事件实时推送手机

## 架构

```
手机通知 (ntfy.sh)          Flutter APP
   │                         │
   └──────────┬──────────────┘
              │
    ┌─────────▼─────────┐
    │   FastAPI 后端     │
    │                    │
    │  数据采集 (AKShare)│── 免费，每30秒
    │  规则引擎 (Detector)│── 免费，零token
    │  AI分析 (DeepSeek) │── 仅事件触发时
    │  推送 (ntfy.sh)    │── 免费
    └───────────────────┘
```

## 快速启动

### 1. 后端

```bash
cd backend
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 AI_API_KEY

# 启动
python main.py
# 后端运行在 http://localhost:8000
```

### 2. 手机端

```bash
cd stock_sentinel_app

# 配置后端地址（编辑 lib/config.dart）
# Android模拟器: http://10.0.2.2:8000/api
# 真机: http://你的电脑IP:8000/api

flutter pub get
flutter run
```

### 3. 推送通知

手机安装 [ntfy APP](https://ntfy.sh/app/)，订阅 topic: `stock-sentinel`

## 数据源

| 数据源 | 接口 | 覆盖 |
|--------|------|------|
| 财联社全球快讯 | `stock_info_global_cls` | 实时A股/政策/宏观 |
| 东方财富全球快讯 | `stock_info_global_em` | 全球市场 |
| 东方财富个股新闻 | `stock_news_em` | 个股关联 |
| 百度经济日历 | `news_economic_baidu` | 全球宏观经济事件 |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/watchlist` | 自选股列表 |
| POST | `/api/watchlist` | 添加自选股 `{code, name}` |
| DELETE | `/api/watchlist/{code}` | 删除自选股 |
| GET | `/api/quotes` | 所有自选股行情 |
| GET | `/api/events?code=&limit=` | 事件列表 |
| GET | `/api/news?limit=` | 全球新闻事件 |
| GET | `/api/status` | 系统状态 |
| WS | `/api/ws` | 实时推送 |

## 成本

- 行情轮询: **免费** (AKShare)
- 规则检测: **免费** (纯Python)
- AI分析: **~¥0.5/天** (仅事件触发时调用，DeepSeek)
- 推送通知: **免费** (ntfy.sh)
