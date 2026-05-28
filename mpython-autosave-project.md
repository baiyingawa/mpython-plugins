# MPlugins — mPython 插件框架

> 最后更新: 2026-05-26 22:13
> 当前版本: v1.50
> 项目状态: 框架重构完成，从单插件升级为框架+模块架构

---

## 一、项目位置

### 工作目录
```
E:\workbuddy\MpythonPlugins\     ← 新工作目录
├── mplugin-core.js              ← 唯一注入文件（框架 + 所有模块）
├── install.py                   ← 安装/更新脚本
├── uninstall.py                 ← 卸载脚本
├── build.py                     ← 构建/打包脚本
├── README.html                  ← 使用说明
├── version.txt                  ← 版本号（唯一源）
└── history\                     ← 打包存档
    └── mpython-mplugins-v1.30.zip
```

### mPython 活跃文件
| 文件 | 路径 | 说明 |
|------|------|------|
| 插件框架 | `D:\APP DATA\mPython\resources\app\build\mplugin-core.js` | 核心脚本 |
| 入口页面 | `D:\APP DATA\mPython\resources\app\build\index.html` | 已修改，引入 mplugin-core.js |
| 原始备份 | `D:\APP DATA\mPython\resources\app\build\index.html.backup` | 未修改的原始文件 |
| 旧版保留 | `D:\APP DATA\mPython\resources\app\build\autosave.js` | 保留作为降级备用 |
| mPython 主程序 | `D:\APP DATA\mPython\mPython.exe` | Electron 应用 |

### mPython 核心结构
```
D:\APP DATA\mPython\
├── mPython.exe                    # Electron 主程序
├── resources\app\
│   ├── package.json               # Electron 配置
│   ├── mainJs.min.js              # 主进程（压缩）
│   ├── preload.min.js             # preload（contextBridge API）
│   ├── otherUtil.js               # 主进程工具（IPC处理，已扩展）
│   └── build\                     # 渲染进程（核心）
│       ├── index.html             # 入口页面 ← 注入了 mplugin-core.js
│       ├── mplugin-core.js        # ← MPlugins 框架
│       ├── autosave.js            # ← 保留旧版
│       ├── app.db0e780e.js        # Vue 应用（webpack 打包）
│       ├── chunk-vendors.*.js     # 三方库（Blockly 在此打包）
│       └── ...
```

---

## 二、架构设计

### 模块注册 API

```javascript
MP.register('moduleName', {
  name: '显示名',
  init: function(api) { /* 初始化 */ },
  rescue: function() { /* 顶栏重建后恢复 UI */ }
});
```

`api` 参数提供的能力：

| API | 说明 |
|-----|------|
| `api.log/warn/err` | 框架日志系统 |
| `api.gel(id)` | 按 ID 获取 DOM 元素 |
| `api.getWorkspace()` | 查找 Blockly workspace |
| `api.getXML(ws)` | 获取 Blockly XML |
| `api.getState()` | 获取 Vuex store state |
| `api.readFile(path)` | 读取本地文件（同步 XHR） |
| `api.saveFile(url, data, absPath)` | 调用 routerDesk.saveFile |
| `api.getCache/setCache/removeCache` | 模块专属 localStorage |
| `api.showNotice/hideNotice` | 框架级通知（居中显示） |
| `api.setTime/setStatus` | 框架状态显示 |
| `api.helper` | preload 桥接（autosaveHelper） |
| `api.electronAPI` | Electron preload API |
| `api.setSlotHTML(html)` | 设置模块在顶栏的内容 |
| `api.injectSlotHTML(html)` | 向顶栏追加内容 |
| `api.refreshEls()` | 刷新框架元素缓存 |

### 框架核心层（约100行）

```
框架核心
├── 日志系统 (log/warn/err/showLogModal)
├── 模块注册表 (MP.register/MP.get)
├── 顶栏引擎 (createBar, rescueTimer)
├── 模块 API 工厂 (createModuleAPI)
└── 启动器 (boot → startAllModules)
```

### 模块：autosave（约400行）

