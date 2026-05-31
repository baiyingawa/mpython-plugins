"""
配置文件 - MQTT 及服务器配置
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MQTTConfig:
    """MQTT Broker 连接配置"""
    host: str = "127.0.0.1"
    port: int = 1883
    username: str = "web"
    password: str = "web233"
    client_id: str = "mqtt-server-backend"
    keepalive: int = 60
    protocol_version: int = 5          # MQTT v5.0
    clean_session: bool = True
    reconnect_interval: float = 5.0    # 断线重连间隔（秒）
    max_reconnect_attempts: int = 10   # 最大重连次数，-1 表示无限

    # TLS 配置（可选）
    tls_enabled: bool = False
    ca_cert_path: Optional[str] = None
    client_cert_path: Optional[str] = None
    client_key_path: Optional[str] = None

    # 默认订阅主题（启动时自动订阅）
    default_topics: list = field(default_factory=lambda: [
        "topic1",          # 光线传感器
        "topic2",          # 温度传感器
        "topic3",          # RGB 灯光控制
        "topic4",          # SOS 报警
        "topic5",          # 站点距离配置
        "device/#",        # 所有设备消息
        "server/#",        # 服务器下行消息
        "status/#",        # 状态上报
        "data/#",          # 数据上报
    ])


@dataclass
class ServerConfig:
    """FastAPI 服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    # 消息历史最大条数
    max_message_history: int = 500
    # WebSocket 心跳间隔（秒）
    ws_heartbeat_interval: int = 30

    # HTTPS / SSL 配置（为空则不启用 HTTPS）
    ssl_certfile: Optional[str] = None   # 证书文件路径 (.pem / .crt)
    ssl_keyfile: Optional[str] = None     # 私钥文件路径 (.key)
    ssl_port: int = 443                   # HTTPS 监听端口


# 全局配置实例
mqtt_config = MQTTConfig()
server_config = ServerConfig(
    ssl_certfile=r"E:\sever\uu233.xyz_certificate.pem",
    ssl_keyfile=r"E:\sever\uu233.xyz_private.key",
    ssl_port=443,
)
