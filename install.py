#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MPlugins for mPython v1.60 — 安装/更新脚本
===========================================
自动查找 mPython 安装位置，备份原文件，安装或更新 MPlugins 插件框架。
支持保存 mPython 位置配置，后续安装/更新无需重复搜索。
"""
import os, sys, shutil, json, subprocess, urllib.request, urllib.error, platform, zipfile, hashlib

PACKAGE_DIR   = os.path.dirname(os.path.abspath(__file__))
CFG_FILE      = os.path.join(os.path.expanduser("~"), ".mpython_autosave", "mpython_cfg.json")
BACKUP_DIR    = "D:/mpython自动备份"
SCRIPT_NAME   = "mplugin-core.js"


def load_config():
    if os.path.isfile(CFG_FILE):
        try:
            with open(CFG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}


def save_config(data):
    try:
        os.makedirs(os.path.dirname(CFG_FILE), exist_ok=True)
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [!] 配置保存失败: {e}")


def find_mpython(saved_root=None):
    """查找 mPython 安装路径，优先使用已保存的路径"""
    candidates = []

    # 优先使用已保存的路径
    if saved_root and os.path.isdir(saved_root):
        candidates.append(saved_root)

    candidates += [
        "D:/APP DATA/mPython",
        "D:/mPython",
        "D:/Program Files/mPython",
        "C:/Program Files/mPython",
        "C:/Program Files (x86)/mPython",
        os.environ.get("M_PYTHON_HOME", ""),
    ]

    # 注册表查找
    try:
        import winreg
        for key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for subkey in [r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                           r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"]:
                try:
                    with winreg.OpenKey(key, subkey) as k:
                        i = 0
                        while True:
                            try:
                                name = winreg.EnumKey(k, i)
                                with winreg.OpenKey(k, name) as sk:
                                    try:
                                        dn = winreg.QueryValueEx(sk, "DisplayName")[0]
                                        if "mpython" in dn.lower():
                                            ip = winreg.QueryValueEx(sk, "InstallLocation")[0]
                                            if ip and os.path.isdir(ip):
                                                candidates.append(ip)
                                    except: pass
                            except OSError:
                                break
                            i += 1
                except: pass
    except ImportError:
        pass

    for c in candidates:
        if c and os.path.isdir(c):
            build = os.path.join(c, "resources", "app", "build")
            index = os.path.join(build, "index.html")
            if os.path.isfile(index):
                return c, build, index
    return None, None, None


def detect_install_state(build_dir):
    """检测是首次安装还是更新"""
    index_html    = os.path.join(build_dir, "index.html")
    index_bak     = index_html + ".backup"
    plugin_file   = os.path.join(build_dir, SCRIPT_NAME)

    if os.path.isfile(plugin_file):
        if os.path.isfile(index_bak):
            # 有备份 + 有插件文件 → 正常安装状态，执行更新
            return "update"
        elif os.path.isfile(index_html):
            with open(index_html, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
            if SCRIPT_NAME in html:
                # 有插件引用但没有备份 → 残缺安装，修复
                return "repair"
    return "fresh"


def patch_index_html(index_path, is_update):
    """在 index.html 的 </body> 前插入 mplugin-core.js（二进制读写，防编码损坏）"""
    backup = index_path + ".backup"
    has_backup = os.path.isfile(backup)

    with open(index_path, "rb") as f:
        raw = f.read()

    # 检查脚本引用是否已存在
    tag_bytes = b'<script src="./' + SCRIPT_NAME.encode() + b'"></script>'
    if tag_bytes in raw:
        if is_update:
            print(f"  [跳过] {SCRIPT_NAME} 引用已存在")
        return True

    # 需要修补
    if is_update:
        print(f"  [检测] index.html 缺少 {SCRIPT_NAME} 引用，重新修补")
    else:
        if not has_backup:
            shutil.copy2(index_path, backup)
            print(f"  [备份] {index_path} → {backup}")

    body_end = b'</body>'
    if body_end in raw:
        new_raw = raw.replace(body_end, tag_bytes + b'\n' + body_end, 1)
    else:
        new_raw = raw.rstrip() + b'\n' + tag_bytes + b'\n'

    with open(index_path, "wb") as f:
        f.write(new_raw)

    action = "重新" if is_update else ""
    print(f"  [修改] index.html → 已{action}插入 {SCRIPT_NAME}")
    return True


def file_hash(path):
    """计算文件 SHA256 哈希"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk: break
            h.update(chunk)
    return h.hexdigest()


