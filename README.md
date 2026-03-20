<h1 align="center">CareerAI</h1>

<p align="center">
  <strong>把 Boss 职位抓取、岗位分析、个性化建议和报告生成整合成一次对话流程</strong>
</p>

<p align="center">
  像和职业教练聊天一样，把“我要找什么工作”变成“我下一步该怎么投”。
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Flask-Web_App-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Report-Markdown%20%7C%20HTML%20%7C%20PDF-2E8B57?style=for-the-badge" alt="Report" />
  <img src="https://img.shields.io/badge/Status-Active-00A86B?style=for-the-badge" alt="Status" />
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#核心能力">核心能力</a> ·
  <a href="#web-流程">Web 流程</a> ·
  <a href="#cli-命令">CLI 命令</a> ·
  <a href="#常见问题-faq">常见问题</a>
</p>

---

## 为什么做CareerAI

一句话版本：不想再把找工作做成一份“重复劳动型兼职”。

找工作时大家经常卡在这几件事：

- 职位很多，但不知道市场真实要求是什么
- 知道方向，但不清楚自己的优势和短板如何映射到岗位
- 手动抓数据、做统计、写分析报告太慢
- 同样的查询每次都要重复一堆步骤

CareerAI把这条链路打通成一个流程：

`输入需求 -> 自动抓取 -> 结构化分析 -> AI 洞察 -> 生成报告`

你只需要给一句自然语言请求，系统会自动把后面的事做完。

你可以把它理解成一个“会做功课的求职搭子”：

- 你负责提出目标
- 它负责把市场信息拆开、整理、总结
- 最后再给你一份可以直接拿去行动的建议

---

## 核心能力

从“我想找工作”到“我知道该怎么投”，中间每一步都有人接力：

| 模块 | 能力 | 说明 |
|---|---|---|
| 职位抓取 | 关键词搜索、推荐职位抓取 | 支持城市、页数、条件组合 |
| 风控处理 | 自动识别风控场景 | 首轮有数据则继续分析，首轮无数据且风控才触发二轮 |
| 数据分析 | 薪资、技能、地点、学历、经验、行业统计 | 可用于岗位画像和投递策略 |
| 个性化画像 | 从自由文本提取目标、项目、技术栈、奖项、研究方向 | 支持简历式长文本 |
| AI 洞察 | 结合市场数据和个人画像给出建议 | 支持 OpenAI 兼容模型 |
| 报告生成 | Markdown / HTML / PDF | 报告中心可在线查看 |
| 实时反馈 | 任务进度 + 事件流消息 | 抓取、分析、出报告过程可视化 |

补充说明：

- 主 AI 不稳定时，系统会自动切到备用 AI，流程不中断
- 任务事件流会提示关键阶段，让你知道它不是在“假装思考”
- PDF 报告已包含图表，方便快速看结论也方便复盘细节

---

## Web 流程

整条 Web 路径的体验目标是：少点按钮，多点结果。

### 1. 自动登录检测

- 系统启动后自动检测是否已有 Boss 登录态
- 已登录：提示“您已登录，进入首页”
- 未登录：弹出 MCP 登录窗口引导扫码

### 2. MCP 扫码登录（弹窗）

- 点击按钮后在新窗口打开二维码
- 用户扫码后系统自动检测并关闭二维码窗口
- 主界面继续等待 Cookie 获取与写入完成

### 3. 对话式任务执行

- 用户输入自然语言请求
- 后端创建任务并按阶段推进
- 前端展示进度条和实时事件文本
- 完成后自动刷新报告列表

小提示：

- 任务执行中请耐心等待事件流更新，避免重复提交相同请求
- 如果网络波动，优先观察任务状态接口返回，而不是立即重启流程

---

## 快速开始

如果你只想先跑起来看效果，可以直接按下面 3 步走：安装依赖 -> 启动服务 -> 发起第一条任务。

### 环境要求

- Python 3.10+
- Windows / macOS / Linux
- 推荐使用虚拟环境

### 安装

```bash
# 进入项目目录
cd CareerAI

# 创建并激活虚拟环境（Windows PowerShell）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

### 启动 Web 应用

```bash
python web_app.py
```

访问地址：`http://127.0.0.1:5000`

建议第一条测试请求：

`帮我分析深圳 AI 产品经理岗位，重点看技能要求和薪资区间`

---

## CLI 命令

入口文件：`src/main.py`

CLI 适合这些场景：

- 想批量跑任务
- 想把流程接进你自己的脚本
- 想在没有 Web 页面时快速验证配置

```bash
# 交互式初始化配置
python src/main.py init

# 设置 Cookie
python src/main.py set-cookie --cookie "你的cookie" --bst "你的bst"

# 关键词搜索并分析
python src/main.py search --keyword "AI应用开发" --city 深圳 --pages 5

# 搜索并输出 HTML 报告
python src/main.py search --keyword "前端工程师" --city 上海 --html

# 获取推荐职位并分析
python src/main.py recommend --pages 2

# 从已有数据文件生成分析
python src/main.py analyze --file data/jobs_xxx.json --html
```

