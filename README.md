# MPlugins for mPython

> **本插件为 AI 辅助开发**
>
> 版本 v1.80 · mPython 插件框架 — 自动保存 + IoT MQTT + 界面美化

## 功能

### 🔄 自动保存
- 拖拽 Blockly 积木块时自动保存（1 秒防抖）
- 选择文件：通过 [浏览] 按钮选取 .mxml 文件
- 备份机制：每次保存同时写到 `D:\mpython自动备份\`
- 5 分钟快照备份（最多 100 个轮换）
- 文件切换防护：检测到切换文件时自动从备份还原旧文件
- **自动捕获路径**：通过 Vuex store 订阅自动监听 mPython 打开文件事件，无需手动点击 [浏览]
- 快照数量显示、备份目录浏览

### 📡 IoT MQTT 服务器
- **一键启停** Mosquitto MQTT Broker（面板开关）
- **自动注入** MQTT 连接积木到程序中心，自动获取本机 LAN IP 填入积木并注入已打开的程序
- **智能更新** 已有积木则自动修正 IP，不重复添加
- **🌐 Web 仪表盘** （FastAPI + WebSocket）
  - 通用可配置 MQTT 面板（`http://本机IP:8000`）
  - 6 种视图：折线图、数值、状态、文本日志、按钮、滑块
  - 用户自定义主题（增删改、方向、显示方式）
  - WebSocket 实时数据流
  - 配置持久化

### 🎨 界面美化
- **树标签缩短**：`微信小程序（掌控iot小程序）` → `掌控iot`
- **隐藏 graphArea** 白色面板
- **控制台自动隐藏/展开**：鼠标离开 N 秒后自动收起，有新数据自动展开（支持独立开关）
- 所有美化功能可即时开关（重启还原）

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
