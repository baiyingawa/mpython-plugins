/**
 * MPlugins — mPython 插件框架 v1.60
 * - 框架核心：日志、顶栏引擎、模块注册表、workspace/API 工具
 * - 模块集成：autosave（自动保存）
 * - 框架自动维护顶栏生命期，模块只管注册自己的逻辑
 */
(function() {
  'use strict';

  // ================================================================
  //  第一部分：框架核心
  // ================================================================

  var VERSION = '1.60';
  var LOG = [];
  // 统一的间距 CSS（所有 body 子元素下移，插件自身除外）
  var SPACER_CSS = 'body>#app{margin-top:28px!important}';

  // ---- 日志系统 ----
  function persistLog() {
    try { localStorage.setItem('mplugin_log', JSON.stringify(LOG.slice(-50))); } catch(e) {}
  }
  function addLog(level, msg) {
    LOG.push({ t: new Date(), level: level, msg: msg });
    if (LOG.length > 200) LOG.splice(0, LOG.length - 200);
    persistLog();
    var prefix = '[MPlugins]';
    if (level === 'ERR') console.error(prefix, msg);
    else if (level === 'WARN') console.warn(prefix, msg);
    else console.log(prefix, msg);
  }
  function log()  { addLog('LOG',  Array.prototype.slice.call(arguments).join(' ')); }
  function warn() { addLog('WARN', Array.prototype.slice.call(arguments).join(' ')); }
  function err()  { addLog('ERR',  Array.prototype.slice.call(arguments).join(' ')); }

  // ---- 日志展示（顶栏 [日志] 弹窗）----
  function showLogModal() {
    try {
      var existing = document.getElementById('mplugin-log-modal');
      if (existing) { existing.style.display = 'flex'; return; }
      var overlay = document.createElement('div');
      overlay.id = 'mplugin-log-modal';
      overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:100000;display:flex;align-items:center;justify-content:center;';
      var box = document.createElement('div');
      box.style.cssText = 'background:#1a1a2e;border:1px solid #0f3460;border-radius:6px;padding:14px;max-width:80%;max-height:80%;display:flex;flex-direction:column;';
      var hdr = document.createElement('div');
      hdr.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;';
      hdr.innerHTML = '<span style="color:#e94560;font-weight:bold;font-size:13px;">MPlugins 日志</span><span style="color:#888;font-size:11px;margin-left:8px;">（点击标题栏模块/关闭框退出）</span>';
      var closeBtn = document.createElement('span');
      closeBtn.textContent = '[关闭]';
      closeBtn.style.cssText = 'color:#888;font-size:12px;cursor:pointer;margin-left:auto;';
      closeBtn.onclick = function() { overlay.style.display = 'none'; };
      hdr.appendChild(closeBtn);
      var ta = document.createElement('textarea');
      ta.readOnly = true;
      ta.id = 'mplugin-log-text';
      ta.style.cssText = 'background:#0d0d1a;color:#b0b0b0;border:1px solid #0f3460;border-radius:4px;padding:8px;font-size:11px;font-family:Consolas,monospace;width:580px;height:360px;resize:both;outline:none;';
      ta.value = LOG.map(function(l) { return '[' + l.t.toLocaleTimeString() + '][' + l.level + '] ' + l.msg; }).join('\n') || '(无日志)';
      box.appendChild(hdr);
      box.appendChild(ta);
      overlay.appendChild(box);
      document.body.appendChild(overlay);
      overlay.onclick = function(e) { if (e.target === overlay) overlay.style.display = 'none'; };
    } catch(e) { console.error('[MPlugins] log modal:', e); }
  }

  // ---- 模块注册表 ----
  var MP = window.MP = {};
  var _modules = {};       // name → module definition
  var _moduleStates = {};  // name → { started: bool }

  MP.register = function(name, def) {
    _modules[name] = def;
    _moduleStates[name] = { started: false };
  };

  MP.get = function(name) { return _modules[name]; };

  // ---- 顶栏引擎 ----
  var _bar = null;
  var _rescueTimer = null;
  var _els = {};       // 框架级元素缓存
  var _clickHandler = null;

  var FRAMEWORK_EL_IDS = [
    'mplugin-bar', 'mplugin-time', 'mplugin-status',
    'mplugin-notice', 'mplugin-logbtn'
  ];

  function gel(id) { try { return document.getElementById(id); } catch(e) { return null; } }

  function refreshEls() {
    for (var i = 0; i < FRAMEWORK_EL_IDS.length; i++) _els[FRAMEWORK_EL_IDS[i]] = gel(FRAMEWORK_EL_IDS[i]);
  }

  /** 事件委托处理顶栏点击 */
  function onBarClick(e) {
    try {
      var id = e.target && (e.target.id || '');
      if (id === 'mplugin-logbtn') { showLogModal(); }
      else if (_clickHandler) { _clickHandler(e); }
    } catch(ex) { err('barClick:', ex.message); }
  }

  /** 注册模块的点击处理 */
  MP.onBarClick = function(handler) { _clickHandler = handler; };

  /** 创建顶栏，返回 modules 插槽的 DOM 引用 */
  function createBar() {
    try {
      // 清理旧版 autosave-bar 残留（旧版升级用户）
      var oldBar = document.getElementById('autosave-bar');
      if (oldBar) { oldBar.parentNode.removeChild(oldBar); }

      if (gel('mplugin-bar')) { refreshEls(); return gel('mplugin-bar'); }
      var bar = document.createElement('div');
      bar.id = 'mplugin-bar';
      bar.style.cssText = 'position:fixed;top:0;left:0;right:0;height:28px;background:linear-gradient(90deg,#1a1a2e,#16213e);color:#e0e0e0;font-size:12px;font-family:Segoe UI,sans-serif;align-items:center;padding:0 12px;z-index:99999;border-bottom:1px solid #0f3460;box-shadow:0 2px 4px rgba(0,0,0,0.3);white-space:nowrap;';
      bar.style.display = 'flex';  // 单独设置，避免 cssText 吞display
      bar.innerHTML =
        '<span style="color:#e94560;font-weight:bold;font-size:13px;margin-right:2px;">MPlugins</span><span style="color:#666;font-size:9px;margin-right:10px;">by uu</span>' +
        '<span id="mplugin-time" style="margin-right:16px;"></span>' +
        '<span id="mplugin-status" style="display:none;"></span>' +
        '<span id="mplugin-module-slot" style="display:flex;align-items:center;flex:1;min-width:0;"></span>' +
        '<span id="mplugin-notice" style="font-size:11px;display:none;position:absolute;left:50%;transform:translateX(-50%);"></span>' +
        '<span id="mplugin-logbtn" style="color:#888;font-size:11px;cursor:pointer;margin-left:6px;">[日志]</span>' +
        '<span style="color:#666;font-size:11px;margin-left:4px;">' + VERSION + '</span>';
      document.body.insertBefore(bar, document.body.firstChild);
      // CSS 注入强制所有 body 子元素下移（仅排除插件自身）
      var barSpacer = document.getElementById('mplugin-bar-spacer');
      function _setSpacerCSS() {
        if (!barSpacer) {
          barSpacer = document.createElement('style');
          barSpacer.id = 'mplugin-bar-spacer';
          document.head.appendChild(barSpacer);
        }
        barSpacer.textContent = SPACER_CSS;
      }
      _setSpacerCSS();
      _bar = bar;
      refreshEls();
      bar.addEventListener('click', onBarClick);

      // 启动 rescueTimer（Vue 可能销毁顶栏 DOM）
      if (_rescueTimer) clearInterval(_rescueTimer);
      _rescueTimer = setInterval(function() {
        try {
          var b = gel('mplugin-bar');
          if (!b) {
            log('重建');
            createBar();
            // 重新注入所有模块的 UI
            for (var n in _modules) {
              try { if (_modules[n].rescue) _modules[n].rescue(); } catch(ex) {}
            }
            return;
          }
          refreshEls();
        } catch(ex) { err('rescue:', ex.message); }
      }, 2000);
      log('v' + VERSION);
      return bar;
    } catch(e) { err('createBar:', e.message); return null; }
  }

  // ---- 模块 API 工厂 ----
  function createModuleAPI(moduleName) {
    var prefix = '[' + moduleName + ']';
    return {
      log:    function() { addLog('LOG',  prefix + ' ' + Array.prototype.slice.call(arguments).join(' ')); },
      warn:   function() { addLog('WARN', prefix + ' ' + Array.prototype.slice.call(arguments).join(' ')); },
      err:    function() { addLog('ERR',  prefix + ' ' + Array.prototype.slice.call(arguments).join(' ')); },
      gel:    gel,
      els:    _els,
      VERSION: VERSION,

      /** 将 HTML 注入顶栏的模块插槽，返回插入的元素 */
      injectSlotHTML: function(html) {
        var slot = gel('mplugin-module-slot');
        if (!slot) return null;
        slot.insertAdjacentHTML('beforeend', html);
        return slot.lastElementChild;
      },

      /** 设置模块插槽内容（替换全部） */
      setSlotHTML: function(html) {
        var slot = gel('mplugin-module-slot');
        if (!slot) return;
        slot.innerHTML = html;
      },

      /** 获取/刷新框架元素缓存 */
      refreshEls: refreshEls,

      /** Workspace 查找 */
      getWorkspace: function() {
        try {
          if (window.vm && window.vm.$store && window.vm.$store.state && window.vm.$store.state.workspace) {
            var ws = window.vm.$store.state.workspace;
            if (ws && ws.getTopBlocks) return ws;
          }
          var svgs = document.querySelectorAll('svg');
          for (var i = 0; i < svgs.length; i++) {
            if (svgs[i].blocklyWorkspace && svgs[i].blocklyWorkspace.getTopBlocks) return svgs[i].blocklyWorkspace;
          }
        } catch(e) {}
        return null;
      },

      /** 获取 Blockly XML */
      getXML: function(ws) {
        try {
          if (window.vm && window.vm.$store && window.vm.$store.state && window.vm.$store.state.xmlCode) {
            var x = window.vm.$store.state.xmlCode;
            if (x && x !== '<xml xmlns="https://developers.google.com/blockly/xml"></xml>') return x;
          }
        } catch(e) {}
        return '<xml xmlns="https://developers.google.com/blockly/xml"></xml>';
      },

      /** 获取 Vuex state */
      getState: function() {
        try { if (window.vm && window.vm.$store) return window.vm.$store.state; } catch(e) {}
        return null;
      },

      /** 读取文件（同步 XHR，仅用于本地 file://） */
      readFile: function(filePath) {
        try {
          var url = 'file:///' + filePath.replace(/\\/g, '/');
          var xhr = new XMLHttpRequest();
          xhr.open('GET', url, false);
          xhr.overrideMimeType('text/plain;charset=utf-8');
          xhr.send();
          if (xhr.status === 0 || xhr.status === 200) return xhr.responseText;
          return null;
        } catch(e) { return null; }
      },

      /** routerDesk.saveFile 封装 */
      saveFile: function(url, data, absolutePath) {
        if (window.routerDesk && typeof window.routerDesk.saveFile === 'function') {
          return window.routerDesk.saveFile({ url: url, data: data, project: 'project', modeSate: 0, absolutePath: absolutePath || url });
        }
        return false;
      },

      /** localStorage 缓存 */
      getCache: function(key) {
        try { var d = localStorage.getItem('mplugin_' + moduleName + '_' + key); return d ? JSON.parse(d) : null; } catch(e) { return null; }
      },
      setCache: function(key, val) {
        try { localStorage.setItem('mplugin_' + moduleName + '_' + key, JSON.stringify(val)); } catch(e) {}
      },
      removeCache: function(key) {
        try { localStorage.removeItem('mplugin_' + moduleName + '_' + key); } catch(e) {}
      },

      /** 提示/隐藏（框架级通知） */
      showNotice: function(text, color) {
        try {
          var e = gel('mplugin-notice');
          if (!e) return;
          e.textContent = text;
          e.style.color = color || '#ff9800';
          e.style.display = 'inline';
        } catch(ex) {}
      },
      hideNotice: function() {
        try { var e = gel('mplugin-notice'); if (e) e.style.display = 'none'; } catch(ex) {}
      },

      /** 框架时间显示 */
      setTime: function(text, color) {
        try {
          var e = gel('mplugin-time');
          if (e) { e.textContent = text; if (color) e.style.color = color; }
        } catch(ex) {}
      },

      /** 框架状态显示 */
      setStatus: function(text, color) {
        try {
          var e = gel('mplugin-status');
          if (!e) return;
          e.textContent = text;
          e.style.color = color || '#ff9800';
          e.style.display = 'inline';
          if (color === '#4caf50') { setTimeout(function() { try { if (gel('mplugin-status')) gel('mplugin-status').style.display = 'none'; } catch(ex) {} }, 5000); }
        } catch(ex) {}
      },

      /** preload 桥接 */
      helper: window.autosaveHelper || null,

      /** Electron API 桥接 */
      electronAPI: window.electronAPI || null,
    };
  }

  // ---- 工具函数 ----
  function fmt(date) {
    return [date.getHours().toString().padStart(2, '0'), date.getMinutes().toString().padStart(2, '0'), date.getSeconds().toString().padStart(2, '0')].join(':');
  }
  function ts(date) {
    var y = date.getFullYear();
    var M = (date.getMonth() + 1).toString().padStart(2, '0');
    var d = date.getDate().toString().padStart(2, '0');
    var h = date.getHours().toString().padStart(2, '0');
    var m = date.getMinutes().toString().padStart(2, '0');
    var s = date.getSeconds().toString().padStart(2, '0');
    return y + M + d + '_' + h + m + s;
  }

  // ---- 启动所有模块 ----
  function startAllModules() {
    for (var name in _modules) {
      try {
        var def = _modules[name];
        var api = createModuleAPI(name);
        if (def.init) def.init(api);
        _moduleStates[name].started = true;
        log('模块 ' + name + ' 已启动');
      } catch(e) { err('模块 ' + name + ' 启动失败:', e.message); }
    }
  }

  // ================================================================
  //  第二部分：模块 - autosave（自动保存）
  // ================================================================

  MP.register('autosave', {
    name: '自动保存',

    init: function(api) {
      var AUTO_SAVE_DELAY = 1000;
      var BACKUP_INTERVAL = 5 * 60 * 1000;
      var BACKUP_MAX = 100;
      var BACKUP_DIR = 'D:/mpython自动备份/';
      var saveTimer = null;
      var backupTimer = null;
      var lastSaveTime = null;
      var lastXML = '';
      var isSaving = false;
      var foundWs = null;
      var isReady = false;
      var wsSetupDone = false;
      var userSetPath = false;
      var lastFileId = null;
      var appStartedAt = Date.now();
      var alertShown = false;
      var filePicker = null;
      var moduleEls = {};
      var barRef = null;
      var autosaveEnabled = true;

      function mEl(id) {
        try { return document.getElementById(id); } catch(e) { return null; }
      }

      // ====== 注入模块 UI 到顶栏 ======
      var cachedPath = api.getCache('mxml');
      var pv = (cachedPath && cachedPath.absolutePath) || '';
      var slotHTML =
        '<span id="as-status" style="display:none;"></span>' +
        '<span style="color:#888;font-size:11px;margin-left:4px;">路径:</span>' +
        '<span id="as-path-display" style="color:#b0b0b0;font-size:11px;margin-left:4px;flex:1;min-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + (pv || '未设置') + '</span>' +
        '<span id="as-browse-btn" style="color:#4ecdc4;font-size:11px;cursor:pointer;margin-left:4px;text-decoration:underline;">[浏览]</span>' +
        '<span id="as-snapcount" style="color:#555;font-size:11px;margin-left:4px;"></span>' +
        '<span id="as-openbak-btn" style="color:#888;font-size:11px;cursor:pointer;margin-left:4px;text-decoration:underline;">[浏览备份]</span>';
      api.setSlotHTML(slotHTML);

      function refreshModuleEls() {
        moduleEls.status    = mEl('as-status');
        moduleEls.pathDisp  = mEl('as-path-display');
        moduleEls.snapcount = mEl('as-snapcount');
      }
      refreshModuleEls();

      // ====== 文件选择器（原生 Electron）======
      function createFilePicker() {
        if (filePicker) return;
        try {
          filePicker = document.createElement('input');
          filePicker.type = 'file';
          filePicker.accept = '.mxml';
          filePicker.style.display = 'none';
          filePicker.id = 'as-file-picker';
          document.body.appendChild(filePicker);
          filePicker.addEventListener('change', function(e) {
            try {
              if (e.target.files && e.target.files[0]) {
                var fullPath = e.target.files[0].path;
                if (moduleEls.pathDisp) moduleEls.pathDisp.textContent = fullPath;
                api.setCache('mxml', { url: fullPath, absolutePath: fullPath });
                userSetPath = true;
                lastFileId = getCurrentFileId();
                api.hideNotice();
                startBackupTimer();
                api.log('浏览:', fullPath);
              }
              e.target.value = '';
            } catch(ex) { api.err('picker:', ex.message); }
          });
        } catch(e) { api.err('createFilePicker:', e.message); }
      }

      // ====== 点击处理 ======
      MP.onBarClick(function(e) {
        try {
          var id = e.target && (e.target.id || '');
          if (id === 'as-logbtn') { showLogModal(); }
          else if (id === 'as-browse-btn') { if (filePicker) filePicker.click(); }
          else if (id === 'as-openbak-btn') { openBackupDir(); }
        } catch(ex) { api.err('click:', ex.message); }
      });

      function openBackupDir() {
        try {
          if (api.electronAPI && typeof api.electronAPI.openInDefaultBrowser === 'function') {
            api.electronAPI.openInDefaultBrowser('file:///D:/mpython自动备份');
            api.log('浏览备份目录');
          }
        } catch(e) { api.err('openBackupDir:', e.message); }
      }

      // ====== 功能开关 ======
      function toggleAutosave() {
        console.log('[MPlugins DIAG] toggleAutosave 被调用, 当前 autosaveEnabled=' + autosaveEnabled);
        autosaveEnabled = !autosaveEnabled;
        var modDef = MP.get('autosave');
        if (modDef) modDef.enabled = autosaveEnabled;
        console.log('[MPlugins DIAG] toggleAutosave 后, autosaveEnabled=' + autosaveEnabled + ', modDef.enabled=' + (modDef ? modDef.enabled : '?'));

        if (autosaveEnabled) {
          // 开启：恢复顶栏 + margin
          console.log('[MPlugins DIAG] 开启, bar=' + !!document.getElementById('mplugin-bar'));
          var bar = document.getElementById('mplugin-bar');
          if (bar) bar.style.display = 'flex';
          // 恢复 body margin CSS
          var spacer = document.getElementById('mplugin-bar-spacer');
          if (spacer) spacer.textContent = SPACER_CSS;
          if (modDef && modDef.rescue) modDef.rescue();
          startBackupTimer();
          api.setTime('已恢复', '#4caf50');
          api.log('模块已恢复');
        } else {
          // 关闭：隐藏顶栏 + 移除 margin + 隐藏通知
          console.log('[MPlugins DIAG] 关闭');
          if (backupTimer) { clearInterval(backupTimer); backupTimer = null; }
          api.hideNotice();
          var bar = document.getElementById('mplugin-bar');
          if (bar) bar.style.display = 'none';
          var spacer = document.getElementById('mplugin-bar-spacer');
          if (spacer) spacer.textContent = '';
          api.setTime('');
          api.log('模块已暂停');
        }
      }

      // ====== 快照列表 ======
      var SNAPSHOT_KEY = 'mplugin_autosave_snapshots';
      function getSnapshotList() {
        try { var d = localStorage.getItem(SNAPSHOT_KEY); return d ? JSON.parse(d) : []; }
        catch(e) { return []; }
      }
      function saveSnapshotList(list) {
        try { localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(list)); } catch(e) {}
      }

      function updateSnapCount(baseName) {
        try {
          if (!moduleEls.snapcount) refreshModuleEls();
          if (!moduleEls.snapcount) return;
          if (api.helper && typeof api.helper.countFiles === 'function' && baseName) {
            api.helper.countFiles(BACKUP_DIR, baseName).then(function(n) {
              moduleEls.snapcount.textContent = n > 0 ? '存档:' + n : '';
            });
          } else {
            var n = getSnapshotList().length;
            moduleEls.snapcount.textContent = n > 0 ? '存档:' + n : '';
          }
        } catch(e) {}
      }

      // ====== 备份系统 ======
      function startBackupTimer() {
        if (backupTimer) clearInterval(backupTimer);
        backupTimer = setInterval(function() {
          try {
            var target = getTargetPath();
            if (!target) return;
            var baseName = target.path.replace(/^.*[\\/]/, '').replace(/\.mxml$/i, '');
            var bakPath = BACKUP_DIR + baseName + '_bak_main.py.mxml';
            var content = api.readFile(bakPath);
            if (!content || content.length < 50) return;
            takeSnapshot(content, baseName);
          } catch(e) { api.err('backupTimer:', e.message); }
        }, BACKUP_INTERVAL);
        api.log('备份快照 (5min)');
      }

      function takeSnapshot(content, baseName) {
        try {
          var list = getSnapshotList();
          var now = new Date();
          var stamp = ts(now);
          var snapPath;
          if (list.length < BACKUP_MAX) {
            snapPath = BACKUP_DIR + baseName + '_bak_main.py.' + stamp + '.mxml';
          } else {
            var oldest = list.shift();
            snapPath = oldest.path;
          }
          api.saveFile(snapPath, content, snapPath);
          list.push({ path: snapPath, time: now.toISOString() });
          saveSnapshotList(list);
          api.log('快照:', content.length + 'B', '#' + (list.length < BACKUP_MAX ? list.length : '轮换'));
          updateSnapCount(baseName);
        } catch(e) { api.err('takeSnapshot:', e.message); }
      }

      function saveBackup(content, targetPath) {
        try {
          var baseName = targetPath.replace(/^.*[\\/]/, '').replace(/\.mxml$/i, '');
          var safePath = BACKUP_DIR + baseName + '_bak_main.py.mxml';
          api.saveFile(safePath, content, safePath);
          api.log('备份:', 'OK', content.length + 'B', '→', safePath);
          if (getSnapshotList().length === 0) takeSnapshot(content, baseName);
        } catch(e) { api.err('saveBackup:', e.message); }
      }

      function restoreFromBackup(originalPath) {
        try {
          var baseName = originalPath.replace(/^.*[\\/]/, '').replace(/\.mxml$/i, '');
          var bakPath = BACKUP_DIR + baseName + '_bak_main.py.mxml';
          var restoreData = api.readFile(bakPath);
          if (restoreData) {
            api.saveFile(originalPath, restoreData, originalPath);
            api.log('还原:', originalPath);
          }
        } catch(e) { api.err('restore:', e.message); }
      }

      // ====== 路径 ======
      function getTargetPath() {
        try {
          var s = api.getState(); if (!s || s.modeSate !== 0) return null;
          var c = api.getCache('mxml'); return (c && c.absolutePath) ? { path: c.absolutePath, modeSate: 0 } : null;
        } catch(e) { return null; }
      }

      function getCurrentFileId() {
        try {
          var state = api.getState();
          if (!state) return null;
          if (state.xmlFileName) return 'mxml:' + state.xmlFileName;
          if (state.editorList) {
            for (var i = 0; i < state.editorList.length; i++) {
              if (state.editorList[i].select) return 'editor:' + (state.editorList[i].absolutePath || state.editorList[i].path || '');
            }
          }
        } catch(e) {}
        return null;
      }

      function clearSaveState() {
        var cached = api.getCache('mxml');
        if (cached && cached.absolutePath) restoreFromBackup(cached.absolutePath);
        userSetPath = false;
        api.removeCache('mxml');
        if (moduleEls.pathDisp) moduleEls.pathDisp.textContent = '未设置';
        if (backupTimer) { clearInterval(backupTimer); backupTimer = null; }
        api.showNotice('请点击[浏览]选择保存路径！', '#ff9800');
      }

      // ====== 保存 ======
      function silentSave(target) {
        if (!target || target.modeSate !== 0) return false;
        try {
          var ws = api.getWorkspace(); if (!ws) return false;
          var content = api.getXML(ws);
          if (!content || content.length < 15) { api.warn('XML过短:', (content || '').length); return false; }
          if (lastXML && content === lastXML) { api.log('跳过: 无变化'); return false; }
          lastXML = content;

          var now = new Date();
          var since = lastSaveTime ? Math.round((now - lastSaveTime) / 1000) + 's' : '首次';
          var blocks = 0;
          try { var bs = ws.getTopBlocks(true); blocks = bs ? bs.length : 0; } catch(ex) {}
          content = '<!--mPythonType:0-->\r\n' + content;

          api.log('保存:', content.length + 'B', blocks + '块', '距上次' + since, '→', target.path);
          saveBackup(content, target.path);
          api.saveFile(target.path, content, target.path);

          lastSaveTime = now;
          api.setTime('上次保存: ' + fmt(now), '#4caf50');
        } catch(e) { api.warn('保存失败:', e.message); }
        return true;
      }

      function doSave() {
        if (!autosaveEnabled) { api.log('跳过: 已暂停'); return; }
        if (isSaving || !isReady) return;
        var state = api.getState();
        if (state && state.modeSate !== 0) { api.log('跳过: 代码模式'); return; }
        var currentId = getCurrentFileId();
        if (lastFileId !== null && currentId !== null && lastFileId !== currentId) {
          api.log('防护拦截: lastId=' + lastFileId + ' curId=' + currentId);
          clearSaveState();
          return;
        }
        var target = getTargetPath();
        if (!target) { api.log('跳过: 无路径'); return; }
        isSaving = true;
        silentSave(target);
        isSaving = false;
      }

      function trigger() { if (saveTimer) clearTimeout(saveTimer); saveTimer = setTimeout(doSave, AUTO_SAVE_DELAY); }

      // ====== 文件切换保护 ======
      function checkFileChanged() {
        var cur = getCurrentFileId();
        if (!cur) return false;
        if (lastFileId === null) { lastFileId = cur; return false; }
        if (lastFileId !== cur) {
          api.log('文件切换:', lastFileId, '->', cur);
          lastFileId = cur;
          clearSaveState();
          return true;
        }
        return false;
      }

      function startPathWatcher() {
        setInterval(function() {
          try {
            checkFileChanged();
            var cp = api.getCache('mxml');
            if (isReady && !cp && !userSetPath) {
              api.showNotice('请点击[浏览]选择保存路径！', '#ff9800');
              if (Date.now() - appStartedAt > 180000 && !alertShown) {
                alertShown = Date.now();
                window.alert('选择文件路径以开启自动保存！');
                api.log('弹出路径提醒');
              }
            }
            if (alertShown && Date.now() - alertShown > 3600000) alertShown = false;
          } catch(e) {}
        }, 3000);
      }

      // ====== 启动 ======
      function startReadyCheck(ws) {
        var minDelay = 2000, maxDelay = 10000, startedAt = Date.now();
        var lastCount = -1, stableCount = 0;
        setTimeout(function() {
          if (!isReady) {
            isReady = true;
            api.setTime('已连接', '#4caf50');
            api.log('5s就绪');
            var cp = api.getCache('mxml');
            if (!cp && !userSetPath) api.showNotice('请点击[浏览]选择保存路径！', '#ff9800');
          }
        }, minDelay);
        function check() {
          var e = Date.now() - startedAt;
          var b = 0;
          try { var bs = ws.getTopBlocks(true); b = bs ? bs.length : 0; } catch(ex) {}
          if (b === lastCount) stableCount++; else { stableCount = 0; lastCount = b; }
          if (isReady || (e >= minDelay && stableCount >= 2) || e >= maxDelay) {
            if (!isReady) {
              isReady = true;
              api.setTime('就绪(' + Math.round(e / 1000) + 's,' + b + '块)', '#4caf50');
              api.log('就绪');
              var cp2 = api.getCache('mxml');
              if (!cp2 && !userSetPath) api.showNotice('请点击[浏览]选择保存路径！', '#ff9800');
            }
            return;
          }
          api.setTime('加载...(' + Math.round(e / 1000) + 's,' + b + '块)', '#ff9800');
          setTimeout(check, 1000);
        }
        setTimeout(check, 1000);
      }

      function doSetup(ws) {
        if (wsSetupDone) return;
        wsSetupDone = true;
        foundWs = ws;
        if (ws.addChangeListener) ws.addChangeListener(function(e) { if (e && e.type === 'ui') return; trigger(); });
        var blocks = 0;
        try { var bs = ws.getTopBlocks(true); blocks = bs ? bs.length : 0; } catch(ex) {}
        api.log('setup: blocks=' + blocks, 'changeListener OK');
        startReadyCheck(ws);
      }

      // ====== 初始化执行 ======
      try {
        api.removeCache('mxml');
        userSetPath = false;
        createFilePicker();

        var state = api.getState();
        api.log('启动', 'vm=' + !!window.vm, 'rD=' + (typeof window.routerDesk), 'store=' + (state ? '有' : '无'));
        var shellKeys = [];
        try { for (var k in window) if (k.match(/shell|electron|native|bridge/i)) shellKeys.push(k); } catch(ex) {}
        if (shellKeys.length) api.log('shell API:', shellKeys.join(','));

        startPathWatcher();
        if (!moduleEls.snapcount) refreshModuleEls();
        updateSnapCount();

        var ws = api.getWorkspace();
        if (ws) { api.setTime('detect ws', '#ff9800'); doSetup(ws); return; }
        api.log('wait ws...');
        new MutationObserver(function() {
          if (!foundWs) { var w = api.getWorkspace(); if (w) doSetup(w); }
        }).observe(document.body, { childList: true, subtree: true });
        var cnt = 0, tmr = setInterval(function() {
          cnt++;
          if (foundWs) { clearInterval(tmr); return; }
          var w = api.getWorkspace();
          if (w) { api.setTime('ok(' + cnt + 's)', '#4caf50'); doSetup(w); clearInterval(tmr); return; }
          if (cnt <= 5) api.setTime('启动(' + cnt + 's)', '#ff9800');
          else if (cnt <= 10) api.setTime('等待(' + cnt + 's)...', '#ff9800');
          else if (!isReady) { isReady = true; api.setTime('备用模式', '#4caf50'); api.log(cnt + 's备用'); var cp3 = api.getCache('mxml'); if (!cp3 && !userSetPath) api.showNotice('请点击[浏览]选择保存路径！', '#ff9800'); }
        }, 1000);
      } catch(e) { api.err('autosave init:', e.message); }

      // 暴露 toggle 给面板
      var modDef = MP.get('autosave');
      if (modDef) {
        modDef.toggle = toggleAutosave;
        modDef.enabled = true;
        // 暴露 _diag 让全局诊断能读取内部变量
        modDef._diag = function() {
          console.log('[autosave 内部] autosaveEnabled=' + autosaveEnabled);
          console.log('[autosave 内部] backupTimer=' + !!backupTimer);
          console.log('[autosave 内部] isReady=' + isReady);
        };
      }
    },

    /** 顶栏重建时重新注入 UI */
    rescue: function() {
      // rescue 由框架 rescueTimer 自动调用，re-init 时 module init 内部的 UI 创建会重新执行
      // 但 rescue 是直接执行，我们只需重新注入 slot HTML
      var cachedPath = null;
      try { var d = localStorage.getItem('mplugin_autosave_mxml'); cachedPath = d ? JSON.parse(d) : null; } catch(e) {}
      var pv = (cachedPath && cachedPath.absolutePath) || '';
      var slotHTML =
        '<span id="as-status" style="display:none;"></span>' +
        '<span style="color:#888;font-size:11px;margin-left:4px;">路径:</span>' +
        '<span id="as-path-display" style="color:#b0b0b0;font-size:11px;margin-left:4px;flex:1;min-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + (pv || '未设置') + '</span>' +
        '<span id="as-browse-btn" style="color:#4ecdc4;font-size:11px;cursor:pointer;margin-left:4px;text-decoration:underline;">[浏览]</span>' +
        '<span id="as-snapcount" style="color:#555;font-size:11px;margin-left:4px;"></span>' +
        '<span id="as-openbak-btn" style="color:#888;font-size:11px;cursor:pointer;margin-left:4px;text-decoration:underline;">[浏览备份]</span>';
      var slot = document.getElementById('mplugin-module-slot');
      if (slot) slot.innerHTML = slotHTML;
      // 不再调用 refreshModuleEls()（它在 init 闭包里，rescue 访问不到）
      // 如果模块已关闭，重建后也只隐藏顶栏
      try {
        var modDef = MP.get('autosave');
        if (modDef && !modDef.enabled) {
          var bar = document.getElementById('mplugin-bar');
          if (bar) bar.style.display = 'none';
          var spacer = document.getElementById('mplugin-bar-spacer');
          if (spacer) spacer.textContent = '';
          var notice = document.getElementById('mplugin-notice');
          if (notice) notice.style.display = 'none';
        }
      } catch(e) {}
    }
  });

  // ================================================================
  //  模块 - iot（IoT 服务器管理器）
  // ================================================================

  MP.register('iot', {
    name: 'IoT 服务器',

    init: function(api) {
      // 从 mplugin_pkg.json 读取包路径（install.py 写入）
      var _pkgDir = '';
      try {
        var _req = new XMLHttpRequest();
        _req.open('GET', './mplugin_pkg.json', false);
        _req.send();
        if (_req.status === 200 || _req.status === 0) {
          var _cfg = JSON.parse(_req.responseText);
          _pkgDir = _cfg.package_dir || '';
        }
      } catch(e) {}
      // 回退硬编码路径（本地开发）
      var scriptDir = (_pkgDir || 'E:\\PROJECT\\MpythonPlugins') + '\\mqtt';
      var python = scriptDir + '\\venv\\Scripts\\python.exe';
      var script = scriptDir + '\\server_manager.py';
      var mqttEls = {};
      var _iotStopTriggered = false;

      // 注入失败帮助弹窗
      function showInjectHelp(localIp) {
        var overlay = document.createElement('div');
        overlay.id = 'mplugin-inject-help';
        overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;z-index:999999;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;';
        var imgPath = (_pkgDir || 'E:\\PROJECT\\MpythonPlugins') + '/mqtt/static/mqtt-block-help.png';
        overlay.innerHTML =
          '<div style="background:#1a1a2e;border:1px solid #0f3460;border-radius:10px;padding:20px;max-width:600px;width:90%;max-height:90vh;overflow:auto;box-shadow:0 8px 32px rgba(0,0,0,0.5);color:#e0e0e0;font-family:Segoe UI,sans-serif;">' +
            '<h2 style="color:#e94560;margin:0 0 12px;font-size:16px;">MQTT 积木注入失败</h2>' +
            '<p style="color:#b0b0b0;font-size:13px;margin:0 0 16px;">请检查后重试，或手动添加 MQTT 连接积木：</p>' +
            '<div style="margin-bottom:12px;">' +
              '<span style="color:#888;font-size:12px;">1. 在程序中拖出 MQTT 连接积木</span><br>' +
              '<span style="color:#888;font-size:12px;">2. 服务器 IP 填入：<strong style="color:#4ecdc4;font-size:14px;">' + localIp + '</strong></span><br>' +
              '<span style="color:#888;font-size:12px;">3. 账号 zkb 密码 zkb1234 端口 1883</span><br>' +
              '<span style="color:#888;font-size:12px;">4. 参考下方积木位置</span>' +
            '</div>' +
            '<div style="background:#0a0a1e;border-radius:6px;padding:8px;margin-bottom:16px;text-align:center;">' +
              '<img src="file:///' + imgPath.replace(/\\\\/g, '/') + '" style="max-width:100%;border-radius:4px;" onerror="this.style.display=\'none\'">' +
            '</div>' +
            '<button onclick="var e=document.getElementById(\'mplugin-inject-help\');if(e)e.parentNode.removeChild(e);" style="background:#e94560;color:#fff;border:none;border-radius:6px;padding:8px 24px;font-size:14px;cursor:pointer;display:block;margin:0 auto;">确定</button>' +
          '</div>';
        document.body.appendChild(overlay);
      }

      // 子进程执行封装：优先用 preload 暴露的 mqttHelper，备用 require (nodeIntegration:true 时)
      var _cpExec = null;
      try { _cpExec = require('child_process').exec; } catch(e) {}
      function execAsync(cmd) {
        return new Promise(function(resolve, reject) {
          // 优先 mqttHelper（preload 桥接，最可靠）
          var helper = window.mqttHelper;
          if (helper && typeof helper.exec === 'function') {
            helper.exec(cmd).then(resolve).catch(reject);
            return;
          }
          // 备用：直接 child_process
          if (!_cpExec) { reject('child_process 不可用'); return; }
          _cpExec(cmd, { maxBuffer: 1024 * 1024, cwd: scriptDir, windowsHide: true }, function(error, stdout, stderr) {
            if (error) reject(error.message + '\nstderr:' + stderr);
            else resolve(stdout);
          });
        });
      }

      // MQTT 积木模板
      var MQTT_BLOCK_XML =
        '<block type="mqtt_common_setup" id="mqtt_auto_{ID}" x="{X}" y="{Y}">' +
          '<value name="client_id"><shadow type="text"><field name="TEXT">zkb</field></shadow></value>' +
          '<value name="server"><shadow type="text"><field name="TEXT">{SERVER_IP}</field></shadow></value>' +
          '<value name="port"><shadow type="math_number"><field name="NUM">1883</field></shadow></value>' +
          '<value name="user"><shadow type="text"><field name="TEXT">zkb</field></shadow></value>' +
          '<value name="password"><shadow type="text"><field name="TEXT">zkb1234</field></shadow></value>' +
          '<value name="keepalive"><shadow type="math_number"><field name="NUM">30</field></shadow></value>' +
        '</block>';

      function injectMqttBlock(localIp, tryCount) {
        if (tryCount === undefined) tryCount = 0;
        var injectAction = ''; // 'add'=新增 'update'=仅更新IP ''=无需变更
        try {
          // 1. 获取 workspace 和当前 XML
          var ws = api.getWorkspace();
          if (!ws) { api.warn('inject: 无 workspace'); return; }
          var currentXml = api.getXML(ws);
          if (!currentXml || currentXml.length < 20) { api.warn('inject: XML 过短'); return; }

          // 2. 解析 XML，查找已有 MQTT 积木
          var parser = new DOMParser();
          var xmlDoc = parser.parseFromString(currentXml, 'text/xml');
          var existingBlocks = xmlDoc.querySelectorAll('block[type="mqtt_common_setup"]');
          var needUpdate = false;
          var needAdd = false;

          if (existingBlocks.length > 0) {
            // 已有 MQTT 积木 → 检查 IP
            api.log('注入: 找到已有 MQTT 积木');
            for (var i = 0; i < existingBlocks.length; i++) {
              var blk = existingBlocks[i];
              // 查找 server → shadow → field TEXT
              var serverVal = blk.querySelector('value[name="server"]');
              if (serverVal) {
                var shadow = serverVal.querySelector('shadow[type="text"], block[type="text"]');
                if (shadow) {
                  var field = shadow.querySelector('field[name="TEXT"]');
                  if (field && field.textContent !== localIp) {
                    field.textContent = localIp;
                    needUpdate = true;
                    injectAction = 'update';
                    api.log('注入: 更新 IP ' + localIp);
                  }
                }
              }
            }
          } else {
            // 没有 MQTT 积木 → 新增
            needAdd = true;
            injectAction = 'add';
          }

          if (!needUpdate && !needAdd) {
            injectAction = '';
            api.log('注入: IP 已正确，无需修改');
            return;
          }

          // 3. 序列化修改后的 XML
          var mergedXml = '<!--mPythonType:0-->\n' + new XMLSerializer().serializeToString(xmlDoc.documentElement);

          if (needAdd) {
            // 4a. 新增：计算中心位置
            var topBlocks = [];
            try { topBlocks = ws.getTopBlocks(true) || []; } catch(e) {}
            var minX = 0, minY = 0, maxX = 0, maxY = 0;
            if (topBlocks.length > 0) {
              for (var i = 0; i < topBlocks.length; i++) {
                var b = topBlocks[i];
                try {
                  var xy = b.getRelativeToSurfaceXY ? b.getRelativeToSurfaceXY() : null;
                  if (xy) {
                    var bw = b.getHeightWidth ? (b.getHeightWidth().width || 200) : 200;
                    if (i === 0) { minX = xy.x; maxX = xy.x + bw; minY = xy.y; maxY = xy.y + 80; }
                    else { minX = Math.min(minX, xy.x); maxX = Math.max(maxX, xy.x + bw); minY = Math.min(minY, xy.y); maxY = Math.max(maxY, xy.y + 80); }
                  }
                } catch(e) {}
              }
            }
            var centerX = Math.round((minX + maxX) / 2 - 130);
            var centerY = minY - 180;

            // 5a. 生成积木 XML 插入
            var blockXml = MQTT_BLOCK_XML
              .replace('{SERVER_IP}', localIp || '127.0.0.1')
              .replace('{ID}', Date.now().toString(36))
              .replace('{X}', centerX)
              .replace('{Y}', centerY);
            var insertPos = mergedXml.lastIndexOf('</xml>');
            if (insertPos < 0) { api.warn('inject: 无法找到 </xml>'); return; }
            mergedXml = mergedXml.substring(0, insertPos) + '  ' + blockXml + '\n' + mergedXml.substring(insertPos);
            api.log('注入: 新增 MQTT 积木');
          } else {
            api.log('注入: 已更新 IP');
          }

          // 6. 读取 autosave 路径
          var autoCache = null;
          try { var d = localStorage.getItem('mplugin_autosave_mxml'); autoCache = d ? JSON.parse(d) : null; } catch(e) {}
          var savePath = (autoCache && autoCache.absolutePath) || '';
          if (!savePath) { api.warn('注入: 无保存路径'); return; }

          // 7. 保存
          api.saveFile(savePath, mergedXml, savePath);
          api.log('注入: 已保存 ' + savePath);

          // 8. 打开文件（优先 mqttHelper IPC，备用 Electron shell）
          try {
            var helper = window.mqttHelper;
            if (helper && typeof helper.openFile === 'function') {
              helper.openFile(savePath);
              api.log('注入: 已打开');
            } else {
              var _shell = require('electron').shell;
              if (_shell && typeof _shell.openPath === 'function') {
                _shell.openPath(savePath);
                api.log('注入: 已打开');
              }
            }
          } catch(e) { api.log('注入: 文件已保存，请手动打开'); }

          api.log('注入完成');

          // 验证 + 重试逻辑
          // tryCount 0=首次 1=自动重试 2=询问重试 3-4=继续询问 5=放弃
          // injectAction 'add'=新增 'update'=仅更新IP ''=无需变更
          setTimeout(function() {
            try {
              var ws2 = api.getWorkspace();
              if (!ws2) return;
              var xml2 = api.getXML(ws2);
              if (xml2 && xml2.indexOf('mqtt_common_setup') > -1) {
                api.log('验证通过: MQTT 积木已加载');
                if (injectAction === 'add') {
                  // 新增 MQTT → 始终弹窗
                  alert('注入成功！\n已启动IoT服务器并自动注入模块至程序中');
                } else if (injectAction === 'update' && tryCount >= 2) {
                  // 更新 IP → 仅重试后弹窗（原有逻辑）
                  alert('注入成功！');
                }
                // injectAction='' 或 update+首次成功 → 不弹窗
                return;
              }
              // 未找到 → 需要重试
              tryCount++;
              if (tryCount >= 5) {
                showInjectHelp(localIp);
                api.log('注入失败: 已显示帮助面板');
                return;
              }
              if (tryCount <= 1) {
                // 前两次自动重试
                api.log('注入重试: 第 ' + (tryCount+1) + ' 次');
                injectMqttBlock(localIp, tryCount);
              } else {
                // 后续每次询问用户
                if (confirm('MQTT 积木注入可能未成功，第 ' + (tryCount+1) + ' 次尝试，是否重新注入？')) {
                  api.log('注入重试: 用户确认');
                  injectMqttBlock(localIp, tryCount);
                } else {
                  api.log('注入重试: 用户取消');
                }
              }
            } catch(e) { api.err('验证失败:', e.message); }
          }, 3000);
        } catch(e) { api.err('注入失败:', e.message); }
      }

      function startAll() {
        _iotStopTriggered = false;
        api.log('启动中...');
        api.setTime('MQTT启动...', '#ff9800');
        execAsync('"' + python + '" "' + script + '" start').then(function(out) {
          try { var info = JSON.parse(out.trim().split('\n').pop()); } catch(e) { api.err('解析输出失败:', e.message); return; }
          if (info.status === 'starting' || info.backend_url) {
            var url = info.backend_url || 'http://127.0.0.1:8000';
            var mqttIp = info.mqtt_host || '127.0.0.1';
            api.setTime('MQTT ' + mqttIp + ':1883', '#4caf50');
            api.showNotice(mqttIp + ':1883 | 后端:' + url, '#4caf50');
            api.log('IoT 服务已启动 (' + mqttIp + ':1883)');
              // 自动注入 MQTT 连接积木（需先设置自动保存路径）
              var autoCache = null;
              try { var d = localStorage.getItem('mplugin_autosave_mxml'); autoCache = d ? JSON.parse(d) : null; } catch(e) {}
              if (autoCache && autoCache.absolutePath) {
                injectMqttBlock(mqttIp);
              } else {
                window.alert('请先在自动保存中设置保存路径！\n点击顶栏 [浏览] 按钮选择要保存的 .mxml 文件。');
                api.log('注入跳过: 未设置保存路径');
                _iotStopTriggered = true;
                var modDef = MP.get('iot');
                if (modDef) modDef.enabled = false;
                stopAll();
              }
            }
          }).catch(function(err) {
            api.err('启动失败:', err);
            api.setTime('MQTT失败', '#e94560');
          }).then(function() {
            // 完成：解除忙碌、刷新面板（stopAll 已触发时跳过）
            if (!_iotStopTriggered) {
              var m = MP.get('iot'); if (m) m.busy = false;
              if (_panelEl) { _panelEl.innerHTML = buildPanelHTML(); bindPanelHandlers(); }
            }
          });
        }

      function stopAll() {
        api.log('停止中...');
        execAsync('"' + python + '" "' + script + '" stop').then(function(out) {
          api.setTime('');
          api.hideNotice();
          api.log('IoT 服务已停止');
        }).catch(function(err) {
          api.err('停止失败:', err);
        }).then(function() {
          var m = MP.get('iot'); if (m) m.busy = false;
          if (_panelEl) { _panelEl.innerHTML = buildPanelHTML(); bindPanelHandlers(); }
        });
      }

      function toggleIot() {
        var modDef = MP.get('iot');
        if (!modDef || modDef.busy) return;
        modDef.busy = true;
        modDef.enabled = !modDef.enabled;
        if (modDef.enabled) { startAll(); }
        else { stopAll(); }
      }

      // 暴露 toggle 给面板
      var modDef = MP.get('iot');
      if (modDef) { modDef.toggle = toggleIot; modDef.enabled = false; }
    },

    rescue: function() {
      // bar 重建后恢复状态（仅显示已启动过，不重启）
    }
  });

  // ================================================================
  //  第三部分：启动
  // ================================================================

  /** 创建 MPlugins 浮动面板按钮 */
  var _panelState = { expanded: false };
  var _panelEl = null;

  // ====== 诊断工具 ======
  window.__mplugin_diag = function() {
    console.log('========== MPlugins 诊断 ==========');
    // 1. 框架对象
    console.log('MP:', typeof MP, 'MP.toggleModule:', typeof MP.toggleModule);
    console.log('_modules:', Object.keys(_modules));
    console.log('_moduleStates:', JSON.stringify(_moduleStates));
    for (var n in _modules) {
      console.log('  [' + n + '] enabled:', _modules[n].enabled, 'toggle:', typeof _modules[n].toggle);
    }
    // 2. DOM 元素
    var bar = document.getElementById('mplugin-bar');
    if (bar) { console.log('bar: OK, display=' + bar.style.display + ', position=' + (bar.style.position || getComputedStyle(bar).position)); }
    else { console.log('bar: 不存在!'); }
    
    var panel = document.getElementById('mplugin-panel');
    if (panel) {
      console.log('panel: OK, display=' + panel.style.display);
      var tgl = document.getElementById('mplugin-panel-toggle-autosave');
      if (tgl) {
        console.log('  toggle: bg=' + tgl.style.background + ', onclick=' + (tgl.getAttribute('onclick') || '无'));
        var dot = tgl.querySelector('div');
        if (dot) console.log('  dot: left=' + dot.style.left + ' right=' + dot.style.right);
        else console.log('  dot: 不存在');
      } else { console.log('  toggle: 不存在'); }
      var st = document.getElementById('mplugin-panel-status-autosave');
      if (st) console.log('  status: ' + st.textContent + ' color=' + st.style.color);
      else console.log('  status elem: 不存在');
    } else { console.log('panel: 不存在'); }
    
    // 3. Body 状态
    console.log('body margin-top:', getComputedStyle(document.body).marginTop);
    console.log('body position:', getComputedStyle(document.body).position);
    console.log('body overflow:', getComputedStyle(document.body).overflow);
    // mqttHelper
    console.log('mqttHelper:', typeof window.mqttHelper);
    // 列出 body 直接子元素
    var children = document.body.children;
    console.log('body 子元素数:', children.length);
    for (var i = 0; i < children.length; i++) {
      var c = children[i];
      var pos = getComputedStyle(c).position;
      var top = getComputedStyle(c).top;
      var mt = getComputedStyle(c).marginTop;
      console.log('  [' + i + ']', c.tagName, (c.id ? '#' + c.id : ''), (c.className ? '.' + c.className.split(' ').join('.') : ''), 'pos=' + pos, 'top=' + top, 'marginTop=' + mt);
    }
    
    // 4. 自动保存模块内部变量（通过闭包暴露）
    var modDef = _modules['autosave'];
    if (modDef && modDef._diag) modDef._diag();
    
    console.log('====================================');
  };

  // 在面板添加诊断按钮
  function buildPanelHTML() {
    var rows = '';
    for (var n in _modules) {
      var started = _moduleStates[n] && _moduleStates[n].started;
      var moduleDef = _modules[n];
      var isRunning = started && (moduleDef.enabled !== false);
      var isBusy = moduleDef.busy === true;
      var statusText = isBusy ? '操作中...' : (isRunning ? '运行中' : (started ? '已暂停' : '未启动'));
      var statusColor = isBusy ? '#888' : (isRunning ? '#4caf50' : '#888');
      var toggleBg = isBusy ? '#444' : (isRunning ? '#4caf50' : '#555');
      var toggleDot = isRunning ? 'right:3px' : 'left:3px';
      var cursorStyle = isBusy ? 'not-allowed' : 'pointer';
      // 忙碌时 onclick 仍在，但 MP.toggleModule 会通过 modDef.busy 拦截
      rows += '<tr>' +
        '<td style="padding:8px;border-bottom:1px solid #0a0a1e;color:#b0b0b0;font-size:13px;">' + (moduleDef.name || n) + '</td>' +
        '<td style="padding:8px;border-bottom:1px solid #0a0a1e;"><span id="mplugin-panel-status-' + n + '" style="color:' + statusColor + ';font-size:12px;">' + statusText + '</span></td>' +
        '<td style="padding:8px;border-bottom:1px solid #0a0a1e;text-align:right;">' +
          '<div id="mplugin-panel-toggle-' + n + '" onclick="MP.toggleModule(\'' + n + '\')" style="display:inline-block;width:36px;height:20px;background:' + toggleBg + ';border-radius:10px;cursor:' + cursorStyle + ';transition:background 0.2s;position:relative;vertical-align:middle;">' +
            '<div style="position:absolute;top:2px;width:16px;height:16px;background:#fff;border-radius:50%;' + toggleDot + ';transition:left 0.2s,right 0.2s;"></div>' +
          '</div>' +
        '</td></tr>';
    }
    return '<div style="position:relative;width:800px;padding:0;">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 30px 10px 14px;border-bottom:1px solid #0f3460;">' +
      '<span style="color:#e94560;font-weight:bold;font-size:15px;">MPlugins</span>' +
      '<span style="color:#666;font-size:11px;margin-right:10px;">v' + (VERSION || '1.60') + '</span>' +
      '<span id="mplugin-diag-btn" style="color:#ff9800;font-size:11px;cursor:pointer;">[诊断]</span></div>' +
      '<div style="padding:0 14px 14px;">' +
      '<table style="width:100%;font-size:12px;border-collapse:collapse;margin-top:10px;">' +
      '<tr><th style="text-align:left;padding:6px 8px;border-bottom:1px solid #0f3460;color:#888;">模块</th><th style="text-align:left;padding:6px 8px;border-bottom:1px solid #0f3460;color:#888;">状态</th><th style="text-align:right;padding:6px 8px;border-bottom:1px solid #0f3460;color:#888;">开关</th></tr>' +
      rows +
      '</table>' +
      '<div style="margin-top:12px;color:#555;font-size:11px;">已加载 ' + Object.keys(_modules).length + ' 个模块</div></div>' +
      '<div style="position:absolute;top:8px;right:8px;color:#888;font-size:18px;cursor:pointer;width:24px;height:24px;line-height:24px;text-align:center;" id="mplugin-panel-close">×</div></div>';
  }

  /** 面板中点击模块行切换开关 */
  MP.toggleModule = function(name) {
    console.log('[MPlugins DIAG] toggleModule 被调用, name=' + name);
    var modDef = _modules[name];
    if (!modDef) { console.log('[MPlugins DIAG] modDef 不存在!'); return; }
    if (modDef.busy) { console.log('[MPlugins DIAG] 忙碌中, 跳过'); return; }
    console.log('[MPlugins DIAG] toggle前 enabled=' + modDef.enabled);
    // 调 toggle 函数，内部自己管理 enabled
    if (typeof modDef.toggle === 'function') {
      modDef.toggle();
    }
    console.log('[MPlugins DIAG] toggle后 enabled=' + modDef.enabled);
    // 重建面板 HTML（最可靠）
    if (_panelEl) {
      _panelEl.innerHTML = buildPanelHTML();
      bindPanelHandlers();
    }
  };

  /** 绑定面板关闭 + 诊断按钮事件 */
  function bindPanelHandlers() {
    if (!_panelEl) return;
    var cb = document.getElementById('mplugin-panel-close');
    if (cb) cb.onclick = function() { _panelState.expanded = false; _panelEl.style.display = 'none'; };
    var db = document.getElementById('mplugin-diag-btn');
    if (db) db.onclick = function() { window.__mplugin_diag(); };
  }

  /** 更新面板中某模块行的开关与状态文本 —— 已废弃，改用面板重建 */
  function updatePanelRow(name, modDef) {
    // 保留空函数避免引用报错，逻辑已移至面板重建
  }

  function createPluginPanel() {
    try {
      // 浮动按钮（可拖动）
      var btn = document.createElement('div');
      btn.id = 'mplugin-float-btn';
      btn.textContent = 'M';
      btn.style.cssText = 'width:32px;height:32px;background:#e94560;color:#fff;position:fixed;top:150px;right:40px;z-index:999;border-radius:50%;font-size:16px;font-weight:bold;display:flex;align-items:center;justify-content:center;cursor:grab;box-shadow:0 2px 8px rgba(0,0,0,.3);user-select:none;';

      // 拖动逻辑
      var dragState = { dragging: false, startX: 0, startY: 0, origX: 0, origY: 0 };
      btn.addEventListener('mousedown', function(e) {
        e.preventDefault();
        dragState.dragging = true;
        dragState.startX = e.clientX;
        dragState.startY = e.clientY;
        dragState.origX = btn.offsetLeft;
        dragState.origY = btn.offsetTop;
        btn.style.cursor = 'grabbing';
      });
      document.addEventListener('mousemove', function(e) {
        if (!dragState.dragging) return;
        var dx = e.clientX - dragState.startX;
        var dy = e.clientY - dragState.startY;
        var btnW = 32, btnH = 32;
        var maxX = window.innerWidth - btnW;
        var maxY = window.innerHeight - btnH;
        var newX = Math.max(0, Math.min(maxX, dragState.origX + dx));
        var newY = Math.max(28, Math.min(maxY, dragState.origY + dy));
        btn.style.left = newX + 'px';
        btn.style.top = newY + 'px';
        btn.style.right = 'auto';
      });
      document.addEventListener('mouseup', function() {
        if (dragState.dragging) {
          dragState.dragging = false;
          btn.style.cursor = 'grab';
        }
      });
      document.body.appendChild(btn);

      // 面板（默认隐藏）
      var panel = document.createElement('div');
      panel.id = 'mplugin-panel';
      panel.style.cssText = 'display:none;position:fixed;top:80px;left:50%;transform:translateX(-50%);z-index:99999;background:#1a1a2e;border:1px solid #0f3460;border-radius:8px;padding:0;box-shadow:0 4px 24px rgba(0,0,0,.5);';
      panel.innerHTML = buildPanelHTML();
      _panelEl = panel;
      document.body.appendChild(panel);

      // 关闭按钮事件
      var cb = document.getElementById('mplugin-panel-close');
      if (cb) cb.onclick = function() { _panelState.expanded = false; panel.style.display = 'none'; };
      // 诊断按钮事件
      var db = document.getElementById('mplugin-diag-btn');
      if (db) db.onclick = function() { window.__mplugin_diag(); };

      // 点击浮动按钮 Toggle
      btn.onclick = function() {
        _panelState.expanded = !_panelState.expanded;
        panel.style.display = _panelState.expanded ? 'block' : 'none';
      };
    } catch(e) { console.warn('[MPlugins] createPluginPanel:', e); }
  }

  MP.register('beautify', {
    name: '界面美化',

    init: function(api) {
      var _obs = []; // MutationObservers

      function apply() {
        // 1. 树标签缩短
        try {
          var _ob1 = new MutationObserver(function() {
            var els = document.querySelectorAll('.blocklyTreeLabel');
            for (var i = 0; i < els.length; i++) {
              if (els[i].textContent === '微信小程序（掌控iot小程序）') {
                els[i].textContent = '掌控iot';
              }
            }
          });
          _ob1.observe(document.body, { childList: true, subtree: true, characterData: true });
          _obs.push(_ob1);
          // 立即扫一遍
          var els = document.querySelectorAll('.blocklyTreeLabel');
          for (var i = 0; i < els.length; i++) {
            if (els[i].textContent === '微信小程序（掌控iot小程序）') {
              els[i].textContent = '掌控iot';
            }
          }
        } catch(e) { api.err('美化(label):', e.message); }

        // 2. 删除 graphArea 白色面板
        try {
          var _ob2 = new MutationObserver(function() {
            var ga = document.querySelector('div.graphArea.white-D');
            if (ga && ga.parentNode) {
              ga.parentNode.removeChild(ga);
            }
          });
          _ob2.observe(document.body, { childList: true, subtree: true });
          _obs.push(_ob2);
          var ga = document.querySelector('div.graphArea.white-D');
          if (ga && ga.parentNode) {
            ga.parentNode.removeChild(ga);
          }
        } catch(e) { api.err('美化(graphArea):', e.message); }

        api.log('界面美化已启用');
      }

      function clean() {
        // 断开观察器（已做的修改保留到重启）
        for (var i = 0; i < _obs.length; i++) {
          try { _obs[i].disconnect(); } catch(e) {}
        }
        _obs = [];
        api.log('界面美化已禁用（修改将在重启后还原）');
      }

      // 挂载 toggle
      var modDef = MP.get('beautify');
      if (modDef) {
        modDef.toggle = function() {
          if (modDef.enabled) {
            clean();
            modDef.enabled = false;
          } else {
            apply();
            modDef.enabled = true;
          }
        };
        modDef.enabled = true;  // 默认开启
      }

      apply();
    }
  });

  function boot() {
    // 隐藏 mPython 自带助手
    try {
      var s = document.createElement('style');
      s.id = 'mplugin-assist-style';
      s.textContent = '.assistant-container{display:none!important}';
      document.head.appendChild(s);
    } catch(e) {}
    createBar();
    startAllModules();
    createPluginPanel();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() { setTimeout(boot, 300); });
  } else { setTimeout(boot, 300); }

})();