def copy_plugin_files(build_dir):
    """复制插件文件到 build 目录（哈希不一致才替换）"""
    success = True
    src = os.path.join(PACKAGE_DIR, SCRIPT_NAME)
    dst = os.path.join(build_dir, SCRIPT_NAME)
    if not os.path.isfile(src):
        print(f"  [!] 缺失文件: {src}")
        return False
    # 哈希比较
    if os.path.isfile(dst):
        src_hash = file_hash(src)
        dst_hash = file_hash(dst)
        if src_hash == dst_hash:
            print(f"  [跳过] {SCRIPT_NAME} 哈希一致，无需更新")
            return True
        print(f"  [哈希] {SCRIPT_NAME} 不一致，更新...")
    try:
        shutil.copy2(src, dst)
        size = os.path.getsize(dst)
        print(f"  ✓ {SCRIPT_NAME} ({size}B) → {dst}")
    except Exception as e:
        print(f"  [!] 复制失败: {e}")
        success = False
    return success


def ensure_backup_dir():
    """创建备份目录"""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        print(f"  [创建] {BACKUP_DIR}")
    except Exception as e:
        print(f"  [!警告] 无法创建备份目录 {BACKUP_DIR}: {e}")
        print(f"         请手动创建，否则备份功能不可用")


# ================================================================
#  IPC 桥修补（preload.min.js — preload 可直接 require child_process）
# ================================================================

_PRELOAD_EXPOSE = r"""
try{(function(){var e=require("electron"),c=require("child_process");e.contextBridge.exposeInMainWorld("mqttHelper",{exec:function(m){return new Promise(function(a,b){c.exec(m,{maxBuffer:1048576,windowsHide:!0},function(e,o,s){e?b(e.message+"\nstderr:"+s):a(o)})})},spawn:function(m,a){var p=c.spawn(m,a,{detached:!0,stdio:"ignore"});return p.unref(),Promise.resolve("ok")},kill:function(n){return new Promise(function(a){c.exec("taskkill /F /IM "+n,{windowsHide:!0},function(){a("killed")})})},openFile:function(p){try{e.shell.openPath(p)}catch(e){}}}})}catch(e){}
"""


def patch_preload(build_dir):
    """修补 preload.min.js → 暴露 mqttHelper（二进制读写，防编码损坏）"""
    preload_path = os.path.join(os.path.dirname(build_dir), "preload.min.js")
    if not os.path.isfile(preload_path):
        print(f"  [!] 未找到 {preload_path}，跳过修补")
        return False

    # 二进制读写，彻底避免编码问题
    patch_bytes = _PRELOAD_EXPOSE.encode("utf-8").strip()
    patch_hash = hashlib.sha256(patch_bytes).hexdigest()[:12]

    with open(preload_path, "rb") as f:
        raw = f.read()

    # 检测补丁是否已完整存在（末尾哈希匹配）
    tail = raw[-len(patch_bytes)-20:] if len(raw) > len(patch_bytes)+20 else raw
    tail_hash = hashlib.sha256(tail).hexdigest()[:12]
    if tail_hash == patch_hash:
        # 再验证括号平衡
        ob = raw.count(b"{")
        cb = raw.count(b"}")
        if ob == cb:
            print(f"  [跳过] preload.min.js 补丁一致，无需更新 ({patch_hash})")
            return True
        else:
            print(f"  [修复] preload.min.js 补丁一致但括号不平衡 (开{ob}闭{cb})，重新写入")
    else:
        if b"mqttHelper" in raw:
            print(f"  [更新] preload.min.js 存在旧版/损坏补丁，重新写入")

    # 二进制写入
    new_raw = raw.rstrip() + b"\n\n" + patch_bytes
    with open(preload_path, "wb") as f:
        f.write(new_raw)
        f.flush()
        os.fsync(f.fileno())

    # 二进制验证
    with open(preload_path, "rb") as f:
        verified = f.read()
    ob2 = verified.count(b"{")
    cb2 = verified.count(b"}")
    if ob2 == cb2:
        print(f"  ✓ preload.min.js → 已注入 mqttHelper ({patch_hash})")
        return True
    else:
        print(f"  ❌ 写入后括号仍不平衡 (开{ob2}闭{cb2})！请确认 mPython 已关闭后重试")
        return False


# ================================================================
#  MQTT 环境安装（Mosquitto + Python 虚拟环境）
# ================================================================

MQTT_DIR    = os.path.join(PACKAGE_DIR, "mqtt")
MOSQ_DIR    = os.path.join(MQTT_DIR, "mosquitto")
MOSQ_BIN    = os.path.join(MOSQ_DIR, "bin")
VENV_DIR    = os.path.join(MQTT_DIR, "venv")
# Mosquitto 二进制压缩包（已预提取，不含安装器）
# 来源：GitHub Release → 下载解压即用，无需管理员权限
MOSQ_BIN_URL = "https://github.com/baiyingawa/mpython-plugins/releases/download/mosquitto-installer/mosquitto-bin.zip"


