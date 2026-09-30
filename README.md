# <h1 align="center">🎯 CareerAI</h1>

<p align="center">
  <strong>Your AI Career Navigator — From vast job listings to precise planning, let AI guide you through the entire job search journey</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="#"><img src="https://img.shields.io/badge/Status-Active-00A86B?style=for-the-badge" alt="Status"></a>
</p>

<p align="center">
  <a href="#why-careerai">Why CareerAI</a> · <a href="#quick-start">Quick Start</a> · <a href="#core-features">Core Features</a> · <a href="#architecture">Architecture</a> · <a href="#faq">FAQ</a>
</p>

---

## Why CareerAI?

Job hunting is an information war. The problems you face are real:

- 📊 "What's the salary level for this position in the industry?" → **Don't know**, just guessing
- 🎯 "Which positions fit my background?" → **Unclear**, mass applications are inefficient
- 🧭 "Which direction should I develop my career?" → **No clue**, career planning relies on luck
- 🎤 "How do I prepare for interviews to pass?" → **No feedback**, no one to critique mock interviews
- 🎥 "How's my interview performance?" → **Can't see**, don't know what needs improvement
- 💼 "What skills does this company's position require?" → **Have to check one by one**, too time-consuming

**All these problems can be solved with data and AI, but require a complete system.**

Every job seeker is repeating the same tasks—scraping positions, analyzing markets, mock interviews, reflection and improvement. This work should be automated.

**CareerAI turns this into a complete loop:**

```
Scrape Jobs → Market Analysis → Position Matching → Mock Interview → Feedback & Improvement → Targeted Job Search
```

One system, from data to decision, from simulation to real battle.

> ⭐ **Star this project**, we'll continuously track recruitment market changes, optimize matching algorithms, and enhance interview feedback capabilities.

### ✅ Before you use it, you might want to know

|                      |                                                              |
| -------------------- | ------------------------------------------------------------ |
| 🔒 **Privacy Secure** | All data stored locally, not uploaded or shared. Supports multi-user isolation for job search privacy |
| 🚀 **Ready to Use** | One command to start, auto-scrapes Boss Zhipin data, no manual configuration |
| 🤖 **AI Companion** | From position analysis to interview simulation, AI throughout the job search process |
| 📈 **Data-Driven** | Market analysis based on real recruitment data, not guesswork advice |
| 🎥 **Real-time Feedback** | Camera analyzes expression, eye contact, posture during interview with comprehensive scoring |

---

## Core Features

| Feature | Description | Output |
| --- | --- | --- |
| 🔍 **Smart Scraping** | Efficiently scrape Boss Zhipin real-time job data with flexible keyword/city/page configuration | Raw JSON + Vector Index |
| 📊 **Market Analysis** | Auto-generate multi-dimensional metrics: salary distribution, skill heatmap, education requirements, experience preferences | Structured Analysis Report |
| 🧭 **Career Planning** | RAG-based technology combining personal background for job-candidate matching suggestions and action plans | Interactive Planning Report |
| 🎤 **Mock Interview** | Structured AI interviewer with 8-15 immersive Q&A, supports deep follow-ups and professional feedback | Interview Log + Evaluation |
| 🎥 **Demeanor Analysis** | Real-time camera tracking during interview: expression, eye contact, head posture with comprehensive scoring | Demeanor Metrics + Score |
| 👤 **Account System** | Multi-user support with strict data isolation ensuring job search privacy | User-isolated Storage |

---

## Quick Start

### 1. Environment Setup

- **Python 3.10+**
- **Windows recommended** (project includes pre-configured Chrome kernel, Linux/Mac requires manual configuration)

### 2. One-Command Launch

```bash
# Clone the project
git clone https://github.com/yourusername/CareerAI.git
cd CareerAI

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
# source .venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Start service
python web_app.py
```

Visit `http://127.0.0.1:5000` to begin your AI career journey.

<details>
<summary><strong>What to expect after launch? (Click to expand)</strong></summary>

