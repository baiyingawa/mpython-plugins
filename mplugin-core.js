/**
 * MPlugins — mPython 插件框架 v1.30
 * - 框架核心：日志、顶栏引擎、模块注册表、workspace/API 工具
 * - 模块集成：autosave（自动保存）
 * - 框架自动维护顶栏生命期，模块只管注册自己的逻辑
 */
(function() {
  'use strict';

  // ================================================================
  //  第一部分：框架核心
  // ================================================================

  var VERSION = '1.30';
  var LOG = [];

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
      if (gel('mplugin-bar')) { refreshEls(); return gel('mplugin-bar'); }
      var bar = document.createElement('div');
      bar.id = 'mplugin-bar';
      bar.style.cssText = 'position:fixed;top:0;left:0;right:0;height:28px;background:linear-gradient(90deg,#1a1a2e,#16213e);color:#e0e0e0;font-size:12px;font-family:Segoe UI,sans-serif;display:flex;align-items:center;padding:0 12px;z-index:99999;border-bottom:1px solid #0f3460;box-shadow:0 2px 4px rgba(0,0,0,0.3);';
      bar.innerHTML =
        '<span style="color:#e94560;font-weight:bold;font-size:13px;margin-right:2px;">MPlugins</span><span style="color:#666;font-size:9px;margin-right:10px;">by uu</span>' +
        '<span id="mplugin-time" style="margin-right:16px;"></span>' +
        '<span id="mplugin-status" style="display:none;"></span>' +
        '<span id="mplugin-module-slot" style="display:flex;align-items:center;flex:1;min-width:0;"></span>' +
        '<span id="mplugin-notice" style="font-size:11px;display:none;position:fixed;left:50%;transform:translateX(-50%);"></span>' +
        '<span id="mplugin-logbtn" style="color:#888;font-size:11px;cursor:pointer;margin-left:6px;">[日志]</span>' +
        '<span style="color:#666;font-size:11px;margin-left:4px;">' + VERSION + '</span>';
      document.body.insertBefore(bar, document.body.firstChild);
      document.body.style.marginTop = '28px';
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
      refreshModuleEls();
    }
  });

  // ================================================================
  //  第三部分：启动
  // ================================================================

  /** 创建 MPlugins 浮动面板按钮 */
  var _panelState = { expanded: false };

  function buildPanelHTML() {
    var rows = '';
    for (var n in _modules) {
      var started = _moduleStates[n] && _moduleStates[n].started;
      rows += '<tr><td style="padding:6px 8px;border-bottom:1px solid #0a0a1e;color:#b0b0b0;">' + (_modules[n].name || n) + '</td>' +
        '<td style="padding:6px 8px;border-bottom:1px solid #0a0a1e;color:' + (started ? '#4caf50' : '#888') + ';">' + (started ? '运行中' : '未启动') + '</td></tr>';
    }
    return '<div style="position:relative;width:800px;padding:0;">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid #0f3460;">' +
      '<span style="color:#e94560;font-weight:bold;font-size:15px;">MPlugins</span>' +
      '<span style="color:#666;font-size:11px;">v' + (VERSION || '1.30') + '</span></div>' +
      '<div style="padding:0 14px 14px;">' +
      '<table style="width:100%;font-size:12px;border-collapse:collapse;margin-top:10px;">' +
      '<tr><th style="text-align:left;padding:6px 8px;border-bottom:1px solid #0f3460;color:#888;">模块</th><th style="text-align:left;padding:6px 8px;border-bottom:1px solid #0f3460;color:#888;">状态</th></tr>' +
      rows +
      '</table>' +
      '<div style="margin-top:12px;color:#555;font-size:11px;">已加载 ' + Object.keys(_modules).length + ' 个模块</div></div>' +
      '<div style="position:absolute;top:8px;right:8px;color:#888;font-size:18px;cursor:pointer;width:24px;height:24px;line-height:24px;text-align:center;" id="mplugin-panel-close">×</div></div>';
  }

  function createPluginPanel() {
    try {
      // 浮动按钮
      var btn = document.createElement('div');
      btn.id = 'mplugin-float-btn';
      btn.textContent = 'M';
      btn.style.cssText = 'width:32px;height:32px;background:#e94560;color:#fff;position:absolute;top:150px;right:40px;z-index:999;border-radius:50%;font-size:16px;font-weight:bold;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.3);';
      document.body.appendChild(btn);

      // 面板（默认隐藏）
      var panel = document.createElement('div');
      panel.id = 'mplugin-panel';
      panel.style.cssText = 'display:none;position:fixed;top:80px;left:50%;transform:translateX(-50%);z-index:99999;background:#1a1a2e;border:1px solid #0f3460;border-radius:8px;padding:0;box-shadow:0 4px 24px rgba(0,0,0,.5);';
      panel.innerHTML = buildPanelHTML();
      document.body.appendChild(panel);

      // 关闭按钮事件
      var closeBtn = document.getElementById('mplugin-panel-close');
      if (closeBtn) closeBtn.onclick = function() { _panelState.expanded = false; panel.style.display = 'none'; };

      // 点击浮动按钮 Toggle
      btn.onclick = function() {
        _panelState.expanded = !_panelState.expanded;
        panel.style.display = _panelState.expanded ? 'block' : 'none';
      };
    } catch(e) { console.warn('[MPlugins] createPluginPanel:', e); }
  }

  function boot() {
    // 隐藏 mPython 自带助手（我们用自己创建的按钮）
    try {
      var s = document.createElement('style');
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
