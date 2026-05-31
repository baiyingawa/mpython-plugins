#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MPlugins MQTT — 下载 Mosquitto + 创建 Python 虚拟环境
========================================================
在安装 MPlugins 后的附加步骤。
"""
import os, sys, json, subprocess, urllib.request, urllib.error
import shutil, zipfile, platform, time

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
MQTT_DIR    = os.path.join(PACKAGE_DIR, "mqtt")
MOSQ_DIR    = os.path.join(MQTT_DIR, "mosquitto")
MOSQ_BIN    = os.path.join(MOSQ_DIR, "bin")
VENV_DIR    = os.path.join(MQTT_DIR, "venv")

MOSQ_VERSION = "2.1.2"
MOSQ_URL     = f"https://mosquitto.org/files/binary/win64/mosquitto-{MOSQ_VERSION}-install-windows-x64.exe"
MOSQ_EXE     = os.path.join(MQTT_DIR, f"mosquitto-{MOSQ_VERSION}-install.exe")


def download(url, dest):
    """下载文件，显示进度"""
    print(f"  下载 {url}...")
    try:
        urllib.request.urlretrieve(url, dest, lambda b, bs, ts: None)
        size = os.path.getsize(dest)
        print(f"  ✓ 下载完成 ({size // 1024 // 1024}MB)" if size > 1024*1024 else f"  ✓ 下载完成 ({size // 1024}KB)")
        return True
    except Exception as e:
        print(f"  ✗ 下载失败: {e}")
        return False


def extract_installer(exe_path, out_dir):
    """用 7-Zip 或 PowerShell 解压 NSIS 安装包"""
    # 方法 1: 7-Zip
    for prog in [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        r"C:\Program Files\AMD\AMDInstallManager\7z.exe",
    ]:
        if os.path.isfile(prog):
            print("  使用 7-Zip 解压...")
            r = subprocess.run([prog, "x", exe_path, f"-o{out_dir}", "-y"],
                               capture_output=True, timeout=30)
            if r.returncode == 0:
                return True
            print(f"  7-Zip 失败 (code={r.returncode})")

    # 方法 2: PowerShell（可能失败，取决于系统）
    print("  使用 PowerShell 解压...")
    ps_cmd = (
        f'$s = New-Object -ComObject Shell.Application; '
        f'$z = $s.Namespace("{exe_path}"); '
        f'$t = $s.Namespace("{out_dir}"); '
        f'$t.CopyHere($z.Items(), 0x14)'
    )
    try:
        subprocess.run(["powershell", "-Command", ps_cmd], timeout=60)
        return len(os.listdir(out_dir)) > 5
    except:
        pass

    return False


def install_mosquitto():
    """下载并解压 Mosquitto"""
    print()
    print("=" * 56)
    print("  MPlugins MQTT — 安装 Mosquitto Broker")
    print("=" * 56)
    print()

    os.makedirs(MOSQ_DIR, exist_ok=True)
    os.makedirs(MOSQ_BIN, exist_ok=True)

    # 检查是否已安装
    existing = os.path.join(MOSQ_BIN, "mosquitto.exe")
    if os.path.isfile(existing):
        print("  Mosquitto 已安装，跳过下载")
        return True

    # 下载
    if not os.path.isfile(MOSQ_EXE):
        if not download(MOSQ_URL, MOSQ_EXE):
            print()
            print("  ✗ 下载失败，请手动下载后重试:")
            print(f"    {MOSQ_URL}")
            print(f"    放置到: {MOSQ_EXE}")
            return False
    else:
        print("  安装包已存在，直接解压")

    # 解压到临时目录
    temp_dir = os.path.join(MQTT_DIR, "_mosquitto_extract")
    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    if not extract_installer(MOSQ_EXE, temp_dir):
        print("  ✗ 解压失败")
        return False

    # 复制二进制文件
    for f in os.listdir(temp_dir):
        if f.endswith(".exe") or f.endswith(".dll"):
            shutil.copy2(os.path.join(temp_dir, f), os.path.join(MOSQ_BIN, f))

    # 清理
    shutil.rmtree(temp_dir)

    if os.path.isfile(os.path.join(MOSQ_BIN, "mosquitto.exe")):
        print(f"  ✓ Mosquitto v{MOSQ_VERSION} 安装完成 ({len(os.listdir(MOSQ_BIN))} 文件)")
        return True
    else:
        print("  ✗ mosquitto.exe 未找到，安装可能不完整")
        return False


def install_venv():
    """创建虚拟环境并安装 Python 依赖"""
    print()
    print("  --- Python 虚拟环境 ---")

    if os.path.isdir(VENV_DIR) and os.path.isfile(os.path.join(VENV_DIR, "Scripts", "python.exe")):
        print("  虚拟环境已存在")
    else:
        print("  创建虚拟环境...")
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
        print("  ✓ 虚拟环境已创建")

    # 安装依赖
    req_file = os.path.join(MQTT_DIR, "requirements.txt")
    if os.path.isfile(req_file):
        pip = os.path.join(VENV_DIR, "Scripts", "pip.exe")
        print("  安装 Python 依赖...")
        subprocess.run([pip, "install", "-r", req_file], check=True)
        print("  ✓ 依赖已安装")

    # 记录 Python 路径
    py_path = os.path.join(VENV_DIR, "Scripts", "python.exe")
    cfg = {"python": py_path}
    with open(os.path.join(MQTT_DIR, ".mqtt_cfg.json"), "w") as f:
        json.dump(cfg, f)
    print(f"  ✓ 配置已保存")


def main():
    print()
    print(f"  MPlugins — MQTT 环境安装")
    print(f"  项目: {PACKAGE_DIR}")
    print()

    install_mosquitto()
    install_venv()

    print()
    print("=" * 56)
    print("  ✓ 安装完成！")
    print()
    print("  使用方法:")
    print("    1. 启动 mPython")
    print("    2. 打开 MPlugins 面板（点浮动 M 按钮）")
    print("    3. 点击 IoT 服务器开关 — 一键启动")
    print()
    input("  按 Enter 键退出...")


if __name__ == "__main__":
    main()
