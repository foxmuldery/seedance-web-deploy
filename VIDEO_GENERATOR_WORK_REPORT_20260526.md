# 兔狲视频生成器工作报告

日期：2026-05-26

工具：兔狲视频生成器（Seedance）

仓库：seedance-web-deploy

## 本次范围

本次只处理 Seedance 视频生成器，不调整统一管理台结构，不修改其他工具文件。重点完成两项工作：接入统一用量主账本的补充说明与实现整理，以及新增“项目预设”能力，方便同一个项目内统一画幅比、模型、时长、分辨率和共享提示词。

## 已完成

1. 统一用量上报
   - 服务端读取环境变量：`TSUN_USAGE_ENDPOINT`、`TSUN_USAGE_INGEST_TOKEN`、`TSUN_APP_ID`、`TSUN_APP_LABEL`、`TSUN_USAGE_PROVIDER`。
   - 生成任务记录 `video_generation`。
   - 状态查询记录 `video_status`。
   - 下载成功记录 `video_download`，并包含 `responseBytes`。
   - 上报内容不包含真实 API Key、请求头、签名下载地址或浏览器临时密钥。

2. 项目预设
   - 新增内置预设：横版预览、竖版短视频、纪录片空镜、图生视频统一风格。
   - 每个预设可统一设置模式、画幅比、分辨率、时长、模型和共享提示词。
   - 应用预设后，所有字段仍可手动修改。
   - 支持保存和删除自定义预设。
   - 自定义预设仅保存非敏感项目参数到浏览器本地存储，不保存 API Key。

3. 文档补充
   - `.env.seedance-web.example` 增加统一用量上报环境变量示例。
   - `README.md` 补充部署侧环境变量与上报说明。

## 验证记录

1. Python 编译检查通过：
   - `python3 -m py_compile volcengine_seedance_web.py`

2. 前端脚本语法检查通过：
   - 已抽取页面内联脚本并执行 `node --check`

3. 本地页面结构检查通过：
   - 本地端口：8768
   - 已确认页面包含“项目预设”、预设选择、共享提示词、自定义预设保存/删除逻辑。
   - 本次 2026-05-26 验证未发起真实 Ark 生成任务。

4. 真实成功路径回归记录：
   - 测试时间：2026-05-24 14:04:02-14:14:47 Asia/Shanghai
   - appId：`video_generator`
   - provider：`seedance`
   - 模型：`doubao-seedance-2-0-fast-260128`
   - 视频时长：5 秒
   - 主账本记录齐全：`video_generation`、`video_status`、`video_download`
   - 下载记录包含 `responseBytes`
   - 验证材料不包含 `ARK_API_KEY`、真实请求头或签名下载地址。

## 安全说明

生产环境长期 Key 只应保存在服务端环境变量，例如 `ARK_API_KEY`。页面端不应依赖用户临时输入长期 API Key，也不应把 Key 写入代码、文档、截图或日志摘要。

## 后续建议

1. 在生产入口隐藏或移除浏览器临时 API Key 输入，只保留服务端环境变量模式。
2. 将用户名优先绑定到 Cloudflare Access 邮箱，减少手工输入。
3. 给状态轮询增加更细的节流与展示，避免主账本被频繁刷新记录刷屏。
4. 为项目预设增加导入/导出 JSON，方便同事之间复用同一套项目风格配置。

## 安全验收补充

时间：2026-05-26

1. 已隐藏生产环境 API Key 输入：线上默认不展示浏览器 Key 输入框。
2. 已禁止线上请求体传 `apiKey`：后端检测到生产环境请求体包含 `apiKey` 字段时直接拒绝。
3. 已改为服务端优先读取 `ARK_API_KEY`：生产环境长期 Key 不依赖浏览器输入。
4. 已接入 Cloudflare Access 用户名优先级：优先读取 Access 邮箱，其次使用 Basic Auth 用户名。
5. 已增加状态入账节流：`video_status` 仅在状态变化或达到 `TSUN_STATUS_REPORT_MIN_SECONDS` 间隔时写入主账本。

安全回归验证：

- 模拟线上 Host：`video.bianjuziyuan.com`
- `/api/config` 返回 `allowBrowserApiKey=false`
- 线上请求体包含 `apiKey` 时，后端拒绝请求
- Cloudflare Access 邮箱头可进入 `authUser`
- 不使用真实 `ARK_API_KEY`，不发起真实 Ark 生成任务
