# Claude Code MCP 配置指南

## 📋 配置文件位置

Claude Code的MCP配置文件位于：
```
~/.claude/claude_desktop_config.json
```

## 🔧 Boss直聘 MCP服务器配置

### 基础配置

```json
{
  "mcpServers": {
    "boss-zhipin": {
      "command": "python",
      "args": ["/Users/songbingrong/PycharmProjects/mcp-bosszp/boss_zhipin_mcp.py"],
      "disabled": false
    }
  },
  "mcpEnabled": true,
  "globalShortcut": "cmd+shift+m"
}
```

### 配置说明

- **mcpServers**: MCP服务器列表
  - **boss-zhipin**:服务器名称（可自定义）
  - **command**: 执行命令（python）
  - **args**: Python脚本的绝对路径
  - **disabled**: 是否禁用（false表示启用）

- **mcpEnabled**: 全局MCP功能开关
- **globalShortcut**: 全局快捷键（可自定义）

## 🚀 启动步骤

### 1. 确认Python环境

```bash
# 检查Python版本（需要3.12+）
python --version

# 确认项目目录存在
ls /Users/songbingrong/PycharmProjects/mcp-bosszp/

# 测试MCP服务器是否可运行
cd /Users/songbingrong/PycharmProjects/mcp-bosszp
python boss_zhipin_mcp.py --help
```

### 2. 重启Claude Code

配置完成后，需要重启Claude Code应用以加载新的MCP配置。

### 3. 验证配置

重启后，您应该能在Claude Code中看到Boss直聘相关的功能。

## 🎯 可用功能

配置成功后，您可以使用以下功能：

### 资源（Resources）
- `boss-zp://login/status` - 查看登录状态
- `boss-zp://login/start` - 启动登录流程
- `boss-zp://config` - 获取配置信息
- `boss-zp://recommendJobs/...` - 获取推荐职位
- `boss-zp://greeting/...` - 发送打招呼

### 工具（Tools）
- `login_full_auto` - 完全自动登录
- `get_recommend_jobs` - 获取职位列表
- `send_greeting` - 发送打招呼消息

## 🛠️ 故障排除

### 常见问题

1. **MCP服务器无法启动**
   ```bash
   # 检查Python路径
   which python

   # 检查脚本权限
   chmod +x /Users/songbingrong/PycharmProjects/mcp-bosszp/boss_zhipin_mcp.py

   # 测试直接运行
   python /Users/songbingrong/PycharmProjects/mcp-bosszp/boss_zhipin_mcp.py
   ```

2. **依赖包缺失**
   ```bash
   cd /Users/songbingrong/PycharmProjects/mcp-bosszp
   pip install -r requirements.txt
   ```

3. **配置文件格式错误**
   ```bash
   # 验证JSON格式
   python -m json.tool ~/.claude/claude_desktop_config.json
   ```

### 调试模式

如需调试，可以在配置中添加环境变量：

```json
{
  "mcpServers": {
    "boss-zhipin": {
      "command": "python",
      "args": ["/Users/songbingrong/PycharmProjects/mcp-bosszp/boss_zhipin_mcp.py"],
      "env": {
        "DEBUG": "1"
      },
      "disabled": false
    }
  }
}
```

## 📝 使用示例

配置完成后，您可以这样使用：

```
请帮我启动Boss直聘登录流程
```

```
查看当前的登录状态
```

```
获取3-5年经验的Python工程师职位推荐
```

```
向这个HR发送打招呼：security_id=xxx, job_id=yyy
```

## 🔄 更新配置

如果需要更新配置：

1. 修改 `~/.claude/claude_desktop_config.json`
2. 重启Claude Code
3. 验证功能是否正常

---

💡 **提示**: 确保Python路径和脚本路径都是绝对路径，避免使用相对路径导致的问题。