"""
应用入口 - FastAPI + MQTT 异步启动

注意：Windows 下请通过 run.py 启动，以确保 SelectorEventLoopPolicy 正确设置。
"""
import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api_routes import router
from config import mqtt_config, server_config
from mqtt_client import MQTTClient
from mqtt_manager import mqtt_manager

# ──────────────────────────────────────────
# 日志配置
# ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# 静态文件目录
# ──────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────
# 全局 MQTT 客户端实例（由 api_routes 通过 import 引用）
# ──────────────────────────────────────────

# 每个 MQTT 客户端使用唯一 client_id，避免多进程（reload + HTTPS 子进程）互相踢
mqtt_config.client_id = f"mqtt-server-{uuid.uuid4().hex[:8]}"
mqtt_client = MQTTClient(mqtt_config)


# ──────────────────────────────────────────
# 生命周期（lifespan）
# ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    logger.info("============ MQTT Web Server 启动 ============")
    logger.info("Broker: mqtt://%s:%d  (MQTT v5.0)", mqtt_config.host, mqtt_config.port)

    mqtt_client.add_message_handler(mqtt_manager.on_mqtt_message)
    await mqtt_client.start()

    connected = await mqtt_client.wait_connected(timeout=8.0)
    if connected:
        logger.info("MQTT Broker 连接成功")
        await mqtt_manager.broadcast_notification("服务器已上线", level="success")
    else:
        logger.warning("MQTT Broker 连接超时，将在后台继续重连...")

    logger.info("API 文档: http://%s:%d/docs", server_config.host, server_config.port)
    logger.info("WebSocket: ws://%s:%d/api/ws", server_config.host, server_config.port)
    if server_config.ssl_certfile and server_config.ssl_keyfile:
        logger.info("HTTPS 已启用: https://%s:%d", server_config.host, server_config.ssl_port)
        logger.info("WSS: wss://%s:%d/api/ws", server_config.host, server_config.ssl_port)
    logger.info("==============================================")

    yield  # 应用运行中

    # ---- shutdown ----
    logger.info("正在关闭 MQTT 连接...")
    await mqtt_client.stop()
    logger.info("服务已停止")


# ──────────────────────────────────────────
# FastAPI 应用
# ──────────────────────────────────────────
app = FastAPI(
    title="MQTT Web Server",
    description=(
        "通过 FastAPI + aiomqtt 实现的本地 MQTT Web 服务端。\n\n"
        "- **REST API** 用于查询状态、历史消息及主动发布\n"
        "- **WebSocket** (`/api/ws`) 用于前端实时订阅消息流\n"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS（开发阶段允许所有来源，生产环境请收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 路由
app.include_router(router, prefix="/api", tags=["MQTT"])


# ──────────────────────────────────────────
# 根路由 — 返回 index.html（禁用缓存）
# ──────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(
        str(STATIC_DIR / "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


# 静态文件挂载（放在路由之后）
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
