# SSH Skill 安全注意事项

## 私钥处理原则

1. **不要记录私钥内容**：不在日志、stdout、对话中展示私钥内容
2. **临时文件**：如果必须写磁盘，用 `tempfile.NamedTemporaryFile`，权限设为 0o600，用完立即 `os.unlink()`
3. **内存加载**：优先使用 `paramiko.RSAKey.from_private_key(io.StringIO(...))` 避免落盘
4. **会话结束告知用户**：提醒用户这次会话的连接信息不会被保存

## 主机验证

- 默认使用 `AutoAddPolicy`（首次连接自动信任）
- 生产环境建议：让用户提供已知的 host fingerprint，用 `RejectPolicy` + 手动 known_hosts

## 命令注入防护

- 不要把用户输入直接拼接进 shell 命令
- 敏感参数用引号包裹：`f"ls '{user_path}'"` → 但更好的做法是白名单验证路径

## 需要二次确认的操作

| 操作 | 原因 |
|------|------|
| `rm -rf` | 不可恢复删除 |
| `reboot/shutdown` | 服务中断 |
| `dd if=... of=/dev/...` | 磁盘覆盖 |
| `DROP/TRUNCATE TABLE` | 数据丢失 |
| `iptables -F` | 防火墙清空 |
| `chmod -R 777` | 权限漏洞 |
| `kill -9 1` (PID 1) | 系统崩溃 |

## sudo 配置建议（给用户）

推荐的最小权限 sudoers 配置（仅允许特定服务操作）：

```
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart myapp, /bin/systemctl status myapp
```

避免：`deploy ALL=(ALL) NOPASSWD: ALL`
