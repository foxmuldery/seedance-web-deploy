# 火山 Seedance 本地测试说明

本说明配套脚本：

- `volcengine_seedance_test.py`
- `volcengine_seedance_web.py`

脚本用于快速测试火山方舟 Seedance 视频生成 API。命令行脚本会把结果保存到 `seedance_test_outputs/`，网页测试台默认把结果保存到桌面的 `seedance_web_outputs/`。

## 0. 启动网页测试台

推荐先把 API Key 设置到环境变量里，再启动网页：

```bash
cd /Users/tusun/Documents/互动影游
export ARK_API_KEY="你的火山方舟 API Key"
.venv/bin/python volcengine_seedance_web.py
```

启动后打开终端里显示的地址，通常是：

```text
http://127.0.0.1:8765
```

如果 8765 被占用，脚本会自动换到后面的空闲端口，比如 8766、8767。

网页里可以选择：

- 连线检测：只查询最近 1 条任务，不创建视频任务，用于快速验证 API Key 和网络
- 费用中心：跳转火山控制台查看账户余额、充值、账单
- TOS 外链上传：选择本地图片后，先上传到火山 TOS，再生成临时签名 HTTPS URL 给 Seedance 图生视频使用
- 文生视频
- 图生视频
- 视频生视频
- 混合参考
- Seedance 2.0 Fast / Seedance 2.0 标准 / 自定义模型 ID
- 时长、比例、分辨率
- 水印、生成音频、返回尾帧
- seed、轮询间隔、超时时间
- 接口请求超时，默认 300 秒；如果出现 read operation timed out，可以先调到 600 秒
- 本地输出根目录：默认 `/Users/tusun/Desktop/seedance_web_outputs`，可以在页面里改成其他本地目录
- 本地图片/视频/音频文件，或公开 URL
- 终止任务：会先停止本地轮询，再调用火山任务取消/删除接口
- 手动终止：如果你已有 `task_id`，也可以粘到“任务 ID”框后终止
- 查询任务：粘贴已有 `task_id` 后可以单次查询状态
- 查询并下载：粘贴已有 `task_id` 后查询状态；如果已成功并返回 `video_url`，会直接下载到本地
- 查询本地全部任务：读取当前“本地输出根目录”以及默认输出目录里的 `create_response.json`，逐个查询状态，成功的视频会自动下载
- 最近任务：创建请求返回中断时，先查最近任务，避免重复创建导致重复计费
- 轮询重试：如果查询任务状态时遇到 SSL EOF、Network error、timeout，会自动重试最多 8 次
- 生成音频：默认显式传 `generate_audio:false`；只有勾选时才传 `true`
- 错误说明：创建、轮询、查询、TOS 检测失败时，会在右侧解释常见原因和下一步
- 费用估算：成功后优先按火山返回的 `usage.total_tokens` 计算；如果没有 usage，则按页面里的“兜底元/秒”估算，最终以火山账单为准

如果没有设置环境变量，也可以在网页的 API Key 输入框临时填写。Key 只会发给本地代理服务，不会写入输出日志。

费用估算区默认单价：

- 生成单价：46 元/百万 token，适用于文生视频、图生视频等不含视频输入/参考的请求
- 视频输入单价：28 元/百万 token，适用于视频生视频或混合参考里包含视频输入的请求
- 兜底元/秒：1 元/秒，仅在接口没有返回 usage 时使用

这些值可以直接在页面里改。火山最终扣费以费用中心账单为准。

注意：账户余额查询属于火山引擎费用中心 OpenAPI，例如 `QueryBalanceAcct`，通常需要火山云账号的 AccessKey/SecretKey 签名鉴权；它和火山方舟 `ARK_API_KEY` 不是同一套 Bearer Key。当前网页先提供费用中心入口和 Ark 连线检测。

图生视频模式会自动给首帧图片加 `role: first_frame`。混合参考模式会按输入类型加 `reference_image`、`reference_video`、`reference_audio` 等角色。

## 0.2 配置 TOS 外链上传

先在火山 TOS 创建一个 bucket，建议使用北京区域。bucket 可以保持私有，因为网页会生成带签名的临时访问 URL。

启动前可以把 TOS 配置放到环境变量里：

```bash
export TOS_ACCESS_KEY_ID="你的火山 AccessKey"
export TOS_SECRET_ACCESS_KEY="你的火山 SecretKey"
export TOS_BUCKET="你的 bucket 名"
export TOS_REGION="cn-beijing"
export TOS_ENDPOINT="https://tos-cn-beijing.volces.com"
export TOS_PREFIX="seedance-inputs"
export TOS_REQUEST_TIMEOUT="300"
```

也可以不设环境变量，直接在网页的 TOS 配置区填写。

如果上传本地图片时报 `HTTPSConnectionPool(...tos-cn-beijing...) Read timed out` 或 `SSLEOFError`，说明图片还没稳定传到 TOS，或 Seedance 读取这张 TOS 图片时链路中断。优先保持“上传前压缩图片”开启，默认会压到最长边 1920、JPEG 质量 0.88；仍失败时把“TOS 上传超时”调到 600 秒，并尽量让压缩后的图片控制在 5 MB 以内。

图生视频步骤：

1. 勾选“本地图片自动上传 TOS 外链”。
2. 填 TOS Bucket、Region、Endpoint、AK/SK。
3. 点“检测 TOS 配置”。
4. 点“保存并锁定配置”。以后打开网页会自动带出并锁定 TOS 信息，不用每次重复输入；需要修改时点“解锁修改”。
5. 切到“图生视频”。
6. 选择本地图片文件。
7. 点“预览请求”或“创建任务”。网页会先上传图片，生成外链，再提交 Seedance。

