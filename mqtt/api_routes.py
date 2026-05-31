"""
API 路由 - REST 接口 + WebSocket 接口
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from models import APIResponse, PublishRequest, SubscribeRequest

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────────────────────
# 依赖注入：获取全局 MQTTClient 和 MQTTManager
# ──────────────────────────────────────────────────────────────

def get_mqtt_client():
    from main import mqtt_client
    return mqtt_client


def get_mqtt_manager():
    from mqtt_manager import mqtt_manager
    return mqtt_manager


# ──────────────────────────────────────────────────────────────
# REST - 连接状态
# ──────────────────────────────────────────────────────────────

@router.get("/status", response_model=APIResponse, summary="获取 MQTT 连接状态")
async def get_status(client=Depends(get_mqtt_client)):
    """返回 Broker 连接状态和当前订阅主题列表"""
    return APIResponse(
        success=True,
        data={
            "connected": client.is_connected,
            "subscribed_topics": client.subscribed_topics,
        },
    )


# ──────────────────────────────────────────────────────────────
# REST - 发布消息
# ──────────────────────────────────────────────────────────────

@router.post("/publish", response_model=APIResponse, summary="向指定主题发布消息")
async def publish_message(
    req: PublishRequest,
    client=Depends(get_mqtt_client),
    manager=Depends(get_mqtt_manager),
):
    """
    向指定 MQTT 主题发布一条消息。
    
    - **topic**: 目标主题，例如 `device/001/cmd`
    - **payload**: 任意 JSON 可序列化内容
    - **qos**: 0 / 1 / 2
    - **retain**: 是否保留消息
    """
    if not client.is_connected:
        raise HTTPException(status_code=503, detail="MQTT Broker 未连接")

    ok = await client.publish(req.topic, req.payload, qos=req.qos, retain=req.retain)
    if not ok:
        raise HTTPException(status_code=500, detail="消息发布失败")

    # 记录出站消息到历史 & 广播给 WebSocket 客户端
    await manager.on_mqtt_publish(req.topic, req.payload)

    return APIResponse(success=True, message=f"消息已发布至 {req.topic}")


# ──────────────────────────────────────────────────────────────
# REST - 订阅管理
# ──────────────────────────────────────────────────────────────

@router.post("/subscribe", response_model=APIResponse, summary="动态订阅主题")
async def subscribe_topic(
    req: SubscribeRequest,
    client=Depends(get_mqtt_client),
):
    if not client.is_connected:
        raise HTTPException(status_code=503, detail="MQTT Broker 未连接")
    ok = await client.subscribe(req.topic, qos=req.qos)
    if not ok:
        raise HTTPException(status_code=500, detail="订阅失败")
    return APIResponse(success=True, message=f"已订阅 {req.topic}")


@router.delete("/subscribe", response_model=APIResponse, summary="取消订阅主题")
async def unsubscribe_topic(
    topic: str,
    client=Depends(get_mqtt_client),
):
    ok = await client.unsubscribe(topic)
    if not ok:
        raise HTTPException(status_code=500, detail="取消订阅失败")
    return APIResponse(success=True, message=f"已取消订阅 {topic}")


# ──────────────────────────────────────────────────────────────
# REST - 消息历史
# ──────────────────────────────────────────────────────────────

@router.get("/messages", summary="获取消息历史")
async def get_messages(
    topic: Optional[str] = None,
    limit: int = 100,
    manager=Depends(get_mqtt_manager),
):
    """
    查询历史消息。
    
    - **topic**: 主题前缀过滤（可选），例如 `device/`
    - **limit**: 最多返回条数（默认 100）
    """
    msgs = manager.get_message_history(topic_filter=topic, limit=limit)
    return APIResponse(
        success=True,
        data=[m.dict() for m in msgs],
    )


# ──────────────────────────────────────────────────────────────
# REST - 设备状态
# ──────────────────────────────────────────────────────────────

@router.get("/devices", summary="获取所有设备状态")
async def get_devices(manager=Depends(get_mqtt_manager)):
    statuses = manager.get_device_status()
    return APIResponse(
        success=True,
        data={k: v.dict() for k, v in statuses.items()},
    )


@router.get("/devices/{device_id}", summary="获取指定设备状态")
async def get_device(device_id: str, manager=Depends(get_mqtt_manager)):
    status = manager.get_device_status(device_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"设备 {device_id} 不存在")
    return APIResponse(success=True, data=status.dict())


# ──────────────────────────────────────────────────────────────
# WebSocket - 实时消息推送
# ──────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    manager=Depends(get_mqtt_manager),
    client=Depends(get_mqtt_client),
):
    """
    WebSocket 连接端点。
    
    连接后会立即收到最近的历史消息快照（event: "history"）。
    之后实时推送每条 MQTT 消息（event: "message"）和设备状态变化（event: "status"）。
    
    前端也可通过此连接发送 JSON 指令（目前支持 publish）：
    ```json
    {"action": "publish", "topic": "device/001/cmd", "payload": {"cmd": "reboot"}}
    ```
    """
    await manager.connect_ws(websocket)
    try:
        # 同时接收前端指令 + 保持连接
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                await _handle_ws_command(raw, websocket, client, manager)
            except asyncio.TimeoutError:
                # 发送心跳
                from models import WSFrame
                frame = WSFrame(event="ping", data=None)
                await websocket.send_text(frame.json())
    except WebSocketDisconnect:
        logger.info("WebSocket 客户端主动断开")
    except Exception as exc:
        logger.warning("WebSocket 连接异常: %s", exc)
    finally:
        await manager.disconnect_ws(websocket)


async def _handle_ws_command(raw: str, ws: WebSocket, client, manager) -> None:
    """处理前端通过 WebSocket 发来的指令"""
    import json
    from models import WSFrame
    try:
        cmd = json.loads(raw)
    except Exception:
        return

    action = cmd.get("action")
    if action == "publish":
        topic = cmd.get("topic", "")
        payload = cmd.get("payload", "")
        qos = int(cmd.get("qos", 0))
        ok = await client.publish(topic, payload, qos=qos)
        if ok:
            await manager.on_mqtt_publish(topic, payload)
        ack = WSFrame(event="ack", data={"action": "publish", "success": ok, "topic": topic})
        await ws.send_text(ack.json())

    elif action == "subscribe":
        topic = cmd.get("topic", "")
        qos = int(cmd.get("qos", 0))
        ok = await client.subscribe(topic, qos=qos)
        ack = WSFrame(event="ack", data={"action": "subscribe", "success": ok, "topic": topic})
        await ws.send_text(ack.json())

    elif action == "unsubscribe":
        topic = cmd.get("topic", "")
        ok = await client.unsubscribe(topic)
        ack = WSFrame(event="ack", data={"action": "unsubscribe", "success": ok, "topic": topic})
        await ws.send_text(ack.json())
