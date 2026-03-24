# CareerAI

> 🚀 你的 AI 求职作战台：从岗位抓取到职业规划，一站式跑完整条链路。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-Web_App-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Feature-Career_Planning-0B7A75?style=for-the-badge" alt="Career Planning" />
  <img src="https://img.shields.io/badge/Feature-Mock_Interview-0E7490?style=for-the-badge" alt="Mock Interview" />
  <img src="https://img.shields.io/badge/Status-Active-00A86B?style=for-the-badge" alt="Status" />
</p>

## ✨ 项目亮点

CareerAI 不只是“给你一段建议”，而是把求职过程拆成可执行步骤：

- 🔍 抓岗位：自动抓取 Boss 职位信息并沉淀数据。
- 📊 看市场：输出薪资、技能、经验等维度分析。
- 🧭 做规划：根据你的背景生成人岗匹配与行动路径。
- 🎤 练面试：围绕目标岗位进行结构化模拟问答。
- 🛡️ 保隐私：账号数据隔离，报告按用户独立存储。

## 🧩 能力地图

| 模块 | 能做什么 | 输出形式 |
| --- | --- | --- |
| 🔍 岗位抓取 | 关键词、城市、页数抓取；支持推荐岗位 | 原始 JSON、数据库记录 |
| 📊 数据分析 | 薪资、学历、经验、技能需求统计 | 分析结果、可读摘要 |
| 🧭 职业规划 | 匹配度评估、路径规划、行动建议 | PDF |
| 🎤 模拟面试 | 8-15 题面试链路，含深度追问与反馈 | 面试日志、评估结果 |
| 👤 账户系统 | 注册、登录、退出、目录隔离 | output/users/<token>/ |

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- Windows / macOS / Linux
- 建议使用虚拟环境

### 2. 安装依赖

```bash
cd CareerAI
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. 启动服务

```bash
python web_app.py
```

浏览器访问：`http://127.0.0.1:5000`

建议使用流程：

1. 注册并登录账号。
2. 完成 MCP 扫码登录。
3. 在对话引擎发起抓取与分析任务。
4. 进入职业规划和模拟面试模块深化准备。

## 🧱 目录结构

```text
CareerAI/
├── web_app.py
├── config.json
├── requirements.txt
├── data/
├── output/
├── src/
│   ├── analyzer.py
│   ├── report.py
│   ├── scraper.py
│   ├── boss_zp/
│   └── career_planning/
│       ├── ai/
│       ├── data/
│       ├── dialogue/
│       ├── matching/
│       ├── reports/
│       └── resume/
├── template/
│   ├── index.html
│   └── login.html
└── static/
```

## 📡 API 速览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/status` | 系统状态（登录态、Boss 登录态、模型配置） |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 退出 |
| GET | `/api/reports` | 当前用户报告列表 |
| GET | `/api/reports/<name>` | 读取指定报告 |
| POST | `/api/chat` | 发起对话任务 |
| GET | `/api/chat/task/<task_id>` | 轮询任务进度 |
| POST | `/api/career/analyze` | 职业规划分析 |
| POST | `/api/interview/start` | 启动模拟面试 |
| POST | `/api/interview/answer` | 提交面试回答 |

## ❓ 常见问题

### Q1: 登录 Boss 后还是抓不到数据怎么办？

先确认 MCP 登录状态是否成功，再检查关键词和页数设置。建议先从小页数重试。

### Q2: 为什么任务偶尔会比较慢？

抓取、分析、报告生成是分阶段执行的，网络和模型响应时间都会影响总耗时。

### Q3: 为什么看不到别人的报告？

这是预期行为。系统按账号隔离输出目录，默认互不可见，确保隐私安全。

## 🗺️ 路线图

- [ ] 增加登录失败限流与密码强度策略。
- [ ] 提供更细粒度的职业路径对比视图。
- [ ] 增强面试反馈可视化能力。
- [ ] 丰富报告模板和导出主题。

## ⚠️ 免责声明

本项目用于职业规划辅助，不构成就业保证或最终决策依据。
请结合真实岗位信息与个人情况综合判断。

<p align="center">Made with ❤️ by CareerAI Team</p>
