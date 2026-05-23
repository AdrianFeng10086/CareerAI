# <h1 align="center">🎯 CareerAI</h1>

<p align="center">
  <strong>你的 AI 求职导航仪 — 从海量岗位到精准规划，让 AI 陪你跑通求职全链路</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="#"><img src="https://img.shields.io/badge/Status-Active-00A86B?style=for-the-badge" alt="Status"></a>
</p>

<p align="center">
  <a href="#为什么需要-careerai">为什么需要</a> · <a href="#快速上手">快速上手</a> · <a href="#核心能力">核心能力</a> · <a href="#架构设计">架构设计</a> · <a href="#常见问题">常见问题</a>
</p>

---

## 为什么需要 CareerAI？

求职是一场信息战。你面对的问题很现实：

- 📊 "这个岗位的薪资在行业里什么水平？" → **不知道**，只能靠感觉
- 🎯 "我的背景适合哪些岗位？" → **不清楚**，海投简历效率低
- 🧭 "我应该往哪个方向发展？" → **没思路**，职业规划全靠运气
- 🎤 "怎么准备面试才能通过？" → **没反馈**，模拟面试没人给意见
- 🎥 "我的面试表现怎么样？" → **看不见**，不知道自己哪里有问题
- 💼 "这个公司的岗位要求什么技能？" → **要自己一个一个看**，太费时间

**这些问题都可以用数据和 AI 来解决，但需要一个完整的系统。**

每个求职者都在重复做同样的事情——抓取岗位、分析市场、模拟面试、反思改进。这些工作本来就应该被自动化。

**CareerAI 把这件事变成一个完整的闭环：**

```
抓取岗位 → 分析市场 → 匹配职位 → 模拟面试 → 反馈改进 → 精准求职
```

一个系统，从数据到决策，从模拟到实战。

> ⭐ **Star 这个项目**，我们会持续追踪招聘市场变化、优化匹配算法、增强面试反馈能力。

### ✅ 在你用之前，你可能想知道

|                      |                                                              |
| -------------------- | ------------------------------------------------------------ |
| 💰 **完全免费**       | 所有功能开源、所有数据本地存储。不需要付费 API、不需要云服务 |
| 🔒 **隐私安全**       | 所有数据存储在本地，不上传不外传。支持多用户隔离，求职隐私有保障 |
| 🚀 **开箱即用**       | 一条命令启动，自动抓取 Boss 直聘数据，无需手动配置          |
| 🤖 **AI 全程陪伴**    | 从岗位分析到面试模拟，AI 贯穿整个求职流程                   |
| 📈 **数据驱动**       | 基于真实招聘数据的市场分析，不是凭感觉的建议                |
| 🎥 **实时反馈**       | 面试时摄像头实时分析表情、眼神、姿态，给出综合评分           |

---

## 核心能力

| 功能 | 说明 | 输出 |
| --- | --- | --- |
| 🔍 **智能抓取** | 高效抓取 Boss 直聘实时岗位数据，支持关键词/城市/页数灵活配置 | 原始 JSON + 向量索引 |
| 📊 **市场分析** | 自动统计薪资分布、技能热图、学历要求、经验偏好等多维度指标 | 结构化分析报告 |
| 🧭 **职业规划** | 基于 RAG 技术，结合个人背景提供人岗匹配建议与行动路线 | 交互式规划报告 |
| 🎤 **模拟面试** | 结构化 AI 面试官，8-15 题沉浸式问答，支持深度追问与专业反馈 | 面试日志 + 评估 |
| 🎥 **神态分析** | 面试期间实时开启摄像头，追踪表情、眼神、头部姿态与综合评分 | 神态指标 + 综合评分 |
| 👤 **账户体系** | 多用户支持，数据严格物理隔离，确保求职隐私 | 用户隔离存储 |

---

## 快速上手

### 1. 环境准备

- **Python 3.10+**
- **推荐 Windows 环境**（项目包含预置 Chrome 内核，Linux/Mac 需自行配置）

### 2. 一键启动

```bash
# 克隆项目
git clone https://github.com/yourusername/CareerAI.git
cd CareerAI

# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate   # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 启动服务
python web_app.py
```

