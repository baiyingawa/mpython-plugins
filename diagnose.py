#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MPlugins 诊断脚本 — 检查插件安装状态
用法: python diagnose.py
      python diagnose.py D:\mPython   # 指定 mPython 路径
"""
import os, sys, json, re

def find_mpython():
    """查找 mPython 安装目录"""
    candidates = []
    if len(sys.argv) > 1:
        candidates.append(sys.argv[1].strip('"').strip("'"))
    candidates += [
        "D:/APP DATA/mPython", "D:/mPython",
        os.environ.get("M_PYTHON_HOME", ""),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            build = os.path.join(c, "resources", "app", "build")
            index = os.path.join(build, "index.html")
            if os.path.isfile(index):
                return c, build
    return None, None


def check_file(path, label):
    if not os.path.isfile(path):
        return f"  ✗ {label}: 不存在"
    size = os.path.getsize(path)
    return f"  ✓ {label}: 存在 ({size/1024:.1f}KB)"


def main():
    print("=" * 56)
    print("  MPlugins 诊断脚本")
    print("=" * 56)
    print()

    # 1. 查找 mPython
    root, build_dir = find_mpython()
    if not root:
        print("  [!] 未找到 mPython")
        print("  用法: python diagnose.py D:\\mPython  (指定路径)")
        input("  按 Enter 退出...")
        return
    app_dir = os.path.dirname(build_dir)  # resources/app/
    print(f"  mPython 安装: {root}")
    print(f"  build 目录:   {build_dir}")
    print()

    # 2. 检查关键文件
    print("--- 文件检查 ---")
    print(check_file(build_dir, "mplugin-core.js"))
    print(check_file(build_dir, "index.html"))
    print(check_file(app_dir, "preload.min.js"))
    print(check_file(app_dir, "otherUtil.js"))
    print()

    # 3. mplugin-core.js 版本
    core_path = os.path.join(build_dir, "mplugin-core.js")
    if os.path.isfile(core_path):
        with open(core_path, "r", encoding="utf-8", errors="replace") as f:
            core = f.read()
        ver_match = re.search(r"VERSION\s*=\s*'([\d.]+)'", core)
        if ver_match:
            print(f"  插件版本: v{ver_match.group(1)}")
        else:
            print("  插件版本: 未找到 (可能已损坏)")
        # 检查模式
        if "window.mqttHelper" in core:
            print("  IPC 模式:   preload 桥接 (mqttHelper)")
        elif "require('child_process')" in core:
            print("  IPC 模式:   require (nodeIntegration)")
        print()

    # 4. preload.min.js 补丁检查
    preload_path = os.path.join(app_dir, "preload.min.js")
    if os.path.isfile(preload_path):
        with open(preload_path, "r", encoding="utf-8", errors="replace") as f:
            preload = f.read()

        print("--- preload.min.js 补丁 ---")
        if '"mqttHelper"' in preload:
            # 判断是 IPC 转发版还是直接版
            if 'child_process' in preload:
                print("  状态: ✅ 已修补（直接 require child_process 版）")
            elif 'mqtt-exec' in preload:
                print("  状态: ⚠️ 已修补（旧 IPC 转发版，需要 otherUtil.js 配合）")
            else:
                print("  状态: ⚠️ 已修补（未知版本）")
        else:
            print("  状态: ❌ 未修补（mqttHelper 不存在）")
            print("  建议: 重新运行 python install.py")

        # 检查可写性
        try:
            with open(preload_path, "a") as f:
                pass
            print("  权限: ✅ 可写入")
        except PermissionError:
            print("  权限: ❌ 无法写入（需要管理员权限）")
            print("  建议: 以管理员身份运行 install.py")
        print()

    # 5. otherUtil.js 检查
    other_path = os.path.join(app_dir, "otherUtil.js")
    if os.path.isfile(other_path):
        with open(other_path, "r", encoding="utf-8", errors="replace") as f:
            other = f.read()
        print("--- otherUtil.js IPC 处理器 ---")
        if '"mqtt-exec"' in other:
            print("  mqtt-exec: ✅ 已注册")
        else:
            print("  mqtt-exec: ❌ 未注册（新版不需要，不影响）")
        print()

    # 6. index.html 脚本引用
    index_path = os.path.join(build_dir, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
        print("--- index.html ---")
        if 'mplugin-core.js' in html:
            print("  脚本引用: ✅ 已注入")
        else:
            print("  脚本引用: ❌ 未注入（需要重新安装）")
        print()

    # 7. mplugin_pkg.json
    pkg_path = os.path.join(build_dir, "mplugin_pkg.json")
    if os.path.isfile(pkg_path):
        with open(pkg_path, "r") as f:
            pkg = json.load(f)
        print("--- 包配置 ---")
        print(f"  包路径: {pkg.get('package_dir', '?')}")
        mqtt_dir = os.path.join(pkg.get('package_dir', ''), 'mqtt')
        if os.path.isdir(mqtt_dir):
            print(f"  mqtt/ 目录: ✅ 存在")
        else:
            print(f"  mqtt/ 目录: ❌ 不存在（install.py 不在解压目录运行？）")
    else:
        print("--- 包配置 ---")
        print("  mplugin_pkg.json: ❌ 不存在（版本过旧或安装不完整）")
    print()

    # 8. 总结
    print("=" * 56)
    print("  诊断完成")
    print()
    print("  常见问题:")
    print("  1. 'No handler registered' → 旧版 install.py，重新下载并运行")
    print("  2. 'mqttHelper不可用'      → preload 未修补，重新安装")
    print("  3. 'child_process 不可用'  → nodeIntegration=false + 缺补丁")
    print("  4. 以上都不是              → 带诊断结果截图反馈")
    print("=" * 56)
    input("  按 Enter 退出...")


if __name__ == "__main__":
    main()
