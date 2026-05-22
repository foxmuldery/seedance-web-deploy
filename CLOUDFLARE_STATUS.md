# Cloudflare 发布状态

发布时间：2026-05-22

## 已完成

- GitHub 私有仓库：`https://github.com/foxmuldery/seedance-web-deploy`
- Cloudflare Pages 项目：`seedance-web-deploy`
- Cloudflare Pages 正式域名：`https://seedance-web-deploy.pages.dev/`
- 本次部署地址：`https://8526a094.seedance-web-deploy.pages.dev/`
- 后端正式 Tunnel 目标域名：`https://video.bianjuziyuan.com/`
- Cloudflare Tunnel：`seedance-web` / `f99dc628-6b74-4134-91d6-11c6934d65bd`

## 当前形态

当前 Cloudflare Pages 发布的是安全入口页，代码在 `public/index.html`。

这个入口页不包含火山方舟 API Key、TOS AK/SK，也不会在前端执行视频生成。视频生成后端仍需要运行在服务器上，再通过 Cloudflare Tunnel、反向代理或后续 Workers 改造接入。

## 后续接入后端

推荐顺序：

1. 在服务器运行 Docker 版后端。
2. 用 Cloudflare Tunnel 绑定 `video.bianjuziyuan.com`。
3. 用 Cloudflare Access 做同事登录权限。
4. 确认权限和日志后，再把入口页改成真实生成器地址。

## DNS 记录

在 `bianjuziyuan.com` 的 DNS 中添加：

- Type: `CNAME`
- Name: `video`
- Target: `f99dc628-6b74-4134-91d6-11c6934d65bd.cfargotunnel.com`
- Proxy status: Proxied
- TTL: Auto

## GitHub 自动部署说明

当前项目由 Wrangler 直接上传到 Cloudflare Pages。Cloudflare 后台显示 `Git Provider: No`。

如果需要 Cloudflare 每次监听 GitHub `main` 分支自动构建，需要在 Cloudflare Dashboard 里新建或重新绑定 Pages 项目：

- Framework preset: `None`
- Build command: 留空
- Build output directory: `public`
- Production branch: `main`
