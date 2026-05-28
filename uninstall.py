#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MPlugins for mPython v1.50 — 卸载脚本
======================================
还原 index.html，删除 mplugin-core.js，清除已保存的 mPython 位置配置。
"""
import os, sys, shutil, json

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_FILE    = os.path.join(os.path.expanduser("~"), ".mpython_autosave", "mpython_cfg.json")
SCRIPT_NAME = "mplugin-core.js"


def load_config():
    if os.path.isfile(CFG_FILE):
        try:
            with open(CFG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}


def find_mpython(saved_root=None):
    """查找 mPython 安装路径，优先使用已保存的路径"""
    candidates = []
    if saved_root and os.path.isdir(saved_root):
        candidates.append(saved_root)

    candidates += [
        "D:/APP DATA/mPython",
        "D:/Program Files/mPython",
        "C:/Program Files/mPython",
        "C:/Program Files (x86)/mPython",
        os.environ.get("M_PYTHON_HOME", ""),
    ]
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
            if os.path.isfile(os.path.join(build, "index.html")):
                return c, build
    return None, None


def main():
    print("=" * 56)
    print("  MPlugins for mPython v1.50  卸载程序")
    print("=" * 56)
    print()

    cfg = load_config()
    saved_root = cfg.get("mpython_root", "")

    root, build_dir = find_mpython(saved_root)
    if not root:
        print("  [!] 未找到 mPython 安装目录")
        print("  请输入 build 目录路径（例如 D:\\APP DATA\\mPython\\resources\\app\\build）")
        user = input("  路径: ").strip().strip('"').strip("'")
        if not user or not os.path.isdir(user):
            print("  卸载中止")
            input("  按 Enter 键退出...")
            return
        build_dir = user

    index_html    = os.path.join(build_dir, "index.html")
    index_bak     = index_html + ".backup"
    plugin_file   = os.path.join(build_dir, SCRIPT_NAME)

    print(f"  ✓ mPython: {root}")
    print(f"  ✓ 构建目录: {build_dir}")
    print()
    print(f"  将要执行的操作:")
    has_bak = os.path.isfile(index_bak)
    has_js  = os.path.isfile(plugin_file)

    actions = []
    if has_bak:
        actions.append("还原 index.html（来自备份）")
    elif has_js:
        actions.append(f"从 index.html 移除 {SCRIPT_NAME} 引用")
    else:
        actions.append("index.html 无需修改")

    actions.append(f"删除 {plugin_file}" if has_js else f"{SCRIPT_NAME} 不存在，跳过")
    actions.append("清除已保存的 mPython 位置配置")

    for a in actions:
        print(f"    · {a}")

    print()
    confirm = input("  确认卸载？(Y/n): ").strip().lower()
    if confirm == 'n':
        print("  卸载已取消。")
        input("  按 Enter 键退出...")
        sys.exit(0)
    print()

    # 还原 index.html
    if has_bak:
        shutil.copy2(index_bak, index_html)
        os.remove(index_bak)
        print(f"  ✓ 还原 index.html（来自备份）")
    else:
        if os.path.isfile(index_html):
            with open(index_html, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
            old = html
            tag = f'<script src="./{SCRIPT_NAME}"></script>'
            html = html.replace(tag, '')
            if html != old:
                with open(index_html, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  ✓ 从 index.html 移除 {SCRIPT_NAME} 引用")
            else:
                print(f"  - index.html 中未发现 {SCRIPT_NAME} 引用")
        else:
            print(f"  [!] 未找到 {index_html}")

    # 删除插件文件
    if has_js:
        os.remove(plugin_file)
        print(f"  ✓ 已删除 {plugin_file}")
    else:
        print(f"  - {SCRIPT_NAME} 不存在，跳过")

    # 清除配置
    if os.path.isfile(CFG_FILE):
        try:
            os.remove(CFG_FILE)
            print(f"  ✓ 已清除配置 {CFG_FILE}")
        except Exception as e:
            print(f"  [!] 配置清除失败: {e}")

    print()
    print("  ✓ 卸载完成。重启 mPython 后插件将消失。")
    print("  （备份目录 D:\\mpython自动备份\\ 中的文件不会被删除）")
    print("=" * 56)
    print()
    input("  按 Enter 键退出...")


if __name__ == "__main__":
    main()
