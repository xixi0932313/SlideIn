# SlideIn Agent - Web 服务
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

try:
    from .agent import SlideInAgent
    from .state import AgentState
    from .config import load_config
except ImportError:
    from agent import SlideInAgent
    from state import AgentState
    from config import load_config

app = FastAPI(title="SlideIn Agent")

_sessions: dict[str, SlideInAgent] = {}
_output_dir = (Path(os.getenv("SLIDEIN_OUTPUT_DIR", "."))).resolve()


def _get_or_create_agent(session_id: str) -> SlideInAgent:
    if session_id not in _sessions:
        _sessions[session_id] = SlideInAgent(config=load_config())
    return _sessions[session_id]


class ChatRequest(BaseModel):
    message: str = ""
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    state: str
    session_id: str
    export_files: list = []


@app.post("/api/chat", response_model=ChatResponse)
def api_chat(req: ChatRequest, request: Request):
    session_id = req.session_id or request.headers.get("X-Session-ID") or str(uuid.uuid4())
    agent = _get_or_create_agent(session_id)
    message = (req.message or "").strip()
    if not message:
        return ChatResponse(
            reply="请输入内容。",
            state=agent.state.value,
            session_id=session_id,
            export_files=[],
        )
    try:
        reply = agent.turn(message)
    except Exception as e:
        import traceback
        traceback.print_exc()
        reply = "处理您的请求时出错，请稍后重试。错误：" + (str(e).strip() or repr(e))
    export_files = []
    for i, item in enumerate(agent.last_export_paths):
        export_files.append({"label": item.get("label", "文件"), "download_id": str(i)})
    return ChatResponse(
        reply=reply,
        state=agent.state.value,
        session_id=session_id,
        export_files=export_files,
    )


