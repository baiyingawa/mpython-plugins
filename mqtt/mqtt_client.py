"""
MQTT 客户端核心 - 基于 aiomqtt (MQTT v5.0) 的异步封装
"""
import asyncio
import json
import logging
from typing import Callable, Optional

import aiomqtt

from config import MQTTConfig

logger = logging.getLogger(__name__)


class MQTTClient:
    """
    异步 MQTT 客户端封装。

    设计原则：
    - 一个后台 Task 持续监听消息，收到消息后回调 message_handler
    - 支持运行时动态订阅/取消订阅
    - 掉线后自动重连
    """

    def __init__(self, config: MQTTConfig):
        self.config = config
        self._client: Optional[aiomqtt.Client] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._connected = asyncio.Event()
        self._running = False

        # 消息回调：topic -> [handler]
        self._handlers: list[Callable] = []

        # 当前已订阅的主题集合
        self._subscribed_topics: set[str] = set()

    # ──────────────────────────────────────
    # 公开接口
    # ──────────────────────────────────────

    def add_message_handler(self, handler: Callable) -> None:
        """注册消息处理器，签名: async def handler(topic: str, payload: Any)"""
        self._handlers.append(handler)

    def remove_message_handler(self, handler: Callable) -> None:
        self._handlers.remove(handler)

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @property
    def subscribed_topics(self) -> list[str]:
        return sorted(self._subscribed_topics)

    async def start(self) -> None:
        """启动客户端（后台运行，自动重连）"""
        self._running = True
        self._listen_task = asyncio.create_task(
            self._reconnect_loop(), name="mqtt-listen"
        )
        logger.info("MQTT 客户端已启动，等待连接 %s:%d",
                    self.config.host, self.config.port)

    async def stop(self) -> None:
        """停止客户端"""
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        self._connected.clear()
        logger.info("MQTT 客户端已停止")

    async def publish(
        self,
        topic: str,
        payload: any,
        qos: int = 0,
        retain: bool = False,
    ) -> bool:
        """发布消息到指定主题"""
        if not self.is_connected or self._client is None:
            logger.warning("publish 失败：未连接到 Broker")
            return False
        try:
            # 如果是 dict/list，序列化为 JSON 字符串
            if isinstance(payload, (dict, list)):
                raw = json.dumps(payload, ensure_ascii=False)
            else:
                raw = str(payload)
            await self._client.publish(topic, raw, qos=qos, retain=retain)
            logger.debug("已发布 -> [%s] %s", topic, raw[:120])
            return True
        except Exception as exc:
            logger.error("publish 异常: %s", exc)
            return False

    async def subscribe(self, topic: str, qos: int = 0) -> bool:
        """运行时动态订阅主题"""
        if not self.is_connected or self._client is None:
            logger.warning("subscribe 失败：未连接到 Broker")
            return False
        try:
            await self._client.subscribe(topic, qos=qos)
            self._subscribed_topics.add(topic)
            logger.info("已订阅主题: %s (QoS %d)", topic, qos)
            return True
        except Exception as exc:
            logger.error("subscribe 异常: %s", exc)
            return False

    async def unsubscribe(self, topic: str) -> bool:
        """取消订阅"""
        if not self.is_connected or self._client is None:
            return False
        try:
            await self._client.unsubscribe(topic)
            self._subscribed_topics.discard(topic)
            logger.info("已取消订阅: %s", topic)
            return True
        except Exception as exc:
            logger.error("unsubscribe 异常: %s", exc)
            return False

    async def wait_connected(self, timeout: float = 10.0) -> bool:
        """等待连接成功，返回是否在超时内连上"""
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # ──────────────────────────────────────
    # 内部实现
    # ──────────────────────────────────────

    async def _reconnect_loop(self) -> None:
        """带重连的监听循环"""
        attempt = 0
        max_attempts = self.config.max_reconnect_attempts
        interval = self.config.reconnect_interval

        while self._running:
            if max_attempts != -1 and attempt >= max_attempts:
                logger.error("达到最大重连次数 %d，停止重连", max_attempts)
                break
            try:
                logger.info("尝试连接 MQTT Broker (第 %d 次)...", attempt + 1)
                await self._connect_and_listen()
                attempt = 0          # 成功后重置计数
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._connected.clear()
                attempt += 1
                logger.warning(
                    "MQTT 连接断开: %s，%g 秒后重连...", exc, interval
                )
                await asyncio.sleep(interval)

    async def _connect_and_listen(self) -> None:
        """连接并持续监听消息"""
        cfg = self.config

        # 构建 TLS 参数（可选）
        tls_params = None
        if cfg.tls_enabled and cfg.ca_cert_path:
            import ssl
            ctx = ssl.create_default_context(cafile=cfg.ca_cert_path)
            if cfg.client_cert_path and cfg.client_key_path:
                ctx.load_cert_chain(cfg.client_cert_path, cfg.client_key_path)
            tls_params = aiomqtt.TLSParameters(ssl_context=ctx)

        async with aiomqtt.Client(
            hostname=cfg.host,
            port=cfg.port,
            username=cfg.username,
            password=cfg.password,
            identifier=cfg.client_id,
            keepalive=cfg.keepalive,
            protocol=aiomqtt.ProtocolVersion.V5,
            tls_params=tls_params,
        ) as client:
            self._client = client
            self._connected.set()
            logger.info("已连接到 MQTT Broker %s:%d", cfg.host, cfg.port)

            # 重新订阅所有主题（重连后恢复）
            all_topics = list(
                set(cfg.default_topics) | self._subscribed_topics
            )
            for topic in all_topics:
                await client.subscribe(topic)
                self._subscribed_topics.add(topic)
                logger.debug("已订阅: %s", topic)

            # 持续监听消息
            async for message in client.messages:
                if not self._running:
                    break
                await self._dispatch(message)

        self._client = None
        self._connected.clear()

    async def _dispatch(self, message: aiomqtt.Message) -> None:
        """解码消息并分发给所有注册的 handler"""
        topic = str(message.topic)
        raw = message.payload

        # 尝试 JSON 解析，否则保留字符串
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            payload = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw

        logger.debug("收到消息 <- [%s] %s", topic, str(payload)[:120])

        for handler in list(self._handlers):
            try:
                await handler(topic, payload)
            except Exception as exc:
                logger.error("消息处理器异常 [%s]: %s", topic, exc)
