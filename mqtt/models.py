"""
数据模型 - Pydantic 数据结构定义
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────
# MQTT 消息模型
# ──────────────────────────────────────────

class MQTTMessage(BaseModel):
    """MQTT 收到/发送的消息"""
    topic: str
    payload: Any
    qos: int = 0
    retain: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    direction: str = "inbound"   # "inbound" | "outbound"

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PublishRequest(BaseModel):
    """前端请求发布消息的 Body"""
    topic: str = Field(..., description="目标主题，例如 device/001/cmd")
    payload: Any = Field(..., description="消息内容，字符串或 JSON 对象均可")
    qos: int = Field(default=0, ge=0, le=2, description="QoS 等级 0/1/2")
    retain: bool = Field(default=False, description="是否保留消息")


class SubscribeRequest(BaseModel):
    """订阅/取消订阅请求"""
    topic: str = Field(..., description="主题，支持通配符 # 和 +")
    qos: int = Field(default=0, ge=0, le=2)


# ──────────────────────────────────────────
# 设备状态模型（示例）
# ──────────────────────────────────────────

class DeviceStatus(BaseModel):
    """设备在线状态"""
    device_id: str
    online: bool = False
    last_seen: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ──────────────────────────────────────────
# WebSocket 推送帧
# ──────────────────────────────────────────

class WSFrame(BaseModel):
    """向前端 WebSocket 推送的数据帧"""
    event: str                        # "message" | "status" | "error" | "ack"
    data: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ──────────────────────────────────────────
# 通用响应
# ──────────────────────────────────────────

class APIResponse(BaseModel):
    """通用 API 响应"""
    success: bool
    message: str = ""
    data: Any = None
