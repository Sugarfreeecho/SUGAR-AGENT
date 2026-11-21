# vendored: @dsh-wechat/core

- 来源：`dsh-wechat` 仓库 `packages/core`（commit `e0e8cb3`，Release 0.46.0，2026-10-20）
- 复制内容：`src/`、`package.json`、`tsconfig.json`（未带 `tests/`）
- 为什么复制：避免运行时依赖另一个仓库的磁盘路径；钉住版本，升级时整目录替换
- 为什么只 import `src/channel.ts`：`src/index.ts` 会连带 `render.ts` → `qrcode` 依赖，
  而本插件不渲染二维码（登录由 dsh-wechat 自己完成），只需要 `ChannelMonitor` 与 `sendText`
- 许可：沿用上游仓库的许可，未做修改；升级方式见 `README.md` 的「微信通道」
