"""
启动入口 - 确保 Windows 下使用 SelectorEventLoop（aiomqtt 兼容性）

用法：
    python run.py              # 启动 HTTP + HTTPS（如果配置了证书）
    python run.py --http-only  # 仅启动 HTTP

关键修复：
    uvicorn 0.36+ 在 Windows 上强制使用 ProactorEventLoop，
    但 aiomqtt (paho-mqtt) 需要 SelectorEventLoop 来调用 add_reader/add_writer。
    因此需要 monkey-patch uvicorn 的 loop factory。
"""
import platform
import sys
import os

# ============================================================
# Step 1: 设置 SelectorEventLoopPolicy
# ============================================================
if platform.system() == "Windows":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ============================================================
# Step 2: Monkey-patch uvicorn 的 asyncio loop factory
#         uvicorn 0.36+ 在 Windows 非子进程模式下强制返回
#         ProactorEventLoop，会覆盖上面的 policy 设置。
#         我们需要强制让它使用 SelectorEventLoop。
# ============================================================
import uvicorn.loops.asyncio as _uvicorn_asyncio_loop
_original_factory = _uvicorn_asyncio_loop.asyncio_loop_factory


def _selector_loop_factory(use_subprocess: bool = False):
    """强制返回 SelectorEventLoop，忽略 Windows Proactor 默认行为"""
    return asyncio.SelectorEventLoop


_uvicorn_asyncio_loop.asyncio_loop_factory = _selector_loop_factory

import subprocess

# 确保工作目录是 mqtt_server/
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SERVER_DIR)

# 延迟 import，确保 event loop 修复已生效
from config import server_config


def main():
    http_only = "--http-only" in sys.argv
    python_exe = sys.executable

    # 启动 HTTPS 子进程（独立进程，独立 MQTT 客户端）
    if not http_only and server_config.ssl_certfile and server_config.ssl_keyfile:
        https_proc = subprocess.Popen(
            [python_exe, __file__, "--https-worker"],
            cwd=SERVER_DIR,
        )
        print(f"[启动] HTTPS 子进程已启动 (PID {https_proc.pid}), 监听端口 {server_config.ssl_port}")

    # 启动 HTTP 主进程
    import uvicorn
    uvicorn.run(
        "main:app",
        host=server_config.host,
        port=server_config.port,
        log_level="info",
    )


def https_worker():
    """HTTPS 工作进程入口"""
    import uvicorn
    uvicorn.run(
        "main:app",
        host=server_config.host,
        port=server_config.ssl_port,
        log_level="info",
        ssl_certfile=server_config.ssl_certfile,
        ssl_keyfile=server_config.ssl_keyfile,
    )


if __name__ == "__main__":
    if "--https-worker" in sys.argv:
        https_worker()
    else:
        main()
