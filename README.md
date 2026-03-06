# 职探AI

基于 Boss 直聘数据的职位洞察与职业建议工具，支持：
- 职位搜索与推荐抓取
- 薪资/技能/地区/学历等结构化分析
- AI 深度解读与个性化建议
- 多格式报告输出（Markdown / HTML / PDF）
- Web 对话式一键分析流程

## 功能亮点

- 职位数据抓取
  - 支持按关键词和城市搜索职位
  - 支持推荐职位抓取
- 智能分析
  - 薪资区间、年薪估算、技能热度、地区分布、学历与经验要求统计
  - 可接入 OpenAI 兼容接口（如 DeepSeek）进行深度分析
- 报告输出
  - 命令行摘要
  - Markdown 报告
  - HTML 可视化报告
  - PDF 报告
- Web 端能力
  - 报告列表与在线查看
  - 聊天触发“搜索 -> 分析 -> 出报告”任务流
  - 支持保存 Boss Cookie、调用 MCP 登录

## 项目结构

```text
职探AI/
├── web_app.py                 # Flask Web 入口
├── config.json                # 项目配置（含 AI 与 Cookie）
├── requirements.txt           # 依赖列表
├── data/                      # 抓取原始数据输出目录
├── output/                    # 报告输出目录
├── src/
│   ├── main.py                # CLI 入口
│   ├── scraper.py             # Boss 职位抓取
│   ├── analyzer.py            # 数据分析与 AI 洞察
│   ├── report.py              # 报告生成器
│   ├── config.py              # 配置管理
│   ├── models.py              # 数据模型
│   └── boss_zp/               # MCP 登录与 Boss 相关实现
├── template/
│   └── index.html             # Web 页面模板
└── static/                    # Web 静态资源
```

## 运行环境

- Python 3.10+
- Windows / macOS / Linux
- 建议使用虚拟环境

## 安装步骤

```bash
# 1) 进入项目目录
cd 职探AI

# 2) 创建并激活虚拟环境（Windows PowerShell）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) 安装依赖
pip install -r requirements.txt
```

说明：若你使用了 `src/boss_zp` 下的 MCP 登录流程，可能还需要额外安装并初始化 Playwright（按该模块说明执行）。

## 配置说明

主要配置文件是 `config.json`，常用字段如下：

- `ai_api_key`: AI 服务密钥
- `ai_base_url`: OpenAI 兼容接口地址（例如 DeepSeek chat/completions 地址）
- `ai_model`: 模型名称
- `request_delay`: 抓取请求间隔（秒）
- `max_pages_per_search`: 单次搜索最大页数
- `cookie` / `bst`: Boss 登录态参数

你也可以通过环境变量覆盖部分配置，例如：
- `AI_API_KEY` / `OPENAI_API_KEY`
- `AI_BASE_URL` / `OPENAI_BASE_URL`
- `AI_MODEL`
- `BOSS_COOKIE`
- `BOSS_BST`

## 命令行使用（CLI）

入口：`src/main.py`

```bash
# 初始化配置（交互式）
python src/main.py init

# 设置 Cookie
python src/main.py set-cookie --cookie "你的cookie" --bst "你的bst"

# 搜索职位并分析
python src/main.py search --keyword "Python开发" --city 北京 --pages 3

# 搜索并生成 HTML 报告
python src/main.py search --keyword "前端工程师" --city 上海 --html

# 获取推荐职位并分析
python src/main.py recommend --pages 2

# 从本地数据文件分析
python src/main.py analyze --file data/jobs_xxx.json --html
```

## Web 方式使用

启动：

```bash
python web_app.py
```

默认访问：`http://127.0.0.1:5000`

Web 端核心接口（开发调试可用）：
- `GET /api/status`: 系统状态
- `GET /api/reports`: 报告列表
- `GET /api/reports/<report_name>`: 报告内容
- `POST /api/chat`: 发起对话分析任务
- `GET /api/chat/task/<task_id>`: 查询任务进度
- `POST /api/boss/login-save`: 保存 Cookie
- `POST /api/boss/login-mcp`: 调用 MCP 登录

## 输出结果

- 抓取数据默认保存到 `data/`
- 报告默认保存到 `output/`
  - `report_*.md`
  - `report_*.html`
  - `report_*.pdf`

## 常见问题

- 提示未登录或抓取为空
  - 请先确保 `config.json` 中 `cookie` 已配置且有效
- AI 分析无结果
  - 请检查 `ai_api_key`、`ai_base_url`、`ai_model` 是否正确
- 报告未生成
  - 检查 `output/` 目录权限、依赖是否完整安装

## 安全建议

- `config.json` 可能包含敏感信息（API Key、Cookie），请勿上传到公开仓库
- 建议使用环境变量注入密钥，并在版本管理中忽略本地私密配置

## 致谢

感谢 `mcp-booszp` 开源项目提供的思路与实现参考，特别是在 Boss 登录流程与 MCP 能力集成方面提供了重要帮助。

同时也感谢 `mcp-bosszp` 社区与相关开源组件（如 FastMCP、Playwright、Requests、PyCryptodome）的贡献。

## 免责声明

本项目仅用于学习与技术研究。请在合法合规、遵守目标平台服务条款和相关法律法规的前提下使用。