访问 `http://127.0.0.1:5000` 开启你的 AI 职场之旅。

<details>
<summary><strong>启动后看到什么？（点击展开）</strong></summary>

1. **登录界面** — 创建账户或登录，数据隔离存储
2. **岗位抓取** — 输入关键词/城市，一键抓取 Boss 直聘实时数据
3. **市场分析** — 自动生成薪资分布、技能热图、经验要求等分析报告
4. **职业规划** — 上传简历或输入背景，AI 给出人岗匹配建议与行动路线
5. **模拟面试** — 选择岗位，进入 AI 面试官模式，实时反馈与评分
6. **神态分析** — 面试时开启摄像头，实时追踪表情/眼神/姿态，输出综合评分

</details>

---

## 架构设计

```
CareerAI/
├── web_app.py                    # Flask Web 服务入口
├── requirements.txt              # 依赖清单
├── data/                         # 数据中心
│   ├── career_jobs_latest.json   # 岗位数据
│   ├── career_jobs_vector_db/    # 向量数据库
│   └── users.db                  # 用户账户系统
├── src/
│   ├── scraper.py                # Boss 直聘抓取引擎
│   ├── analyzer.py               # 市场数据分析
│   ├── report.py                 # 报告生成逻辑
│   ├── interview_module.py        # AI 面试官
│   ├── camera.py                 # 摄像头神态分析
│   ├── models.py                 # 数据模型定义
│   ├── config.py                 # 全局配置
│   └── career_planning/          # 核心规划算法
│       ├── dialogue/              # 对话管理
│       ├── reports/               # 报告生成
│       └── data/                  # 数据加载
├── app/                          # 前端应用（可选）
├── static/                       # 静态资源
└── template/                     # HTML 模板
```

### 🔌 核心模块说明

