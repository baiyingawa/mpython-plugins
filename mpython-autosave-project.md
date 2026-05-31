# MPlugins — mPython 插件框架

> 最后更新: 2026-05-31 20:50
> 当前版本: v1.50
> 项目状态: 框架 + 自动保存模块 + IoT/MQTT 模块

---

## 一、项目位置

### 工作目录
```
E:\PROJECT\MpythonPlugins\        ← 工作目录（2026-05-28 从 E:\workbuddy 迁移）
├── mplugin-core.js               ← 唯一注入文件（框架 + 所有模块）
├── install.py                    ← 安装/更新脚本
├── uninstall.py                  ← 卸载脚本
├── build.py                      ← 构建/打包脚本
├── install_mqtt.py               ← MQTT 环境安装（下载 Mosquitto + 创建 venv）
├── mqtt/                         ← IoT/MQTT 后端
│   ├── server_manager.py         ← 一键启停（Mosquitto + Python 后端）
│   ├── main.py / run.py          ← FastAPI Web 后端
│   ├── config.py                 ← MQTT 连接配置（web/web233）
│   ├── api_routes.py             ← REST API + WebSocket
│   ├── models.py / mqtt_client.py / mqtt_manager.py
│   ├── requirements.txt
│   ├── .mqtt_cfg.json            ← Python 路径缓存（install_mqtt.py 生成）
│   ├── venv/                     ← Python 虚拟环境（gitignore 建议排除）
│   ├── static/index.html         ← 通用 MQTT Web 面板
│   └── mosquitto/
│       ├── mosquitto.conf        ← Mosquitto 配置
│       ├── mosquitto_passwd.conf  ← 密码文件（zkb/zkb1234, web/web233）
│       ├── mosquitto_acl.conf    ← ACL（两用户全部主题 rw）
│       └── bin/                  ← Mosquitto 二进制（install_mqtt.py 下载，.gitignore 排除）
├── README.md
└── history/                      ← 打包存档
    ├── mpython-mplugins-v1.50.zip
    └── ...
```

### mPython 活跃文件
| 文件 | 路径 | 说明 |
|------|------|------|
| 插件框架 | `D:\APP DATA\mPython\resources\app\build\mplugin-core.js` | 核心脚本 |
| Electron IPC | `D:\APP DATA\mPython\resources\app\otherUtil.js` | 添加 mqtt-exec/spawn/kill IPC |
| Preload | `D:\APP DATA\mPython\resources\app\preload.min.js` | 添加 window.mqttHelper 桥接 |
| 入口页面 | `D:\APP DATA\mPython\resources\app\build\index.html` | 已修改，引入 mplugin-core.js |

---

## 二、已实现模块

### 1. 自动保存 (Autosave)
- 自动保存 `.mxml` 文件（1秒防抖）
- 5 分钟快照备份（最多 100 个轮换）
- 首次保存立即快照
- 无变化跳过保存
- 备份目录 `D:/mpython自动备份/`
- 快照数量显示、备份目录浏览
- 文件切换保护（自动恢复旧路径）
- 顶栏显示路径 + 存档数
- 3 分钟未设路径弹窗提醒

### 2. IoT / MQTT 服务器
**一键启停 Mosquitto MQTT Broker + Python Web 后端**

| 功能 | 说明 |
|------|------|
| Mosquitto Broker | 端口 1883，账号 `zkb/zkb1234` 或 `web/web233`，所有 topic 读写 |
| Python 后端 | FastAPI + WebSocket，端口 8000，自描述文档 `/docs` |
| 自动注入 MQTT 积木 | 开 IoT 时自动添加 `mqtt_common_setup` 块到程序中心 |
| IP 检测 | 自动获取本机 LAN IP 填入积木 |
| 已有检测 | 已有 MQTT 积木则检查 IP 是否匹配，不匹配自动更新 |
| 忙状态锁定 | 启停期间按钮灰色不可点，状态显示 "操作中..." |
| 路径检查 | 未设自动保存路径时弹窗提醒并自动关闭服务 |

---

## 三、IPC 桥接（otherUtil.js → preload.min.js）

| IPC 名称 | 方向 | 说明 |
|----------|------|------|
| `mqtt-exec` | renderer → main | 执行命令返回 stdout |
| `mqtt-spawn` | renderer → main | 后台启动进程（detached） |
| `mqtt-kill` | renderer → main | 按进程名杀进程 |
| `mqtt-open-file` | renderer → main | 打开 .mxml 文件到 mPython |
| `autosave-count-files` | renderer → main | 统计备份文件数 |

**window.mqttHelper（渲染进程 API）：**
```javascript
window.mqttHelper.exec(cmd)       // 返回 Promise<string>
window.mqttHelper.spawn(cmd, args) // 后台启动
window.mqttHelper.kill(name)       // 杀进程
window.mqttHelper.openFile(path)   // 在 mPython 中打开文件
```

---

## 四、Web 面板（mqtt/static/index.html）

通用 MQTT 仪表盘，支持用户自定义主题：

- 6 种视图类型：折线图、数值、状态、文本日志、按钮、滑块
- 输入/输出方向联动筛选视图
- 配置持久化（localStorage）
- WebSocket 实时数据流
- 暗色主题，响应式布局

---

## 五、MQTT 服务架构

```
┌──────────────────┐     MQTT :1883     ┌──────────────────┐
│  Mosquitto       │◄──────────────────►│  Python Backend  │
│  (Broker)        │    (zkb/zkb1234)   │  (FastAPI :8000) │
└──────────────────┘                    └────────┬─────────┘
       ▲  ▲                                      │ WebSocket
       │  │                                      ▼
       │  │                              ┌──────────────────┐
       │  └────── mPython Blockly ──────►│  Web Dashboard   │
       │          (MQTT客户端)           │  (浏览器 :8000)   │
       └─── 终端设备 (掌控板等)           └──────────────────┘
```

---

## 六、开发规范

| 规则 | 说明 |
|------|------|
| 版本号 | `version.txt` 唯一源 |
| 打包 | 手动 `build.py --pack`，不自动构建 |
| Git | `mqtt/mosquitto/bin/` 排除（install_mqtt.py 下载） |
| 发布 | 仅用户说"打包并发布"才操作 GitHub Releases |
| Mosquitto | 安装时下载，不打包进代码 |
