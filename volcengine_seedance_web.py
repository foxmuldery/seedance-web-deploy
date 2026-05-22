#!/usr/bin/env python3
"""
Local web tester for Volcengine Ark Seedance video generation.

Start:
  export ARK_API_KEY="your_api_key"
  python3 volcengine_seedance_web.py

Open:
  http://127.0.0.1:8765
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import io
from datetime import datetime, UTC
import errno
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import socket
import ssl
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen
import uuid


HOST = os.getenv("SEEDANCE_WEB_HOST", "127.0.0.1")
PORT = int(os.getenv("SEEDANCE_WEB_PORT", "8765"))
PORT_SEARCH_LIMIT = 20
DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_OUTPUT_ROOT = Path.home() / "Desktop" / "seedance_web_outputs"
OUTPUT_ROOT = Path(os.getenv("SEEDANCE_OUTPUT_ROOT", str(DEFAULT_OUTPUT_ROOT))).expanduser().resolve()
LOG_DIR = Path(os.getenv("SEEDANCE_LOG_DIR", str(OUTPUT_ROOT / "_logs"))).expanduser().resolve()
CONFIG_PATH = Path(os.getenv("SEEDANCE_WEB_CONFIG", ".seedance_web_config.json")).expanduser()
if not CONFIG_PATH.is_absolute():
    CONFIG_PATH = (Path.cwd() / CONFIG_PATH).resolve()
DEFAULT_REQUEST_TIMEOUT = int(os.getenv("SEEDANCE_REQUEST_TIMEOUT", "300"))
DEFAULT_TOS_ENDPOINT = os.getenv("TOS_ENDPOINT", "https://tos-cn-beijing.volces.com")
DEFAULT_TOS_REGION = os.getenv("TOS_REGION", "cn-beijing")
DEFAULT_TOS_PREFIX = os.getenv("TOS_PREFIX", "seedance-inputs")
DEFAULT_TOS_TIMEOUT = int(os.getenv("TOS_REQUEST_TIMEOUT", "300"))
MAX_TOS_UPLOAD_BYTES = int(os.getenv("SEEDANCE_MAX_TOS_UPLOAD_BYTES", str(30 * 1024 * 1024)))
TERMINAL_SUCCESS = {"succeeded", "completed", "success"}
TERMINAL_FAILURE = {"failed", "cancelled", "canceled", "expired"}

TASKS: dict[str, dict[str, Any]] = {}
OUTPUT_DIRS: dict[str, str] = {}
TASK_LOCK = threading.Lock()
LOG_LOCK = threading.Lock()


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>兔狲视频生成器</title>
  <style>
    :root {
      --bg: #f6f7f8;
      --surface: #ffffff;
      --surface-2: #f0f3f5;
      --line: #d6dde2;
      --line-strong: #aeb8c2;
      --text: #14181d;
      --muted: #5e6874;
      --soft: #7a8490;
      --accent: #0f766e;
      --accent-2: #b45309;
      --danger: #b42318;
      --ok: #16803c;
      --shadow: 0 16px 38px rgba(28, 35, 43, 0.08);
      color-scheme: light;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    button, input, textarea, select {
      font: inherit;
    }

    .app {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }

    .topbar {
      position: sticky;
      top: 0;
      z-index: 5;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: center;
      padding: 14px 22px;
      background: rgba(255, 255, 255, 0.94);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(14px);
    }

    .brand {
      min-width: 0;
    }

    .brand h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
      font-weight: 720;
    }

    .brand p {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.3;
    }

    .top-actions {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(360px, 520px) minmax(0, 1fr);
      gap: 18px;
      padding: 18px 22px 24px;
      max-width: 1520px;
      width: 100%;
      margin: 0 auto;
    }

    .pane {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      min-width: 0;
    }

    .pane-header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfc;
      border-radius: 8px 8px 0 0;
    }

    .pane-header h2 {
      margin: 0;
      font-size: 15px;
      line-height: 1.25;
    }

    .pane-body {
      padding: 16px;
    }

    .stack {
      display: grid;
      gap: 14px;
    }

    .grid-2 {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .grid-3 {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }

    label {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.25;
      font-weight: 650;
    }

    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line-strong);
      border-radius: 7px;
      background: #fff;
      color: var(--text);
      padding: 9px 10px;
      outline: none;
      min-height: 40px;
    }

    textarea {
      min-height: 116px;
      resize: vertical;
      line-height: 1.45;
    }

    input:focus, textarea:focus, select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.14);
    }

    .segmented {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 4px;
      padding: 4px;
      background: var(--surface-2);
      border: 1px solid var(--line);
      border-radius: 8px;
    }

    .segmented button {
      border: 0;
      border-radius: 6px;
      min-height: 38px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      padding: 7px 8px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .segmented button.active {
      background: #fff;
      color: var(--text);
      box-shadow: 0 1px 3px rgba(16, 24, 40, 0.12);
      font-weight: 700;
    }

    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 40px;
      border: 1px solid var(--line-strong);
      border-radius: 7px;
      padding: 8px 12px;
      background: #fff;
      color: var(--text);
      cursor: pointer;
      text-decoration: none;
      white-space: nowrap;
    }

    .button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 720;
    }

    .button.warn {
      border-color: rgba(180, 83, 9, 0.45);
      color: var(--accent-2);
    }

    .button.danger {
      border-color: rgba(180, 35, 24, 0.5);
      color: var(--danger);
    }

    .button:disabled {
      opacity: 0.54;
      cursor: not-allowed;
    }

    .toggle-row {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }

    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fbfcfc;
      color: var(--text);
      min-height: 40px;
      font-size: 13px;
      font-weight: 600;
    }

    .check input {
      width: 16px;
      height: 16px;
      min-height: 16px;
      padding: 0;
    }

    .drop {
      display: grid;
      gap: 7px;
      padding: 12px;
      border: 1px dashed var(--line-strong);
      border-radius: 8px;
      background: #fbfcfc;
    }

    .drop input[type="file"] {
      padding: 7px;
      min-height: 38px;
      background: #fff;
    }

    .hint {
      color: var(--soft);
      font-size: 12px;
      line-height: 1.45;
      font-weight: 500;
    }

    .helper-box {
      display: grid;
      gap: 8px;
      color: var(--soft);
      font-size: 12px;
      line-height: 1.5;
      font-weight: 500;
    }

    .helper-box strong {
      color: var(--text);
    }

    .helper-box ul {
      margin: 0;
      padding-left: 18px;
    }

    .asset-list {
      display: grid;
      gap: 8px;
    }

    .asset-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: end;
    }

    .status-line {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 26px;
      border-radius: 999px;
      padding: 4px 9px;
      background: var(--surface-2);
      color: var(--muted);
      font-size: 12px;
      font-weight: 680;
      white-space: nowrap;
    }

    .badge.ok {
      color: var(--ok);
      background: rgba(22, 128, 60, 0.1);
    }

    .badge.warn {
      color: var(--accent-2);
      background: rgba(180, 83, 9, 0.11);
    }

    .badge.err {
      color: var(--danger);
      background: rgba(180, 35, 24, 0.1);
    }

    .notice {
      display: grid;
      gap: 5px;
      border: 1px solid rgba(22, 128, 60, 0.28);
      border-radius: 8px;
      background: rgba(22, 128, 60, 0.08);
      color: var(--ok);
      padding: 10px 12px;
      font-size: 13px;
      line-height: 1.4;
    }

    .notice strong {
      color: var(--ok);
    }

    .notice span {
      color: var(--muted);
      word-break: break-word;
    }

    .result-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
      gap: 18px;
    }

    .video-stage {
      display: grid;
      place-items: center;
      min-height: 360px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(45deg, #eef2f5 25%, transparent 25%),
        linear-gradient(-45deg, #eef2f5 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #eef2f5 75%),
        linear-gradient(-45deg, transparent 75%, #eef2f5 75%);
      background-size: 22px 22px;
      background-position: 0 0, 0 11px, 11px -11px, -11px 0;
      overflow: hidden;
    }

    video {
      width: 100%;
      max-height: 560px;
      display: none;
      background: #000;
    }

    .empty-state {
      display: grid;
      gap: 8px;
      place-items: center;
      text-align: center;
      color: var(--muted);
      padding: 22px;
    }

    .empty-state strong {
      color: var(--text);
      font-size: 15px;
    }

    .progress {
      width: 100%;
      height: 8px;
      background: var(--surface-2);
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid var(--line);
    }

    .progress span {
      display: block;
      height: 100%;
      width: 0%;
      background: var(--accent);
      transition: width 180ms ease;
    }

    pre {
      margin: 0;
      background: #111820;
      color: #dce8f0;
      border-radius: 8px;
      padding: 12px;
      min-height: 180px;
      max-height: 420px;
      overflow: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .tabs {
      display: inline-grid;
      grid-template-columns: repeat(3, max-content);
      gap: 4px;
      align-items: center;
      justify-content: start;
      width: max-content;
      max-width: 100%;
      padding: 4px;
      background: var(--surface-2);
      border: 1px solid var(--line);
      border-radius: 8px;
    }

    .tab {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      height: 30px;
      min-height: 30px;
      border: 0;
      background: transparent;
      color: var(--muted);
      border-radius: 6px;
      padding: 0 10px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 650;
      line-height: 1;
      white-space: nowrap;
    }

    .tab.active {
      color: #fff;
      background: #26323f;
      box-shadow: 0 1px 3px rgba(16, 24, 40, 0.14);
    }

    .log {
      display: grid;
      gap: 8px;
      max-height: 210px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfc;
    }

    .log-entry {
      display: grid;
      gap: 2px;
      font-size: 12px;
      line-height: 1.35;
      color: var(--muted);
      padding-bottom: 8px;
      border-bottom: 1px solid var(--line);
    }

    .log-entry:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }

    .log-entry strong {
      color: var(--text);
    }

    .url-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: end;
    }

    .hidden {
      display: none !important;
    }

    @media (max-width: 1080px) {
      .layout,
      .result-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 720px) {
      .topbar {
        grid-template-columns: 1fr;
        padding: 12px;
      }

      .top-actions {
        justify-content: stretch;
      }

      .top-actions .button {
        flex: 1;
      }

      .layout {
        padding: 12px;
      }

      .grid-2,
      .grid-3,
      .toggle-row,
      .segmented,
      .url-row,
      .asset-row {
        grid-template-columns: 1fr;
      }

      .video-stage {
        min-height: 260px;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <h1>兔狲视频生成器</h1>
        <p>本地网页调用本地代理，任务日志和视频会保存到当前目录。</p>
      </div>
      <div class="top-actions">
        <span id="keyBadge" class="badge">检查密钥</span>
        <a class="button" href="https://console.volcengine.com/ark/region%3Aark%2Bcn-beijing/openManagement" target="_blank" rel="noopener">开通管理</a>
        <a class="button" href="https://console.volcengine.com/finance" target="_blank" rel="noopener">费用中心</a>
        <button id="checkConnectionBtn" class="button" type="button">连线检测</button>
        <button id="previewBtn" class="button" type="button">预览请求</button>
        <button id="runBtn" class="button primary" type="button">创建任务</button>
        <button id="cancelBtn" class="button danger" type="button" disabled>终止任务</button>
      </div>
    </header>

    <main class="layout">
      <section class="pane">
        <div class="pane-header">
          <h2>参数</h2>
          <span id="modeBadge" class="badge">文生视频</span>
        </div>
        <div class="pane-body stack">
          <div class="segmented" role="tablist" aria-label="生成模式">
            <button class="active" type="button" data-mode="text">文生视频</button>
            <button type="button" data-mode="image">图生视频</button>
            <button type="button" data-mode="video">视频生视频</button>
            <button type="button" data-mode="mixed">混合参考</button>
          </div>

          <label>
            API Key
            <input id="apiKey" type="password" autocomplete="off" placeholder="留空则使用 ARK_API_KEY 环境变量" />
          </label>

          <div class="grid-2">
            <label>
              模型
              <select id="modelPreset">
                <option value="doubao-seedance-2-0-fast-260128">Seedance 2.0 Fast</option>
                <option value="doubao-seedance-2-0-260128">Seedance 2.0 标准</option>
                <option value="custom">自定义模型 ID</option>
              </select>
            </label>
            <label>
              自定义模型 ID
              <input id="modelCustom" placeholder="选择自定义后填写" disabled />
            </label>
          </div>

          <label>
            Base URL
            <input id="baseUrl" value="https://ark.cn-beijing.volces.com/api/v3" />
          </label>

          <label>
            提示词
            <textarea id="prompt">写实电影风格，雨夜的老街巷口，一盏路灯闪烁，镜头缓慢推进，空气中有薄雾</textarea>
          </label>

          <div class="drop">
            <div class="status-line">
              <strong>Seedance 真人肖像授权</strong>
              <span id="portraitBadge" class="badge">Asset ID</span>
            </div>
            <div id="portraitAssets" class="asset-list">
              <div class="asset-row">
                <label>
                  授权真人 Asset ID
                  <input class="portrait-asset" placeholder="asset-... 或 asset://asset-..." />
                </label>
                <button class="button portrait-remove" type="button">删除</button>
              </div>
            </div>
            <button id="addPortraitAssetBtn" class="button" type="button">+ 添加真人</button>
            <div class="hint">
              在火山方舟真人人像库接收授权素材后，复制 Asset ID 填这里；每个人会按 reference_image 传给 Seedance，不走 TOS 外链。
            </div>
          </div>

          <div id="imageBlock" class="drop hidden">
            <label>
              首帧/参考图 URL
              <input id="imageUrl" placeholder="https://...、asset://asset-... 或使用下方本地文件" />
            </label>
            <label>
              首帧/参考图文件
              <input id="imageFile" type="file" accept="image/*" />
            </label>
          </div>

          <div id="lastImageBlock" class="drop hidden">
            <label>
              尾帧图 URL
              <input id="lastImageUrl" placeholder="可选，https://... 或使用下方本地文件" />
            </label>
            <label>
              尾帧图文件
              <input id="lastImageFile" type="file" accept="image/*" />
            </label>
          </div>

          <div id="videoBlock" class="drop hidden">
            <label>
              参考/输入视频 URL
              <input id="videoUrl" placeholder="https://... 或使用下方本地文件" />
            </label>
            <label>
              参考/输入视频文件
              <input id="videoFile" type="file" accept="video/*" />
            </label>
          </div>

          <div id="audioBlock" class="drop hidden">
            <label>
              参考/输入音频 URL
              <input id="audioUrl" placeholder="可选，https://... 或使用下方本地文件" />
            </label>
            <label>
              参考/输入音频文件
              <input id="audioFile" type="file" accept="audio/*" />
            </label>
          </div>

          <div class="grid-3">
            <label>
              时长
              <select id="duration">
                <option value="5">5 秒</option>
                <option value="10">10 秒</option>
                <option value="15">15 秒</option>
              </select>
            </label>
            <label>
              比例
              <select id="ratio">
                <option value="16:9">16:9 横屏</option>
                <option value="9:16">9:16 竖屏</option>
                <option value="1:1">1:1 方图</option>
                <option value="4:3">4:3</option>
                <option value="3:4">3:4</option>
                <option value="adaptive">adaptive</option>
              </select>
            </label>
            <label>
              分辨率
              <select id="resolution">
                <option value="720p">720p</option>
                <option value="1080p">1080p</option>
                <option value="">不传</option>
              </select>
            </label>
          </div>

          <div class="grid-3">
            <label>
              随机种子
              <input id="seed" type="number" placeholder="可选" />
            </label>
            <label>
              轮询间隔
              <input id="interval" type="number" min="2" value="8" />
            </label>
            <label>
              超时秒数
              <input id="timeout" type="number" min="30" value="1800" />
            </label>
            <label>
              接口请求超时
              <input id="requestTimeout" type="number" min="30" value="300" />
            </label>
          </div>

          <div class="toggle-row">
            <label class="check">
              <input id="watermark" type="checkbox" />
              水印
            </label>
            <label class="check">
              <input id="generateAudio" type="checkbox" />
              生成音频
            </label>
            <label class="check">
              <input id="returnLastFrame" type="checkbox" />
              返回尾帧
            </label>
          </div>

          <label class="check">
            <input id="autoDownload" type="checkbox" checked />
            成功后自动下载到本地输出目录
          </label>

          <label>
            本地输出根目录
            <input id="outputRoot" placeholder="/Users/tusun/Desktop/seedance_web_outputs" />
          </label>

          <div class="drop">
            <div class="status-line">
              <label class="check">
                <input id="tosAutoUpload" type="checkbox" checked />
                本地图片自动上传 TOS 外链
              </label>
              <span id="tosBadge" class="badge">TOS 未检测</span>
            </div>
            <div class="grid-2">
              <label>
                TOS Bucket
                <input id="tosBucket" placeholder="例如 your-bucket-name" />
              </label>
              <label>
                TOS Region
                <input id="tosRegion" value="cn-beijing" />
              </label>
            </div>
            <label>
              TOS Endpoint
              <input id="tosEndpoint" value="https://tos-cn-beijing.volces.com" />
            </label>
            <div class="grid-2">
              <label>
                TOS AccessKey
                <input id="tosAccessKey" type="password" autocomplete="off" placeholder="留空使用 TOS_ACCESS_KEY_ID 环境变量" />
              </label>
              <label>
                TOS SecretKey
                <input id="tosSecretKey" type="password" autocomplete="off" placeholder="留空使用 TOS_SECRET_ACCESS_KEY 环境变量" />
              </label>
            </div>
            <div class="grid-3">
              <label>
                对象前缀
                <input id="tosPrefix" value="seedance-inputs" />
              </label>
              <label>
                外链有效期
                <input id="tosExpires" type="number" min="600" value="86400" />
              </label>
              <label>
                TOS 上传超时
                <input id="tosTimeout" type="number" min="60" value="300" />
              </label>
            </div>
            <div class="grid-3">
              <label class="check">
                <input id="compressImages" type="checkbox" checked />
                上传前压缩图片
              </label>
              <label>
                图片最大边
                <input id="imageMaxSide" type="number" min="512" value="1920" />
              </label>
              <label>
                JPEG 质量
                <input id="imageJpegQuality" type="number" min="0.5" max="1" step="0.05" value="0.88" />
              </label>
            </div>
            <label>
              Security Token
              <input id="tosSecurityToken" type="password" autocomplete="off" placeholder="临时凭证才需要，长期 AK/SK 留空" />
            </label>
            <div class="status-line">
              <button id="checkTosBtn" class="button" type="button">检测 TOS 配置</button>
              <button id="saveTosBtn" class="button primary" type="button">保存并锁定配置</button>
              <button id="unlockTosBtn" class="button" type="button">解锁修改</button>
            </div>
          </div>

          <div class="hint">
            图生视频建议使用公网 HTTPS 图片 URL；本地图片会先压缩、上传到 TOS，再把签名 URL 发给 Seedance。
          </div>
        </div>
      </section>

      <section class="pane">
        <div class="pane-header">
          <h2>任务</h2>
          <div class="status-line">
            <span id="taskBadge" class="badge">未提交</span>
            <span id="elapsedBadge" class="badge">0 秒</span>
          </div>
        </div>
        <div class="pane-body stack">
          <div class="progress" aria-label="任务进度"><span id="progressBar"></span></div>
          <div id="successNotice" class="notice hidden">
            <strong id="successTitle">已完成</strong>
            <span id="successBody">结果已更新。</span>
          </div>
          <div class="result-grid">
            <div class="stack">
              <div class="video-stage">
                <video id="video" controls></video>
                <div id="emptyState" class="empty-state">
                  <strong>结果视频会显示在这里</strong>
                  <span>创建任务后会自动轮询状态。</span>
                </div>
              </div>
              <div class="url-row">
                <label>
                  任务 ID
                  <input id="taskIdOut" placeholder="创建后显示，也可手动粘贴 task_id" />
                </label>
                <button id="queryTaskBtn" class="button" type="button">查询任务</button>
              </div>
              <div class="url-row">
                <button id="listTasksBtn" class="button" type="button">最近任务</button>
                <button id="queryAllLocalBtn" class="button" type="button">查询本地全部任务</button>
                <button id="queryDownloadBtn" class="button primary" type="button">查询并下载</button>
                <button id="cancelInlineBtn" class="button danger" type="button">终止任务</button>
              </div>
              <div class="url-row">
                <label>
                  视频链接
                  <input id="videoUrlOut" readonly placeholder="生成成功后显示" />
                </label>
                <button id="downloadBtn" class="button" type="button" disabled>下载到本地</button>
              </div>
              <div class="log" id="log"></div>
            </div>
            <div class="stack">
              <div class="tabs">
                <button class="tab active" data-tab="request" type="button">请求</button>
                <button class="tab" data-tab="create" type="button">创建返回</button>
                <button class="tab" data-tab="latest" type="button">最新状态</button>
              </div>
              <pre id="jsonBox">{}</pre>
              <label>
                当前任务输出目录
                <input id="outputDir" readonly placeholder="任务创建后显示" />
              </label>
              <label>
                详细日志路径
                <input id="logPath" readonly placeholder="任务创建或配置加载后显示" />
              </label>
              <div class="drop">
                <div class="status-line">
                  <strong>费用估算</strong>
                  <span id="costBadge" class="badge">等待结果</span>
                </div>
                <div class="grid-3">
                  <label>
                    生成单价
                    <input id="priceNoVideoInputPerMTokens" type="number" min="0" step="0.01" value="46" />
                  </label>
                  <label>
                    视频输入单价
                    <input id="priceVideoInputPerMTokens" type="number" min="0" step="0.01" value="28" />
                  </label>
                  <label>
                    兜底元/秒
                    <input id="fallbackPricePerSecond" type="number" min="0" step="0.01" value="1" />
                  </label>
                </div>
                <label>
                  本次费用
                  <input id="costOut" readonly placeholder="成功后自动计算" />
                </label>
                <div id="costDetails" class="helper-box">优先按火山返回的 usage.total_tokens 计算；没有 usage 时按时长估算。</div>
              </div>
              <div class="drop">
                <div class="status-line">
                  <strong>错误说明</strong>
                  <span id="errorBadge" class="badge">等待错误</span>
                </div>
                <div id="errorHelp" class="helper-box">出现失败后，这里会解释常见原因和下一步处理方式。</div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>

  <script>
    const state = {
      mode: "text",
      runId: null,
      taskId: null,
      startedAt: null,
      timer: null,
      activeTab: "request",
      pollErrorCount: 0,
      requestPayload: {},
      createResponse: {},
      latestResponse: {},
      videoUrl: "",
      fileData: {
        image: "",
        lastImage: "",
        video: "",
        audio: "",
      },
      fileMeta: {
        image: null,
        lastImage: null,
        video: null,
        audio: null,
      },
      uploadedMedia: {},
      tosLocked: false,
    };

    const $ = (id) => document.getElementById(id);
    const modeNames = {
      text: "文生视频",
      image: "图生视频",
      video: "视频生视频",
      mixed: "混合参考",
    };

    function setBadge(el, text, cls = "") {
      el.className = "badge" + (cls ? " " + cls : "");
      el.textContent = text;
    }

    function addLog(title, body = "") {
      const row = document.createElement("div");
      row.className = "log-entry";
      const time = new Date().toLocaleTimeString();
      row.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(time + (body ? " · " + body : ""))}</span>`;
      $("log").prepend(row);
    }

    function showSuccess(title, body = "") {
      $("successTitle").textContent = title;
      $("successBody").textContent = body || "结果已更新。";
      $("successNotice").classList.remove("hidden");
    }

    function clearSuccess() {
      $("successNotice").classList.add("hidden");
      $("successTitle").textContent = "已完成";
      $("successBody").textContent = "结果已更新。";
    }

    function setLogPath(data = {}) {
      const path = data.taskLogPath || data.logPath || "";
      if (path) $("logPath").value = path;
    }

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      }[ch]));
    }

    function errorMessage(err) {
      if (typeof err === "string") return err;
      return String(err?.message || err || "");
    }

    function explainError(message) {
      const text = String(message || "");
      const lower = text.toLowerCase();
      const item = (badge, title, reason, actions, level = "err") => ({ badge, title, reason, actions, level });

      if (text.includes("ModelNotOpen")) {
        return item("模型未开通", "当前模型没有开通", "火山方舟拒绝了这个模型 ID，通常是账号还没开通该模型，或选到了 Fast/标准里未开通的那个。", ["去火山方舟开通管理里开通当前模型", "或切换到已开通的模型 ID", "确认不要误选 Fast/标准"]);
      }
      if (text.includes("InputImageSensitiveContentDetected") || text.includes("SensitiveContent")) {
        return item("内容审核", "输入素材被内容审核拦截", "输入图片或提示词可能包含真人、隐私信息、敏感内容，任务没有进入正常生成。", ["如果是真人肖像，先在火山方舟真人人像库完成授权并使用 Asset ID", "不要把真人原图直接当 TOS 外链提交", "换成不含真人和隐私信息的测试图验证流程"]);
      }
      if (text.includes("PrivacyInformation")) {
        return item("隐私拦截", "输入图片疑似包含真实人物或隐私信息", "火山把图片判断为可能包含可识别真人或隐私信息。", ["真人肖像不要走普通图片 URL/TOS 外链", "在方舟真人人像库完成授权后，复制 Asset ID 到“Seedance 真人肖像授权”", "处理掉证件、车牌、手机号、工牌等可识别信息"]);
      }
      if (text.includes("HTTPSConnectionPool") && text.includes("tos-")) {
        return item("TOS 拉取失败", "TOS 图片外链读取不稳定", "本地图片已上传或正在上传，但 TOS 链路过慢，或 Seedance 服务端读取图片外链时 SSL/读取超时。", ["保持“上传前压缩图片”开启", "把图片最大边改成 1280，JPEG 质量改成 0.8 再试", "把 TOS 上传超时调到 600 秒", "避免直接上传手机原图或很大的 PNG"]);
      }
      if (lower.includes("ssl") || lower.includes("eof") || lower.includes("network error")) {
        return item("网络中断", "接口连接在返回前中断", "常见于本机到火山方舟/TOS 的链路、代理/VPN、跨境网络、或创建任务返回包中断。创建阶段中断时可能已经创建了任务。", ["不要马上重复点创建", "先点“最近任务”找回可能已创建的 task_id", "如果只是轮询失败，稍后点“查询任务”继续查", "尽量关闭不稳定代理，或把后端部署到火山国内服务器"]);
      }
      if (lower.includes("timed out") || text.includes("read operation timed out") || text.includes("http request timeout")) {
        return item("请求超时", "接口在限定时间内没有返回", "可能是任务创建响应较慢、TOS 上传/读取较慢，或本地网络抖动。", ["接口请求超时改到 600 秒", "TOS 上传超时改到 600 秒", "图生视频先压缩图片", "创建失败后先查最近任务"]);
      }
      if (text.includes("Missing API Key")) {
        return item("缺少 Key", "没有可用的方舟 API Key", "网页没有填 API Key，服务端环境变量里也没有 ARK_API_KEY。", ["在页面 API Key 输入框填写方舟 API Key", "或重启服务前设置 ARK_API_KEY"]);
      }
      if (text.includes("Missing TOS")) {
        return item("TOS 配置缺失", "TOS 上传参数不完整", "图生视频本地文件上传需要 TOS Bucket 和 AK/SK。", ["填写 TOS Bucket、AccessKey、SecretKey", "点“检测 TOS 配置”确认可用", "也可以直接填公网 HTTPS 图片 URL 跳过本地上传"]);
      }
      if (lower.includes("unauthorized") || lower.includes("authentication") || text.includes("401")) {
        return item("鉴权失败", "Key 不正确或已失效", "方舟 API Key 或 TOS AK/SK 无法通过鉴权。", ["检查 Key 是否复制完整", "确认方舟 API Key 和火山云 AK/SK 不是同一个东西", "必要时重新生成 Key"]);
      }
      if (lower.includes("permission") || text.includes("403")) {
        return item("权限不足", "账号或子用户没有对应权限", "可能是模型权限、TOS bucket 权限、对象读写权限或项目空间权限不足。", ["检查模型是否开通", "检查 TOS 子用户是否有 PutObject/GetObject/ListBucket 权限", "检查 bucket 区域和 endpoint 是否一致"]);
      }
      if (text.includes("Insufficient") || lower.includes("balance") || lower.includes("quota")) {
        return item("额度/余额", "账户余额或配额不足", "火山账户余额、模型额度、并发或限额可能不足。", ["去费用中心看余额和账单", "检查模型额度/并发限制", "降低并发或稍后重试"]);
      }
      if (text.includes("429") || lower.includes("rate")) {
        return item("限流", "请求过于频繁或并发不足", "账号当前并发或 QPS 达到限制。", ["稍后重试", "降低同时提交任务数", "需要稳定多人使用时找火山开并发或保量资源"]);
      }
      if (text.includes("No video URL found")) {
        return item("无视频链接", "任务还没有返回可下载视频", "任务可能还在排队/生成，或最终返回结构里没有 video_url。", ["稍后点“查询任务”", "查看最新状态 JSON 里的 status 和 content"]);
      }
      if (text.includes("Bad Request") || text.includes("Invalid")) {
        return item("参数错误", "请求参数不被火山接受", "通常是模型、时长、比例、分辨率、素材 URL 或输入组合不符合当前模型要求。", ["看最新状态 JSON 里的 error.code 和 message", "先用文生视频最小参数测通", "再逐项打开图生视频、音频、尾帧等选项"]);
      }
      return item("未知错误", "暂未匹配到固定原因", "这个错误不在常见模板里，需要看完整返回内容和发生阶段。", ["复制错误原文", "查看最新状态 JSON", "如果是创建阶段失败，先查最近任务再决定是否重试"], "warn");
    }

    function renderErrorHelp(err) {
      const message = errorMessage(err);
      const info = explainError(message);
      setBadge($("errorBadge"), info.badge, info.level);
      $("errorHelp").innerHTML = [
        `<strong>${escapeHtml(info.title)}</strong>`,
        `<span>${escapeHtml(info.reason)}</span>`,
        `<strong>建议处理</strong>`,
        `<ul>${info.actions.map((action) => `<li>${escapeHtml(action)}</li>`).join("")}</ul>`,
      ].join("");
      return info;
    }

    function hasVideoInput(data) {
      const content = Array.isArray(data?.content) ? data.content : [];
      return content.some((item) => item?.type === "video_url" || Boolean(item?.video_url));
    }

    function findUsage(data) {
      if (!data || typeof data !== "object") return null;
      const usage = data.usage;
      if (usage && typeof usage === "object") {
        const tokens = Number(usage.total_tokens || usage.completion_tokens || usage.prompt_tokens || 0);
        if (tokens > 0) return { tokens, usage };
      }
      if (Array.isArray(data)) {
        for (const item of data) {
          const found = findUsage(item);
          if (found) return found;
        }
      } else {
        for (const value of Object.values(data)) {
          const found = findUsage(value);
          if (found) return found;
        }
      }
      return null;
    }

    function yuan(value) {
      return `¥${Number(value || 0).toFixed(2)}`;
    }

    function renderCost(data, label = "") {
      const source = data || state.latestResponse || state.requestPayload || {};
      const usage = findUsage(source);
      const payload = state.requestPayload || {};
      const model = source.model || payload.model || selectedModel();
      const duration = Number(source.duration || payload.duration || $("duration").value || 0);
      const resolution = source.resolution || payload.resolution || $("resolution").value || "未返回";
      const videoInput = hasVideoInput(payload);
      const tokenRate = Number((videoInput ? $("priceVideoInputPerMTokens") : $("priceNoVideoInputPerMTokens")).value || 0);
      const fallbackRate = Number($("fallbackPricePerSecond").value || 0);
      let amount = 0;
      let method = "";
      let detail = "";
      if (usage?.tokens) {
        amount = usage.tokens / 1000000 * tokenRate;
        method = "按实际 usage";
        detail = `${usage.tokens.toLocaleString()} tokens x ${tokenRate} 元/百万 token`;
      } else if (duration > 0) {
        amount = duration * fallbackRate;
        method = "按时长估算";
        detail = `${duration} 秒 x ${fallbackRate} 元/秒`;
      } else {
        setBadge($("costBadge"), "无法计算", "warn");
        $("costOut").value = "";
        $("costDetails").textContent = "没有 usage，也没有可用时长，暂时无法计算。";
        return;
      }
      setBadge($("costBadge"), method, usage?.tokens ? "ok" : "warn");
      $("costOut").value = `${yuan(amount)}${label ? " · " + label : ""}`;
      $("costDetails").innerHTML = [
        `<strong>${escapeHtml(detail)}</strong>`,
        `<span>模型：${escapeHtml(model || "未知")}；分辨率：${escapeHtml(resolution)}；时长：${duration || "未知"} 秒；输入类型：${videoInput ? "含视频输入/参考" : "不含视频输入/参考"}。</span>`,
        usage?.tokens ? "<span>这是按接口返回 usage 计算的估算费用，最终以火山账单为准。</span>" : "<span>接口未返回 usage，这是兜底估算，最终以火山账单为准。</span>",
      ].join("");
    }

    function normalizeBaseUrl(value) {
      const trimmed = value.trim().replace(/\/+$/, "");
      return trimmed.endsWith("/api/v3") ? trimmed : trimmed + "/api/v3";
    }

    function selectedModel() {
      const preset = $("modelPreset").value;
      if (preset === "custom") return $("modelCustom").value.trim();
      return preset;
    }

    function mediaObject(kind, value, role = "") {
      const item = { type: kind, [kind]: { url: value } };
      if (role) item.role = role;
      return item;
    }

    function normalizeAssetUri(value) {
      const trimmed = String(value || "").trim();
      if (!trimmed) return "";
      if (trimmed.startsWith("asset://")) return trimmed;
      if (trimmed.startsWith("asset-") || trimmed.startsWith("asset_")) return `asset://${trimmed}`;
      return trimmed;
    }

    function portraitAssetInputs() {
      return Array.from(document.querySelectorAll(".portrait-asset"));
    }

    function portraitAssetValues() {
      const seen = new Set();
      const values = [];
      for (const input of portraitAssetInputs()) {
        const uri = normalizeAssetUri(input.value);
        if (uri && !seen.has(uri)) {
          values.push(uri);
          seen.add(uri);
        }
      }
      return values;
    }

    function updatePortraitBadge() {
      const count = portraitAssetValues().length;
      setBadge($("portraitBadge"), count ? `${count} 人` : "Asset ID", count ? "ok" : "");
    }

    function addPortraitAssetRow(value = "") {
      const row = document.createElement("div");
      row.className = "asset-row";
      row.innerHTML = `
        <label>
          授权真人 Asset ID
          <input class="portrait-asset" placeholder="asset-... 或 asset://asset-..." />
        </label>
        <button class="button portrait-remove" type="button">删除</button>
      `;
      row.querySelector(".portrait-asset").value = value;
      $("portraitAssets").appendChild(row);
      updatePortraitBadge();
      row.querySelector(".portrait-asset").focus();
    }

    function removePortraitRow(button) {
      const rows = Array.from($("portraitAssets").querySelectorAll(".asset-row"));
      const row = button.closest(".asset-row");
      if (rows.length <= 1) {
        row.querySelector(".portrait-asset").value = "";
      } else {
        row.remove();
      }
      updatePortraitBadge();
    }

    function currentMediaValue(inputId, fileKey) {
      const direct = $(inputId).value.trim();
      return direct || state.fileData[fileKey] || "";
    }

    function tosConfig() {
      return {
        accessKey: $("tosAccessKey").value.trim(),
        secretKey: $("tosSecretKey").value.trim(),
        securityToken: $("tosSecurityToken").value.trim(),
        bucket: $("tosBucket").value.trim(),
        endpoint: $("tosEndpoint").value.trim(),
        region: $("tosRegion").value.trim(),
        prefix: $("tosPrefix").value.trim(),
        expires: Math.max(600, Number($("tosExpires").value || 86400)),
        timeout: Math.max(60, Number($("tosTimeout").value || 300)),
      };
    }

    function tosFieldIds() {
      return [
        "tosBucket",
        "tosRegion",
        "tosEndpoint",
        "tosAccessKey",
        "tosSecretKey",
        "tosSecurityToken",
        "tosPrefix",
        "tosExpires",
        "tosTimeout",
      ];
    }

    function fillTosConfig(config = {}) {
      if (config.bucket !== undefined) $("tosBucket").value = config.bucket || "";
      if (config.region !== undefined) $("tosRegion").value = config.region || "cn-beijing";
      if (config.endpoint !== undefined) $("tosEndpoint").value = config.endpoint || "https://tos-cn-beijing.volces.com";
      if (config.accessKey !== undefined) $("tosAccessKey").value = config.accessKey || "";
      if (config.secretKey !== undefined) $("tosSecretKey").value = config.secretKey || "";
      if (config.securityToken !== undefined) $("tosSecurityToken").value = config.securityToken || "";
      if (config.prefix !== undefined) $("tosPrefix").value = config.prefix || "seedance-inputs";
      if (config.expires !== undefined) $("tosExpires").value = config.expires || 86400;
      if (config.timeout !== undefined) $("tosTimeout").value = config.timeout || 300;
    }

    function setTosLocked(locked) {
      state.tosLocked = locked;
      for (const id of tosFieldIds()) {
        $(id).disabled = locked;
      }
      $("saveTosBtn").disabled = locked;
      $("unlockTosBtn").disabled = !locked;
      if (locked) setBadge($("tosBadge"), "TOS 已锁定", "ok");
    }

    async function saveTosConfig() {
      try {
        setBadge($("tosBadge"), "保存中", "warn");
        const data = await postJson("/api/tos/save", tosConfig());
        setLogPath(data);
        fillTosConfig(data.tos || {});
        setTosLocked(true);
        addLog("TOS 配置已保存并锁定", data.configPath || "");
      } catch (err) {
        setBadge($("tosBadge"), "保存失败", "err");
        renderErrorHelp(err);
        addLog("保存 TOS 配置失败", err.message || err);
      }
    }

    function dataFingerprint(value) {
      return `${value.length}:${value.slice(0, 64)}:${value.slice(-64)}`;
    }

    function imageCompressionFingerprint() {
      return [
        $("compressImages").checked ? "compress" : "original",
        $("imageMaxSide").value,
        $("imageJpegQuality").value,
      ].join(":");
    }

    function replaceExtension(filename, extension) {
      const clean = filename || "image";
      return clean.replace(/\.[^.]+$/, "") + extension;
    }

    function compressImageDataUrl(dataUrl, meta) {
      if (!$("compressImages").checked) {
        return Promise.resolve({ dataUrl, meta, changed: false });
      }
      if (!String(meta?.type || "").startsWith("image/")) {
        return Promise.resolve({ dataUrl, meta, changed: false });
      }
      return new Promise((resolve) => {
        const image = new Image();
        image.onload = () => {
          const maxSide = Math.max(512, Number($("imageMaxSide").value || 1920));
          const quality = Math.max(0.5, Math.min(1, Number($("imageJpegQuality").value || 0.88)));
          const scale = Math.min(1, maxSide / Math.max(image.naturalWidth || image.width, image.naturalHeight || image.height));
          if (scale >= 1 && meta?.type === "image/jpeg") {
            resolve({ dataUrl, meta, changed: false });
            return;
          }
          const canvas = document.createElement("canvas");
          canvas.width = Math.max(1, Math.round((image.naturalWidth || image.width) * scale));
          canvas.height = Math.max(1, Math.round((image.naturalHeight || image.height) * scale));
          const ctx = canvas.getContext("2d", { alpha: false });
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
          const output = canvas.toDataURL("image/jpeg", quality);
          const outputMeta = {
            ...(meta || {}),
            name: replaceExtension(meta?.name || "image", ".jpg"),
            type: "image/jpeg",
            originalSize: meta?.size || 0,
            size: Math.round((output.length - "data:image/jpeg;base64,".length) * 0.75),
          };
          resolve({ dataUrl: output, meta: outputMeta, changed: true, width: canvas.width, height: canvas.height });
        };
        image.onerror = () => resolve({ dataUrl, meta, changed: false });
        image.src = dataUrl;
      });
    }

    async function uploadLocalMedia(fileKey) {
      const dataUrl = state.fileData[fileKey];
      if (!dataUrl) return "";
      if (!$("tosAutoUpload").checked) return dataUrl;

      const rawMeta = state.fileMeta[fileKey] || {};
      const media = ["image", "lastImage"].includes(fileKey)
        ? await compressImageDataUrl(dataUrl, rawMeta)
        : { dataUrl, meta: rawMeta, changed: false };
      const uploadDataUrl = media.dataUrl;
      const meta = media.meta || rawMeta;
      const fingerprint = `${dataFingerprint(uploadDataUrl)}:${imageCompressionFingerprint()}`;
      const cached = state.uploadedMedia[fileKey];
      if (cached && cached.fingerprint === fingerprint) return cached.url;

      setBadge($("tosBadge"), "上传中", "warn");
      if (media.changed) {
        addLog(
          "图片已压缩",
          `${Math.round((rawMeta.size || 0) / 1024)} KB -> ${Math.round((meta.size || 0) / 1024)} KB · ${media.width}x${media.height}`
        );
      }
      addLog("上传本地文件到 TOS", `${meta.name || fileKey}${meta.size ? " · " + Math.round(meta.size / 1024) + " KB" : ""}`);
      const data = await postJson("/api/tos/upload", {
        ...tosConfig(),
        dataUrl: uploadDataUrl,
        filename: meta.name || `${fileKey}.bin`,
        contentType: meta.type || "",
      });
      state.uploadedMedia[fileKey] = { fingerprint, url: data.url, key: data.key };
      setBadge($("tosBadge"), "TOS 已上传", "ok");
      addLog("TOS 外链已生成", data.key || "");
      return data.url;
    }

    async function mediaValueForPayload(inputId, fileKey) {
      const direct = $(inputId).value.trim();
      if (direct) return direct;
      return uploadLocalMedia(fileKey);
    }

    async function buildPayload() {
      const content = [];
      const prompt = $("prompt").value.trim();
      if (prompt) content.push({ type: "text", text: prompt });

      const image = await mediaValueForPayload("imageUrl", "image");
      const lastImage = await mediaValueForPayload("lastImageUrl", "lastImage");
      const video = await mediaValueForPayload("videoUrl", "video");
      const audio = await mediaValueForPayload("audioUrl", "audio");

      for (const portraitAsset of portraitAssetValues()) {
        content.push(mediaObject("image_url", portraitAsset, "reference_image"));
      }
      updatePortraitBadge();

      if (state.mode === "image" && image) {
        content.push(mediaObject("image_url", image, "first_frame"));
      }
      if (state.mode === "mixed" && image) {
        content.push(mediaObject("image_url", image, "reference_image"));
      }
      if (state.mode === "mixed" && lastImage) {
        content.push(mediaObject("image_url", lastImage, "last_frame"));
      }
      if (["video", "mixed"].includes(state.mode) && video) {
        content.push(mediaObject("video_url", video, "reference_video"));
      }
      if (state.mode === "mixed" && audio) {
        content.push(mediaObject("audio_url", audio, "reference_audio"));
      }

      const payload = {
        model: selectedModel(),
        content,
        ratio: $("ratio").value,
        duration: Number($("duration").value),
        watermark: $("watermark").checked,
      };
      const resolution = $("resolution").value;
      if (resolution) payload.resolution = resolution;
      payload.generate_audio = $("generateAudio").checked;
      if ($("returnLastFrame").checked) payload.return_last_frame = true;
      const seed = $("seed").value.trim();
      if (seed) payload.seed = Number(seed);
      return payload;
    }

    function outputRootValue() {
      return $("outputRoot").value.trim();
    }

    function displayJson(tab = state.activeTab) {
      state.activeTab = tab;
      document.querySelectorAll(".tab").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.tab === tab);
      });
      let data = {};
      if (tab === "request") data = sanitizeForPreview(state.requestPayload);
      if (tab === "create") data = state.createResponse;
      if (tab === "latest") data = state.latestResponse;
      $("jsonBox").textContent = JSON.stringify(data || {}, null, 2);
    }

    function sanitizeForPreview(data) {
      const clone = JSON.parse(JSON.stringify(data || {}));
      if (Array.isArray(clone.content)) {
        for (const item of clone.content) {
          for (const key of ["image_url", "video_url", "audio_url"]) {
            if (item[key]?.url?.startsWith("data:")) {
              const raw = item[key].url;
              item[key].url = raw.slice(0, 80) + `... [${raw.length} chars]`;
            }
          }
        }
      }
      return clone;
    }

    async function previewRequest() {
      state.requestPayload = await buildPayload();
      displayJson("request");
      renderCost(state.requestPayload, "提交前估算");
      addLog("已生成请求预览", `${state.requestPayload.content.length} 个 content item`);
    }

    async function postJson(url, body) {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { raw: text }; }
      if (!res.ok) {
        const err = data.error || text || `HTTP ${res.status}`;
        throw new Error(typeof err === "string" ? err : JSON.stringify(err));
      }
      return data;
    }

    async function getJson(url) {
      const res = await fetch(url);
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { raw: text }; }
      if (!res.ok) {
        const err = data.error || text || `HTTP ${res.status}`;
        throw new Error(typeof err === "string" ? err : JSON.stringify(err));
      }
      return data;
    }

    async function startTask() {
      try {
        $("runBtn").disabled = true;
        setProgress(5);
        setBadge($("taskBadge"), "提交中", "warn");
        state.videoUrl = "";
        $("videoUrlOut").value = "";
        $("taskIdOut").value = "";
        $("video").style.display = "none";
        $("emptyState").style.display = "grid";
        $("downloadBtn").disabled = true;
        $("cancelBtn").disabled = true;
        clearSuccess();

        const payload = await buildPayload();
        if (!payload.model) throw new Error("请填写模型 ID");
        if (!payload.content.length) throw new Error("至少需要提示词、图片、视频或音频之一");

        state.requestPayload = payload;
        displayJson("request");

        const data = await postJson("/api/tasks", {
          apiKey: $("apiKey").value.trim(),
          baseUrl: normalizeBaseUrl($("baseUrl").value),
          requestTimeout: Math.max(30, Number($("requestTimeout").value || 300)),
          outputRoot: outputRootValue(),
          payload,
        });

        state.runId = data.runId;
        state.taskId = data.taskId;
        $("taskIdOut").value = data.taskId || "";
        state.startedAt = Date.now();
        state.pollErrorCount = 0;
        state.createResponse = data.createResponse || {};
        state.latestResponse = {};
        $("outputDir").value = data.outputDir || "";
        setLogPath(data);
        $("cancelBtn").disabled = false;
        displayJson("create");
        setBadge($("taskBadge"), data.status || "已创建", "warn");
        addLog("任务已创建", `task_id=${state.taskId}`);

        beginPolling();
      } catch (err) {
        setBadge($("taskBadge"), "错误", "err");
        const explanation = renderErrorHelp(err);
        addLog("创建失败", err.message || err);
        addLog("错误说明", explanation.title);
        if (String(err.message || err).includes("ModelNotOpen")) {
          addLog("模型未开通", "去火山方舟开通管理里开通当前模型，或切换到已开通模型 ID");
        }
        if (String(err.message || err).includes("Network error")) {
          addLog("创建返回中断", "可能已创建但没拿到返回；先点“最近任务”确认，避免重复扣费");
          $("runBtn").disabled = true;
          setBadge($("taskBadge"), "先查最近任务", "warn");
          addLog("自动查询最近任务", "只查询历史任务，不会创建新任务");
          await listRecentTasks();
        } else {
          $("runBtn").disabled = false;
        }
        $("jsonBox").textContent = String(err.stack || err);
      }
    }

    function beginPolling() {
      if (state.timer) clearInterval(state.timer);
      const interval = Math.max(2, Number($("interval").value || 8)) * 1000;
      const timeout = Math.max(30, Number($("timeout").value || 1800)) * 1000;

      const tick = async () => {
        if (!state.runId) return;
        const elapsed = Date.now() - state.startedAt;
        $("elapsedBadge").textContent = `${Math.round(elapsed / 1000)} 秒`;
        setProgress(Math.min(90, 10 + elapsed / timeout * 80));

        try {
          const data = await getJson(`/api/tasks/${encodeURIComponent(state.runId)}`);
          state.pollErrorCount = 0;
          state.latestResponse = data.task || {};
          setLogPath(data);
          displayJson(state.activeTab === "request" || state.activeTab === "create" ? state.activeTab : "latest");
          const status = (data.status || "unknown").toLowerCase();
          if (status) setBadge($("taskBadge"), status, statusClass(status));

          if (data.videoUrl) {
            state.videoUrl = data.videoUrl;
            $("videoUrlOut").value = data.videoUrl;
          }

          if (data.done) {
            clearInterval(state.timer);
            state.timer = null;
            $("runBtn").disabled = false;
            $("cancelBtn").disabled = true;
            setProgress(statusClass(status) === "ok" ? 100 : 0);
            addLog(statusClass(status) === "ok" ? "任务成功" : "任务结束", status);
            if (statusClass(status) === "ok") renderCost(data.task || state.latestResponse, "实际用量");
            if (state.videoUrl) {
              showVideo(state.videoUrl);
              $("downloadBtn").disabled = false;
              showSuccess("生成成功", `task_id=${state.taskId || data.taskId || ""}，可以预览或下载到本地。`);
            }
            if (state.videoUrl && $("autoDownload").checked) downloadCurrent();
          }
        } catch (err) {
          state.pollErrorCount += 1;
          const message = String(err.message || err);
          const retryable = state.pollErrorCount <= 8 && (
            message.includes("Network error") ||
            message.includes("SSL") ||
            message.includes("timed out") ||
            message.includes("EOF")
          );

          if (retryable) {
          setBadge($("taskBadge"), `轮询重试 ${state.pollErrorCount}/8`, "warn");
            renderErrorHelp(message);
            addLog("轮询临时失败，继续重试", message);
            return;
          }

          clearInterval(state.timer);
          state.timer = null;
          $("runBtn").disabled = false;
          $("cancelBtn").disabled = false;
          setBadge($("taskBadge"), "轮询错误", "err");
          renderErrorHelp(message);
          addLog("轮询失败", message);
        }
      };

      tick();
      state.timer = setInterval(tick, interval);
    }

    async function cancelCurrentTask() {
      const manualTaskId = $("taskIdOut").value.trim();
      if (!state.runId && !manualTaskId) {
        addLog("没有可终止的任务", "需要先创建任务或粘贴 task_id");
        return;
      }

      if (state.timer) {
        clearInterval(state.timer);
        state.timer = null;
      }
      $("cancelBtn").disabled = true;
      $("runBtn").disabled = false;
      setBadge($("taskBadge"), "终止中", "warn");
      addLog("已停止本地轮询", state.taskId ? `task_id=${state.taskId}` : "");

      try {
        const data = state.runId
          ? await postJson(`/api/tasks/${encodeURIComponent(state.runId)}/cancel`, {})
          : await postJson("/api/cancel-task", {
              apiKey: $("apiKey").value.trim(),
              baseUrl: normalizeBaseUrl($("baseUrl").value),
              taskId: manualTaskId,
              requestTimeout: Math.max(30, Number($("requestTimeout").value || 300)),
            });
        state.latestResponse = data.response || {};
        setLogPath(data);
        displayJson("latest");
        setBadge($("taskBadge"), "已请求终止", "warn");
        addLog("已向火山发送终止请求", data.taskId || "");
      } catch (err) {
        setBadge($("taskBadge"), "本地已停止", "warn");
        renderErrorHelp(err);
        addLog("远端终止失败", err.message || err);
      }
    }

    function findTaskIds(value, output = []) {
      if (!value || output.length >= 10) return output;
      if (typeof value === "string" && value.startsWith("cgt-")) {
        output.push(value);
        return output;
      }
      if (Array.isArray(value)) {
        for (const item of value) findTaskIds(item, output);
        return output;
      }
      if (typeof value === "object") {
        for (const item of Object.values(value)) findTaskIds(item, output);
      }
      return output;
    }

    async function queryManualTask() {
      const taskId = $("taskIdOut").value.trim();
      if (!taskId) {
        addLog("缺少任务 ID", "先粘贴 task_id，或点最近任务");
        return;
      }
      try {
        setBadge($("taskBadge"), "查询中", "warn");
        const data = await postJson("/api/query-task", {
          apiKey: $("apiKey").value.trim(),
          baseUrl: normalizeBaseUrl($("baseUrl").value),
          taskId,
          requestTimeout: Math.max(30, Number($("requestTimeout").value || 300)),
          outputRoot: outputRootValue(),
        });
        state.latestResponse = data.task || {};
        setLogPath(data);
        if (data.runId) {
          state.runId = data.runId;
        }
        state.taskId = taskId;
        state.videoUrl = data.videoUrl || "";
        $("outputDir").value = data.outputDir || "";
        displayJson("latest");
        renderCost(data.task || {}, "查询返回");
        setBadge($("taskBadge"), data.status || "已查询", statusClass(String(data.status || "").toLowerCase()));
        addLog("任务状态已更新", data.status || taskId);
        if (state.videoUrl) {
          $("videoUrlOut").value = state.videoUrl;
          showVideo(state.videoUrl);
          $("downloadBtn").disabled = false;
          showSuccess("生成成功", `task_id=${taskId}，视频链接已返回。`);
        }
      } catch (err) {
        setBadge($("taskBadge"), "查询失败", "err");
        renderErrorHelp(err);
        addLog("查询任务失败", err.message || err);
      }
    }

    async function queryAndDownloadManualTask() {
      await queryManualTask();
      if (state.videoUrl) {
        await downloadCurrent();
      } else {
        addLog("暂未下载", "任务还没有返回 video_url，稍后再查询");
      }
    }

    async function listRecentTasks() {
      try {
        setBadge($("taskBadge"), "查询最近任务", "warn");
        const data = await postJson("/api/list-tasks", {
          apiKey: $("apiKey").value.trim(),
          baseUrl: normalizeBaseUrl($("baseUrl").value),
          requestTimeout: Math.max(30, Number($("requestTimeout").value || 300)),
          pageSize: 10,
        });
        state.latestResponse = data.response || {};
        setLogPath(data);
        displayJson("latest");
        const ids = findTaskIds(data.response || {});
        if (ids.length) {
          $("taskIdOut").value = ids[0];
          addLog("已找到最近任务", ids.slice(0, 3).join(", "));
        } else {
          addLog("最近任务已返回", "未自动识别到 cgt- 开头的任务 ID，请看最新状态 JSON");
        }
        $("runBtn").disabled = false;
        setBadge($("taskBadge"), "最近任务", "warn");
      } catch (err) {
        setBadge($("taskBadge"), "查询失败", "err");
        renderErrorHelp(err);
        addLog("查询最近任务失败", err.message || err);
      }
    }

    async function queryAllLocalTasks() {
      try {
        setBadge($("taskBadge"), "查询全部", "warn");
        const data = await postJson("/api/query-local-tasks", {
          apiKey: $("apiKey").value.trim(),
          baseUrl: normalizeBaseUrl($("baseUrl").value),
          requestTimeout: Math.max(30, Number($("requestTimeout").value || 300)),
          outputRoot: outputRootValue(),
          download: true,
        });
        state.latestResponse = data;
        setLogPath(data);
        displayJson("latest");
        const okCount = (data.results || []).filter((item) => item.status === "succeeded").length;
        const runningCount = (data.results || []).filter((item) => item.status === "running").length;
        const errCount = (data.results || []).filter((item) => item.error).length;
        setBadge($("taskBadge"), `全部查询 ${okCount}/${data.results.length}`, errCount ? "warn" : "ok");
        addLog("本地全部任务已查询", `成功 ${okCount} · 运行中 ${runningCount} · 错误 ${errCount}`);
        const firstVideo = (data.results || []).find((item) => item.videoUrl);
        if (firstVideo) {
          $("taskIdOut").value = firstVideo.taskId;
          $("videoUrlOut").value = firstVideo.videoUrl;
          $("outputDir").value = firstVideo.outputDir || "";
          renderCost(firstVideo.task || {}, "批量查询返回");
          showVideo(firstVideo.fileUrl || firstVideo.videoUrl);
          $("downloadBtn").disabled = false;
          showSuccess(firstVideo.filePath ? "下载成功" : "生成成功", firstVideo.filePath || `task_id=${firstVideo.taskId}`);
        }
      } catch (err) {
        setBadge($("taskBadge"), "全部查询失败", "err");
        renderErrorHelp(err);
        addLog("查询本地全部任务失败", err.message || err);
      }
    }

    async function checkConnection() {
      try {
        const started = performance.now();
        setBadge($("keyBadge"), "检测中", "warn");
        setBadge($("taskBadge"), "检测连线", "warn");
        const data = await postJson("/api/check-connection", {
          apiKey: $("apiKey").value.trim(),
          baseUrl: normalizeBaseUrl($("baseUrl").value),
          requestTimeout: Math.max(30, Number($("requestTimeout").value || 300)),
        });
        const elapsed = Math.round(performance.now() - started);
        state.latestResponse = data.response || {};
        setLogPath(data);
        displayJson("latest");
        setBadge($("keyBadge"), `连线正常 ${elapsed}ms`, "ok");
        setBadge($("taskBadge"), "连线正常", "ok");
        addLog("连线检测成功", `耗时 ${elapsed}ms`);
      } catch (err) {
        const message = String(err.message || err);
        setBadge($("keyBadge"), "连线失败", "err");
        setBadge($("taskBadge"), "连线失败", "err");
        renderErrorHelp(message);
        addLog("连线检测失败", message);
        if (message.includes("Missing API Key")) {
          addLog("缺少 API Key", "在页面填 Key，或重启服务前设置 ARK_API_KEY");
        }
      }
    }

    async function checkTosConfig() {
      try {
        setBadge($("tosBadge"), "检测中", "warn");
        const data = await postJson("/api/tos/check", tosConfig());
        setLogPath(data);
        setBadge($("tosBadge"), "TOS 可用", "ok");
        addLog("TOS 配置可用", data.bucket || "");
      } catch (err) {
        setBadge($("tosBadge"), "TOS 不可用", "err");
        renderErrorHelp(err);
        addLog("TOS 检测失败", err.message || err);
      }
    }

    function statusClass(status) {
      if (["succeeded", "completed", "success"].includes(status)) return "ok";
      if (["failed", "cancelled", "canceled", "expired"].includes(status)) return "err";
      return "warn";
    }

    function setProgress(value) {
      $("progressBar").style.width = `${Math.max(0, Math.min(100, value))}%`;
    }

    function showVideo(url) {
      const video = $("video");
      video.src = url;
      video.style.display = "block";
      $("emptyState").style.display = "none";
    }

    async function downloadCurrent() {
      if (!state.runId) return;
      try {
        $("downloadBtn").disabled = true;
        const data = await postJson(`/api/tasks/${encodeURIComponent(state.runId)}/download`, {});
        setLogPath(data);
        if (data.fileUrl) showVideo(data.fileUrl);
        if (data.filePath) showSuccess("下载成功", data.filePath);
        addLog("已下载到本地", data.filePath || "");
      } catch (err) {
        renderErrorHelp(err);
        addLog("下载失败", err.message || err);
      } finally {
        $("downloadBtn").disabled = false;
      }
    }

    function setMode(mode) {
      state.mode = mode;
      document.querySelectorAll("[data-mode]").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.mode === mode);
      });
      $("modeBadge").textContent = modeNames[mode];
      $("imageBlock").classList.toggle("hidden", !["image", "mixed"].includes(mode));
      $("lastImageBlock").classList.toggle("hidden", mode !== "mixed");
      $("videoBlock").classList.toggle("hidden", !["video", "mixed"].includes(mode));
      $("audioBlock").classList.toggle("hidden", mode !== "mixed");
    }

    function readFileAsDataUrl(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
    }

    function bindFile(inputId, key) {
      $(inputId).addEventListener("change", async (event) => {
        const file = event.target.files && event.target.files[0];
        state.fileData[key] = "";
        state.fileMeta[key] = null;
        state.uploadedMedia[key] = null;
        if (!file) return;
        setBadge($("taskBadge"), "读取文件", "warn");
        state.fileData[key] = await readFileAsDataUrl(file);
        state.fileMeta[key] = { name: file.name, type: file.type, size: file.size };
        setBadge($("taskBadge"), "未提交");
        addLog("本地文件已载入", `${file.name} · ${Math.round(file.size / 1024)} KB`);
      });
    }

    async function loadConfig() {
      try {
        const data = await getJson("/api/config");
        setBadge($("keyBadge"), data.hasServerKey ? "环境变量已设置" : "需要输入 Key", data.hasServerKey ? "ok" : "warn");
        setBadge($("tosBadge"), data.hasTosKey ? "TOS 环境变量已设置" : "TOS 未检测", data.hasTosKey ? "ok" : "");
        fillTosConfig(data.tos || {
          bucket: data.tosBucket,
          endpoint: data.tosEndpoint,
          region: data.tosRegion,
          prefix: data.tosPrefix,
          timeout: data.tosTimeout,
        });
        setTosLocked(Boolean(data.tosLocked));
        setLogPath(data);
        if (data.outputRoot) $("outputRoot").value = data.outputRoot;
      } catch (_) {
        setBadge($("keyBadge"), "配置检查失败", "err");
      }
    }

    document.querySelectorAll("[data-mode]").forEach((btn) => btn.addEventListener("click", () => setMode(btn.dataset.mode)));
    document.querySelectorAll(".tab").forEach((btn) => btn.addEventListener("click", () => displayJson(btn.dataset.tab)));
    $("modelPreset").addEventListener("change", () => {
      $("modelCustom").disabled = $("modelPreset").value !== "custom";
      if (!$("modelCustom").disabled) $("modelCustom").focus();
    });
    $("previewBtn").addEventListener("click", previewRequest);
    $("runBtn").addEventListener("click", startTask);
    $("checkConnectionBtn").addEventListener("click", checkConnection);
    $("checkTosBtn").addEventListener("click", checkTosConfig);
    $("saveTosBtn").addEventListener("click", saveTosConfig);
    $("unlockTosBtn").addEventListener("click", () => {
      setTosLocked(false);
      setBadge($("tosBadge"), "TOS 已解锁", "warn");
      addLog("TOS 配置已解锁", "修改后可重新保存并锁定");
    });
    $("addPortraitAssetBtn").addEventListener("click", () => addPortraitAssetRow());
    $("portraitAssets").addEventListener("click", (event) => {
      if (event.target.classList.contains("portrait-remove")) removePortraitRow(event.target);
    });
    $("portraitAssets").addEventListener("input", updatePortraitBadge);
    $("queryTaskBtn").addEventListener("click", queryManualTask);
    $("queryDownloadBtn").addEventListener("click", queryAndDownloadManualTask);
    $("queryAllLocalBtn").addEventListener("click", queryAllLocalTasks);
    $("listTasksBtn").addEventListener("click", listRecentTasks);
    $("cancelBtn").addEventListener("click", cancelCurrentTask);
    $("cancelInlineBtn").addEventListener("click", cancelCurrentTask);
    $("downloadBtn").addEventListener("click", downloadCurrent);
    ["priceNoVideoInputPerMTokens", "priceVideoInputPerMTokens", "fallbackPricePerSecond"].forEach((id) => {
      $(id).addEventListener("input", () => renderCost(state.latestResponse?.usage ? state.latestResponse : state.requestPayload, "单价更新"));
    });

    bindFile("imageFile", "image");
    bindFile("lastImageFile", "lastImage");
    bindFile("videoFile", "video");
    bindFile("audioFile", "audio");

    setMode("text");
    setTosLocked(false);
    updatePortraitBadge();
    loadConfig();
    previewRequest();
  </script>
</body>
</html>
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def load_server_api_key() -> str | None:
    for name in ("ARK_API_KEY", "VOLCENGINE_API_KEY", "SEEDANCE_API_KEY"):
        value = os.getenv(name)
        if value:
            return value
    return None


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def load_local_config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def saved_tos_config() -> dict[str, Any]:
    tos_config = load_local_config().get("tos")
    return tos_config if isinstance(tos_config, dict) else {}


def config_value(section: dict[str, Any], key: str) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def load_tos_access_key() -> str | None:
    return first_env("TOS_ACCESS_KEY_ID", "TOS_ACCESS_KEY", "VOLCENGINE_ACCESS_KEY_ID", "VOLCENGINE_AK") or config_value(saved_tos_config(), "accessKey")


def load_tos_secret_key() -> str | None:
    return first_env("TOS_SECRET_ACCESS_KEY", "TOS_SECRET_KEY", "VOLCENGINE_SECRET_ACCESS_KEY", "VOLCENGINE_SK") or config_value(saved_tos_config(), "secretKey")


def load_tos_security_token() -> str | None:
    return first_env("TOS_SECURITY_TOKEN", "VOLCENGINE_SECURITY_TOKEN") or config_value(saved_tos_config(), "securityToken")


def normalize_base_url(value: str) -> str:
    value = (value or DEFAULT_BASE_URL).strip().rstrip("/")
    if value.endswith("/api/v3"):
        return value
    return value + "/api/v3"


def safe_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_")
    return value[:80] or "file"


def safe_prefix(value: str) -> str:
    value = (value or DEFAULT_TOS_PREFIX).strip().strip("/")
    value = re.sub(r"[^a-zA-Z0-9_./-]+", "_", value)
    return value.strip("/") or DEFAULT_TOS_PREFIX


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def redact_url(value: str) -> str:
    if not value.startswith(("http://", "https://")):
        return value
    parsed = urlparse(value)
    if parsed.query:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?..."
    return value


def sanitize_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if key_lower in {"apikey", "api_key", "accesskey", "secretkey", "securitytoken", "authorization"}:
                output[key] = "[redacted]"
            elif key_lower in {"dataurl", "content"} and isinstance(item, str) and item.startswith("data:"):
                output[key] = f"[data-url {len(item)} chars]"
            else:
                output[key] = sanitize_for_log(item)
        return output
    if isinstance(value, list):
        return [sanitize_for_log(item) for item in value]
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            return redact_url(value)
        if len(value) > 2000:
            return value[:2000] + f"... [{len(value)} chars]"
    return value


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


def log_event(event: str, run_id: str | None = None, output_dir: Path | str | None = None, **fields: Any) -> None:
    record = {
        "ts": now_iso(),
        "event": event,
        **sanitize_for_log(fields),
    }
    if run_id:
        record["run_id"] = run_id
    if output_dir:
        record["output_dir"] = str(output_dir)
    with LOG_LOCK:
        append_jsonl(LOG_DIR / "seedance_web_events.jsonl", record)
        if output_dir:
            append_jsonl(Path(output_dir) / "events.jsonl", record)


def resolve_output_root(value: Any = None) -> Path:
    raw = str(value or "").strip()
    path = Path(raw).expanduser() if raw else OUTPUT_ROOT
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise RuntimeError(f"Output path is not a directory: {path}")
    return path


def output_root_from_body(body: dict[str, Any]) -> Path:
    return resolve_output_root(body.get("outputRoot"))


def register_output_dir(run_id: str, output_dir: Path) -> None:
    with TASK_LOCK:
        OUTPUT_DIRS[run_id] = str(output_dir.resolve())


def parse_data_url(data_url: str) -> tuple[str, bytes]:
    match = re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data_url, re.S)
    if not match:
        raise RuntimeError("Local file is not a valid data URL")
    content_type = match.group(1) or "application/octet-stream"
    is_base64 = bool(match.group(2))
    raw = match.group(3)
    if is_base64:
        data = base64.b64decode(raw, validate=False)
    else:
        data = unquote(raw).encode("utf-8")
    if len(data) > MAX_TOS_UPLOAD_BYTES:
        raise RuntimeError(f"File is too large for local TOS upload: {len(data)} bytes")
    return content_type, data


def local_task_ids(output_roots: list[Path] | None = None) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    roots = output_roots or [OUTPUT_ROOT]
    unique_roots: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in unique_roots:
            unique_roots.append(resolved)
    for root in unique_roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*/create_response.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            task_id = data.get("id") or data.get("task_id")
            if isinstance(task_id, str) and task_id and task_id not in seen:
                ids.append(task_id)
                seen.add(task_id)
    return ids


def http_json(
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}\n{detail}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError(
            f"火山接口在 {timeout} 秒内没有返回。"
            f"请求地址：{url}。"
            "可以把页面里的“接口请求超时”调大，或先用文生视频/公网图片 URL 做最小测试。"
        ) from exc
    except (URLError, ssl.SSLError) as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Response is not JSON:\n{raw[:1000]}") from exc


def extract_task_id(response: dict[str, Any]) -> str:
    task_id = response.get("id") or response.get("task_id")
    if not task_id:
        raise RuntimeError("Create response did not contain id/task_id")
    return str(task_id)


def get_status(data: dict[str, Any]) -> str:
    status = data.get("status")
    if isinstance(status, str):
        return status.lower()
    return "unknown"


def find_video_url(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in ("video_url", "file_url"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        value = data.get("url")
        if isinstance(value, str) and value.startswith(("http://", "https://")) and (
            ".mp4" in value.lower() or "tos" in value.lower()
        ):
            return value
        for value in data.values():
            found = find_video_url(value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_video_url(item)
            if found:
                return found
    return None


def send_json(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def send_text(handler: BaseHTTPRequestHandler, text: str, content_type: str = "text/html; charset=utf-8") -> None:
    raw = text.encode("utf-8")
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON body: {exc}") from exc


def create_task(body: dict[str, Any]) -> dict[str, Any]:
    output_dir: Path | None = None
    run_id = ""
    api_key = (body.get("apiKey") or "").strip() or load_server_api_key()
    if not api_key:
        raise RuntimeError("Missing API Key. Set ARK_API_KEY before starting the server, or enter it in the page.")

    base_url = normalize_base_url(body.get("baseUrl") or DEFAULT_BASE_URL)
    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError("Missing payload")
    if not payload.get("model"):
        raise RuntimeError("Missing model")
    if not payload.get("content"):
        raise RuntimeError("Missing content")
    request_timeout = int(body.get("requestTimeout") or DEFAULT_REQUEST_TIMEOUT)
    request_timeout = max(30, min(request_timeout, 1800))

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_root = output_root_from_body(body)
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    log_event(
        "task.create.start",
        run_id=run_id,
        output_dir=output_dir,
        base_url=base_url,
        model=payload.get("model"),
        request_timeout=request_timeout,
        content_count=len(payload.get("content") or []),
        payload=payload,
    )

    write_json(output_dir / "request_payload.json", payload)
    write_json(
        output_dir / "run_metadata.json",
        {
            "created_at": now_iso(),
            "base_url": base_url,
            "model": payload.get("model"),
            "output_root": str(output_root),
            "request_timeout": request_timeout,
            "request_payload_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
        },
    )

    try:
        response = http_json(
            "POST",
            f"{base_url}/contents/generations/tasks",
            api_key,
            payload,
            timeout=request_timeout,
        )
    except Exception as exc:
        log_event("task.create.error", run_id=run_id, output_dir=output_dir, error=str(exc))
        raise
    task_id = extract_task_id(response)
    write_json(output_dir / "create_response.json", response)
    log_event(
        "task.create.response",
        run_id=run_id,
        output_dir=output_dir,
        task_id=task_id,
        status=get_status(response),
        response=response,
    )

    task = {
        "run_id": run_id,
        "task_id": task_id,
        "api_key": api_key,
        "base_url": base_url,
        "request_timeout": request_timeout,
        "output_dir": str(output_dir),
        "created_at": time.time(),
        "latest": response,
        "video_url": find_video_url(response),
    }
    with TASK_LOCK:
        TASKS[run_id] = task
        OUTPUT_DIRS[run_id] = str(output_dir.resolve())

    return {
        "runId": run_id,
        "taskId": task_id,
        "status": get_status(response),
        "createResponse": response,
        "outputDir": str(output_dir),
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
        "taskLogPath": str(output_dir / "events.jsonl"),
        "videoUrl": task["video_url"],
    }


def poll_task(run_id: str) -> dict[str, Any]:
    with TASK_LOCK:
        task = TASKS.get(run_id)
    if not task:
        raise RuntimeError("Unknown run id. If the server restarted, create a new task from the page.")

    log_event("task.poll.start", run_id=run_id, output_dir=task["output_dir"], task_id=task["task_id"])
    response = http_json(
        "GET",
        f"{task['base_url']}/contents/generations/tasks/{task['task_id']}",
        task["api_key"],
        timeout=int(task.get("request_timeout") or DEFAULT_REQUEST_TIMEOUT),
    )
    status = get_status(response)
    video_url = find_video_url(response) or task.get("video_url")
    task["latest"] = response
    task["video_url"] = video_url
    write_json(Path(task["output_dir"]) / "latest_task_response.json", response)

    if status in TERMINAL_SUCCESS:
        write_json(Path(task["output_dir"]) / "final_task_response.json", response)
    if status in TERMINAL_FAILURE:
        write_json(Path(task["output_dir"]) / "failed_task_response.json", response)

    done = status in TERMINAL_SUCCESS or status in TERMINAL_FAILURE
    log_event(
        "task.poll.response",
        run_id=run_id,
        output_dir=task["output_dir"],
        task_id=task["task_id"],
        status=status,
        done=done,
        has_video_url=bool(video_url),
        usage=response.get("usage") if isinstance(response, dict) else None,
        response=response,
    )
    return {
        "runId": run_id,
        "taskId": task["task_id"],
        "status": status,
        "done": done,
        "task": response,
        "videoUrl": video_url,
        "outputDir": task["output_dir"],
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
        "taskLogPath": str(Path(task["output_dir"]) / "events.jsonl"),
    }


def download_task_video(run_id: str) -> dict[str, Any]:
    with TASK_LOCK:
        task = TASKS.get(run_id)
    if not task:
        raise RuntimeError("Unknown run id")

    video_url = task.get("video_url") or find_video_url(task.get("latest"))
    if not video_url:
        raise RuntimeError("No video URL found yet")

    parsed = urlparse(video_url)
    suffix = Path(unquote(parsed.path)).suffix or ".mp4"
    filename = safe_name(task["task_id"]) + suffix
    output_dir = Path(task["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / filename
    log_event("task.download.start", run_id=run_id, output_dir=output_dir, task_id=task["task_id"], target=str(target), video_url=video_url)
    request = Request(video_url, headers={"User-Agent": "volcengine-seedance-web-test/1.0"})
    with urlopen(request, timeout=180) as response:
        target.write_bytes(response.read())
    register_output_dir(run_id, output_dir)
    log_event("task.download.done", run_id=run_id, output_dir=output_dir, task_id=task["task_id"], file_path=str(target), bytes=target.stat().st_size)

    return {
        "filePath": str(target),
        "fileUrl": f"/outputs/{run_id}/{filename}",
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
        "taskLogPath": str(output_dir / "events.jsonl"),
    }


def download_video_to_dir(video_url: str, output_dir: Path, task_id: str) -> dict[str, str]:
    parsed = urlparse(video_url)
    suffix = Path(unquote(parsed.path)).suffix or ".mp4"
    filename = safe_name(task_id) + suffix
    target = output_dir / filename
    output_dir.mkdir(parents=True, exist_ok=True)
    log_event("manual.download.start", output_dir=output_dir, task_id=task_id, target=str(target), video_url=video_url)
    request = Request(video_url, headers={"User-Agent": "volcengine-seedance-web-test/1.0"})
    with urlopen(request, timeout=180) as response:
        target.write_bytes(response.read())
    register_output_dir(output_dir.name, output_dir)
    log_event("manual.download.done", output_dir=output_dir, task_id=task_id, file_path=str(target), bytes=target.stat().st_size)
    return {
        "filePath": str(target),
        "fileUrl": f"/outputs/{output_dir.name}/{filename}",
    }


def cancel_task(run_id: str) -> dict[str, Any]:
    with TASK_LOCK:
        task = TASKS.get(run_id)
    if not task:
        raise RuntimeError("Unknown run id")

    log_event("task.cancel.start", run_id=run_id, output_dir=task["output_dir"], task_id=task["task_id"])
    response = http_json(
        "DELETE",
        f"{task['base_url']}/contents/generations/tasks/{task['task_id']}",
        task["api_key"],
        timeout=int(task.get("request_timeout") or DEFAULT_REQUEST_TIMEOUT),
    )
    task["latest"] = response
    task["cancel_requested_at"] = time.time()
    write_json(Path(task["output_dir"]) / "cancel_response.json", response)
    log_event("task.cancel.response", run_id=run_id, output_dir=task["output_dir"], task_id=task["task_id"], response=response)
    return {
        "runId": run_id,
        "taskId": task["task_id"],
        "response": response,
        "outputDir": task["output_dir"],
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
        "taskLogPath": str(Path(task["output_dir"]) / "events.jsonl"),
    }


def cancel_task_by_id(body: dict[str, Any]) -> dict[str, Any]:
    api_key = (body.get("apiKey") or "").strip() or load_server_api_key()
    if not api_key:
        raise RuntimeError("Missing API Key. Set ARK_API_KEY before starting the server, or enter it in the page.")

    task_id = (body.get("taskId") or "").strip()
    if not task_id:
        raise RuntimeError("Missing task id")

    base_url = normalize_base_url(body.get("baseUrl") or DEFAULT_BASE_URL)
    request_timeout = int(body.get("requestTimeout") or DEFAULT_REQUEST_TIMEOUT)
    request_timeout = max(30, min(request_timeout, 1800))
    log_event("task.cancel_by_id.start", task_id=task_id, base_url=base_url)
    response = http_json(
        "DELETE",
        f"{base_url}/contents/generations/tasks/{task_id}",
        api_key,
        timeout=request_timeout,
    )
    log_event("task.cancel_by_id.response", task_id=task_id, response=response)
    return {
        "taskId": task_id,
        "response": response,
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
    }


def query_task_by_id(body: dict[str, Any]) -> dict[str, Any]:
    api_key = (body.get("apiKey") or "").strip() or load_server_api_key()
    if not api_key:
        raise RuntimeError("Missing API Key. Set ARK_API_KEY before starting the server, or enter it in the page.")

    task_id = (body.get("taskId") or "").strip()
    if not task_id:
        raise RuntimeError("Missing task id")

    base_url = normalize_base_url(body.get("baseUrl") or DEFAULT_BASE_URL)
    request_timeout = int(body.get("requestTimeout") or DEFAULT_REQUEST_TIMEOUT)
    request_timeout = max(30, min(request_timeout, 1800))
    log_event("task.query_by_id.start", task_id=task_id, base_url=base_url)
    response = http_json(
        "GET",
        f"{base_url}/contents/generations/tasks/{task_id}",
        api_key,
        timeout=request_timeout,
    )
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f_query")
    output_root = output_root_from_body(body)
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "run_metadata.json",
        {
            "created_at": now_iso(),
            "base_url": base_url,
            "task_id": task_id,
            "mode": "manual_query",
            "output_root": str(output_root),
            "request_timeout": request_timeout,
        },
    )
    write_json(output_dir / "latest_task_response.json", response)

    task = {
        "run_id": run_id,
        "task_id": task_id,
        "api_key": api_key,
        "base_url": base_url,
        "request_timeout": request_timeout,
        "output_dir": str(output_dir),
        "created_at": time.time(),
        "latest": response,
        "video_url": find_video_url(response),
    }
    with TASK_LOCK:
        TASKS[run_id] = task
        OUTPUT_DIRS[run_id] = str(output_dir.resolve())

    log_event(
        "task.query_by_id.response",
        run_id=run_id,
        output_dir=output_dir,
        task_id=task_id,
        status=get_status(response),
        has_video_url=bool(find_video_url(response)),
        response=response,
    )
    return {
        "runId": run_id,
        "taskId": task_id,
        "status": get_status(response),
        "task": response,
        "videoUrl": find_video_url(response),
        "outputDir": str(output_dir),
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
        "taskLogPath": str(output_dir / "events.jsonl"),
    }


def query_local_tasks(body: dict[str, Any]) -> dict[str, Any]:
    api_key = (body.get("apiKey") or "").strip() or load_server_api_key()
    if not api_key:
        raise RuntimeError("Missing API Key. Set ARK_API_KEY before starting the server, or enter it in the page.")

    base_url = normalize_base_url(body.get("baseUrl") or DEFAULT_BASE_URL)
    request_timeout = int(body.get("requestTimeout") or DEFAULT_REQUEST_TIMEOUT)
    request_timeout = max(30, min(request_timeout, 1800))
    should_download = bool(body.get("download"))
    output_root = output_root_from_body(body)
    scan_roots = [output_root]
    if output_root != OUTPUT_ROOT:
        scan_roots.append(OUTPUT_ROOT)
    results: list[dict[str, Any]] = []
    task_ids = local_task_ids(scan_roots)
    log_event("task.query_local.start", output_root=output_root, scan_roots=[str(root) for root in scan_roots], task_count=len(task_ids), download=should_download)

    for task_id in task_ids:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f_batch")
        output_dir = output_root / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        register_output_dir(run_id, output_dir)
        item: dict[str, Any] = {
            "taskId": task_id,
            "runId": run_id,
            "outputDir": str(output_dir),
        }
        try:
            response = http_json(
                "GET",
                f"{base_url}/contents/generations/tasks/{task_id}",
                api_key,
                timeout=request_timeout,
            )
            status = get_status(response)
            video_url = find_video_url(response)
            write_json(
                output_dir / "run_metadata.json",
                {
                    "created_at": now_iso(),
                    "base_url": base_url,
                    "task_id": task_id,
                    "mode": "batch_query",
                    "output_root": str(output_root),
                    "scan_roots": [str(root) for root in scan_roots],
                    "request_timeout": request_timeout,
                },
            )
            write_json(output_dir / "latest_task_response.json", response)
            item.update({"status": status, "task": response, "videoUrl": video_url})
            log_event("task.query_local.item", run_id=run_id, output_dir=output_dir, task_id=task_id, status=status, has_video_url=bool(video_url), response=response)
            if should_download and video_url:
                item.update(download_video_to_dir(video_url, output_dir, task_id))
        except Exception as exc:
            item["error"] = str(exc)
            log_event("task.query_local.item_error", run_id=run_id, output_dir=output_dir, task_id=task_id, error=str(exc))
        results.append(item)

    log_event("task.query_local.done", output_root=output_root, count=len(results), errors=sum(1 for item in results if item.get("error")))
    return {
        "checkedAt": now_iso(),
        "count": len(results),
        "outputRoot": str(output_root),
        "results": results,
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
    }


def list_tasks(body: dict[str, Any]) -> dict[str, Any]:
    api_key = (body.get("apiKey") or "").strip() or load_server_api_key()
    if not api_key:
        raise RuntimeError("Missing API Key. Set ARK_API_KEY before starting the server, or enter it in the page.")

    base_url = normalize_base_url(body.get("baseUrl") or DEFAULT_BASE_URL)
    request_timeout = int(body.get("requestTimeout") or DEFAULT_REQUEST_TIMEOUT)
    request_timeout = max(30, min(request_timeout, 1800))
    page_size = int(body.get("pageSize") or 10)
    page_size = max(1, min(page_size, 50))
    log_event("task.list.start", base_url=base_url, page_size=page_size)
    response = http_json(
        "GET",
        f"{base_url}/contents/generations/tasks?page_num=1&page_size={page_size}",
        api_key,
        timeout=request_timeout,
    )
    log_event("task.list.response", base_url=base_url, page_size=page_size, response=response)
    return {
        "response": response,
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
    }


def check_connection(body: dict[str, Any]) -> dict[str, Any]:
    api_key = (body.get("apiKey") or "").strip() or load_server_api_key()
    if not api_key:
        raise RuntimeError("Missing API Key. Set ARK_API_KEY before starting the server, or enter it in the page.")

    base_url = normalize_base_url(body.get("baseUrl") or DEFAULT_BASE_URL)
    request_timeout = int(body.get("requestTimeout") or DEFAULT_REQUEST_TIMEOUT)
    request_timeout = max(30, min(request_timeout, 1800))
    started = time.monotonic()
    log_event("connection.check.start", base_url=base_url)
    response = http_json(
        "GET",
        f"{base_url}/contents/generations/tasks?page_num=1&page_size=1",
        api_key,
        timeout=request_timeout,
    )
    elapsed_ms = round((time.monotonic() - started) * 1000)
    log_event("connection.check.response", base_url=base_url, elapsed_ms=elapsed_ms, response=response)
    return {
        "ok": True,
        "elapsedMs": elapsed_ms,
        "checkedAt": now_iso(),
        "baseUrl": base_url,
        "response": response,
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
    }


def tos_config_from_body(body: dict[str, Any]) -> dict[str, Any]:
    saved = saved_tos_config()
    access_key = (body.get("accessKey") or "").strip() or load_tos_access_key()
    secret_key = (body.get("secretKey") or "").strip() or load_tos_secret_key()
    security_token = (body.get("securityToken") or "").strip() or load_tos_security_token()
    bucket = (body.get("bucket") or "").strip() or os.getenv("TOS_BUCKET", "").strip() or config_value(saved, "bucket") or ""
    endpoint = (body.get("endpoint") or "").strip() or os.getenv("TOS_ENDPOINT", "").strip() or config_value(saved, "endpoint") or DEFAULT_TOS_ENDPOINT
    region = (body.get("region") or "").strip() or os.getenv("TOS_REGION", "").strip() or config_value(saved, "region") or DEFAULT_TOS_REGION
    prefix = safe_prefix((body.get("prefix") or "").strip() or config_value(saved, "prefix") or DEFAULT_TOS_PREFIX)
    expires = int(body.get("expires") or config_value(saved, "expires") or 86400)
    expires = max(600, min(expires, 7 * 24 * 3600))
    timeout = int(body.get("timeout") or config_value(saved, "timeout") or DEFAULT_TOS_TIMEOUT)
    timeout = max(60, min(timeout, 1800))

    if not access_key:
        raise RuntimeError("Missing TOS AccessKey. Fill it in the page or set TOS_ACCESS_KEY_ID.")
    if not secret_key:
        raise RuntimeError("Missing TOS SecretKey. Fill it in the page or set TOS_SECRET_ACCESS_KEY.")
    if not bucket:
        raise RuntimeError("Missing TOS Bucket.")

    return {
        "access_key": access_key,
        "secret_key": secret_key,
        "security_token": security_token,
        "bucket": bucket,
        "endpoint": endpoint,
        "region": region,
        "prefix": prefix,
        "expires": expires,
        "timeout": timeout,
    }


def load_tos_module():
    try:
        return importlib.import_module("tos")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "TOS SDK is not installed for the Python running this server. "
            "Start with .venv/bin/python volcengine_seedance_web.py."
        ) from exc


def make_tos_client(config: dict[str, Any]):
    tos = load_tos_module()
    return tos.TosClientV2(
        ak=config["access_key"],
        sk=config["secret_key"],
        endpoint=config["endpoint"],
        region=config["region"],
        security_token=config["security_token"] or None,
        max_retry_count=5,
        request_timeout=config["timeout"],
        connection_time=30,
        enable_crc=False,
        except100_continue_threshold=0,
        socket_timeout=config["timeout"],
    )


def check_tos(body: dict[str, Any]) -> dict[str, Any]:
    config = tos_config_from_body(body)
    log_event("tos.check.start", bucket=config["bucket"], endpoint=config["endpoint"], region=config["region"])
    client = make_tos_client(config)
    client.list_objects(config["bucket"], max_keys=1)
    log_event("tos.check.done", bucket=config["bucket"], endpoint=config["endpoint"], region=config["region"], timeout=config["timeout"])
    return {
        "ok": True,
        "bucket": config["bucket"],
        "endpoint": config["endpoint"],
        "region": config["region"],
        "timeout": config["timeout"],
    }


def tos_config_for_client(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "accessKey": config["access_key"],
        "secretKey": config["secret_key"],
        "securityToken": config["security_token"],
        "bucket": config["bucket"],
        "endpoint": config["endpoint"],
        "region": config["region"],
        "prefix": config["prefix"],
        "expires": config["expires"],
        "timeout": config["timeout"],
    }


def tos_config_for_browser(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "bucket": config.get("bucket") or "",
        "endpoint": config.get("endpoint") or DEFAULT_TOS_ENDPOINT,
        "region": config.get("region") or DEFAULT_TOS_REGION,
        "prefix": config.get("prefix") or DEFAULT_TOS_PREFIX,
        "expires": config.get("expires") or 86400,
        "timeout": config.get("timeout") or DEFAULT_TOS_TIMEOUT,
        "hasAccessKey": bool(config.get("accessKey") or config.get("access_key")),
        "hasSecretKey": bool(config.get("secretKey") or config.get("secret_key")),
        "hasSecurityToken": bool(config.get("securityToken") or config.get("security_token")),
    }


def save_tos_config(body: dict[str, Any]) -> dict[str, Any]:
    config = tos_config_from_body(body)
    local_config = load_local_config()
    local_config["tos"] = tos_config_for_client(config)
    write_json(CONFIG_PATH, local_config)
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass
    log_event("tos.config.saved", config_path=str(CONFIG_PATH), bucket=config["bucket"], endpoint=config["endpoint"], region=config["region"], prefix=config["prefix"], timeout=config["timeout"])
    return {
        "ok": True,
        "configPath": str(CONFIG_PATH),
        "tos": tos_config_for_browser(local_config["tos"]),
        "hasTosKey": True,
    }


def upload_to_tos(body: dict[str, Any]) -> dict[str, Any]:
    config = tos_config_from_body(body)
    data_url = body.get("dataUrl")
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        raise RuntimeError("Missing local file data URL")

    content_type, data = parse_data_url(data_url)
    content_type = (body.get("contentType") or "").strip() or content_type
    filename = safe_name((body.get("filename") or "").strip() or "upload")
    suffix = Path(filename).suffix
    if not suffix:
        guessed = mimetypes.guess_extension(content_type)
        suffix = guessed or ".bin"
        filename = filename + suffix

    digest = hashlib.sha256(data).hexdigest()[:16]
    today = datetime.now().strftime("%Y%m%d")
    key = f"{config['prefix']}/{today}/{uuid.uuid4().hex}_{digest}_{filename}"

    log_event("tos.upload.start", bucket=config["bucket"], key=key, filename=filename, content_type=content_type, bytes=len(data), timeout=config["timeout"])
    client = make_tos_client(config)
    client.put_object(
        bucket=config["bucket"],
        key=key,
        content=io.BytesIO(data),
        content_length=len(data),
        content_type=content_type,
    )

    tos = load_tos_module()
    signed = client.pre_signed_url(
        tos.HttpMethodType.Http_Method_Get,
        config["bucket"],
        key,
        expires=config["expires"],
    )
    log_event("tos.upload.done", bucket=config["bucket"], key=key, content_type=content_type, bytes=len(data), expires=config["expires"], url=signed.signed_url)
    return {
        "url": signed.signed_url,
        "key": key,
        "bucket": config["bucket"],
        "contentType": content_type,
        "size": len(data),
        "expires": config["expires"],
        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "SeedanceWebTester/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{now_iso()}] {self.address_string()} {format % args}")

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path.startswith("/api/"):
                log_event("http.request", method="GET", path=path, client=self.address_string())
            if path == "/":
                send_text(self, HTML)
                return
            if path == "/api/config":
                saved_tos = saved_tos_config()
                effective_tos = {
                    "accessKey": "",
                    "secretKey": "",
                    "securityToken": "",
                    "bucket": os.getenv("TOS_BUCKET", "").strip() or config_value(saved_tos, "bucket") or "",
                    "endpoint": os.getenv("TOS_ENDPOINT", "").strip() or config_value(saved_tos, "endpoint") or DEFAULT_TOS_ENDPOINT,
                    "region": os.getenv("TOS_REGION", "").strip() or config_value(saved_tos, "region") or DEFAULT_TOS_REGION,
                    "prefix": config_value(saved_tos, "prefix") or DEFAULT_TOS_PREFIX,
                    "expires": config_value(saved_tos, "expires") or 86400,
                    "timeout": config_value(saved_tos, "timeout") or DEFAULT_TOS_TIMEOUT,
                    "hasAccessKey": bool(load_tos_access_key()),
                    "hasSecretKey": bool(load_tos_secret_key()),
                    "hasSecurityToken": bool(load_tos_security_token()),
                }
                send_json(
                    self,
                    {
                        "hasServerKey": bool(load_server_api_key()),
                        "hasTosKey": bool(load_tos_access_key() and load_tos_secret_key()),
                        "tosLocked": bool(saved_tos or (load_tos_access_key() and load_tos_secret_key())),
                        "tos": effective_tos,
                        "tosBucket": effective_tos["bucket"],
                        "tosEndpoint": effective_tos["endpoint"],
                        "tosRegion": effective_tos["region"],
                        "tosPrefix": effective_tos["prefix"],
                        "tosTimeout": effective_tos["timeout"],
                        "outputRoot": str(OUTPUT_ROOT),
                        "logPath": str(LOG_DIR / "seedance_web_events.jsonl"),
                    },
                )
                return
            if path.startswith("/api/tasks/"):
                run_id = path.rsplit("/", 1)[-1]
                send_json(self, poll_task(run_id))
                return
            if path.startswith("/outputs/"):
                self.serve_output(path)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            log_event("http.error", method="GET", path=self.path, error=str(exc))
            send_json(self, {"error": str(exc)}, status=500)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path.startswith("/api/"):
                log_event("http.request", method="POST", path=path, client=self.address_string())
            if path == "/api/tasks":
                send_json(self, create_task(read_json_body(self)))
                return
            if path == "/api/tos/check":
                send_json(self, check_tos(read_json_body(self)))
                return
            if path == "/api/tos/save":
                send_json(self, save_tos_config(read_json_body(self)))
                return
            if path == "/api/tos/upload":
                send_json(self, upload_to_tos(read_json_body(self)))
                return
            if path == "/api/check-connection":
                send_json(self, check_connection(read_json_body(self)))
                return
            if path == "/api/query-task":
                send_json(self, query_task_by_id(read_json_body(self)))
                return
            if path == "/api/query-local-tasks":
                send_json(self, query_local_tasks(read_json_body(self)))
                return
            if path == "/api/list-tasks":
                send_json(self, list_tasks(read_json_body(self)))
                return
            if path == "/api/cancel-task":
                send_json(self, cancel_task_by_id(read_json_body(self)))
                return
            if path.startswith("/api/tasks/") and path.endswith("/cancel"):
                run_id = path.split("/")[3]
                send_json(self, cancel_task(run_id))
                return
            if path.startswith("/api/tasks/") and path.endswith("/download"):
                run_id = path.split("/")[3]
                send_json(self, download_task_video(run_id))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            log_event("http.error", method="POST", path=self.path, error=str(exc))
            send_json(self, {"error": str(exc)}, status=500)

    def serve_output(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) < 4:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        run_id = safe_name(parts[2])
        filename = safe_name(parts[3])
        with TASK_LOCK:
            output_dir = OUTPUT_DIRS.get(run_id)
            task = TASKS.get(run_id)
            if not output_dir and task:
                output_dir = task.get("output_dir")
        base_dir = Path(output_dir).resolve() if output_dir else (OUTPUT_ROOT / run_id).resolve()
        target = (base_dir / filename).resolve()
        try:
            target.relative_to(base_dir)
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    server = None
    selected_port = PORT
    for candidate_port in range(PORT, PORT + PORT_SEARCH_LIMIT):
        try:
            server = ThreadingHTTPServer((HOST, candidate_port), Handler)
            selected_port = candidate_port
            break
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
    if server is None:
        raise RuntimeError(f"No available port from {PORT} to {PORT + PORT_SEARCH_LIMIT - 1}")

    print(f"兔狲视频生成器: http://{HOST}:{selected_port}")
    print(f"Output directory: {OUTPUT_ROOT}")
    print(f"Log file: {LOG_DIR / 'seedance_web_events.jsonl'}")
    if load_server_api_key():
        print("API key: loaded from environment")
    else:
        print("API key: not set in environment; enter it in the web page")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