@app.get("/api/download")
def api_download(session_id: str, index: str):
    if not session_id or index is None:
        raise HTTPException(status_code=400, detail="缺少 session_id 或 index")
    agent = _sessions.get(session_id)
    if not agent or not agent.last_export_paths:
        raise HTTPException(status_code=404, detail="未找到导出文件")
    idx = int(index)
    if idx < 0 or idx >= len(agent.last_export_paths):
        raise HTTPException(status_code=404, detail="索引无效")
    path = Path(agent.last_export_paths[idx].get("url", ""))
    if not path.is_absolute():
        path = _output_dir / path
    path = path.resolve()
    try:
        path.resolve().relative_to(_output_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="不允许访问该路径")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=path.name)


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SlideIn Agent</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #fffbf3; }
    .app-root { display: flex; min-height: 100vh; width: 100vw; background: #fffbf3; color: #333; overflow: hidden; }
    .sidebar { width: 56px; background: #f9f5ff; color: #4b5563; display: flex; flex-direction: column; align-items: center; padding: 12px 8px; gap: 16px; }
    .sidebar-logo { width: 32px; height: 32px; border-radius: 999px; flex-shrink: 0; background-image: url(/avatar.png); background-size: cover; background-position: center; background-repeat: no-repeat; overflow: hidden; clip-path: circle(50% at 50% 50%); -webkit-clip-path: circle(50% at 50% 50%); }
    .sidebar-btn { width: 40px; height: 40px; border-radius: 12px; border: none; background: #e5defd; color: #4338ca; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 12px; }
    .sidebar-btn span { font-size: 18px; }
    .sidebar-btn:hover { background: #ddd6fe; }
    .sidebar-spacer { flex: 1; }
    .sidebar-footer { display: flex; flex-direction: column; gap: 8px; align-items: center; }
    .sidebar-btn-ghost { width: 48px; height: 48px; border-radius: 999px; border: 1px solid #9ca3af; background: transparent; color: #6b7280; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 20px; }
    .sidebar-btn-ghost:hover { background: rgba(148,163,184,0.08); }
    .history-drawer { width: 0; transition: width 0.2s ease; background: #ede9fe; color: #374151; overflow: hidden; }
    .history-drawer.open { width: 200px; }
    .history-inner { padding: 16px 12px; height: 100%; display: flex; flex-direction: column; gap: 8px; }
    .history-title { font-size: 0.9rem; font-weight: 600; margin-bottom: 4px; }
    .history-item { padding: 8px 10px; border-radius: 8px; background: #f5f0ff; cursor: pointer; font-size: 0.85rem; color: #111827; }
    .history-item:hover { background: #e9ddff; }
    .main { flex: 1; display: flex; flex-direction: column; padding: 12px 16px; width: 100%; min-width: 0; }
    .top-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
    .title { font-size: 1.1rem; font-weight: 600; }
    .new-project-btn { width: 30px; height: 30px; border-radius: 999px; border: none; background: #e5e7eb; color: #4b5563; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 18px; }
    .new-project-btn:hover { background: #d1d5db; }
    .content-row { flex: 1; display: flex; gap: 16px; min-height: 0; }
    .content-row.preview-wide .chat-panel { flex: 1; }
    .content-row.preview-wide .preview-shell { flex: 2; }
    .content-row.preview-full .chat-panel { display: none; }
    .content-row.preview-full .preview-shell { flex: 1; }
    .chat-panel { flex: 2; background: #fff; border-radius: 16px; padding: 12px 16px; display: flex; flex-direction: column; box-shadow: 0 1px 3px rgba(15,23,42,0.08); }
    .messages { flex: 1; overflow-y: auto; padding: 4px 0 8px 0; }
    .msg { margin-bottom: 12px; display: flex; gap: 8px; }
    .msg.user { justify-content: flex-end; }
    .msg.agent { justify-content: flex-start; }
    .msg .bubble { max-width: 90%; padding: 10px 14px; border-radius: 16px; white-space: pre-wrap; word-break: break-word; font-size: 0.95rem; }
    .msg.user .bubble { background: #2563eb; color: #fff; border-bottom-right-radius: 4px; }
    .msg.agent .bubble { background: #f9fafb; color: #111827; border-bottom-left-radius: 4px; box-shadow: 0 1px 3px rgba(15,23,42,0.06); }
    .agent-avatar { width: 32px; height: 32px; border-radius: 999px; flex-shrink: 0; background-image: url(/avatar.png); background-size: cover; background-position: center; background-repeat: no-repeat; overflow: hidden; clip-path: circle(50% at 50% 50%); -webkit-clip-path: circle(50% at 50% 50%); }
    .input-row { display: flex; gap: 8px; padding-top: 8px; border-top: 1px solid #e5e7eb; margin-top: 4px; align-items: center; }
    .upload-btn { width: 34px; height: 34px; border-radius: 999px; border: 1px solid #d1d5db; background: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 16px; color: #4b5563; }
    .upload-btn:hover { background: #f3f4f6; }
    #input { flex: 1; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 999px; font-size: 0.95rem; outline: none; }
    #input:focus { border-color: #2563eb; box-shadow: 0 0 0 1px rgba(37,99,235,0.15); }
    #send { width: 42px; height: 42px; background: #e5e7eb; color: #4b5563; border: none; border-radius: 999px; cursor: pointer; font-size: 20px; display: flex; align-items: center; justify-content: center; }
    #send:hover { background: #d4d4d8; }
    #send:disabled { background: #9ca3af; cursor: not-allowed; }
    .export-links { margin-top: 8px; }
    .export-links a { display: inline-block; margin-right: 12px; color: #2563eb; font-size: 0.85rem; }
    .preview-shell { flex: 1; display: flex; align-items: stretch; position: relative; }
    .preview-toggle { width: 20px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: #6b7280; user-select: none; }
    .preview-toggle-inner { width: 18px; height: 60px; border-radius: 999px 0 0 999px; background: #e5e7eb; display: flex; align-items: center; justify-content: center; font-size: 14px; }
    .preview-panel { flex: 1; max-width: none; background: #f3f4f6; color: #111827; border-radius: 16px; padding: 12px 14px; display: flex; flex-direction: column; border: 1px solid #e5e7eb; box-shadow: 0 1px 4px rgba(15,23,42,0.12); }
    .preview-panel.collapsed { transform: scaleX(0.02); opacity: 0; pointer-events: none; }
    .preview-title { display: flex; align-items: center; justify-content: space-between; font-size: 0.95rem; font-weight: 600; margin-bottom: 8px; }
    .preview-title-text { flex: 1; }
    .preview-fullscreen-btn { border: none; background: transparent; color: #6b7280; cursor: pointer; font-size: 14px; padding: 2px 4px; }
    .preview-fullscreen-btn:hover { color: #111827; }
    .preview-main { flex: 1; display: flex; gap: 8px; min-height: 0; position: relative; }
    .preview-body { flex: 1; border-radius: 12px; background: #fff; padding: 10px 12px; font-size: 0.85rem; overflow-y: auto; border: 1px solid #e5e7eb; }
    .preview-body[contenteditable="true"] { outline: none; }
    .preview-side-tools { width: 44px; display: flex; flex-direction: column; align-items: stretch; gap: 6px; }
    .preview-tool-btn { border-radius: 10px; border: 1px solid #e5e7eb; background: #fff; color: #4b5563; font-size: 12px; padding: 6px 4px; cursor: pointer; }
    .preview-tool-btn:hover { background: #f3f4f6; }
    .preview-tool-options { position: absolute; top: 0; left: 0; padding: 6px 8px; background: #fff; border-radius: 8px; box-shadow: 0 8px 20px rgba(15,23,42,0.16); display: none; flex-direction: column; gap: 4px; min-width: 140px; z-index: 25; }
    .preview-tool-option { font-size: 0.8rem; padding: 4px 6px; border-radius: 6px; cursor: pointer; color: #374151; white-space: nowrap; }
    .preview-tool-option:hover { background: #f3f4f6; }
    .preview-footer { margin-top: 8px; display: flex; justify-content: flex-end; }
    #polishBtn { border-radius: 999px; border: none; padding: 6px 14px; font-size: 0.85rem; cursor: pointer; background: #4f46e5; color: #fff; }
    #polishBtn:hover { background: #4338ca; }
    .preview-placeholder { color: #6b7280; }
    .quick-form { padding: 10px 12px; border-radius: 12px; background: #f9fafb; font-size: 0.9rem; }
    .quick-form-section { margin-bottom: 8px; }
    .chip-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
    .chip-group.hidden { display: none; }
    .chip-option { border-radius: 999px; padding: 4px 10px; border: 1px solid #e5e7eb; background: #fff; cursor: pointer; font-size: 0.85rem; }
    .chip-option.selected { background: #4f46e5; color: #fff; border-color: #4f46e5; }
    .settings-panel { position: fixed; left: 76px; bottom: 16px; width: 260px; background: #fff; border-radius: 12px; box-shadow: 0 10px 25px rgba(15,23,42,0.18); padding: 10px 12px; font-size: 0.85rem; z-index: 30; display: none; }
    .settings-panel.open { display: block; }
    .settings-header { font-weight: 600; font-size: 0.9rem; margin-bottom: 6px; }
    .settings-row { position: relative; padding: 6px; border-radius: 8px; margin-bottom: 4px; cursor: default; }
    .settings-row:hover { background: #f3f4f6; }
    .settings-label { color: #374151; }
    .settings-options { position: absolute; left: 100%; top: 0; margin-left: 8px; padding: 6px 8px; background: #fff; border-radius: 8px; box-shadow: 0 8px 20px rgba(15,23,42,0.16); display: none; flex-direction: column; gap: 4px; min-width: 120px; z-index: 40; }
    .settings-option { padding: 4px 6px; border-radius: 6px; cursor: pointer; white-space: nowrap; }
    .settings-option:hover { background: #e5e7eb; }
    .preview-panel.preview-animate { animation: previewPulse 1.5s ease-in-out infinite; }
    @keyframes previewPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.9; } }
  </style>
</head>
<body>
  <div class="app-root">
    <aside class="sidebar">
      <div class="sidebar-logo" role="img" aria-label="Logo"></div>
      <button class="sidebar-btn" id="historyToggle" title="历史项目"><span>&#128193;</span></button>
      <div class="sidebar-spacer"></div>
      <div class="sidebar-footer">
        <button class="sidebar-btn-ghost" id="settingsBtn" title="设置">&#9881;</button>
      </div>
    </aside>
    <div class="history-drawer" id="historyDrawer">
      <div class="history-inner">
        <div class="history-title">历史项目</div>
        <div class="history-item" data-project-id="1">项目一：示例课程汇报</div>
        <div class="history-item" data-project-id="2">项目二：新品发布会</div>
      </div>
    </div>
    <main class="main">
      <div class="top-bar">
        <div class="title">SlideIn Agent &#8212; 智能 PPT 助手</div>
        <button class="new-project-btn" id="newProjectBtn" title="创建新项目">+</button>
      </div>
      <div class="content-row" id="contentRow">
        <section class="chat-panel">
          <div class="messages" id="messages"></div>
          <div class="input-row">
            <button id="uploadBtn" class="upload-btn" title="上传本地文件">&#128206;</button>
            <input type="file" id="uploadInput" multiple accept="audio/*,video/*,image/*,.pdf,.doc,.docx,.ppt,.pptx,.txt" style="display:none" />
            <input type="text" id="input" placeholder="输入需求，例如：帮我做一个关于碳中和的课程汇报" />
            <button id="send" title="发送（回车）">&#8593;</button>
          </div>
        </section>
        <aside class="preview-shell">
          <div class="preview-toggle" id="previewToggle"><div class="preview-toggle-inner" id="previewToggleInner">&lt;</div></div>
          <div class="preview-panel" id="previewPanel">
            <div class="preview-title"><span class="preview-title-text">PPT 预览</span><button class="preview-fullscreen-btn" id="previewFullscreenBtn" title="全屏预览">&#90914;</button></div>
            <div class="preview-main">
              <div class="preview-body" id="previewBody" contenteditable="true">
                <div class="preview-placeholder" id="previewPlaceholder">这里将展示当前项目的 PPT 大纲预览。可直接编辑，下方可 AI 一键润色。</div>
              </div>
              <div class="preview-side-tools">
                <button class="preview-tool-btn" id="toolFont" title="字体">字</button>
                <button class="preview-tool-btn" id="toolColor" title="颜色">&#127912;</button>
                <button class="preview-tool-btn" id="toolImage" title="插入图片">&#128444;</button>
                <button class="preview-tool-btn" id="toolAnim" title="动画">&#10024;</button>
                <input type="file" id="imageInput" accept="image/*" style="display:none" />
              </div>
              <div class="preview-tool-options" id="previewToolOptions"></div>
            </div>
            <div class="preview-footer"><button id="polishBtn">AI 一键润色</button></div>
          </div>
        </aside>
      </div>
    </main>
    <div class="settings-panel" id="settingsPanel">
      <div class="settings-header">设置</div>
      <div class="settings-row" data-settings-key="model"><div class="settings-label">大模型</div><div class="settings-options"><div class="settings-option">DeepSeek Chat</div><div class="settings-option">DeepSeek Reasoner</div></div></div>
      <div class="settings-row" data-settings-key="lang"><div class="settings-label">语言</div><div class="settings-options"><div class="settings-option">中文</div><div class="settings-option">English</div></div></div>
      <div class="settings-row" data-settings-key="font"><div class="settings-label">字体大小</div><div class="settings-options"><div class="settings-option">小</div><div class="settings-option">中</div><div class="settings-option">大</div></div></div>
      <div class="settings-row" data-settings-key="privacy"><div class="settings-label">隐私</div><div class="settings-options"><div class="settings-option">输入内容仅用于调试模型，不会对外泄露。</div></div></div>
    </div>
  </div>
  <script>
    var messagesEl = document.getElementById("messages");
    var inputEl = document.getElementById("input");
    var sendBtn = document.getElementById("send");
    var uploadBtn = document.getElementById("uploadBtn");
    var uploadInput = document.getElementById("uploadInput");
    var previewPanel = document.getElementById("previewPanel");
    var previewToggle = document.getElementById("previewToggle");
    var previewToggleInner = document.getElementById("previewToggleInner");
    var previewBody = document.getElementById("previewBody");
    var previewPlaceholder = document.getElementById("previewPlaceholder");
    var historyToggle = document.getElementById("historyToggle");
    var historyDrawer = document.getElementById("historyDrawer");
    var newProjectBtn = document.getElementById("newProjectBtn");
    var settingsBtn = document.getElementById("settingsBtn");
    var settingsPanel = document.getElementById("settingsPanel");
    var polishBtn = document.getElementById("polishBtn");
    var toolFont = document.getElementById("toolFont");
    var toolColor = document.getElementById("toolColor");
    var toolImage = document.getElementById("toolImage");
    var toolAnim = document.getElementById("toolAnim");
    var imageInput = document.getElementById("imageInput");
    var previewToolOptions = document.getElementById("previewToolOptions");
    var previewFullscreenBtn = document.getElementById("previewFullscreenBtn");
    var contentRow = document.getElementById("contentRow");
    var sessionId = localStorage.getItem("slidein_session_id") || "";
    var lastUploads = [];
    var initFormStage = "not_started";
    var initSelections = { purpose: null, pages: null, lang: null, template: null };

    function escapeHtml(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
    function addMsg(role, text, exportFiles) {
      var div = document.createElement("div");
      div.className = "msg " + role;
      var html = "";
      if (role === "agent") html += '<div class="agent-avatar" role="img" aria-label="AI"></div>';
      html += '<div class="bubble">' + escapeHtml(text);
      if (exportFiles && exportFiles.length) {
        html += '<div class="export-links">';
        for (var i = 0; i < exportFiles.length; i++) {
          var f = exportFiles[i];
          html += '<a href="/api/download?session_id=' + encodeURIComponent(sessionId) + '&index=' + encodeURIComponent(f.download_id) + '" download>' + escapeHtml(f.label) + ' 下载</a>';
        }
        html += '</div>';
      }
      html += '</div>';
      div.innerHTML = html;
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function renderInitFormIfNeeded() {
      if (initFormStage !== "not_started" || messagesEl.children.length > 0) return;
      initFormStage = "showing";
      var div = document.createElement("div");
      div.className = "msg agent";
      div.innerHTML =
        '<div class="agent-avatar" role="img" aria-label="AI"></div>' +
        '<div class="bubble">' +
          '<div class="quick-form">' +
            '<div class="quick-form-section">' +
              '<div>我们先确定 PPT 的基础信息：</div>' +
              '<div>1）用途</div>' +
              '<div class="chip-group" data-group="purpose">' +
                '<button class="chip-option" data-value="课程汇报">课程汇报</button>' +
                '<button class="chip-option" data-value="项目路演">项目路演</button>' +
                '<button class="chip-option" data-value="答辩">答辩</button>' +
                '<button class="chip-option" data-value="工作汇报">工作汇报</button>' +
              '</div>' +
            '</div>' +
            '<div class="quick-form-section">' +
              '<div>2）页数</div>' +
              '<div class="chip-group" data-group="pages">' +
                '<button class="chip-option" data-value="8页以内">8 页以内</button>' +
                '<button class="chip-option" data-value="10-15页">10-15 页</button>' +
                '<button class="chip-option" data-value="15页以上">15 页以上</button>' +
              '</div>' +
            '</div>' +
            '<div class="quick-form-section">' +
              '<div>3）语言</div>' +
              '<div class="chip-group" data-group="lang">' +
                '<button class="chip-option" data-value="中文">中文</button>' +
                '<button class="chip-option" data-value="英文">英文</button>' +
                '<button class="chip-option" data-value="中英双语">中英双语</button>' +
              '</div>' +
            '</div>' +
            '<div class="quick-form-section chip-group hidden" data-group="template">' +
              '<div style="width:100%;margin-bottom:4px;">是否使用系统模版？</div>' +
              '<button class="chip-option" data-value="打开模版">打开模版</button>' +
              '<button class="chip-option" data-value="跳过">跳过</button>' +
            '</div>' +
          '</div>' +
        '</div>';
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
    function sendInitStructuredRequest() {
      if (!initSelections.purpose || !initSelections.pages || !initSelections.lang || !initSelections.template) return;
      initFormStage = "done";
      var msg = "我想制作一份 PPT，用途是：" + initSelections.purpose + "，大致页数：" + initSelections.pages + "，语言：" + initSelections.lang + "。对于系统模版的选择是：" + initSelections.template + "。请根据这些信息帮我规划合适的大纲和后续内容。";
      inputEl.value = msg;
      send();
    }
    renderInitFormIfNeeded();

    function send() {
      var message = inputEl.value.trim();
      if (!message) return;
      addMsg("user", message, null);
      inputEl.value = "";
      sendBtn.disabled = true;
      fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: message, session_id: sessionId || undefined }) })
        .then(function(r) { return r.json().then(function(data) { if (!r.ok) throw new Error(data.detail || "HTTP " + r.status); return data; }); })
        .then(function(data) {
          if (data.session_id) { sessionId = data.session_id; localStorage.setItem("slidein_session_id", sessionId); }
          var replyText = data.reply != null ? data.reply : "\uFF08\u65E0\u56DE\u590D\uFF09";
          addMsg("agent", replyText, data.export_files || []);
          if (previewPlaceholder) previewPlaceholder.style.display = "none";
          previewBody.innerText = replyText;
        })
        .catch(function(e) { addMsg("agent", "\u8BF7\u6C42\u5931\u8D25\uFF1A" + (e.message || String(e)), []); })
        .finally(function() { sendBtn.disabled = false; });
    }
    sendBtn.onclick = send;
    inputEl.onkeydown = function(e) {
      if (e.key === "Enter") {
        if (e.shiftKey) {
          var start = inputEl.selectionStart, end = inputEl.selectionEnd, val = inputEl.value;
          inputEl.value = val.slice(0, start) + "\n" + val.slice(end);
          inputEl.selectionStart = inputEl.selectionEnd = start + 1;
        } else { e.preventDefault(); send(); }
      }
    };

    if (uploadBtn && uploadInput) {
      uploadBtn.onclick = function() { uploadInput.click(); };
      uploadInput.onchange = function() {
        var files = Array.prototype.slice.call(uploadInput.files || []);
        if (!files.length) return;
        lastUploads = files.map(function(f) { return f.name; });
        addMsg("agent", "\u5DF2\u4E0A\u4F20\u672C\u5730\u6587\u4EF6\uFF1A\n" + lastUploads.map(function(n) { return "- " + n; }).join("\n") + "\n\n\u8BF7\u5728\u8F93\u5165\u6846\u8BF4\u660E\u60A8\u60F3\u5982\u4F55\u4F7F\u7528\u8FD9\u4E9B\u6587\u4EF6\u3002", []);
        uploadInput.value = "";
      };
    }

    messagesEl.addEventListener("click", function(e) {
      var btn = e.target.closest(".chip-option");
      if (!btn) return;
      var groupEl = btn.closest(".chip-group");
      if (!groupEl) return;
      var group = groupEl.getAttribute("data-group");
      if (!group) return;
      var opts = groupEl.querySelectorAll(".chip-option");
      for (var i = 0; i < opts.length; i++) opts[i].classList.remove("selected");
      btn.classList.add("selected");
      var value = btn.getAttribute("data-value");
      if (group === "purpose") initSelections.purpose = value;
      if (group === "pages") initSelections.pages = value;
      if (group === "lang") initSelections.lang = value;
      if (group === "template") initSelections.template = value;
      if (group !== "template" && initSelections.purpose && initSelections.pages && initSelections.lang) {
        var tpl = document.querySelector('.chip-group[data-group="template"]');
        if (tpl) tpl.classList.remove("hidden");
      }
      if (group === "template" && initSelections.template) sendInitStructuredRequest();
    });

    var previewWide = false;
    previewToggle.addEventListener("click", function() {
      previewWide = !previewWide;
      if (contentRow) contentRow.classList.toggle("preview-wide", previewWide);
      previewToggleInner.textContent = previewWide ? ">" : "<";
    });
    historyToggle.addEventListener("click", function() { historyDrawer.classList.toggle("open"); });
    historyDrawer.addEventListener("click", function(e) {
      var item = e.target.closest(".history-item");
      if (!item) return;
      if (previewPlaceholder) previewPlaceholder.style.display = "none";
      previewBody.innerHTML = "<div class=\"preview-slide\"><strong>" + escapeHtml(item.textContent) + "</strong></div>";
      if (previewPanel.classList.contains("collapsed")) { previewPanel.classList.remove("collapsed"); previewToggleInner.textContent = previewWide ? ">" : "<"; }
    });

    newProjectBtn.addEventListener("click", function() {
      sessionId = "";
      localStorage.removeItem("slidein_session_id");
      messagesEl.innerHTML = "";
      inputEl.value = "";
      previewBody.innerHTML = "";
      if (previewPlaceholder) { previewPlaceholder.style.display = "block"; previewBody.appendChild(previewPlaceholder); }
      if (contentRow && contentRow.classList.contains("preview-full")) contentRow.classList.remove("preview-full");
      initFormStage = "not_started";
      initSelections.purpose = initSelections.pages = initSelections.lang = initSelections.template = null;
      renderInitFormIfNeeded();
    });

    settingsBtn.addEventListener("click", function() { settingsPanel.classList.toggle("open"); });
    settingsPanel.addEventListener("click", function(e) {
      var row = e.target.closest(".settings-row");
      if (!row) return;
      var options = row.querySelector(".settings-options");
      if (!options) return;
      var isOpen = options.style.display === "flex";
      Array.prototype.forEach.call(settingsPanel.querySelectorAll(".settings-options"), function(el) { el.style.display = "none"; });
      if (!isOpen) options.style.display = "flex";
    });
    settingsPanel.addEventListener("click", function(e) {
      var opt = e.target.closest(".settings-option");
      if (!opt) return;
      opt.parentElement.querySelectorAll(".settings-option").forEach(function(el) { el.style.backgroundColor = ""; });
      opt.style.backgroundColor = "#e5e7eb";
      e.stopPropagation();
    });

    if (previewFullscreenBtn && contentRow) previewFullscreenBtn.addEventListener("click", function() { contentRow.classList.toggle("preview-full"); previewFullscreenBtn.textContent = contentRow.classList.contains("preview-full") ? "\u2912" : "\u2914"; });

    var previewThemes = [{ bg: "#ffffff", border: "#e5e7eb" }, { bg: "linear-gradient(135deg, #f9fafb, #e5e7eb)", border: "#d1d5db" }, { bg: "linear-gradient(135deg, #fefce8, #fffbeb)", border: "#eab308" }];
    var previewThemeIndex = 0, animOn = false;
    function toggleToolOptions(kind, anchorEl) {
      if (!previewToolOptions) return;
      if (previewToolOptions.dataset.kind === kind && previewToolOptions.style.display === "flex") { previewToolOptions.style.display = "none"; return; }
      previewToolOptions.dataset.kind = kind;
      previewToolOptions.innerHTML = "";
      if (kind === "font") { ["\u5C0F\u53F7\u5B57\u53F7", "\u9ED8\u8BA4\u5B57\u53F7", "\u5927\u53F7\u5B57\u53F7"].forEach(function(l, i) { var d = document.createElement("div"); d.className = "preview-tool-option"; d.textContent = l; d.dataset.value = String(i); previewToolOptions.appendChild(d); }); }
      else if (kind === "color") { ["\u7EAF\u767D\u80CC\u666F", "\u7070\u8272\u6E10\u53D8", "\u6696\u8272\u6E10\u53D8"].forEach(function(l, i) { var d = document.createElement("div"); d.className = "preview-tool-option"; d.textContent = l; d.dataset.value = String(i); previewToolOptions.appendChild(d); }); }
      else if (kind === "image") { var d = document.createElement("div"); d.className = "preview-tool-option"; d.textContent = "\u4ECE\u672C\u5730\u63D2\u5165\u56FE\u7247\u2026"; d.dataset.value = "pick"; previewToolOptions.appendChild(d); }
      else if (kind === "anim") { ["\u5173\u95ED\u52A8\u753B", "\u8F7B\u5FAE\u547C\u5438\u52A8\u753B"].forEach(function(l, i) { var d = document.createElement("div"); d.className = "preview-tool-option"; d.textContent = l; d.dataset.value = String(i); previewToolOptions.appendChild(d); }); }
      if (anchorEl && previewPanel) {
        var br = anchorEl.getBoundingClientRect(), pr = previewPanel.getBoundingClientRect();
        previewToolOptions.style.top = (br.top - pr.top) + "px";
        previewToolOptions.style.left = (br.right - pr.left + 8) + "px";
      }
      previewToolOptions.style.display = "flex";
    }
    toolFont.onclick = function() { toggleToolOptions("font", this); };
    toolColor.onclick = function() { toggleToolOptions("color", this); };
    toolImage.onclick = function() { toggleToolOptions("image", this); };
    toolAnim.onclick = function() { toggleToolOptions("anim", this); };
    if (imageInput) imageInput.onchange = function() {
      var files = Array.prototype.slice.call(imageInput.files || []);
      imageInput.value = "";
      files.forEach(function(file) {
        if (!file.type.startsWith("image/")) return;
        var r = new FileReader();
        r.onload = function(ev) { var img = document.createElement("img"); img.src = ev.target.result; img.style.maxWidth = "100%"; img.style.margin = "6px 0"; previewBody.appendChild(img); };
        r.readAsDataURL(file);
      });
    };
    if (previewToolOptions) previewToolOptions.addEventListener("click", function(e) {
      var opt = e.target.closest(".preview-tool-option");
      if (!opt) return;
      var kind = previewToolOptions.dataset.kind, value = opt.dataset.value || "";
      if (kind === "font") previewBody.style.fontSize = value === "0" ? "0.8rem" : (value === "2" ? "0.95rem" : "0.85rem");
      else if (kind === "color") { var idx = parseInt(value, 10) || 0; var t = previewThemes[idx % previewThemes.length]; previewBody.style.backgroundImage = t.bg.indexOf("linear") === 0 ? t.bg : ""; previewBody.style.backgroundColor = t.bg.indexOf("#") === 0 ? t.bg : "transparent"; previewBody.style.borderColor = t.border; }
      else if (kind === "image" && value === "pick" && imageInput) imageInput.click();
      else if (kind === "anim") { animOn = value === "1"; previewPanel.classList.toggle("preview-animate", animOn); }
      previewToolOptions.style.display = "none";
    });
    if (previewPanel) previewPanel.style.animation = "none";

    // 简化版工具栏交互：按钮本身也直接生效，确保“点一下就有反馈”
    var fontMode = 1; // 0 小，1 中，2 大
    toolFont.onclick = function() {
      fontMode = (fontMode + 1) % 3;
      if (fontMode === 0) previewBody.style.fontSize = "0.8rem";
      if (fontMode === 1) previewBody.style.fontSize = "0.85rem";
      if (fontMode === 2) previewBody.style.fontSize = "0.95rem";
    };
    toolColor.onclick = function() {
      previewThemeIndex = (previewThemeIndex + 1) % previewThemes.length;
      var t = previewThemes[previewThemeIndex];
      previewBody.style.backgroundImage = t.bg.indexOf("linear") === 0 ? t.bg : "";
      previewBody.style.backgroundColor = t.bg.indexOf("#") === 0 ? t.bg : "transparent";
      previewBody.style.borderColor = t.border;
    };
    toolImage.onclick = function() {
      if (imageInput) imageInput.click();
    };
    toolAnim.onclick = function() {
      animOn = !animOn;
      previewPanel.classList.toggle("preview-animate", animOn);
    };
    polishBtn.addEventListener("click", function() {
      var text = (previewBody.innerText || "").trim();
      if (!text) { addMsg("agent", "\u8BF7\u5148\u5728\u53F3\u4FA7\u9884\u89C8\u533A\u7F16\u8F91\u5185\u5BB9\uFF0C\u518D\u4F7F\u7528\u4E00\u952E\u6DA6\u8272\u3002", []); return; }
      polishBtn.disabled = true;
      fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: "\u8BF7\u5E2E\u6211\u6DA6\u8272\u4E0B\u9762\u8FD9\u6BB5 PPT \u5185\u5BB9\uFF0C\u53EA\u8FD4\u56DE\u6DA6\u8272\u540E\u7684\u6587\u672C\uFF1A\n\n" + text, session_id: sessionId || undefined }) })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data && data.reply && data.reply.trim()) { previewBody.innerText = data.reply.trim(); if (previewPlaceholder) previewPlaceholder.style.display = "none"; }
          if (data && data.session_id) { sessionId = data.session_id; localStorage.setItem("slidein_session_id", sessionId); }
        })
        .catch(function(e) { addMsg("agent", "\u4E00\u952E\u6DA6\u8272\u5931\u8D25\uFF1A" + (e.message || String(e)), []); })
        .finally(function() { polishBtn.disabled = false; });
    });
  </script>
</body>
</html>
"""


@app.get("/avatar.png", response_class=FileResponse)
def avatar():
    p = Path(__file__).resolve().parent / "static" / "avatar.png"
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(p)

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE


def main():
    import uvicorn
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("WEB_PORT", "8000")))
    print("SlideIn Agent Web \u5DF2\u542F\u52A8\uFF0C\u672C\u673A\u8BBF\u95EE: http://127.0.0.1:%s" % port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
