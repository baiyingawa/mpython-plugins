"""
MQTT 管理器 - 消息路由、历史记录、WebSocket 广播
"""
import asyncio
import json
import logging
from collections import deque
from datetime import datetime
from typing import Optional

from fastapi.websockets import WebSocket

from config import server_config
from models import DeviceStatus, MQTTMessage, WSFrame

logger = logging.getLogger(__name__)


class MQTTManager:
    """
    全局消息调度中心。

    职责：
    1. 接收来自 MQTTClient 的消息
    2. 维护消息历史（循环队列）
    3. 将消息广播给所有已连接的 WebSocket 客户端
    4. 维护设备在线状态表
    """

    def __init__(self):
        self._ws_clients: set[WebSocket] = set()
        self._message_history: deque[MQTTMessage] = deque(
            maxlen=server_config.max_message_history
        )
        self._device_status: dict[str, DeviceStatus] = {}
        self._lock = asyncio.Lock()

    # ──────────────────────────────────────
    # WebSocket 客户端管理
    # ──────────────────────────────────────

    async def connect_ws(self, websocket: WebSocket) -> None:
        """新 WebSocket 客户端连接"""
        await websocket.accept()
        async with self._lock:
            self._ws_clients.add(websocket)
        logger.info("WebSocket 客户端已连接，当前共 %d 个", len(self._ws_clients))

        # 推送历史消息快照
        history = list(self._message_history)
        if history:
            frame = WSFrame(
                event="history",
                data=[m.dict() for m in history],
            )
            try:
                await websocket.send_text(frame.json())
            except Exception:
                pass

    async def disconnect_ws(self, websocket: WebSocket) -> None:
        """WebSocket 客户端断开"""
        async with self._lock:
            self._ws_clients.discard(websocket)
        logger.info("WebSocket 客户端已断开，剩余 %d 个", len(self._ws_clients))

    # ──────────────────────────────────────
    # 消息处理（由 MQTTClient 调用）
    # ──────────────────────────────────────

    async def on_mqtt_message(self, topic: str, payload) -> None:
        """处理 MQTT 入站消息"""
        msg = MQTTMessage(
            topic=topic,
            payload=payload,
            direction="inbound",
            timestamp=datetime.utcnow(),
        )
        self._message_history.append(msg)

        # 解析设备状态（约定：status/<device_id> 主题）
        parts = topic.split("/")
        if len(parts) >= 2 and parts[0] == "status":
            device_id = parts[1]
            await self._update_device_status(device_id, payload)

        # 广播给所有 WebSocket 客户端
        frame = WSFrame(event="message", data=msg.dict())
        await self._broadcast(frame.json())

    async def on_mqtt_publish(self, topic: str, payload) -> None:
        """记录出站消息（后端主动发布时调用）"""
        msg = MQTTMessage(
            topic=topic,
            payload=payload,
            direction="outbound",
            timestamp=datetime.utcnow(),
        )
        self._message_history.append(msg)
        frame = WSFrame(event="message", data=msg.dict())
        await self._broadcast(frame.json())

    # ──────────────────────────────────────
    # 设备状态
    # ──────────────────────────────────────

    async def _update_device_status(self, device_id: str, payload) -> None:
        """根据消息更新设备状态"""
        online = True
        metadata = {}
        if isinstance(payload, dict):
            online = payload.get("online", True)
            metadata = payload
        elif isinstance(payload, str):
            online = payload.lower() not in ("offline", "0", "false")

        status = DeviceStatus(
            device_id=device_id,
            online=online,
            last_seen=datetime.utcnow(),
            metadata=metadata if isinstance(metadata, dict) else {},
        )
        self._device_status[device_id] = status

        # 广播状态变化
        frame = WSFrame(event="status", data=status.dict())
        await self._broadcast(frame.json())
        logger.debug("设备状态更新: %s online=%s", device_id, online)

    def get_device_status(self, device_id: Optional[str] = None):
        """获取设备状态（None 返回全部）"""
        if device_id:
            return self._device_status.get(device_id)
        return dict(self._device_status)

    # ──────────────────────────────────────
    # 消息历史
    # ──────────────────────────────────────

    def get_message_history(
        self,
        topic_filter: Optional[str] = None,
        limit: int = 100,
    ) -> list[MQTTMessage]:
        """
        获取历史消息。
        topic_filter 支持前缀匹配，例如 "device/" 匹配所有设备消息。
        """
        history = list(self._message_history)
        if topic_filter:
            history = [
                m for m in history
                if m.topic.startswith(topic_filter)
            ]
        return history[-limit:]

    # ──────────────────────────────────────
    # 广播工具
    # ──────────────────────────────────────

    async def _broadcast(self, text: str) -> None:
        """向所有 WebSocket 客户端广播文本"""
        if not self._ws_clients:
            return
        dead: set[WebSocket] = set()
        for ws in list(self._ws_clients):
            try:
                await ws.send_text(text)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                self._ws_clients -= dead
            logger.debug("清理失效 WebSocket 连接 %d 个", len(dead))

    async def broadcast_notification(self, message: str, level: str = "info") -> None:
        """向所有客户端推送系统通知"""
        frame = WSFrame(
            event="notification",
            data={"message": message, "level": level},
        )
        await self._broadcast(frame.json())

    @property
    def ws_client_count(self) -> int:
        return len(self._ws_clients)


# 全局单例
mqtt_manager = MQTTManager()
