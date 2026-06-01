"""
MQTT 服务管理器 — 一键启停 Mosquitto + 后端
用法: server_manager.py start|stop|status
"""
import subprocess, os, sys, time, json, socket

PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.mqtt_pids.json')
MQTT_DIR = os.path.dirname(os.path.abspath(__file__))
MOSQUITTO_DIR = os.path.join(MQTT_DIR, 'mosquitto')
MOSQUITTO_BIN = os.path.join(MOSQUITTO_DIR, 'bin', 'mosquitto.exe')
MOSQUITTO_CONF = os.path.join(MOSQUITTO_DIR, 'mosquitto.conf')
CFG_FILE = os.path.join(MQTT_DIR, '.mqtt_cfg.json')

# 读取 Python 路径（由 install_mqtt.py 生成）
def _get_python():
    if os.path.isfile(CFG_FILE):
        try:
            with open(CFG_FILE) as f:
                cfg = json.load(f)
            if 'python' in cfg and os.path.isfile(cfg['python']):
                return cfg['python']
        except: pass
    # 回退：尝试本地 venv
    fallback = os.path.join(MQTT_DIR, 'venv', 'Scripts', 'python.exe')
    if os.path.isfile(fallback):
        return fallback
    # 最后回退：系统 python
    return sys.executable

PYTHON = _get_python()


def get_local_ip():
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def start():
    pids = {}
    local_ip = get_local_ip()

    # 1. 启动 Mosquitto
    print("正在启动 Mosquitto MQTT Broker...")
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [MOSQUITTO_BIN, "-c", MOSQUITTO_CONF],
        cwd=MOSQUITTO_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=flags
    )
    pids['mosquitto'] = proc.pid
    time.sleep(2)
    status_json = {"status": "ok"}

    # 2. 启动 Python 后端
    print("正在启动 MQTT Web 后端...")
    log_path = os.path.join(MQTT_DIR, "backend.log")
    with open(log_path, 'a') as log:
        proc = subprocess.Popen(
            [PYTHON, os.path.join(MQTT_DIR, "run.py"), "--http-only"],
            cwd=MQTT_DIR, stdout=log, stderr=log,
            creationflags=flags
        )
    pids['backend'] = proc.pid
    time.sleep(2)

    # 3. 保存 PID
    with open(PID_FILE, 'w') as f:
        json.dump(pids, f)

    status_json.update({
        "backend_pid": pids['backend'],
        "backend_url": "http://127.0.0.1:8000",
        "mqtt_host": local_ip,
        "mqtt_port": 1883,
        "mqtt_user": "zkb",
        "mqtt_pass": "zkb1234",
        "mosquitto_pid": pids['mosquitto']
    })
    print(json.dumps(status_json))


def stop():
    killed = []
    current_pid = os.getpid()
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pids = json.load(f)
        for name, pid in pids.items():
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=5)
                killed.append(f"{name}(PID:{pid})")
            except:
                pass
        os.remove(PID_FILE)
    # 补杀（排除自身进程，避免自杀报错）
    subprocess.run(["taskkill", "/F", "/IM", "mosquitto.exe"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/FI", f"PID ne {current_pid}", "/IM", "python.exe"],
                   capture_output=True)
    print(json.dumps({"status": "stopped", "killed": killed}))
    sys.exit(0)


def do_status():
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pids = json.load(f)
        print(json.dumps({"running": True, "pids": pids}))
    else:
        print(json.dumps({"running": False}))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "start": start()
    elif cmd == "stop": stop()
    elif cmd == "status": do_status()
    else: print("用法: server_manager.py start|stop|status")