实战建议：

- 先用 `--pages 1` 小规模试跑，确认配置正确后再扩大页数
- 报告验证优先看 HTML，迭代快；最终归档再导出 PDF

---

## 配置说明

主要配置文件：`config.json`

可以把配置理解成两层：

- 基础运行层：抓取参数、Cookie、分页等
- AI 能力层：主模型 + 备用模型，确保分析稳定输出

常用字段：

- `ai_api_key`: AI 服务密钥
- `ai_base_url`: OpenAI 兼容接口地址
- `ai_model`: 模型名称
- `backup_ai_api_key`: 备用 AI 密钥（主 AI 连接异常时自动切换）
- `backup_ai_base_url`: 备用 AI OpenAI 兼容地址（如混元）
- `backup_ai_model`: 备用模型名称（如 `hunyuan-turbos-latest`）
- `request_delay`: 抓取请求间隔（秒）
- `max_pages_per_search`: 单次最大抓取页数
- `cookie` / `bst`: Boss 登录态

支持环境变量覆盖：

- `AI_API_KEY` / `OPENAI_API_KEY`
- `AI_BASE_URL` / `OPENAI_BASE_URL`
- `AI_MODEL`
- `BACKUP_AI_API_KEY` / `HUNYUAN_API_KEY`
- `BACKUP_AI_BASE_URL` / `HUNYUAN_BASE_URL`
- `BACKUP_AI_MODEL` / `HUNYUAN_MODEL`
- `BOSS_COOKIE`
- `BOSS_BST`

推荐实践：

- 本地开发可用 `config.json`
- 部署或共享环境建议全部改用环境变量
- 若你所在网络对某些模型访问不稳定，优先配置备用模型

---

## 项目结构

目录设计遵循“抓取、分析、报告”三段式，便于独立调试与替换模块。

```text
CareerAI/
├── web_app.py
├── config.json
├── requirements.txt
├── data/
├── output/
├── src/
│   ├── main.py
│   ├── scraper.py
│   ├── analyzer.py
│   ├── report.py
│   ├── config.py
│   ├── models.py
│   └── boss_zp/
├── template/
│   └── index.html
└── static/
```

---

## 输出内容

- 原始抓取数据输出到 `data/`
- 报告输出到 `output/`
- 报告格式包括：
  - `report_*.md`
  - `report_*.html`
  - `report_*.pdf`

阅读顺序建议：

- 先看 HTML 快速浏览全局
- 再看 PDF 做分享或留档
- 最后需要二次处理时再用 Markdown

---

## API 概览

如果你准备二次开发，这一节可以当作最小对接清单。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/status` | 系统状态 |
| GET | `/api/reports` | 报告列表 |
| GET | `/api/reports/<name>` | 报告内容 |
| POST | `/api/chat` | 发起对话任务 |
| GET | `/api/chat/task/<task_id>` | 查询任务状态 |
| POST | `/api/boss/mcp-login/start` | 发起 MCP 登录 |
| GET | `/api/boss/mcp-login/task/<task_id>` | 查询 MCP 登录状态 |
| GET | `/api/boss/mcp-login/qr/<task_id>` | 获取登录二维码 |

---

## 常见问题 FAQ

如果你第一次使用，建议先看这一节再看报错信息，通常能省下一半排查时间。

<details>
<summary><strong>提示“未登录”或抓取结果为空怎么办？</strong></summary>

先确认 MCP 登录流程已完成，`config.json` 中存在有效 `cookie`。若触发平台风控，系统会根据当前策略自动判断是否继续首轮数据分析或触发二轮重跑。
</details>

<details>
<summary><strong>为什么任务执行看起来比较久？</strong></summary>

流程包含抓取、统计、AI 洞察和 PDF 排版，任一环节都可能受网络或风控影响。前端会持续显示进度与事件消息，无需重复提交。
</details>

<details>
<summary><strong>AI 分析内容为空或质量不稳定怎么办？</strong></summary>

请检查 `ai_api_key`、`ai_base_url`、`ai_model` 是否正确。若未配置 AI Key，系统会回退到本地规则分析。
</details>

---

## 安全建议

一句话：把密钥和 Cookie 当成密码管理，不要出现在公共截图和公共仓库里。

- `config.json` 可能包含 Cookie 和 API Key，请勿上传公开仓库
- 建议使用环境变量注入密钥
- 建议将私密配置加入 `.gitignore`

---

## 致谢

这些工具让“从数据到洞察”这件事变得可实现、可复用、可维护。

感谢相关开源生态的支持与启发：

- FastMCP
- Playwright
- Requests
- PyCryptodome
- ReportLab

---

## 免责声明

本项目仅用于学习与技术研究，请在合法合规并遵守目标平台服务条款与法律法规的前提下使用。
