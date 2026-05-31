#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MPlugins for mPython v1.60 — 安装/更新脚本
===========================================
自动查找 mPython 安装位置，备份原文件，安装或更新 MPlugins 插件框架。
支持保存 mPython 位置配置，后续安装/更新无需重复搜索。
"""
import os, sys, shutil, json, subprocess, urllib.request, urllib.error, platform

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
    """在 index.html 的 </body> 前插入 mplugin-core.js，先备份（仅首次）"""
    if is_update:
        print("  [跳过] 更新模式，无需修改 index.html")
        return True

    backup = index_path + ".backup"
    if not os.path.isfile(backup):
        shutil.copy2(index_path, backup)
        print(f"  [备份] {index_path} → {backup}")

    with open(index_path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    if SCRIPT_NAME in html:
        print(f"  [跳过] {SCRIPT_NAME} 引用已存在")
        return True

    tag = f'<script src="./{SCRIPT_NAME}"></script>'
    if '</body>' in html:
        html = html.replace('</body>', tag + '\n</body>')
    else:
        html += '\n' + tag

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [修改] index.html → 已插入 {SCRIPT_NAME}")
    return True


def copy_plugin_files(build_dir):
    """复制插件文件到 build 目录"""
    success = True
    src = os.path.join(PACKAGE_DIR, SCRIPT_NAME)
    dst = os.path.join(build_dir, SCRIPT_NAME)
    if not os.path.isfile(src):
        print(f"  [!] 缺失文件: {src}")
        return False
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
#  MQTT 环境安装（Mosquitto + Python 虚拟环境）
# ================================================================

MQTT_DIR    = os.path.join(PACKAGE_DIR, "mqtt")
MOSQ_DIR    = os.path.join(MQTT_DIR, "mosquitto")
MOSQ_BIN    = os.path.join(MOSQ_DIR, "bin")
VENV_DIR    = os.path.join(MQTT_DIR, "venv")
MOSQ_VER    = "2.1.2"
MOSQ_URL    = f"https://mosquitto.org/files/binary/win64/mosquitto-{MOSQ_VER}-install-windows-x64.exe"
MOSQ_EXE    = os.path.join(MQTT_DIR, f"mosquitto-{MOSQ_VER}-install.exe")


def _download(url, dest):
    print(f"  下载 Mosquitto...")
    try:
        urllib.request.urlretrieve(url, dest, lambda b, bs, ts: None)
        size = os.path.getsize(dest)
        print(f"  ✓ 下载完成 ({size // 1024 // 1024}MB)" if size > 1024*1024 else f"  ✓ 下载完成 ({size // 1024}KB)")
        return True
    except Exception as e:
        print(f"  ✗ 下载失败: {e}")
        return False


def _extract_installer(exe_path, out_dir):
    for prog in [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        r"C:\Program Files\AMD\AMDInstallManager\7z.exe",
    ]:
        if os.path.isfile(prog):
            print("  使用 7-Zip 解压...")
            r = subprocess.run([prog, "x", exe_path, f"-o{out_dir}", "-y"], capture_output=True, timeout=30)
            if r.returncode == 0:
                return True
    print("  使用 PowerShell 解压...")
    ps_cmd = f'$s = New-Object -ComObject Shell.Application; $z = $s.Namespace("{exe_path}"); $t = $s.Namespace("{out_dir}"); $t.CopyHere($z.Items(), 0x14)'
    try:
        subprocess.run(["powershell", "-Command", ps_cmd], timeout=60)
        return len(os.listdir(out_dir)) > 5
    except:
        return False


def install_mosquitto():
    print()
    print("  --- Mosquitto MQTT Broker ---")
    os.makedirs(MOSQ_DIR, exist_ok=True)
    os.makedirs(MOSQ_BIN, exist_ok=True)
    if os.path.isfile(os.path.join(MOSQ_BIN, "mosquitto.exe")):
        print("  ✓ Mosquitto 已安装，跳过下载")
        return True
    if not os.path.isfile(MOSQ_EXE):
        if not _download(MOSQ_URL, MOSQ_EXE):
            print(f"  ✗ 下载失败，请手动下载: {MOSQ_URL}\n    放置到: {MOSQ_EXE}")
            return False
    temp_dir = os.path.join(MQTT_DIR, "_mos_extract")
    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    if not _extract_installer(MOSQ_EXE, temp_dir):
        print("  ✗ 解压失败")
        return False
    for f in os.listdir(temp_dir):
        if f.endswith(".exe") or f.endswith(".dll"):
            shutil.copy2(os.path.join(temp_dir, f), os.path.join(MOSQ_BIN, f))
    shutil.rmtree(temp_dir)
    if os.path.isfile(os.path.join(MOSQ_BIN, "mosquitto.exe")):
        print(f"  ✓ Mosquitto v{MOSQ_VER} 安装完成 ({len(os.listdir(MOSQ_BIN))} 文件)")
        return True
    print("  ✗ 安装不完整")
    return False


def install_mqtt_venv():
    print()
    print("  --- Python 虚拟环境 ---")
    if os.path.isdir(VENV_DIR) and os.path.isfile(os.path.join(VENV_DIR, "Scripts", "python.exe")):
        print("  ✓ 虚拟环境已存在")
    else:
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

    # 6. 保存配置
    cfg.update({
        "mpython_root": root,
        "build_dir": build_dir,
        "version": "1.60",
    })
    save_config(cfg)

    action = "更新" if is_update else "安装"
    print("=" * 56)
    print(f"  ✓ 插件框架 {action}成功！")
    print()

    # 7. MQTT 环境（自动）
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
