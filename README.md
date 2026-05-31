# MPlugins for mPython

> **本插件为 AI 辅助开发**
>
> 版本 v1.60 · mPython 插件框架 — 自动保存 + IoT MQTT

## 功能

### 🔄 自动保存
- 拖拽 Blockly 积木块时自动保存（1 秒防抖）
- 仅图形化模式（.mxml），代码模式跳过
- 选择文件：通过 [浏览] 按钮选取 .mxml 文件
- 备份机制：每次保存同时写到 `D:\mpython自动备份\`
- 5 分钟快照备份（最多 100 个轮换）
- 文件切换防护：检测到切换文件时自动从备份还原旧文件
- 快照数量显示、备份目录浏览

### 📡 IoT MQTT 服务器
- **一键启停** Mosquitto MQTT Broker（面板开关）
- **Web 后端** FastAPI + WebSocket，端口 8000
- **自动注入** MQTT 连接积木到程序中心
- **IP 检测** 自动获取本机 LAN IP 填入积木
- **智能更新** 已有积木则自动修正 IP，不重复添加
- **忙状态锁定** 启停期间按钮灰色不可点

- **🌐 Web 仪表盘**
- 通用可配置 MQTT 面板（`http://本机IP:8000`）
- 6 种视图：折线图、数值、状态、文本日志、按钮、滑块
- 用户自定义主题（增删改、方向、显示方式）
- WebSocket 实时数据流
- 配置持久化

## 安装

### 基础插件
```bash
# 一键安装全部功能（插件框架 + Mosquitto + Python 后端）
python install.py
```

安装脚本自动完成：
- 安装插件框架到 mPython
- 下载 Mosquitto MQTT Broker
- 创建 Python 虚拟环境
- 安装后端依赖（FastAPI + aiomqtt）

## MQTT 账号

| 用户 | 密码 | 权限 |
|------|------|------|
| `zkb` | `zkb1234` | 所有主题读写 |
| `web` | `web233` | 所有主题读写 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `mplugin-core.js` | 插件框架（自动保存 + IoT MQTT 模块） |
| `install.py` | 基础安装/更新脚本 |
| `uninstall.py` | 卸载脚本 |
| `install_mqtt.py` | MQTT 环境安装（下载 Mosquitto + 创建 venv） |
| `mqtt/` | MQTT 后端（server_manager.py + config.py + web 面板等） |

## 项目文档

详见 [`MpythonPlugins-project.md`](./MpythonPlugins-project.md)

## 依赖

- Windows 系统
- Python 3.x
- mPython 0.8.7+

## 免责声明

> 本插件由 AI 辅助开发完成，仅供学习交流使用。
