# SSH Control 安全注意事项

## 秘密与本地服务

- 私钥内容、密码、passphrase、令牌不得写入连接索引、命令参数、日志或聊天。
  连接索引可引用本机 key_path；仓库只保留示例连接，不发布本机索引或 keys/。
- 服务只监听 localhost，HTTP API 与 `/mcp` 都要求 `Authorization: Bearer` 令牌。
  令牌在 skill 目录的 `.env`（`SSH_CONTROL_TOKEN=...`，文件 600）：服务、
  `ssh_client.py` 或 Codex 的 `http_headers_helper`（`scripts/ssh_token.py headers`）
  谁先用到谁创建，之后都读同一文件。服务每个请求都重新读取，删除 `.env` 即轮换，
  无需重启。不要打印、粘贴或把令牌写进命令参数/日志/config.toml。同一 macOS 用户
  的进程仍可读取该文件（与读取私钥同级），它防的是浏览器与其他用户。
- MCP 工具与 HTTP API 走同一个 registry：同样的危险命令拦截、host key 校验与会话。
  MCP 的 `ssh_exec sudo` 只用 `sudo -n`；带密码的 sudo 只能走 CLI
  `--sudo-password-env`，密码不进入 MCP 参数。
- 拒绝非本地 `Host`（防 DNS rebinding）、带 `Origin` 的请求（浏览器跨站）以及非
  `application/json` 的 POST（防表单/简单请求 CSRF）。不要向不可信网络开放。
- 主机密钥与原生 ssh 共用 known_hosts（默认 ~/.ssh/known_hosts，或 ssh config 的
  UserKnownHostsFile）。未知主机按 OpenSSH `accept-new` 首次记录；密钥变化一律
  拒绝（`host_key_mismatch`）。ssh config 设 `StrictHostKeyChecking yes` 时未知主机
  也拒绝。遇到 mismatch 不得自行删改 known_hosts，应交给用户核实服务器后处理。
- 远端 detached 任务目录 `~/.codex-ssh-jobs/<id>/` 权限 700，内含命令脚本、stdin
  与输出原文；不要让命令把秘密写进 stdout/stderr，也不要把秘密放进 stdin 以外
  的命令文本。sudo 密码不会进入 detached 任务（带密码的 sudo 只走 attached）。
- 统一客户端从 `--sudo-password-env NAME` 指定的本地环境变量读取密码，只通过
  HTTP 请求内存与 SSH channel 的认证输入发送。服务不记录请求体、不回显异常
  细节，并在输出保存前遮蔽所提供密码（含跨读取边界的匹配）。这不是通用
  敏感数据过滤器：不要让业务命令输出其他秘密，不要开启网络请求体抓包/调试日志。
- Python 字符串无法保证内存擦除；密码不会被设计为持久化状态，使用后释放引用。

## sudo 输入协议

sudo 在现有 SSH Transport 的独立 channel 执行，不占用持久 shell、不保留 root
shell。不提供密码时使用 `sudo -n`，返回结构化 `sudo_password_required`。
提供密码时使用唯一认证提示，只在收到提示后发送一次密码；特权包装命令发出
另一个唯一就绪标记后，才发送业务 stdin 并关闭写端。NOPASSWD/缓存命中时不
发送密码。脚本正文经过 shell quoting 放在命令参数中，不与认证或业务 stdin
拼接。错误密码不重试业务命令；sudo 认证失败、连接异常或未知结果都不自动重放。
不请求 PTY，要求 TTY 或交互认证的策略需要单独处理，不修改 sudoers 绕过。

`cwd` 与 `env` 在独立命令内显式设置，不假定继承持久 shell 状态。env 名称按
POSIX 变量名验证，值与路径按 shell 参数引用。此接口本来就允许执行 shell 代码；
不要将不可信文本直接插入 cmd。

## 授权与共享服务

危险操作需用户明确授权：广泛删除、重启/关机、磁盘格式化/覆盖、修改账号或
sudoers 文件、停止关键服务、生产数据库写入等。服务的危险模式匹配只是辅助，
不替代授权。已有明确授权时按授权范围执行，不额外扩大范围。

不要为了查询失败、加载代码或连接别名重启共享服务。别名变化用 reload；需要
用户组等新登录状态用 force_new。代码更新后先确认其他任务与会话的安全切换时机。
删除 session 会关闭其 Transport 与其上的 attached 任务；detached 任务在远端继续运行，可用 jobs cancel 或原生 `codex-job cancel` 停止。HTTP wait 结束不取消任务；运行时
exit_code 为 null。断连为 unknown，先核实远端状态，不自动重跑安装。
服务重启后 detached 任务可继续查询（restored），attached 任务丢失。日志有限且可能截断，关键业务审计应由
获得授权的远端程序负责，不能依赖此服务作为永久日志库。
