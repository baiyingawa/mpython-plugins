#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MPlugins 修复脚本 — 还原被损坏的 preload/min + index.html
用法: python repair.py
      python repair.py D:\mPython
"""
import os, sys, re, shutil

def find_mpython():
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
            if os.path.isfile(os.path.join(build, "index.html")):
                return c, build, os.path.dirname(build)
    return None, None, None


def main():
    print("=" * 56)
    print("  MPlugins 修复脚本")
    print("=" * 56)
    print()

    root, build_dir, app_dir = find_mpython()
    if not root:
        print("  [!] 未找到 mPython")
        print("  用法: python repair.py D:\\mPython")
        input("  按 Enter 退出...")
        return

    print(f"  mPython: {root}")
    print(f"  build:   {build_dir}")
    print(f"  app:     {app_dir}")
    print()

    # 1. 修复 preload.min.js — 移除所有 MPlugins 补丁
    preload_path = os.path.join(app_dir, "preload.min.js")
    fixed_preload = False
    if os.path.isfile(preload_path):
        print("--- preload.min.js ---")
        with open(preload_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # 逐段拆分：以 try{(function(){ 为分隔，检查每段是否含我们的标记
        marker_start = 'try{(function(){'
        parts = content.split(marker_start)
        new_parts = [parts[0]]  # 第一段（原始代码）保留
        removed = 0
        for seg in parts[1:]:
            # 如果这段含有 mqttHelper 或 autosaveHelper，整体移除
            if 'mqttHelper' in seg or 'autosaveHelper' in seg:
                removed += 1
                continue
            # 否则保留，加回分隔符
            new_parts.append(marker_start + seg)
        new_content = ''.join(new_parts)
        new_content = re.sub(r'\n{3,}', '\n\n', new_content).strip()

        if removed > 0:
            bak = preload_path + ".repair_bak"
            shutil.copy2(preload_path, bak)
            print(f"  [备份] → {bak}")
            print(f"  [移除] {removed} 个 MPlugins 补丁段")
            with open(preload_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"  ✓ preload.min.js 已修复")
            fixed_preload = True
        else:
            print(f"  - 未发现 MPlugins 补丁，无需修复")
    else:
        print(f"  [!] 未找到 preload.min.js")

    # 2. 修复 index.html — 移除 mplugin-core.js 引用 + 还原备份
    index_path = os.path.join(build_dir, "index.html")
    backup_path = index_path + ".backup"
    if os.path.isfile(backup_path):
        shutil.copy2(backup_path, index_path)
        os.remove(backup_path)
        print(f"\n  ✓ index.html 已从备份还原")
    elif os.path.isfile(index_path):
        print(f"\n--- index.html ---")
        with open(index_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
        tag = '<script src="./mplugin-core.js"></script>'
        if tag in html:
            new_html = html.replace(tag, '').replace('\n\n', '\n')
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(new_html)
            print(f"  ✓ 已移除 mplugin-core.js 引用")
        else:
            print(f"  - 未发现 mplugin-core.js 引用")
    else:
        print(f"  [!] 未找到 index.html")

    # 3. 删除 mplugin-core.js
    js_path = os.path.join(build_dir, "mplugin-core.js")
    if os.path.isfile(js_path):
        os.remove(js_path)
        print(f"\n  ✓ 已删除 mplugin-core.js")

    # 4. 删除包配置
    pkg_path = os.path.join(build_dir, "mplugin_pkg.json")
    if os.path.isfile(pkg_path):
        os.remove(pkg_path)
        print(f"  ✓ 已删除 mplugin_pkg.json")

    print()
    if fixed_preload:
        print("  ⚠️ preload.min.js 已被修复。重启 mPython 后 F12 应该恢复。")
    print("  重启 mPython 测试。如果仍然有问题，请联系管理员。")
    print("=" * 56)
    input("  按 Enter 退出...")


if __name__ == "__main__":
    main()