1. **Login Interface** — Create account or login with isolated data storage
2. **Job Scraping** — Enter keywords/city, one-click scrape Boss Zhipin real-time data
3. **Market Analysis** — Auto-generate analysis reports: salary distribution, skill heatmap, experience requirements
4. **Career Planning** — Upload resume or input background, AI provides job-candidate matching suggestions and action plans
5. **Mock Interview** — Select position, enter AI interviewer mode with real-time feedback and scoring
6. **Demeanor Analysis** — Enable camera during interview, real-time tracking of expression/eye contact/posture with comprehensive score

</details>

---

## Architecture

```
CareerAI/
├── web_app.py                    # Flask web service entry
├── requirements.txt              # Dependencies
├── data/                         # Data center
│   ├── career_jobs_latest.json   # Job data
│   ├── career_jobs_vector_db/    # Vector database
│   └── users.db                  # User account system
├── src/
│   ├── scraper.py                # Boss Zhipin scraping engine
│   ├── analyzer.py               # Market data analysis
│   ├── report.py                 # Report generation logic
│   ├── interview_module.py        # AI interviewer
│   ├── camera.py                 # Camera demeanor analysis
│   ├── models.py                 # Data model definitions
│   ├── config.py                 # Global configuration
│   └── career_planning/          # Core planning algorithms
│       ├── dialogue/              # Dialogue management
│       ├── reports/               # Report generation
│       └── data/                  # Data loading
├── app/                          # Frontend app (optional)
├── static/                       # Static resources
└── template/                     # HTML templates
```

### 🔌 Core Module Description

