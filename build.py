#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MPlugins for mPython — 构建/打包脚本 (v1.60)

从 version.txt 读取版本号，更新所有文件，打包至 history/。
用法:  python build.py          # 仅更新版本号
       python build.py --pack   # 更新 + 打包
       python build.py 1.31     # 设新版本号 + 更新 + 打包
"""
import os, sys, re, zipfile, shutil, json, datetime

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR  = os.path.join(PACKAGE_DIR, "history")
VERSION_FILE = os.path.join(PACKAGE_DIR, "version.txt")
CFG_FILE     = os.path.join(os.path.expanduser("~"), ".mpython_autosave", "mpython_cfg.json")
LIVE_SOURCE  = r"D:\APP DATA\mPython\resources\app\build\mplugin-core.js"

FILES_TO_PACK = ["mplugin-core.js", "install.py", "uninstall.py", "README.md"]
MQTT_DIR      = os.path.join(PACKAGE_DIR, "mqtt")


def read_version():
    with open(VERSION_FILE, "r") as f:
        v = f.read().strip()
    return v


def write_version(v):
    with open(VERSION_FILE, "w") as f:
        f.write(v + "\n")


def replace_in_file(path, old, new):
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()
    if old not in data:
        print(f"  [!] {os.path.basename(path)}: 未找到 '{old}'")
        return False
    data = data.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    return True


def update_file(path, old_ver, new_ver):
    """将文件中所有 v{old_ver} 和 '{old_ver}' 替换为 v{new_ver} 和 '{new_ver}'"""
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()
    # 替换 vX.XX 模式
    old_v = f"v{old_ver}"
    new_v = f"v{new_ver}"
    if old_v in data:
        data = data.replace(old_v, new_v)
        count += 1
    # 替换 VERSION = 'X.XX' 模式
    old_q = f"'{old_ver}'"
    new_q = f"'{new_ver}'"
    if old_q in data:
        data = data.replace(old_q, new_q)
        count += 1
    if count > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
    return count > 0


def sync_live():
    if os.path.isfile(LIVE_SOURCE):
        shutil.copy2(LIVE_SOURCE, os.path.join(PACKAGE_DIR, "mplugin-core.js"))
        return True
    return False


def pack(version):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    zip_name = f"mpython-mplugins-v{version}.zip"
    zip_path = os.path.join(HISTORY_DIR, zip_name)
    packed = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES_TO_PACK:
            fp = os.path.join(PACKAGE_DIR, f)
            if os.path.isfile(fp):
                z.write(fp, f)
                packed += 1
                print(f"  ✓ {f}")
        # 打包 mqtt/ 目录（排除 venv 和 bin）
        mqtt_dir = os.path.join(PACKAGE_DIR, "mqtt")
        if os.path.isdir(mqtt_dir):
            for root, dirs, files in os.walk(mqtt_dir):
                # 跳过 venv 和 bin（太大/安装时下载）
                rel = os.path.relpath(root, PACKAGE_DIR)
                parts = rel.replace("\\", "/").split("/")
                if "venv" in parts or "bin" in parts or "__pycache__" in parts:
                    continue
                for f in files:
                    if f.endswith(".pyc") or f.endswith(".log") or f == ".mqtt_cfg.json":
                        continue
                    fp = os.path.join(root, f)
                    arcname = os.path.relpath(fp, PACKAGE_DIR).replace("\\", "/")
                    z.write(fp, arcname)
                    packed += 1
    if packed == 0:
        print("  [!] 没有文件被打包")
        return None
    print(f"\n  ✓ {zip_path} ({os.path.getsize(zip_path)}B)")
    return zip_path


def main():
    args = sys.argv[1:]

    # 确定新旧版本
    old_ver = read_version()
    new_ver = None
    do_pack = "--pack" in args

    for a in args:
        if a.startswith("--"): continue
        new_ver = a.strip().lstrip("v")
        break

    if new_ver and new_ver != old_ver:
        print(f"  版本升级: v{old_ver} → v{new_ver}")
        write_version(new_ver)
    else:
        new_ver = old_ver
        print(f"  当前版本: v{new_ver}")

    print()

    # 1. 从活跃 mPython 同步
    print("[1/4] 同步 mplugin-core.js...")
    if sync_live():
        print("  ✓ 从活跃 mPython 同步")
    else:
        print("  ! 未找到活跃 mPython，使用本地文件")
    print()

    # 2. 更新版本号
    print("[2/4] 更新文件版本号...")
    targets = [
        os.path.join(PACKAGE_DIR, "mplugin-core.js"),
        os.path.join(PACKAGE_DIR, "install.py"),
        os.path.join(PACKAGE_DIR, "uninstall.py"),
    ]
    updated = 0
    for t in targets:
        if t and os.path.isfile(t):
            if update_file(t, old_ver, new_ver):
                print(f"  ✓ {os.path.basename(t)}")
                updated += 1
    print(f"  ({updated} 个文件)")
    print()

    # 3. 更新配置
    print("[3/4] 更新配置...")
    cfg = {}
    if os.path.isfile(CFG_FILE):
        try:
            with open(CFG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except: pass
    cfg["version"] = new_ver
    try:
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"  ✓ mpython_cfg.json (version={new_ver})")
    except Exception as e:
        print(f"  [!] {e}")
    print()

    # 4. 打包
    if do_pack:
        print("[4/4] 打包...")
        pack(new_ver)
        print()
    else:
        print("[4/4] 跳过打包（加 --pack 参数）")
        print()

    print("=" * 56)
    print(f"  ✓ 构建完成！版本 v{new_ver}")
    if not do_pack:
        print(f"  运行 'python build.py --pack' 打包")
    print("=" * 56)


if __name__ == "__main__":
    main()