保存后的 TOS 配置会写入本地 `.seedance_web_config.json`。这是本机测试工具的本地配置文件，里面包含 TOS AK/SK，请不要发给别人。

## 0.3 使用 Seedance 真人肖像授权素材

真人肖像不要直接用本地图片上传 TOS 外链提交，否则很容易触发 `InputImageSensitiveContentDetected.PrivacyInformation`。

正确链路是：

1. 在火山方舟的 Seedance 真人形象/真人人像库里接收或录入已授权素材。
2. 在素材详情里复制 `Asset ID`，格式通常是 `asset-...` 或 `asset_...`。
3. 回到本地网页，在“Seedance 真人肖像授权”里填这个 `Asset ID`。网页会自动补成 `asset://...`。如果需要多个人，点“+ 添加真人”继续增加。
4. 点“预览请求”确认 JSON 里出现：

```json
{
  "type": "image_url",
  "image_url": {
    "url": "asset://asset-..."
  },
  "role": "reference_image"
}
```

这条链路不走 TOS 外链，也不需要把真人原图传给本地上传区。真人授权是否可用仍取决于火山账号侧是否已开通对应素材权限。

终止任务使用火山视频生成 API 的任务删除接口：

```text
DELETE /api/v3/contents/generations/tasks/{task_id}
```

队列中的任务会尝试取消；已经成功、失败或过期的任务通常会从历史记录中删除。是否已经产生费用，以火山侧最终计费记录为准。

## 0.1 网页输出文件

每次网页创建任务会生成类似目录：

```text
/Users/tusun/Desktop/seedance_web_outputs/20260522_153000_123456/
```

也可以在页面里的“本地输出根目录”改成其他目录；如果启动前设置 `SEEDANCE_OUTPUT_ROOT`，网页默认值会跟随这个环境变量。

里面包括：

- `request_payload.json`
- `create_response.json`
- `latest_task_response.json`
- `final_task_response.json`
- 下载后的视频文件
- `run_metadata.json`

## 1. 准备 API Key

在火山方舟控制台创建 API Key，然后在终端设置：

```bash
export ARK_API_KEY="你的火山方舟 API Key"
```

也支持这些变量名：

```bash
export VOLCENGINE_API_KEY="你的火山方舟 API Key"
export SEEDANCE_API_KEY="你的火山方舟 API Key"
```

## 2. 最低成本文生视频测试

默认使用 `doubao-seedance-2-0-fast-260128`、5 秒、720p、16:9、无水印。

```bash
python3 volcengine_seedance_test.py
```

自定义提示词：

```bash
python3 volcengine_seedance_test.py \
  --prompt "写实电影风格，雨夜的老街巷口，一盏路灯闪烁，镜头缓慢推进，空气中有薄雾"
```

## 3. 使用标准版 Seedance 2.0

```bash
python3 volcengine_seedance_test.py \
  --model doubao-seedance-2-0-260128 \
  --prompt "写实电影风格，清晨的县城街道，路边早点摊冒着热气，镜头缓慢横移"
```

## 4. 图生视频测试

图片可以是公开 URL，也可以是本地文件路径。本地文件会被转为 base64 data URL。

```bash
python3 volcengine_seedance_test.py \
  --image-url "/Users/tusun/Desktop/test.png" \
  --prompt "让画面中的街道出现轻微风吹动，镜头缓慢推进，保持写实风格"
```

公开图片 URL：

```bash
python3 volcengine_seedance_test.py \
  --image-url "https://example.com/frame.png" \
  --prompt "镜头轻微推进，人物保持自然动作，电影感写实光线"
```

## 5. 视频参考/视频输入测试

如果你的账号权限支持视频输入，可以这样测：

```bash
python3 volcengine_seedance_test.py \
  --video-url "/Users/tusun/Desktop/reference.mp4" \
  --prompt "参考输入视频的镜头运动和构图，生成一个更写实的雨夜街巷镜头"
```

## 6. 轮询已有任务

如果已经拿到了任务 ID：

```bash
python3 volcengine_seedance_test.py --task-id "cgt-xxxx"
```

## 7. 常用参数

```bash
--duration 5              # 视频秒数
--ratio 16:9              # 画幅比例，如 16:9、9:16、1:1、adaptive
--resolution 720p         # 分辨率，如 720p、1080p
--generate-audio          # 尝试生成音频，可能增加成本/权限要求
--watermark               # 添加水印
--no-watermark            # 不添加水印，默认就是不添加
--interval 10             # 每 10 秒查询一次任务状态
--timeout 1800            # 最长等待 1800 秒
--no-download             # 只保存 video_url，不下载视频
```

## 8. 输出文件

每次运行会生成类似目录：

```text
seedance_test_outputs/20260522_153000/
```

里面包括：

- `request_payload.json`：提交给 API 的请求参数
- `create_response.json`：创建任务返回
- `latest_task_response.json`：最近一次查询返回
- `final_task_response.json`：最终查询返回
- `video_url.txt`：生成视频链接
- `任务ID.mp4`：下载后的视频文件
- `run_metadata.json`：本次运行元信息

## 9. 判断测试结果

重点记录：

- 创建任务是否成功
- 是否出现 `queued`、`running`、`succeeded`、`failed` 等状态
- 从提交到完成耗时
- `usage` 里的 token/计费信息
- 是否有审核拦截或权限不足错误
- 生成视频是否成功下载

如果返回权限错误，优先检查：

1. API Key 是否来自火山方舟，而不是其他火山云服务。
2. Seedance 2.0 模型是否已开通。
3. 账户余额是否满足模型开通/调用要求。
4. 当前账号是否支持视频输入、音频生成、1080p 等高阶能力。
