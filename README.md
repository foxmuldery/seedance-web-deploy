# 兔狲视频生成器

火山方舟 Seedance 2.0 的内部测试网页，支持文生视频、图生视频、视频生视频、真人肖像 Asset 授权、TOS 外链上传、任务轮询、下载、费用估算和详细日志。

## 本地运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-seedance-web.txt
SEEDANCE_WEB_PORT=8767 .venv/bin/python volcengine_seedance_web.py
```

打开：

```text
http://127.0.0.1:8767/
```

## Docker 部署

```bash
cp .env.seedance-web.example .env.seedance-web
# 编辑 .env.seedance-web，填入方舟和 TOS 密钥
docker compose -f docker-compose.seedance-web.yml up -d --build
```

默认访问：

```text
http://服务器IP:8080/
```

## Cloudflare 建议

当前版本是带后端的 Python 工具，推荐先部署到服务器，再用 Cloudflare Tunnel / Access 暴露域名和权限控制。

不建议把密钥写入前端，也不要把 `.env.seedance-web`、`.seedance_web_config.json`、输出视频、日志文件提交到 GitHub。

## 访问密码

在 `.env.seedance-web` 中设置：

```bash
SEEDANCE_WEB_USERNAME=tusun
SEEDANCE_WEB_ALLOW_ANY_USERNAME=1
SEEDANCE_WEB_PASSWORD=你的访问密码
```

设置后，网页和所有 API 都会要求浏览器输入用户名和密码。`SEEDANCE_WEB_ALLOW_ANY_USERNAME=1` 表示用户名可以让同事自己填写，后端只校验共享密码，并把用户名写入日志用于统计。

如果需要恢复固定用户名校验，设置：

```bash
SEEDANCE_WEB_ALLOW_ANY_USERNAME=0
```

不要把 `.env.seedance-web` 提交到 GitHub。

## 统一用量上报

视频生成器会把 Seedance 任务提交、状态查询和下载写入兔狲后期助手统一账本：

```bash
TSUN_USAGE_ENDPOINT=https://voice.bianjuziyuan.com/api/usage/events
TSUN_USAGE_INGEST_TOKEN=统一上报Token
TSUN_APP_ID=video_generator
TSUN_USAGE_PROVIDER=seedance
```

`TSUN_USAGE_INGEST_TOKEN` 未配置时不会阻断生成流程；本地调试可把 `TSUN_USAGE_ENDPOINT` 指到 `http://127.0.0.1:5183/api/usage/events`。