def _download(url, dest):
    print(f"  下载 Mosquitto...", end='', flush=True)
    last_pct = -1.0
    def _progress(b, bs, ts):
        nonlocal last_pct
        if ts > 0:
            pct = b * bs * 100.0 / ts
            if pct - last_pct >= 2.0 or pct == 100.0:
                last_pct = pct
                downloaded = b * bs / (1024 * 1024)
                total = ts / (1024 * 1024)
                print(f"\r  下载中 {pct:.1f}% ({downloaded:.2f}MB/{total:.2f}MB)", end='', flush=True)
    try:
        urllib.request.urlretrieve(url, dest, _progress)
        size = os.path.getsize(dest)
        print(f"\r  ✓ 下载完成 ({size/(1024*1024):.2f}MB)")
        return True
    except Exception as e:
        print(f"\r  ✗ 下载失败: {e}")
        return False


def install_mosquitto():
    print()
    print("  --- Mosquitto MQTT Broker ---")
    os.makedirs(MOSQ_DIR, exist_ok=True)
    os.makedirs(MOSQ_BIN, exist_ok=True)
    if os.path.isfile(os.path.join(MOSQ_BIN, "mosquitto.exe")):
        print("  ✓ Mosquitto 已安装，跳过下载")
        return True
    # 下载二进制 zip
    zip_path = os.path.join(MQTT_DIR, "mosquitto-bin.zip")
    if not os.path.isfile(zip_path):
        if not _download(MOSQ_BIN_URL, zip_path):
            print("  ✗ 下载失败")
            return False
    # 解压到 bin 目录
    print("  解压中...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(MOSQ_BIN)
    except Exception as e:
        print(f"  ✗ 解压失败: {e}")
        return False
    # 清理压缩包
    try:
        os.remove(zip_path)
    except: pass
    # 验证
    count = len([n for n in os.listdir(MOSQ_BIN) if n.endswith(".exe") or n.endswith(".dll")])
    if count >= 5:
        print(f"  ✓ Mosquitto 安装完成 ({count} 文件)")
        return True
    print("  ✗ 安装不完整")
    return False


def install_mqtt_venv():
    print()
    print("  --- Python 虚拟环境 ---")
    venv_ok = os.path.isdir(VENV_DIR) and os.path.isfile(os.path.join(VENV_DIR, "Scripts", "python.exe"))
    # 检查 venv 路径是否匹配当前目录（防止复制后路径不对）
    if venv_ok:
        try:
            py_test = os.path.join(VENV_DIR, "Scripts", "python.exe")
            r = subprocess.run([py_test, "--version"], capture_output=True, timeout=5)
            if r.returncode != 0:
                print("  [发现] venv 路径不匹配，重新创建...")
                shutil.rmtree(VENV_DIR, ignore_errors=True)
                venv_ok = False
        except:
            print("  [发现] venv 不可用，重新创建...")
            shutil.rmtree(VENV_DIR, ignore_errors=True)
            venv_ok = False
    if not venv_ok:
        print("  创建虚拟环境...")
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
        print("  ✓ 虚拟环境已创建")
    req_file = os.path.join(MQTT_DIR, "requirements.txt")
    if os.path.isfile(req_file):
        pip = os.path.join(VENV_DIR, "Scripts", "pip.exe")
        print("  安装 Python 依赖...")
        subprocess.run([pip, "install", "-r", req_file], check=True)
        print("  ✓ 依赖已安装")
    py_path = os.path.join(VENV_DIR, "Scripts", "python.exe")
    with open(os.path.join(MQTT_DIR, ".mqtt_cfg.json"), "w") as f:
        json.dump({"python": py_path}, f)
    print("  ✓ 配置已保存")


def main():
    print("=" * 56)
    print("  MPlugins for mPython  v1.60  安装/更新程序")
    print("=" * 56)
    print()

    cfg = load_config()
    saved_root = cfg.get("mpython_root", "")

    # 1. 查找 mPython
    print("[1/4] 查找 mPython 安装位置...")
    if saved_root:
        print(f"  ℹ 已保存路径: {saved_root}")

    root, build_dir, index_path = find_mpython(saved_root)
    if not root:
        print("  [!] 未自动找到 mPython 安装目录")
        if saved_root:
            print(f"  已保存路径不可用: {saved_root}")
        print("  请输入 mPython 安装路径（例如 D:\\APP DATA\\mPython）")
        user = input("  路径: ").strip().strip('"').strip("'")
        if not user or not os.path.isdir(user):
            print("  [!] 路径无效，安装中止")
            input("  按 Enter 键退出...")
            sys.exit(1)
        root = user
        build_dir = os.path.join(root, "resources", "app", "build")
        index_path = os.path.join(build_dir, "index.html")
        if not os.path.isfile(index_path):
            print(f"  [!] 未找到 {index_path}，请确认路径正确")
            input("  按 Enter 键退出...")
            sys.exit(1)

    print(f"  ✓ mPython: {root}")
    print(f"  ✓ 构建目录: {build_dir}")
    print()

    # 2. 检测安装状态
    state = detect_install_state(build_dir)
    is_update = (state == "update")

    if state == "fresh":
        print(f"  检测到: 首次安装")
        print(f"  将要执行的操作:")
        print(f"    · 备份 index.html → index.html.backup")
        print(f"    · 注入 {SCRIPT_NAME} 引用到 index.html")
        print(f"    · 复制 {SCRIPT_NAME} 到 {build_dir}")
        print(f"    · 创建备份目录 {BACKUP_DIR}")
    elif state == "update":
        print(f"  检测到: 更新（已安装 v{cfg.get('version','?')}）")
        print(f"  将要执行的操作:")
        print(f"    · 复制新版 {SCRIPT_NAME} 到 {build_dir}")
        print(f"    · 检查备份目录")
    elif state == "repair":
        print(f"  检测到: 修复模式（存在插件引用但缺少备份）")
        print(f"  将要执行的操作:")
        print(f"    · 备份 index.html → index.html.backup")
        print(f"    · 复制 {SCRIPT_NAME} 到 {build_dir}")
        print(f"    · 创建备份目录 {BACKUP_DIR}")

    print()
    confirm = input("  确认执行？(Y/n): ").strip().lower()
    if confirm == 'n':
        print("  已取消。")
        input("  按 Enter 键退出...")
        sys.exit(0)
    print()

    # 3. 配置 index.html
    step_label = "[2/4]" if state == "fresh" else "[2/3]"
    print(f"{step_label} 配置 index.html...")
    patch_index_html(index_path, is_update)
    if not is_update:
        print()

    # 4. 复制插件
    step_label = "[3/4]" if state == "fresh" else "[2/3]"
    print(f"{step_label} 复制插件文件...")
    copy_plugin_files(build_dir)
    print()

    # 5. 创建备份目录
    step_label = "[4/4]" if state == "fresh" else "[3/3]"
    print(f"{step_label} 创建备份目录...")
    ensure_backup_dir()
    print()

    # 6. 保存配置 + 写入包路径（mplugin-core.js 运行时读取）
    cfg.update({
        "mpython_root": root,
        "build_dir": build_dir,
        "version": "1.60",
    })
    save_config(cfg)
    # 写入 mplugin_pkg.json → mplugin-core.js 通过它找到 mqtt/ 目录
    try:
        pkg_json = os.path.join(build_dir, "mplugin_pkg.json")
        with open(pkg_json, "w", encoding="utf-8") as f:
            json.dump({"package_dir": PACKAGE_DIR.replace("\\", "\\\\")}, f)
        print(f"  [配置] 包路径已写入 {pkg_json}")
    except Exception as e:
        print(f"  [!] 写入包路径失败: {e}")

    action = "更新" if is_update else "安装"
    print("=" * 56)
    print(f"  ✓ 插件框架 {action}成功！")
    print()

    # 7. IPC 桥修补（preload 内直接 require child_process，无需碰 main process）
    print("  --- IPC 桥修补 ---")
    patch_preload(build_dir)
    print()

    # 8. MQTT 环境（自动）
    print("  --- MQTT 环境 ---")
    install_mosquitto()
    install_mqtt_venv()

    print()
    print("=" * 56)
    print(f"  ✓ 全部安装完成！")
    print()
    print("  使用方法:")
    print("    1. 启动 mPython")
    print("    2. 顶栏出现 MPlugins 插件栏（含自动保存功能）")
    print("    3. 点击 [浏览] 选择要保存的 .mxml 文件")
    print("    4. 点击 M 浮动按钮 → 面板 IoT 开关一键启动 MQTT")
    print("    5. 备份文件存储在 D:\\mpython自动备份\\")
    print()
    print("    4. 点击 M 浮动按钮 → 面板 IoT 开关一键启动 MQTT")
    print()
    print("  MQTT 默认账号: zkb/zkb1234 或 web/web233（端口 1883）")
    print()
    print("  如需卸载，运行 uninstall.py")
    print("  如需更新，重新运行本脚本即可自动检测更新")
    print("=" * 56)
    print()
    input("  按 Enter 键退出...")


if __name__ == "__main__":
    main()