| 模块 | 职责 | 关键方法 |
| --- | --- | --- |
| **scraper.py** | 从 Boss 直聘抓取岗位数据 | `fetch_jobs()`, `parse_job_details()` |
| **analyzer.py** | 统计分析市场数据 | `analyze_salary()`, `extract_skills()`, `generate_report()` |
| **interview_module.py** | AI 面试官逻辑 | `start_interview()`, `ask_question()`, `evaluate_answer()` |
| **camera.py** | 摄像头实时分析 | `detect_expression()`, `track_eye_contact()`, `analyze_posture()` |
| **career_planning/** | 职业规划 RAG 引擎 | `match_jobs()`, `generate_plan()`, `suggest_improvements()` |

---

## API 入口

| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/api/status` | `GET` | 检查登录态、数据库连接状态 |
| `/api/auth/register` | `POST` | 用户注册 |
| `/api/auth/login` | `POST` | 用户登录 |
| `/api/jobs/fetch` | `POST` | 触发岗位抓取任务 |
| `/api/jobs/search` | `POST` | 语义搜索岗位 |
| `/api/analysis/market` | `GET` | 获取市场分析报告 |
| `/api/career/analyze` | `POST` | 生成职业规划报告 |
| `/api/interview/start` | `POST` | 初始化面试场景 |
| `/api/interview/answer` | `POST` | 提交面试答案 |
| `/api/interview/camera/stats` | `GET` | 获取实时神态分析数据 |

---

## 安全性与隐私

CareerAI 在设计上重视求职隐私：

| 措施 | 说明 |
| --- | --- |
| 🔒 **本地存储** | 所有数据存储在本地 `data/` 目录，不上传云端 |
| 👤 **多用户隔离** | 每个用户的数据严格物理隔离，互不可见 |
| 🛡️ **账户系统** | 内置登录认证，支持密码加密存储 |
| 📹 **摄像头隐私** | 摄像头数据仅用于本地分析，不保存不上传 |
| 🔍 **开源透明** | 代码完全开源，随时可审查 |

### 🍪 数据安全建议

- **定期备份** — 重要的分析报告和面试记录建议定期备份
- **账户保护** — 不要在公共电脑上登录，避免数据泄露
- **摄像头权限** — 面试模拟时会请求摄像头权限，可随时关闭

---

## 常见问题 / FAQ

<details>
<summary><strong>怎么抓取 Boss 直聘的岗位数据？</strong></summary>

CareerAI 内置了 Boss 直聘爬虫，支持关键词、城市、页数灵活配置。启动后在 Web 界面输入搜索条件，点击"抓取岗位"即可。数据会自动存储到本地向量数据库，支持语义搜索。

</details>

<details>
<summary><strong>市场分析报告包含哪些内容？</strong></summary>

包括：
- 薪资分布（平均薪资、薪资范围、城市对比）
- 技能热图（高频技能、技能组合、学习优先级）
- 学历要求（本科/硕士/博士占比）
- 经验要求（应届/1-3年/3-5年等分布）
- 公司规模与融资阶段分析

</details>

<details>
<summary><strong>职业规划是怎么工作的？</strong></summary>

基于 RAG（检索增强生成）技术：
1. 你上传简历或输入背景信息
2. AI 从岗位数据库中检索相关岗位
3. 结合你的背景，生成人岗匹配评分
4. 提供具体的改进建议与行动路线

</details>

<details>
<summary><strong>AI 面试官怎么工作？</strong></summary>

结构化面试流程：
1. 选择目标岗位
2. AI 根据岗位要求生成 8-15 道面试题
3. 支持深度追问，模拟真实面试
4. 实时给出答案评分与改进建议
5. 生成面试总结报告

</details>

<details>
<summary><strong>摄像头神态分析准确吗？</strong></summary>

基于 OpenCV 和深度学习模型，可以检测：
- 表情识别（微笑、紧张、困惑等）
- 眼神接触（是否看向镜头）
- 头部姿态（点头、摇头、歪头等）
- 综合评分（0-100 分）

准确度取决于光线、摄像头质量等因素。建议在光线充足的环境下使用。

</details>

<details>
<summary><strong>支持 Linux/Mac 吗？</strong></summary>

支持，但需要手动配置：
- **Linux** — 需要安装 Chrome/Chromium，修改 `config.py` 中的浏览器路径
- **Mac** — 需要安装 Chrome，可能需要调整权限设置
- **Windows** — 开箱即用，项目包含预置 Chrome 内核

建议在 Windows 上使用以获得最佳体验。

</details>

<details>
<summary><strong>数据会被上传到云端吗？</strong></summary>

不会。所有数据存储在本地 `data/` 目录，不上传任何云服务。你完全掌控自己的求职数据。

</details>

---

## 贡献

这个项目是为了帮助求职者而创建的。如果你有想法或遇到问题，欢迎：

- 📝 **提 Issue** — 报告 Bug 或提出功能建议
- 🔧 **提 PR** — 改进代码、优化算法、增加新功能
- 💬 **讨论** — 分享你的求职经验和改进建议

[Issues](https://github.com/yourusername/CareerAI/issues) · [Pull Requests](https://github.com/yourusername/CareerAI/pulls)

---

## ⭐ 为什么值得 Star

- 📊 **真实数据** — 基于 Boss 直聘实时数据，不是凭感觉的建议
- 🤖 **AI 全程陪伴** — 从分析到面试，AI 贯穿整个求职流程
- 🎯 **精准匹配** — RAG 技术确保职位推荐的准确性
- 🔄 **持续迭代** — 随着招聘市场变化，算法不断优化
- 💰 **完全免费** — 开源项目，无任何隐藏费用

Star 一下，下次求职时能找到。⭐

---

## 致谢

感谢以下开源项目的支持：

- [Flask](https://flask.palletsprojects.com/) — Web 框架
- [OpenCV](https://opencv.org/) — 计算机视觉
- [LangChain](https://www.langchain.com/) — LLM 应用框架
- [Chroma](https://www.trychroma.com/) — 向量数据库
- [Anthropic Claude](https://www.anthropic.com/) — AI 模型

---

## 联系方式

- 📧 **Email** — yf2678045931@outlook.com


> Bug 反馈和功能请求请用 [GitHub Issues](https://github.com/yourusername/CareerAI/issues)，更容易跟踪。

---

## License

[MIT](LICENSE)

---

## ⚠️ 声明

本项目仅供职业规划辅助与学术交流使用，不代表最终录用结果。请结合实际情况审慎参考。

<p align="center">Made with ❤️ by CareerAI Team</p>