| Module | Responsibility | Key Methods |
| --- | --- | --- |
| **scraper.py** | Scrape job data from Boss Zhipin | `fetch_jobs()`, `parse_job_details()` |
| **analyzer.py** | Statistical analysis of market data | `analyze_salary()`, `extract_skills()`, `generate_report()` |
| **interview_module.py** | AI interviewer logic | `start_interview()`, `ask_question()`, `evaluate_answer()` |
| **camera.py** | Real-time camera analysis | `detect_expression()`, `track_eye_contact()`, `analyze_posture()` |
| **career_planning/** | Career planning RAG engine | `match_jobs()`, `generate_plan()`, `suggest_improvements()` |

---

## API Endpoints

| Path | Method | Description |
| --- | --- | --- |
| `/api/status` | `GET` | Check login status and database connection |
| `/api/auth/register` | `POST` | User registration |
| `/api/auth/login` | `POST` | User login |
| `/api/jobs/fetch` | `POST` | Trigger job scraping task |
| `/api/jobs/search` | `POST` | Semantic job search |
| `/api/analysis/market` | `GET` | Get market analysis report |
| `/api/career/analyze` | `POST` | Generate career planning report |
| `/api/interview/start` | `POST` | Initialize interview scenario |
| `/api/interview/answer` | `POST` | Submit interview answer |
| `/api/interview/camera/stats` | `GET` | Get real-time demeanor analysis data |

---

## Security & Privacy

CareerAI prioritizes job search privacy by design:

| Measure | Description |
| --- | --- |
| 🔒 **Local Storage** | All data stored locally in `data/` directory, not uploaded to cloud |
| 👤 **Multi-user Isolation** | Each user's data strictly physically isolated, mutually invisible |
| 🛡️ **Account System** | Built-in login authentication with encrypted password storage |
| 📹 **Camera Privacy** | Camera data only used for local analysis, not saved or uploaded |
| 🔍 **Open Source** | Fully open-source code, auditable anytime |

### 🍪 Data Security Recommendations

- **Regular Backups** — Important analysis reports and interview records should be backed up regularly
- **Account Protection** — Don't login on public computers to avoid data leaks
- **Camera Permissions** — Camera permissions requested during mock interviews, can be disabled anytime

---

## FAQ

<details>
<summary><strong>How to scrape Boss Zhipin job data?</strong></summary>

CareerAI has a built-in Boss Zhipin crawler supporting flexible keyword, city, and page configuration. After launch, enter search criteria in the web interface and click "Scrape Jobs". Data is automatically stored in the local vector database supporting semantic search.

</details>

<details>
<summary><strong>What does the market analysis report include?</strong></summary>

Includes:
- Salary distribution (average salary, salary range, city comparison)
- Skill heatmap (high-frequency skills, skill combinations, learning priorities)
- Education requirements (bachelor's/master's/PhD ratio)
- Experience requirements (fresh graduate/1-3 years/3-5 years distribution)
- Company size and funding stage analysis

</details>

<details>
<summary><strong>How does career planning work?</strong></summary>

Based on RAG (Retrieval-Augmented Generation) technology:
1. Upload resume or input background information
2. AI retrieves relevant positions from job database
3. Combined with your background, generates job-candidate matching score
4. Provides specific improvement suggestions and action plans

</details>

<details>
<summary><strong>How does the AI interviewer work?</strong></summary>

Structured interview process:
1. Select target position
2. AI generates 8-15 interview questions based on position requirements
3. Supports deep follow-up questions, simulating real interviews
4. Real-time answer scoring and improvement suggestions
5. Generates interview summary report

</details>

<details>
<summary><strong>Is camera demeanor analysis accurate?</strong></summary>

Based on OpenCV and deep learning models, can detect:
- Expression recognition (smile, tension, confusion, etc.)
- Eye contact (whether looking at camera)
- Head posture (nodding, shaking head, tilting head, etc.)
- Comprehensive score (0-100 points)

Accuracy depends on lighting, camera quality, and other factors. Recommended for use in well-lit environments.

</details>

<details>
<summary><strong>Does it support Linux/Mac?</strong></summary>

Yes, but requires manual configuration:
- **Linux** — Need to install Chrome/Chromium, modify browser path in `config.py`
- **Mac** — Need to install Chrome, may need to adjust permission settings
- **Windows** — Ready to use out of the box, project includes pre-configured Chrome kernel

Recommended for use on Windows for best experience.

</details>

<details>
<summary><strong>Will data be uploaded to the cloud?</strong></summary>

No. All data is stored locally in the `data/` directory, not uploaded to any cloud service. You have complete control over your job search data.

</details>

---

## Contributing

This project was created to help job seekers. If you have ideas or encounter problems, welcome to:

- 📝 **Submit Issues** — Report bugs or propose features
- 🔧 **Submit PRs** — Improve code, optimize algorithms, add new features
- 💬 **Discuss** — Share your job search experience and improvement suggestions

[Issues](https://github.com/yourusername/CareerAI/issues) · [Pull Requests](https://github.com/yourusername/CareerAI/pulls)

---

## ⭐ Why Worth Starring

- 📊 **Real Data** — Based on Boss Zhipin real-time data, not guesswork advice
- 🤖 **AI Companion** — From analysis to interview, AI throughout the job search process
- 🎯 **Precise Matching** — RAG technology ensures position recommendation accuracy
- 🔄 **Continuous Iteration** — Algorithms continuously optimized as recruitment market changes

Star it so you can find it next time you're job hunting. ⭐

---

## Acknowledgments

Thanks to the following open-source projects:

- [Flask](https://flask.palletsprojects.com/) — Web framework
- [OpenCV](https://opencv.org/) — Computer vision
- [LangChain](https://www.langchain.com/) — LLM application framework
- [Chroma](https://www.trychroma.com/) — Vector database
- [Anthropic Claude](https://www.anthropic.com/) — AI model

---

## Contact

- 📧 **Email** — yf2678045931@outlook.com

> Bug reports and feature requests please use [GitHub Issues](https://github.com/yourusername/CareerAI/issues), easier to track.

---

## License

[MIT](LICENSE)

---

## ⚠️ Disclaimer

This project is for career planning assistance and academic exchange only, does not represent final hiring results. Please refer cautiously based on actual circumstances.

<p align="center">Made with ❤️ by CareerAI Team</p>