```
模块架构
├── 配置常量 (AUTO_SAVE_DELAY, BACKUP_DIR 等)
├── UI 初始化 (注入顶栏模块插槽 HTML)
├── 文件选择器 (原生 Electron input[type=file])
├── 备份系统
│   ├── saveBackup — 每次保存同步到 D:\mpython自动备份\
│   ├── restoreFromBackup — 切换文件时还原
│   ├── startBackupTimer — 5min快照
│   ├── takeSnapshot — 写入时间戳快照，轮换100个
│   └── updateSnapCount — 顶栏存档数显示
├── 保存系统
│   ├── trigger → doSave (1s防抖)
│   ├── silentSave — XML对比跳过无变化
│   └── lastFileId 防护 — 切换拦截
├── 文件切换保护 (checkFileChanged / clearSaveState)
├── 启动器 (startPathWatcher / startReadyCheck / doSetup)
└── 重建救援 (rescue 回调)
```

---

## 三、关键技术发现

### 3.0 封闭 Electron 的逆向操作

mPython 是一个**封闭的 Electron 应用**，无官方插件系统。所有功能通过修改 `build/index.html` 注入脚本实现：

- **无 SDK** — 只能通过 DOM、Vuex store、preload API 间接操作
- **Vue 渲染层不可控** — 组件可能随时销毁重建，事件绑定会丢失
- **contextIsolation** — 渲染进程无法 `require('fs')`，文件操作只能走 preload
- **Webpack 隔离** — Blockly 等库在闭包中，不能通过 `window.*` 访问

### 3.1 Blockly 寻找路径
`window.Blockly` **不存在**（Webpack 打包）。通过 `window.vm.$store.state.workspace` 找到。

### 3.2 fs 模块不可用
`require('fs')` 在渲染进程不可用。文件操作走 `window.routerDesk.saveFile()`。

### 3.3 saveFile 文件名规则
如果 `url` 路径中不包含 `main.py` 字符串，mPython 自动在末尾追加 `main.py`。
备份文件名含 `_bak_main.py.mxml` 绕过此限制。

### 3.4 preload / 主进程扩展
已对 mPython 基础文件做了以下扩展：

| 文件 | 扩展内容 |
|------|---------|
| `preload.min.js` | 追加 `autosaveHelper.countFiles(dir, prefix)` — 通过 IPC 统计备份文件数 |
| `otherUtil.js` | 追加 `ipcMain.handle('autosave-count-files')` + 修改 `open-external-link` 支持 `file://` |

---

## 四、开发历程

| 版本 | 说明 |
|------|------|
| v1.01–1.02 | Blockly 未暴露到 window → find workspace 方法确立 |
| v1.03 | 发现 `window.vm.$store.state.workspace` |
| v1.04 | Ctrl+S 不可用 → 需用 Blockly changeListener |
| v1.05–1.06 | `routerDesk.saveFile` 确认可用，但路径不对走 fallback |
| v1.07–1.09 | XML 获取方式 + 日志系统 + `saveFileE` 弹对话框问题 |
| v1.10–1.14 | 保存到 .py 的问题 → `modeSate` 区分，`xmlCode` 获取 XML |
| v1.15 | 首个可用版本，内容脚本 + 文件轮询 |
| v1.16 | 按钮绑定修复（.onclick → DOM 劫持）|
| v1.17 | Vue 加载竞赛修复（无限轮询）|
| v1.18 | 修复保存到 .py（仅 .mxml + 图形模式）|
| v1.19 | 自动检测路径覆盖问题（userSetPath 标志）|
| v1.20 | 移除自动检测，纯手动选路径 |
| v1.21 | 输入框替代按钮（cloning 崩溃）|
| v1.22 | try-catch 全包裹，addEventListener |
| v1.23 | 原生文件选择器替代输入框 |
| v1.24 | 输入框改为只读显示 + 日志弹窗修复 |
| v1.25–1.27 | 文件切换保护（lastFileId）+ 备份系统 |
| v1.28 | backup 文件名修复（_bak_main.py.mxml）|
| v1.29 | 打包系统：build.py + 安装/更新分离 + 路径配置保存 |
| v1.30 | **架构重构**：从 autosave.js 单文件升级为 MPlugins 框架 + 模块化架构 |

---

## 五、已知限制

1. **readFileViaFetch 使用同步 XHR** — 仅用于还原备份（本地 file:// 读取，耗时 < 10ms）
2. **备份目录不可自动创建** — Electron contextIsolation 导致 `fs.mkdir` 不可用，需 install.py 预先创建
3. **快照删除依赖轮换覆盖** — 达到 100 个上限后覆盖最旧文件
4. **依赖 IPC 扩展** — 存档文件计数和浏览备份功能需修改 `otherUtil.js` 和 `preload.min.js`
5. **仅 Windows** — mPython 的 Electron 限制，无 macOS/Linux 版本
