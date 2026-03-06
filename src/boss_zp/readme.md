# Boss 直聘 MCP 服务器

## 简介

这是一个基于 [模型上下文协议 (MCP)](https://modelcontextprotocol.io/introduction) 和 [FastMCP](https://github.com/jlowin/fastmcp) 框架构建的服务器，它为大型语言模型（LLM）提供了与 Boss 直聘 API 交互的能力。通过本服务器，LLM 可以代替用户自动执行以下操作：

- 🔐 **自动登录**：二维码扫码登录，自动完成安全验证
- 💼 **搜索职位**：筛选和搜索工作岗位
- 👋 **发送问候**：向招聘者自动发送问候消息

## 技术栈

- **[Python 3.12+](https://www.python.org/)**
- **[FastMCP](https://github.com/jlowin/fastmcp)**: 现代化 MCP 服务器框架
- **[Playwright](https://playwright.dev/python/)**: 无头浏览器自动化，用于安全验证
- **[Requests](https://requests.readthedocs.io/)**: HTTP 请求库
- **[PyCryptodome](https://pycryptodome.readthedocs.io/)**: 加密库，用于设备指纹生成

## 安装与部署

### 方式一：直接安装（推荐用于开发）

1. **克隆仓库**:
   ```bash
   git clone https://github.com/mucsbr/mcp-bosszp.git
   cd mcp-bosszp
   ```

2. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **运行服务器**:
   ```bash
   python boss_zhipin_fastmcp_v2.py
   ```

### 方式二：Docker 部署（推荐用于生产）

1. **使用 Docker Compose**:
   ```bash
   docker-compose up -d
   ```

2. **或者使用 Docker 命令**:
   ```bash
   docker build -t mcp-boss-zp .
   docker run -p 8000:8000 mcp-boss-zp
   ```

## MCP 客户端配置

要在您的 MCP 客户端（如 Claude Desktop）中使用此服务器，请添加以下配置：

```json
{
  "mcpServers": {
    "mcp-boss-zp": {
      "command": "python",
      "args": [
        "/path/to/boss_zhipin_fastmcp_v2.py"
      ],
      "disabled": false
    }
  }
}
```

**注意**：
- 不需要预先配置 Cookie，服务器支持自动登录功能
- 首次使用需要通过二维码扫码登录

## 功能特性

### 1. 自动登录系统

服务器提供完全自动化的登录流程：

- **生成二维码**：自动生成登录二维码
- **后台监控**：非阻塞方式监控扫码状态
- **安全验证**：使用无头浏览器自动完成安全验证
- **Cookie 管理**：自动获取并保存最终有效的 Cookie

#### 登录流程

```
调用 login_full_auto
    ↓
生成二维码并返回图片 URL
    ↓
用户使用 Boss 直聘 APP 扫码
    ↓
后台自动监控扫码和确认状态
    ↓
自动完成安全验证（获取 __zp_stoken__）
    ↓
登录完成，Cookie 自动保存
```

### 2. 可用资源

#### 登录信息查询
- **URI**: `boss-zp://login/info`
- **描述**: 查看当前登录状态和 Cookie 信息

#### 推荐职位配置
- **URI**: `boss-zp://config`
- **描述**: 获取工作经验、职位类型、薪资范围等配置参数

### 3. 可用工具

#### 自动登录
```python
login_full_auto()
```
完全自动化登录流程，生成二维码并后台监控登录状态。

#### 查看登录信息
```python
get_login_info_tool()
```
获取当前登录状态、Cookie 和 BST 参数。

#### 搜索推荐职位
```python
get_recommend_jobs_tool(
    page: int = 1,
    experience: str = "不限",  # 在校生、应届生、不限、一年以内、一到三年、三到五年、五到十年、十年以上
    job_type: str = "全职",    # 全职、兼职
    salary: str = "不限"       # 3k以下、3-5k、5-10k、10-20k、20-50k、50以上
)
```
获取推荐的工作岗位列表，支持中文参数，后端自动转换。

#### 向 HR 打招呼
```python
greet_boss_tool(
    security_id: str,
    job_id: str
)
```
向指定的招聘者和职位发送问候消息。

## 使用示例

### 1. 首次登录

```
用户: 帮我登录 Boss 直聘
LLM: [调用 login_full_auto]
     已生成二维码: http://127.0.0.1:8000/static/qrcode_xxx.png
     请使用 Boss 直聘 APP 扫码登录

用户: [扫码并确认]
LLM: 登录成功！已获取有效 Cookie
```

### 2. 搜索职位

```
用户: 帮我找一些 Python 后端的工作，要求 3-5 年经验，薪资 20-50k
LLM: [调用 get_recommend_jobs_tool]
     找到以下职位：
     1. 高级 Python 工程师 - 某科技公司 - 30-50k
     2. Python 后端开发 - 某互联网公司 - 25-40k
     ...
```

### 3. 向 HR 打招呼

```
用户: 帮我给第一个职位的 HR 打个招呼
LLM: [调用 greet_boss_tool]
     已成功向 HR 发送问候消息！
```

## 技术亮点

### 非阻塞登录设计

- 使用 **threading** 实现后台监控，不阻塞主线程
- 登录过程中可以正常访问静态文件（二维码图片）
- 实时更新登录状态，支持状态查询

### 自动安全验证

- 使用 **Playwright** 无头浏览器自动完成 security-check
- 通过 JavaScript 直接读取页面 Cookie，确保数据一致性
- 等待网络空闲后再提取 Cookie，确保完整性

### 智能参数转换

- 支持中文参数输入（如 "三到五年"、"20-50k"）
- 后端自动转换为 API 所需的数字代码
- 提供配置资源供 LLM 参考

## 项目结构

```
mcp-bosszp/
├── boss_zhipin_fastmcp_v2.py  # 主服务器文件
├── login_verifier.py           # 登录验证参考实现
├── static/                     # 运行时生成的二维码图片
├── requirements.txt            # Python 依赖
├── Dockerfile                  # Docker 构建文件
├── docker-compose.yml          # Docker Compose 配置
└── README.md                   # 项目文档
```

## 开发与贡献

欢迎提交 Issue 和 Pull Request！

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 运行服务器
python boss_zhipin_fastmcp_v2.py
```

### 调试模式

在 `boss_zhipin_fastmcp_v2.py` 中设置 `headless=False` 可以看到浏览器操作过程：

```python
browser = await p.chromium.launch(headless=False)  # 显示浏览器窗口
```

## 待办事项

- [x] 提供访问 Boss 直聘推荐工作列表的资源
- [x] 提供打招呼的资源
- [x] 自动登录功能
- [x] 安全验证自动化
- [x] Docker 构建方式
- [ ] 提供获取消息信息的资源
- [ ] 更多筛选条件支持

## 许可证

[MIT License](LICENSE)

## 致谢

- [FastMCP](https://github.com/jlowin/fastmcp) - 现代化 MCP 框架
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP 标准
- [Playwright](https://playwright.dev/) - 浏览器自动化工具
