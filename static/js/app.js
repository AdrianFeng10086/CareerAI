const statusEl = document.getElementById("app-status");
const topUserNameEl = document.getElementById("top-user-name");
const typingTitle = document.getElementById("typing-title");
const reportListEl = document.getElementById("report-list");
const reportViewerEl = document.getElementById("report-viewer");
const chatMessagesEl = document.getElementById("chat-messages");
const taskProgressEl = document.getElementById("task-progress");
const taskProgressStageEl = document.getElementById("task-progress-stage");
const taskProgressPctEl = document.getElementById("task-progress-pct");
const taskProgressMsgEl = document.getElementById("task-progress-msg");
const taskProgressBarEl = document.getElementById("task-progress-bar");
const authModalEl = document.getElementById("mcp-auth-modal");
const authStateTextEl = document.getElementById("auth-state-text");
const authHintTextEl = document.getElementById("auth-hint-text");
const accountModalEl = document.getElementById("account-auth-modal");
const accountStateTextEl = document.getElementById("account-state-text");
const accountHintTextEl = document.getElementById("account-hint-text");
const accountUsernameEl = document.getElementById("account-username");
const accountPasswordEl = document.getElementById("account-password");
const careerStudentTextEl = document.getElementById("career-student-text");
const careerMatchStatusEl = document.getElementById("career-match-status");
const careerPathStatusEl = document.getElementById("career-path-status");
const careerAdviceStatusEl = document.getElementById("career-advice-status");
const careerHintEl = document.getElementById("career-hint");
const careerTaskProgressEl = document.getElementById("career-task-progress");
const careerProgressStageEl = document.getElementById("career-progress-stage");
const careerProgressPctEl = document.getElementById("career-progress-pct");
const careerProgressMsgEl = document.getElementById("career-progress-msg");
const careerProgressBarEl = document.getElementById("career-progress-bar");
const careerStreamBodyEl = document.getElementById("career-stream-body");
const careerStreamStateEl = document.getElementById("career-stream-state");
const careerZoneModalEl = document.getElementById("career-zone-modal");
const careerZoneModalTitleEl = document.getElementById("career-zone-modal-title");
const careerZoneModalBodyEl = document.getElementById("career-zone-modal-body");
const careerZoneModalCloseEl = document.getElementById("career-zone-modal-close");
const interviewMetaEl = document.getElementById("interview-meta");
const interviewResumeTextEl = document.getElementById("interview-resume-text");
const interviewProgressEl = document.getElementById("interview-progress");
const interviewDepthFlagEl = document.getElementById("interview-depth-flag");
const interviewQuestionTitleEl = document.getElementById("interview-question-title");
const interviewSubListEl = document.getElementById("interview-sub-list");
const interviewAnswerInputEl = document.getElementById("interview-answer-input");
const interviewLogEl = document.getElementById("interview-log");
const interviewFeedbackEl = document.getElementById("interview-feedback");
const interviewFeedbackBodyEl = document.getElementById("interview-feedback-body");
let currentReport = { name: "", content: "", mode: "render" };
let activeTaskId = "";
let activeTaskLastEventId = 0;
let latestCareerAnalysis = null;
let careerStreamingAbortController = null;
let reassureTimer = null;
let reassureIndex = 0;
let lastServerProgressMsg = "";
let hasBossCookie = false;
let isLoggedIn = false;
let currentUsername = "";
let mcpLoginTaskId = "";
let mcpLoginPolling = false;
let mcpQrWindow = null;
let mcpScanHandled = false;
let careerStreamMarkdownBuffer = "";
let careerStreamRenderTimer = null;
const careerZoneCache = { match: "", path: "", advice: "" };
let mermaidReady = false;
let radarFallbackCounter = 0;
let interviewSessionId = "";
let interviewCurrentQuestion = null;
let interviewTotalQuestions = 0;
let interviewAnsweredCount = 0;

const STAGE_LABELS = {
    queued: "任务排队",
    "ai.intent.start": "AI调用: 意图解析",
    "ai.intent.done": "AI调用: 意图解析完成",
    "rule.intent.start": "规则解析: 意图解析",
    "rule.intent.done": "规则解析: 意图解析完成",
    "intent.start": "理解需求",
    "intent.done": "需求理解完成",
    profile: "解析个人经历",
    prepare: "准备抓取",
    "scraping.page": "抓取职位中",
    "save-data": "保存原始数据",
    "analyzing.start": "开始分析",
    "analyze.aggregate": "统计聚合",
    "ai.deep.start": "AI调用: 深度分析",
    "ai.deep.done": "AI调用: 深度分析完成",
    "analyze.prepare-ai": "准备AI洞察",
    "analyze.done": "分析完成",
    "report.start": "生成报告",
    "report.init": "初始化PDF",
    "report.summary": "写入摘要",
    "report.table": "排版职位表格",
    "report.ai": "排版AI洞察",
    "report.done": "PDF生成完成",
    "retry.wind-control": "风控触发，自动重试",
    finalizing: "整理结果",
    done: "已完成",
    failed: "执行失败",
};

const REASSURE_MESSAGES = [
    "请放心，任务仍在正常进行中。",
    "正在尽量保证分析质量，稍慢一些是正常的。",
    "我们会结合你的经历给出更贴合的建议。",
    "报告排版阶段通常比抓取阶段更耗时，请再稍等片刻。",
    "你无需重复提交，当前任务会持续执行直到完成。",
];

function typeTitle() {
    const targetText = typingTitle?.dataset.text || "职探AI";
    if (!typingTitle) {
        return;
    }

    typingTitle.textContent = "";
    let idx = 0;
    const timer = setInterval(() => {
        typingTitle.textContent += targetText[idx] || "";
        idx += 1;
        if (idx >= targetText.length) {
            clearInterval(timer);
        }
    }, 190);
}

function openPanel(id) {
    const activeCareerPanel = document.getElementById("career-panel");
    const isCareerOpen = activeCareerPanel?.classList.contains("open");
    document.querySelectorAll(".panel").forEach((panel) => {
        panel.classList.remove("open");
        panel.setAttribute("aria-hidden", "true");
    });

    if (isCareerOpen && id !== "career-panel") {
        resetCareerPanelState();
    }

    const panel = document.getElementById(id);
    if (panel) {
        panel.classList.add("open");
        panel.setAttribute("aria-hidden", "false");
    }
}

function closePanel(id) {
    const panel = document.getElementById(id);
    if (panel) {
        panel.classList.remove("open");
        panel.setAttribute("aria-hidden", "true");
    }

    if (id === "career-panel") {
        resetCareerPanelState();
    }

    if (id === "interview-panel") {
        resetInterviewPanelState();
    }
}

function setInterviewMeta(text, isError = false) {
    if (!interviewMetaEl) {
        return;
    }
    interviewMetaEl.textContent = String(text || "");
    interviewMetaEl.style.color = isError ? "#ffc4c4" : "";
}

function appendInterviewLog(text, type = "bot") {
    if (!interviewLogEl) {
        return;
    }
    const row = document.createElement("div");
    row.className = `interview-log-item ${type}`;
    row.textContent = String(text || "");
    interviewLogEl.appendChild(row);
    interviewLogEl.scrollTop = interviewLogEl.scrollHeight;
}

function renderInterviewQuestion(current, total) {
    interviewCurrentQuestion = current || null;
    interviewTotalQuestions = Number(total || interviewTotalQuestions || 0);

    if (!current) {
        if (interviewProgressEl) {
            interviewProgressEl.textContent = "进度: 0 / 0";
        }
        if (interviewDepthFlagEl) {
            interviewDepthFlagEl.textContent = "普通问题";
        }
        if (interviewQuestionTitleEl) {
            interviewQuestionTitleEl.textContent = "等待开始面试...";
        }
        if (interviewSubListEl) {
            interviewSubListEl.innerHTML = "";
        }
        return;
    }

    const index = Number(current.index || 1);
    if (interviewProgressEl) {
        interviewProgressEl.textContent = `进度: ${index} / ${interviewTotalQuestions}`;
    }
    if (interviewDepthFlagEl) {
        interviewDepthFlagEl.textContent = current.is_deep ? "深度问题" : "普通问题";
    }
    if (interviewQuestionTitleEl) {
        interviewQuestionTitleEl.textContent = String(current.question || "");
    }

    const subs = Array.isArray(current.sub_questions) ? current.sub_questions : [];
    if (interviewSubListEl) {
        interviewSubListEl.innerHTML = subs.map((x) => `<li>${escapeHtml(String(x || ""))}</li>`).join("");
    }
}

function renderInterviewFeedback(feedback) {
    if (!interviewFeedbackEl || !interviewFeedbackBodyEl) {
        return;
    }
    const summary = feedback?.summary || {};
    const strengths = Array.isArray(feedback?.strengths) ? feedback.strengths : [];
    const gaps = Array.isArray(feedback?.gaps) ? feedback.gaps : [];
    const actions = Array.isArray(feedback?.action_items) ? feedback.action_items : [];

    interviewFeedbackBodyEl.innerHTML = `
        <div class="interview-feedback-grid">
            <div><b>目标岗位</b> ${escapeHtml(String(summary.target_role || "-"))}</div>
            <div><b>题目数量</b> ${Number(summary.total_questions || 0)}</div>
            <div><b>完整回答</b> ${Number(summary.complete_answers || 0)}</div>
            <div><b>回答欠缺</b> ${Number(summary.incomplete_answers || 0)}</div>
            <div><b>深度题完成</b> ${Number(summary.deep_complete || 0)} / ${Number(summary.deep_questions || 0)}</div>
            <div><b>平均分</b> ${Number(summary.average_score || 0)}</div>
        </div>
        <p class="interview-overall">${escapeHtml(String(feedback?.overall_comment || ""))}</p>
        <div class="interview-feedback-columns">
            <div>
                <h5>优势</h5>
                <ul>${strengths.map((x) => `<li>${escapeHtml(String(x || ""))}</li>`).join("")}</ul>
            </div>
            <div>
                <h5>待补齐</h5>
                <ul>${gaps.map((x) => `<li>${escapeHtml(String(x || ""))}</li>`).join("")}</ul>
            </div>
            <div>
                <h5>行动建议</h5>
                <ul>${actions.map((x) => `<li>${escapeHtml(String(x || ""))}</li>`).join("")}</ul>
            </div>
        </div>
    `;
    interviewFeedbackEl.hidden = false;
}

function resetInterviewPanelState() {
    interviewSessionId = "";
    interviewCurrentQuestion = null;
    interviewTotalQuestions = 0;
    interviewAnsweredCount = 0;
    if (interviewResumeTextEl) {
        interviewResumeTextEl.value = "";
    }
    if (interviewAnswerInputEl) {
        interviewAnswerInputEl.value = "";
    }
    if (interviewLogEl) {
        interviewLogEl.innerHTML = "";
    }
    if (interviewFeedbackEl) {
        interviewFeedbackEl.hidden = true;
    }
    if (interviewFeedbackBodyEl) {
        interviewFeedbackBodyEl.innerHTML = "";
    }
    setInterviewMeta("请先上传简历，然后点击“开始面试”。");
    renderInterviewQuestion(null, 0);
}

async function parseInterviewResume(file) {
    if (!file) {
        return;
    }
    const formData = new FormData();
    formData.append("file", file);
    setInterviewMeta("正在解析简历...");

    try {
        const resp = await fetch("/api/interview/resume/parse", {
            method: "POST",
            body: formData,
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.error || "简历解析失败");
        }

        if (interviewResumeTextEl) {
            const cur = interviewResumeTextEl.value.trim();
            interviewResumeTextEl.value = cur ? `${cur}\n\n${data.text}` : String(data.text || "");
        }
        setInterviewMeta(`简历解析成功: ${data.filename}`);
    } catch (err) {
        setInterviewMeta(`简历解析失败: ${err.message}`, true);
    }
}

async function startInterview() {
    const resumeText = String(interviewResumeTextEl?.value || "").trim();
    if (!resumeText) {
        setInterviewMeta("请先上传或粘贴简历文本。", true);
        return;
    }

    try {
        setInterviewMeta("正在生成面试题...");
        if (interviewLogEl) {
            interviewLogEl.innerHTML = "";
        }
        if (interviewFeedbackEl) {
            interviewFeedbackEl.hidden = true;
        }

        const resp = await fetch("/api/interview/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ resume_text: resumeText, question_count: 10 }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.error || "面试启动失败");
        }

        interviewSessionId = String(data.session_id || "");
        interviewTotalQuestions = Number(data.total_questions || 0);
        interviewAnsweredCount = 0;
        renderInterviewQuestion(data.current, interviewTotalQuestions);
        appendInterviewLog(`面试开始，目标岗位: ${data.target_role || "目标岗位"}`);
        appendInterviewLog(`第1题: ${data.current?.question || ""}`);
        setInterviewMeta(`已生成 ${interviewTotalQuestions} 题（深度题 ${Number(data.deep_questions || 0)} 题）。`);
    } catch (err) {
        setInterviewMeta(`面试启动失败: ${err.message}`, true);
    }
}

function formatMissingSubQuestions(evaluation) {
    const missing = Array.isArray(evaluation?.missing_sub_questions) ? evaluation.missing_sub_questions : [];
    if (!missing.length) {
        return "";
    }
    return `未覆盖小问题: ${missing.join("；")}`;
}

async function submitInterviewAnswer() {
    if (!interviewSessionId) {
        setInterviewMeta("请先开始面试。", true);
        return;
    }
    const answer = String(interviewAnswerInputEl?.value || "").trim();
    if (!answer) {
        setInterviewMeta("请输入回答内容后再提交。", true);
        return;
    }

    try {
        appendInterviewLog(`我的回答: ${answer}`, "user");
        const resp = await fetch("/api/interview/answer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: interviewSessionId, answer }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.error || "回答提交失败");
        }

        const evalResult = data.evaluation || {};
        const quality = Number(evalResult.quality_score || 0);
        const statusText = evalResult.status === "complete" ? "回答完整" : "回答不完全/回答欠缺";
        const missingText = formatMissingSubQuestions(evalResult);
        appendInterviewLog(
            `评估: ${statusText}（质量分: ${quality}）${missingText ? ` | ${missingText}` : ""}`
        );

        if (data.status === "needs_completion") {
            renderInterviewQuestion(data.current, interviewTotalQuestions);
            setInterviewMeta("请先补充当前题缺失的小问题，再继续下一题。", true);
            appendInterviewLog("请继续补充当前题答案。", "bot");
            if (interviewAnswerInputEl) {
                interviewAnswerInputEl.value = "";
            }
            return;
        }

        if (data.status === "next_question") {
            interviewAnsweredCount = Number(data.progress?.answered || interviewAnsweredCount + 1);
            renderInterviewQuestion(data.current, interviewTotalQuestions);
            appendInterviewLog(`下一题: ${data.current?.question || ""}`, "bot");
            setInterviewMeta(`当前进度 ${interviewAnsweredCount} / ${interviewTotalQuestions}`);
            if (interviewAnswerInputEl) {
                interviewAnswerInputEl.value = "";
            }
            return;
        }

        if (data.status === "finished") {
            interviewAnsweredCount = Number(data.progress?.answered || interviewTotalQuestions);
            renderInterviewQuestion(null, interviewTotalQuestions);
            renderInterviewFeedback(data.feedback || {});
            setInterviewMeta("模拟面试已完成，已生成反馈。");
            appendInterviewLog("面试结束，反馈已生成。", "bot");
            if (interviewAnswerInputEl) {
                interviewAnswerInputEl.value = "";
            }
            return;
        }

        setInterviewMeta("已提交回答。", false);
    } catch (err) {
        setInterviewMeta(`提交失败: ${err.message}`, true);
    }
}

function pushMessage(text, type = "bot") {
    const div = document.createElement("div");
    div.className = `msg ${type}`;
    div.textContent = text;
    chatMessagesEl.appendChild(div);
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

async function loadStatus() {
    try {
        const resp = await fetch("/api/status");
        const data = await resp.json();
        if (!data.ok) {
            throw new Error("状态读取失败");
        }
        isLoggedIn = !!data.logged_in;
        currentUsername = String(data.username || "");
        hasBossCookie = !!data.has_cookie;
        statusEl.textContent = [
            isLoggedIn ? `账号: ${currentUsername}` : "账号: 未登录",
            data.has_cookie ? "Boss: 已登录" : "Boss: 未登录",
            data.ai_configured ? `AI: ${data.ai_model}` : "AI: 未配置Key(将走规则解析)",
        ].join(" | ");
        if (topUserNameEl) {
            topUserNameEl.textContent = isLoggedIn ? `账号: ${currentUsername}` : "账号: 未登录";
        }
        return data;
    } catch (err) {
        isLoggedIn = false;
        currentUsername = "";
        statusEl.textContent = `状态异常: ${err.message}`;
        return { ok: false, has_cookie: false, logged_in: false };
    }
}

function setAccountState(text, hint = "") {
    if (accountStateTextEl) {
        accountStateTextEl.textContent = String(text || "");
    }
    if (accountHintTextEl && hint) {
        accountHintTextEl.textContent = String(hint || "");
    }
}

function clearAccountInputs() {
    if (accountUsernameEl) {
        accountUsernameEl.value = "";
    }
    if (accountPasswordEl) {
        accountPasswordEl.value = "";
    }
}

function openAccountModal() {
    if (!accountModalEl) {
        return;
    }
    accountModalEl.classList.add("open");
    accountModalEl.setAttribute("aria-hidden", "false");
}

function closeAccountModal() {
    if (!accountModalEl) {
        return;
    }
    accountModalEl.classList.remove("open");
    accountModalEl.setAttribute("aria-hidden", "true");
}

function requireAccountLogin(reasonText = "请先登录账号。") {
    if (isLoggedIn) {
        return true;
    }
    setAccountState(reasonText, "正在跳转到登录页...");
    window.location.href = "/login";
    return false;
}

async function handleAccountRegister() {
    const username = String(accountUsernameEl?.value || "").trim();
    const password = String(accountPasswordEl?.value || "");
    if (!username || !password) {
        setAccountState("请输入用户名和密码。", "用户名支持字母数字下划线，密码至少6位。", true);
        return;
    }

    try {
        const resp = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.message || "注册失败");
        }
        setAccountState("注册成功，请点击登录。", "账号重复会被拦截，密码采用哈希加密存储。", false);
    } catch (err) {
        setAccountState(`注册失败: ${err.message}`);
    }
}

async function handleAccountLogin() {
    const username = String(accountUsernameEl?.value || "").trim();
    const password = String(accountPasswordEl?.value || "");
    if (!username || !password) {
        setAccountState("请输入用户名和密码。", "用户名支持字母数字下划线，密码至少6位。", true);
        return;
    }

    try {
        const resp = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.message || "登录失败");
        }
        await loadStatus();
        setAccountState(`已登录: ${data.user?.username || username}`, "现在可使用全部功能。", false);
        closeAccountModal();
        await loadReports();
    } catch (err) {
        setAccountState(`登录失败: ${err.message}`);
    }
}

async function handleAccountLogout() {
    try {
        await fetch("/api/auth/logout", { method: "POST" });
        clearAccountInputs();
        isLoggedIn = false;
        currentUsername = "";
        window.location.href = "/login";
    } catch (err) {
        setAccountState(`退出失败: ${err.message}`);
    }
}

function openAuthModal() {
    if (!authModalEl) {
        return;
    }
    authModalEl.classList.add("open");
    authModalEl.setAttribute("aria-hidden", "false");
}

function closeAuthModal() {
    if (!authModalEl) {
        return;
    }
    if (!hasBossCookie) {
        return;
    }
    authModalEl.classList.remove("open");
    authModalEl.setAttribute("aria-hidden", "true");
}

function setAuthState(text, hint = "") {
    if (authStateTextEl) {
        authStateTextEl.textContent = text;
    }
    if (authHintTextEl && hint) {
        authHintTextEl.textContent = hint;
    }
}

function closeQrWindow() {
    if (mcpQrWindow && !mcpQrWindow.closed) {
        mcpQrWindow.close();
    }
}

function openQrWindow(qrUrl) {
    if (!qrUrl) {
        return;
    }
    const win = window.open(qrUrl, "boss_mcp_qr", "width=420,height=540,resizable=yes,scrollbars=yes");
    if (win) {
        mcpQrWindow = win;
    } else {
        pushMessage("二维码窗口被浏览器拦截，请允许弹窗后重试。", "error");
    }
}

async function startMcpLoginFlow() {
    if (mcpLoginPolling) {
        return;
    }

    try {
        setAuthState("正在启动 MCP 登录流程...");
        const resp = await fetch("/api/boss/mcp-login/start", { method: "POST" });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.message || "MCP 登录启动失败");
        }

        if (data.already_logged_in) {
            hasBossCookie = true;
            setAuthState("您已登录，进入首页。", "可以直接开始对话查询和生成报告。");
            closeAuthModal();
            await loadStatus();
            return;
        }

        mcpLoginTaskId = data.task_id;
        mcpScanHandled = false;
        openQrWindow(data.qr_url);
        setAuthState(
            "二维码已在新窗口打开，请使用 Boss 直聘 APP 扫码。",
            "检测到扫码后将自动关闭二维码窗口，并在当前页面继续等待 Cookie 获取完成。"
        );
        await pollMcpLoginTask(mcpLoginTaskId);
    } catch (err) {
        setAuthState(`登录启动失败: ${err.message}`);
        pushMessage(`MCP 登录失败: ${err.message}`, "error");
    }
}

async function pollMcpLoginTask(taskId) {
    mcpLoginPolling = true;
    let guard = 0;
    try {
        while (taskId && taskId === mcpLoginTaskId && guard < 720) {
            guard += 1;
            const resp = await fetch(`/api/boss/mcp-login/task/${encodeURIComponent(taskId)}`);
            const data = await resp.json();
            if (!resp.ok || !data.ok || !data.task) {
                throw new Error(data.message || "登录状态获取失败");
            }

            const task = data.task;
            const step = String(task.step || "");
            const msg = String(task.message || "登录进行中...");
            setAuthState(msg);

            if (step === "scanned" && !mcpScanHandled) {
                mcpScanHandled = true;
                closeQrWindow();
                setAuthState(
                    "已检测到你完成扫码，二维码窗口已关闭。",
                    "正在回到主界面继续等待登录凭证写入，请稍候。"
                );
            }

            if (task.status === "done" && step === "logged_in") {
                closeQrWindow();
                hasBossCookie = true;
                await loadStatus();
                setAuthState("您已登录，进入首页。", "现在可以直接开始对话查询岗位。");
                closeAuthModal();
                pushMessage("MCP 登录成功，Cookie 获取完成。", "bot");
                return;
            }

            if (task.status === "failed") {
                closeQrWindow();
                throw new Error(msg || "MCP 登录失败");
            }

            await new Promise((resolve) => setTimeout(resolve, 1000));
        }

        throw new Error("登录轮询超时，请重试");
    } catch (err) {
        setAuthState(`MCP 登录失败: ${err.message}`);
        pushMessage(`MCP 登录失败: ${err.message}`, "error");
    } finally {
        mcpLoginPolling = false;
    }
}

async function loadReports() {
    reportListEl.innerHTML = "正在加载报告...";
    try {
        const resp = await fetch("/api/reports");
        const data = await resp.json();

        if (!data.ok) {
            throw new Error(data.message || "报告加载失败");
        }

        if (!data.reports.length) {
            reportListEl.textContent = "暂无历史报告";
            reportViewerEl.textContent = "还没有可展示的报告内容。";
            return;
        }

        reportListEl.innerHTML = "";
        for (const item of data.reports) {
            const btn = document.createElement("button");
            btn.className = "report-item";
            const dateStr = new Date(item.mtime * 1000).toLocaleString();
            btn.innerHTML = `${item.name}<small>${dateStr} | ${Math.round(item.size / 1024)} KB</small>`;
            btn.addEventListener("click", () => showReport(item.name));
            reportListEl.appendChild(btn);
        }

        await showReport(data.reports[0].name);
    } catch (err) {
        reportListEl.textContent = `加载失败: ${err.message}`;
    }
}

async function showReport(name) {
    reportViewerEl.classList.remove("viewer-markdown", "viewer-html");
    reportViewerEl.innerHTML = "<div class=\"report-loading\">正在加载报告内容...</div>";
    try {
        const resp = await fetch(`/api/reports/${encodeURIComponent(name)}`);
        const data = await resp.json();

        if (!data.ok) {
            throw new Error(data.message || "读取报告失败");
        }

        if (data.is_binary && data.suffix === ".pdf") {
            renderPdfReport(data.view_url);
            return;
        }

        renderReportContent(data.name, data.content, data.rendered_html || "");
    } catch (err) {
        reportViewerEl.classList.remove("viewer-markdown", "viewer-html");
        reportViewerEl.innerHTML = `<div class=\"report-error\">读取失败: ${escapeHtml(err.message)}</div>`;
    }
}

function renderPdfReport(viewUrl) {
    reportViewerEl.classList.remove("viewer-markdown");
    reportViewerEl.classList.add("viewer-html");
    const safeUrl = String(viewUrl || "");
    reportViewerEl.innerHTML = `<iframe class="report-iframe" src="${encodeURI(safeUrl)}"></iframe>`;
}

function renderReportContent(name, content, renderedHtml = "") {
    currentReport = { name, content, mode: "render", renderedHtml };
    const lowerName = String(name || "").toLowerCase();
    if (lowerName.endsWith(".html")) {
        renderHtmlReport(content);
        return;
    }
    renderMarkdownReport(content, renderedHtml);
}

function renderHtmlReport(content) {
    reportViewerEl.classList.remove("viewer-markdown");
    reportViewerEl.classList.add("viewer-html");

    const iframe = document.createElement("iframe");
    iframe.className = "report-iframe";
    iframe.setAttribute("sandbox", "allow-same-origin");
    iframe.srcdoc = String(content || "");

    reportViewerEl.innerHTML = "";
    reportViewerEl.appendChild(iframe);
}

function renderMarkdownReport(markdown, renderedHtml = "") {
    const source = String(markdown || "");
    const normalizedSource = normalizeMarkdownTables(source);
    reportViewerEl.classList.remove("viewer-html");
    reportViewerEl.classList.add("viewer-markdown");

    const toolbar = `
        <div class="md-toolbar">
            <button class="md-tool-btn active" data-md-mode="render">渲染视图</button>
            <button class="md-tool-btn" data-md-mode="raw">原文视图</button>
        </div>
    `;

    // 后端已生成 table 时优先复用，避免重复渲染差异。
    if (renderedHtml && /<table[\s>]/i.test(renderedHtml)) {
        const tableWrappedHtml = wrapTables(renderedHtml);
        const safeHtml = window.DOMPurify
            ? window.DOMPurify.sanitize(tableWrappedHtml)
            : tableWrappedHtml;
        reportViewerEl.innerHTML = `${toolbar}<article class="report-rendered markdown-body">${safeHtml}</article>`;
        renderMermaidInContainer(reportViewerEl);
        bindMdToolbar();
        return;
    }

    // 其次使用前端解析器；都不可用时回退为原文。
    if (window.markdownit) {
        const md = window.markdownit({
            html: false,
            linkify: true,
            breaks: true,
            typographer: true,
        });
        const rawHtml = md.render(normalizedSource);
        const tableWrappedHtml = wrapTables(rawHtml);
        const safeHtml = window.DOMPurify
            ? window.DOMPurify.sanitize(tableWrappedHtml)
            : tableWrappedHtml;
        reportViewerEl.innerHTML = `${toolbar}<article class=\"report-rendered markdown-body\">${safeHtml}</article>`;
        renderMermaidInContainer(reportViewerEl);
        bindMdToolbar();
        return;
    }

    if (window.marked && typeof window.marked.parse === "function") {
        window.marked.setOptions({ gfm: true, breaks: true, mangle: false, headerIds: false });
        const rawHtml = window.marked.parse(normalizedSource);
        const tableWrappedHtml = wrapTables(rawHtml);
        const safeHtml = window.DOMPurify
            ? window.DOMPurify.sanitize(tableWrappedHtml)
            : tableWrappedHtml;
        reportViewerEl.innerHTML = `${toolbar}<article class=\"report-rendered markdown-body\">${safeHtml}</article>`;
        renderMermaidInContainer(reportViewerEl);
        bindMdToolbar();
        return;
    }

    reportViewerEl.innerHTML = `${toolbar}<pre class=\"report-plain\">${escapeHtml(normalizedSource)}</pre>`;
    bindMdToolbar();
}

function wrapTables(html) {
    return html
        .replace(/<table>/g, '<div class="table-wrap"><table>')
        .replace(/<\/table>/g, "</table></div>");
}

function isPipeLikeLine(line) {
    const raw = String(line || "");
    const trimmed = raw.replace(/｜/g, "|").trim();
    if (!trimmed || trimmed.startsWith("```")) {
        return false;
    }
    const stripped = trimmed.replace(/^[-*+]\s+/, "");
    return stripped.includes("|");
}

function normalizePipeRow(line) {
    let normalized = String(line || "").replace(/｜/g, "|").trim();
    normalized = normalized.replace(/^[-*+]\s+/, "").trim();

    if (!normalized.startsWith("|")) {
        normalized = `| ${normalized}`;
    }
    if (!normalized.endsWith("|")) {
        normalized = `${normalized} |`;
    }

    const parts = normalized.split("|").map((cell) => cell.trim());
    return parts.slice(1, -1);
}

function isSeparatorCells(cells) {
    return Array.isArray(cells) && cells.length > 0
        && cells.every((cell) => /^:?-{3,}:?$/.test(String(cell || "").trim()));
}

function normalizeMarkdownTables(markdown) {
    const lines = String(markdown || "").replace(/\r\n?/g, "\n").split("\n");
    const out = [];
    let i = 0;
    let inFence = false;

    while (i < lines.length) {
        const line = lines[i];
        const trimmed = String(line || "").trim();

        if (trimmed.startsWith("```")) {
            inFence = !inFence;
            out.push(line);
            i += 1;
            continue;
        }

        if (inFence || !isPipeLikeLine(line)) {
            out.push(line);
            i += 1;
            continue;
        }

        const blockRows = [];
        let j = i;
        while (j < lines.length) {
            const cur = lines[j];
            const curTrimmed = String(cur || "").trim();
            if (!curTrimmed) {
                j += 1;
                continue;
            }
            if (!isPipeLikeLine(cur)) {
                break;
            }
            blockRows.push(cur);
            j += 1;
        }

        if (blockRows.length < 2) {
            out.push(line);
            i += 1;
            continue;
        }

        const parsedRows = blockRows
            .map((row) => normalizePipeRow(row))
            .filter((cells) => cells.length >= 2);

        if (parsedRows.length < 2) {
            out.push(...blockRows);
            i = j;
            continue;
        }

        const colCount = Math.max(...parsedRows.map((cells) => cells.length));
        const paddedRows = parsedRows.map((cells) => {
            const row = cells.slice(0, colCount);
            while (row.length < colCount) {
                row.push("");
            }
            return row;
        });

        const tableLines = [];
        tableLines.push(`| ${paddedRows[0].join(" | ")} |`);

        if (isSeparatorCells(paddedRows[1])) {
            const sep = paddedRows[1].map((cell) => {
                const t = String(cell || "").trim();
                return /^:?-{3,}:?$/.test(t) ? t : "---";
            });
            tableLines.push(`| ${sep.join(" | ")} |`);
            for (let k = 2; k < paddedRows.length; k += 1) {
                tableLines.push(`| ${paddedRows[k].join(" | ")} |`);
            }
        } else {
            tableLines.push(`| ${new Array(colCount).fill("---").join(" | ")} |`);
            for (let k = 1; k < paddedRows.length; k += 1) {
                tableLines.push(`| ${paddedRows[k].join(" | ")} |`);
            }
        }

        out.push(...tableLines);
        i = j;
    }

    return out.join("\n");
}

function bindMdToolbar() {
    reportViewerEl.querySelectorAll(".md-tool-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const mode = btn.dataset.mdMode;
            if (!mode || mode === currentReport.mode) {
                return;
            }
            currentReport.mode = mode;
            if (mode === "raw") {
                renderMarkdownRaw(currentReport.content);
                return;
            }
            renderMarkdownReport(currentReport.content, currentReport.renderedHtml || "");
        });
    });
}

function renderMarkdownRaw(markdown) {
    reportViewerEl.classList.remove("viewer-html");
    reportViewerEl.classList.add("viewer-markdown");
    reportViewerEl.innerHTML = `
        <div class="md-toolbar">
            <button class="md-tool-btn" data-md-mode="render">渲染视图</button>
            <button class="md-tool-btn active" data-md-mode="raw">原文视图</button>
        </div>
        <pre class="report-plain">${escapeHtml(markdown)}</pre>
    `;
    bindMdToolbar();
}

function escapeHtml(text) {
    return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function setCareerHint(text, isError = false) {
    if (!careerHintEl) {
        return;
    }
    careerHintEl.textContent = text || "";
    careerHintEl.style.color = isError ? "#ffc4c4" : "";
}

function setCareerProgress(visible, percent, stage, msg) {
    if (!careerTaskProgressEl) {
        return;
    }
    careerTaskProgressEl.hidden = !visible;
    if (!visible) {
        return;
    }

    const pct = Math.max(0, Math.min(100, Number(percent) || 0));
    if (careerProgressStageEl) {
        careerProgressStageEl.textContent = stage || "职业规划处理中";
    }
    if (careerProgressPctEl) {
        careerProgressPctEl.textContent = `${pct}%`;
    }
    if (careerProgressMsgEl) {
        careerProgressMsgEl.textContent = msg || "";
    }
    if (careerProgressBarEl) {
        careerProgressBarEl.style.width = `${pct}%`;
    }
}

function setHomeStreamState(text) {
    if (!careerStreamStateEl) {
        return;
    }
    careerStreamStateEl.textContent = String(text || "");
}

function renderHomeStreamMarkdown(force = false) {
    if (!careerStreamBodyEl) {
        return;
    }

    if (!force) {
        if (careerStreamRenderTimer) {
            return;
        }
        careerStreamRenderTimer = setTimeout(() => {
            careerStreamRenderTimer = null;
            renderHomeStreamMarkdown(true);
        }, 120);
        return;
    }

    const source = normalizeMarkdownTables(String(careerStreamMarkdownBuffer || ""));
    let rendered = "";

    if (window.markdownit) {
        const md = window.markdownit({
            html: false,
            linkify: true,
            breaks: true,
            typographer: true,
        });
        rendered = md.render(source);
    } else if (window.marked && typeof window.marked.parse === "function") {
        window.marked.setOptions({ gfm: true, breaks: true, mangle: false, headerIds: false });
        rendered = window.marked.parse(source);
    }

    if (rendered) {
        const tableWrappedHtml = wrapTables(rendered);
        const safeHtml = window.DOMPurify
            ? window.DOMPurify.sanitize(tableWrappedHtml)
            : tableWrappedHtml;
        careerStreamBodyEl.innerHTML = `<article class="report-rendered markdown-body">${safeHtml}</article>`;
        renderMermaidInContainer(careerStreamBodyEl);
    } else {
        careerStreamBodyEl.textContent = source;
    }

    careerStreamBodyEl.scrollTop = careerStreamBodyEl.scrollHeight;
}

function normalizeMermaidSource(text) {
    return String(text || "")
        .replace(/[“”]/g, '"')
        .replace(/[‘’]/g, "'")
        .replace(/：/g, ":")
        .replace(/，/g, ",")
        .trim();
}

function parseRadarBetaSource(source) {
    const normalized = normalizeMermaidSource(source);
    const lines = normalized
        .split(/\r?\n/)
        .map((x) => String(x || "").trim())
        .filter((x) => x && !x.startsWith("%%"));

    if (!lines.length || !/^radar-beta\b/i.test(lines[0])) {
        return null;
    }

    const axes = [];
    const datasets = [];
    let title = "能力雷达图";
    let minValue = 0;
    let maxValue = 100;

    for (let i = 1; i < lines.length; i += 1) {
        const line = lines[i];
        if (/^title\s+/i.test(line)) {
            title = line.replace(/^title\s+/i, "").trim().replace(/^"|"$/g, "") || title;
            continue;
        }

        const axisMatch = line.match(/^axis\s+"?([^"\[]+?)"?\s*(?:\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\])?$/i);
        if (axisMatch) {
            const axisName = String(axisMatch[1] || "").trim();
            if (axisName) {
                axes.push(axisName);
            }
            if (axisMatch[2] !== undefined && axisMatch[3] !== undefined) {
                minValue = Number(axisMatch[2]);
                maxValue = Number(axisMatch[3]);
            }
            continue;
        }

        const dsMatch = line.match(/^"?([^":]+?)"?\s*:\s*\[\s*([^\]]+)\s*\]$/);
        if (dsMatch) {
            const name = String(dsMatch[1] || "").trim();
            const values = String(dsMatch[2] || "")
                .split(",")
                .map((x) => Number(String(x).trim()))
                .filter((x) => Number.isFinite(x));
            if (name && values.length) {
                datasets.push({ name, values });
            }
        }
    }

    if (!axes.length || !datasets.length) {
        return null;
    }

    const fixedDatasets = datasets
        .map((ds) => {
            const copy = ds.values.slice(0, axes.length);
            while (copy.length < axes.length) {
                copy.push(minValue);
            }
            return { name: ds.name, values: copy };
        })
        .slice(0, 4);

    if (!Number.isFinite(minValue)) {
        minValue = 0;
    }
    if (!Number.isFinite(maxValue) || maxValue <= minValue) {
        maxValue = 100;
    }

    return {
        title,
        axes,
        datasets: fixedDatasets,
        minValue,
        maxValue,
    };
}

function ensureRadarCanvas(container) {
    const canvas = document.createElement("canvas");
    canvas.height = 320;
    canvas.className = "radar-canvas";
    container.appendChild(canvas);
    return canvas;
}

function buildRadarDatasetStyle(index) {
    const palette = [
        { border: "#43d2ff", fill: "rgba(67, 210, 255, 0.18)" },
        { border: "#33ffca", fill: "rgba(51, 255, 202, 0.18)" },
        { border: "#ff9f43", fill: "rgba(255, 159, 67, 0.16)" },
        { border: "#ff6b6b", fill: "rgba(255, 107, 107, 0.14)" },
    ];
    return palette[index % palette.length];
}

function renderRadarFallbackChart(targetNode, radarModel) {
    if (!targetNode || !radarModel) {
        return;
    }

    const wrap = document.createElement("div");
    wrap.className = "radar-fallback-wrap";
    const title = document.createElement("div");
    title.className = "radar-fallback-title";
    title.textContent = radarModel.title || "能力雷达图";
    wrap.appendChild(title);

    const canvas = ensureRadarCanvas(wrap);
    targetNode.replaceWith(wrap);

    if (!window.Chart) {
        const msg = document.createElement("pre");
        msg.className = "mermaid-fallback";
        msg.textContent = "图表引擎未加载，无法渲染雷达图。";
        wrap.appendChild(msg);
        return;
    }

    radarFallbackCounter += 1;
    const labels = radarModel.axes;
    const datasets = radarModel.datasets.map((item, idx) => {
        const style = buildRadarDatasetStyle(idx);
        return {
            label: item.name,
            data: item.values,
            borderColor: style.border,
            backgroundColor: style.fill,
            pointBackgroundColor: style.border,
            pointBorderColor: "#dff2ff",
            pointRadius: 3,
            borderWidth: 2,
            fill: true,
            tension: 0.2,
        };
    });

    // eslint-disable-next-line no-new
    new window.Chart(canvas, {
        type: "radar",
        data: {
            labels,
            datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: "#dff2ff",
                    },
                },
            },
            scales: {
                r: {
                    min: radarModel.minValue,
                    max: radarModel.maxValue,
                    angleLines: { color: "rgba(67, 210, 255, 0.24)" },
                    grid: { color: "rgba(67, 210, 255, 0.2)" },
                    pointLabels: {
                        color: "#dff2ff",
                        font: { size: 12 },
                    },
                    ticks: {
                        color: "#9cc8da",
                        backdropColor: "transparent",
                    },
                },
            },
        },
    });
}

async function ensureMermaidReady() {
    if (!window.mermaid) {
        return false;
    }
    if (!mermaidReady) {
        window.mermaid.initialize({
            startOnLoad: false,
            securityLevel: "loose",
            theme: "base",
            themeVariables: {
                background: "#071c2e",
                primaryColor: "#0f3958",
                primaryTextColor: "#dff2ff",
                lineColor: "#43d2ff",
                fontFamily: "Noto Sans SC, Microsoft YaHei, sans-serif",
            },
        });
        mermaidReady = true;
    }
    return true;
}

function renderMermaidInContainer(container) {
    if (!container) {
        return;
    }

    const codeNodes = container.querySelectorAll("pre code.language-mermaid, pre code.lang-mermaid");
    if (!codeNodes.length) {
        return;
    }

    const nonRadarNodes = [];

    codeNodes.forEach((code, idx) => {
        const pre = code.closest("pre");
        if (!pre) {
            return;
        }
        const source = normalizeMermaidSource(code.textContent || "");
        if (!source) {
            return;
        }

        const radarModel = parseRadarBetaSource(source);
        if (radarModel) {
            renderRadarFallbackChart(pre, radarModel);
            return;
        }

        const holder = document.createElement("div");
        holder.className = "mermaid";
        holder.id = `mermaid-${Date.now()}-${idx}`;
        holder.textContent = source;
        pre.replaceWith(holder);
        nonRadarNodes.push(holder);
    });

    if (!nonRadarNodes.length) {
        return;
    }

    ensureMermaidReady()
        .then((ok) => {
            if (!ok || !window.mermaid) {
                return;
            }
            return window.mermaid.run({ nodes: nonRadarNodes });
        })
        .catch((err) => {
            console.error("Mermaid 渲染失败:", err);
            nonRadarNodes.forEach((node) => {
                node.classList.add("mermaid-fallback");
            });
        });
}

function appendHomeStreamText(text) {
    if (!careerStreamBodyEl) {
        return;
    }
    const chunk = String(text || "");
    if (!chunk) {
        return;
    }

    if (careerStreamBodyEl.dataset.started !== "1") {
        careerStreamMarkdownBuffer = "";
        careerStreamBodyEl.textContent = "";
        careerStreamBodyEl.dataset.started = "1";
    }

    careerStreamMarkdownBuffer += chunk;
    renderHomeStreamMarkdown(false);
}

function resetHomeStream(message = "这里会实时显示职业规划流式内容与关键进度。") {
    careerStreamMarkdownBuffer = "";
    if (careerStreamRenderTimer) {
        clearTimeout(careerStreamRenderTimer);
        careerStreamRenderTimer = null;
    }
    if (careerStreamBodyEl) {
        careerStreamBodyEl.textContent = message;
        careerStreamBodyEl.dataset.started = "0";
    }
    setHomeStreamState("等待任务开始...");
}

function resetCareerPanelState() {
    if (careerStreamingAbortController) {
        try {
            careerStreamingAbortController.abort();
        } catch (e) {
            // ignore
        }
        careerStreamingAbortController = null;
    }

    latestCareerAnalysis = null;
    if (careerStudentTextEl) {
        careerStudentTextEl.value = "";
    }
    if (careerMatchStatusEl) {
        careerMatchStatusEl.textContent = "等待分析结果...";
    }
    if (careerPathStatusEl) {
        careerPathStatusEl.textContent = "等待路径规划结果...";
    }
    if (careerAdviceStatusEl) {
        careerAdviceStatusEl.textContent = "等待职业建议内容...";
    }
    careerZoneCache.match = "";
    careerZoneCache.path = "";
    careerZoneCache.advice = "";
    closeCareerZoneModal();
    setCareerProgress(false, 0, "", "");
    setCareerHint("提示: 请先通过对话引擎抓取过岗位数据，职业规划会优先使用最新爬虫数据。", false);
    resetHomeStream("这里将持续显示报告流式生成内容。");
}

function closeCareerZoneModal() {
    if (!careerZoneModalEl) {
        return;
    }
    careerZoneModalEl.hidden = true;
    careerZoneModalEl.setAttribute("aria-hidden", "true");
}

function openCareerZoneModal(zone) {
    if (!careerZoneModalEl || !careerZoneModalBodyEl || !careerZoneModalTitleEl) {
        return;
    }
    const key = String(zone || "match");
    const titleMap = {
        match: "岗位匹配详情",
        path: "路径规划详情",
        advice: "职业建议详情",
    };
    const body = careerZoneCache[key] || "暂无可展示内容";
    careerZoneModalTitleEl.textContent = titleMap[key] || "详情";
    careerZoneModalBodyEl.innerHTML = body;
    careerZoneModalEl.hidden = false;
    careerZoneModalEl.setAttribute("aria-hidden", "false");
}

function refreshCareerZoneCache() {
    if (!careerZoneCache.match) {
        careerZoneCache.match = "暂无匹配详情";
    }
    if (!careerZoneCache.path) {
        careerZoneCache.path = "暂无路径详情";
    }
    if (!careerZoneCache.advice) {
        careerZoneCache.advice = "暂无建议详情";
    }
}

function parseStreamEventLine(lineText) {
    const line = String(lineText || "").trim();
    if (!line) {
        return null;
    }

    let payload = line;
    if (line.startsWith("data:")) {
        payload = line.replace(/^data:\s?/, "").trim();
    }

    if (!payload || payload === "[DONE]") {
        return null;
    }

    try {
        return JSON.parse(payload);
    } catch (e) {
        return null;
    }
}

function parseSseBlock(blockText) {
    const block = String(blockText || "");
    if (!block.trim()) {
        return null;
    }

    const dataLines = block
        .split(/\r?\n/)
        .map((line) => String(line || "").trim())
        .filter((line) => line.startsWith("data:"));

    if (!dataLines.length) {
        return null;
    }

    const payload = dataLines
        .map((line) => line.replace(/^data:\s?/, "").trim())
        .join("\n");

    if (!payload || payload === "[DONE]") {
        return null;
    }

    try {
        return JSON.parse(payload);
    } catch (e) {
        return null;
    }
}

function readStreamChunkWithTimeout(reader, timeoutMs) {
    return Promise.race([
        reader.read(),
        new Promise((_, reject) => {
            setTimeout(() => reject(new Error("流式连接长时间无数据返回")), timeoutMs);
        }),
    ]);
}

async function streamCareerReport(payload) {
    careerStreamingAbortController = new AbortController();
    const resp = await fetch("/api/career/report/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: careerStreamingAbortController.signal,
    });

    if (!resp.ok || !resp.body) {
        let errText = "流式报告请求失败";
        try {
            const data = await resp.json();
            errText = data.error || errText;
        } catch (e) {
            // ignore
        }
        throw new Error(errText);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let reportText = "";
    let chunkCount = 0;
    let savedFile = "";
    let savedFiles = null;
    let streamWarning = "";
    let receivedBytes = 0;
    let receivedEvents = 0;

    setHomeStreamState("流式连接已建立");

    const handleEvent = (evt) => {
        if (!evt) {
            return;
        }
        receivedEvents += 1;

        if (evt.type === "stage") {
            const stageMsg = String(evt.message || "正在生成报告...");
            setCareerProgress(true, 60, "职业规划报告流式生成", stageMsg);
            setHomeStreamState(stageMsg);
        } else if (evt.type === "chunk") {
            const chunk = String(evt.content || "");
            reportText += chunk;
            chunkCount += 1;
            const streamingPct = Math.min(95, 60 + Math.floor(chunkCount / 3));
            setCareerProgress(true, streamingPct, "职业规划报告流式生成", "报告内容正在连续输出...");
            setHomeStreamState(`流式输出中 (${streamingPct}%)`);
            appendHomeStreamText(chunk);
        } else if (evt.type === "saved") {
            savedFiles = evt.files || null;
            savedFile = String(evt.default_file || evt.files?.pdf || evt.files?.html || evt.files?.markdown || "");
            setCareerProgress(true, 98, "报告已写入文件", "报告文件已生成，正在收尾...");
        } else if (evt.type === "warn") {
            streamWarning = String(evt.message || "");
            setHomeStreamState("流式完成，但保存有警告");
        } else if (evt.type === "error") {
            setHomeStreamState("流式失败");
            throw new Error(String(evt.message || "流式生成失败"));
        } else if (evt.type === "done") {
            setHomeStreamState("流式输出完成");
        }
    };

    while (true) {
        const { value, done } = await readStreamChunkWithTimeout(reader, 20000);
        if (done) {
            break;
        }

        receivedBytes += value?.byteLength || 0;
        buffer += decoder.decode(value, { stream: true });

        // Prefer SSE framing when available: blocks separated by blank lines.
        if (buffer.includes("data:")) {
            const blocks = buffer.split(/\r?\n\r?\n/);
            buffer = blocks.pop() || "";
            for (const block of blocks) {
                const evt = parseSseBlock(block);
                handleEvent(evt);
            }
            continue;
        }

        // Fallback: NDJSON one-event-per-line.
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || "";
        for (const line of lines) {
            const evt = parseStreamEventLine(line);
            handleEvent(evt);
        }
    }

    // Flush decoder internal buffer for trailing multi-byte characters.
    buffer += decoder.decode();

    if (buffer.trim()) {
        if (buffer.includes("data:")) {
            const evt = parseSseBlock(buffer.trim());
            handleEvent(evt);
        } else {
            const evt = parseStreamEventLine(buffer.trim());
            handleEvent(evt);
        }
    }

    if (receivedBytes > 0 && receivedEvents === 0) {
        const snippet = String(buffer || "").slice(0, 180).replace(/\s+/g, " ").trim();
        throw new Error(`已收到网络数据(${receivedBytes}B)但未解析到事件${snippet ? `，片段: ${snippet}` : ""}`);
    }

    return {
        reportText: reportText.trim(),
        savedFile,
        savedFiles,
        warning: streamWarning,
    };
}

async function fetchCareerReportMarkdown(payload) {
    const resp = await fetch("/api/career/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
        throw new Error(data.error || "报告生成失败");
    }
    return String(data.report_markdown || "").trim();
}

async function autoExportCareerReport(reportText) {
    const markdown = String(reportText || "").trim();
    if (!markdown) {
        return "";
    }

    const reportName = `career_plan_${Date.now()}`;
    const resp = await fetch("/api/career/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report_markdown: markdown, report_name: reportName }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
        throw new Error(data.error || "自动导出失败");
    }
    return data.default_file || data.files?.pdf || "";
}

function renderCareerAdviceText(reportText) {
    const source = String(reportText || "").trim();
    if (!source) {
        return;
    }
    careerZoneCache.advice = `
        <div class="career-report">
            <h3>职业建议原文</h3>
            <pre class="report-plain">${escapeHtml(source)}</pre>
        </div>
    `;
    if (careerAdviceStatusEl) {
        careerAdviceStatusEl.textContent = "建议已生成（PDF导出），点击查看原文";
    }
    refreshCareerZoneCache();
}

function renderCareerResult(data) {
    latestCareerAnalysis = data;

    const dataset = data.dataset || {};
    const datasetSummary = [
        `数据源: ${escapeHtml(dataset.path || "未知")}`,
        `岗位数: ${Number(dataset.job_count || 0)}`,
        `画像数: ${Number(dataset.unique_roles || 0)}`,
    ].join(" | ");

    const matches = Array.isArray(data.matches) ? data.matches : [];
    const verticalGraph = Array.isArray(data.vertical_graph) ? data.vertical_graph : [];
    const transitionGraph = Array.isArray(data.transition_graph) ? data.transition_graph : [];
    const topRows = matches.slice(0, 8).map((m) => {
        const dims = m.dimension_scores || {};
        return `
            <tr>
                <td>${escapeHtml(m.job_title || "-")}</td>
                <td>${Number(m.score || 0).toFixed(1)}</td>
                <td>${Number(dims.professional_skills || 0).toFixed(1)}</td>
                <td>${escapeHtml((m.gap_skills || []).slice(0, 3).join("、") || "-")}</td>
            </tr>
        `;
    }).join("");

    const verticalMenuItems = verticalGraph.slice(0, 10).map((item, idx) => `
        <button class="career-menu-item" data-menu="vertical" data-index="${idx}">
            <span>${escapeHtml(item.job_title || `路径 ${idx + 1}`)}</span>
            <b>${Array.isArray(item.path) ? item.path.length : 0}级</b>
        </button>
    `).join("");

    const transitionMenuItems = transitionGraph.slice(0, 10).map((item, idx) => `
        <button class="career-menu-item" data-menu="transition" data-index="${idx}">
            <span>${escapeHtml(item.job_title || `转岗 ${idx + 1}`)}</span>
            <b>${Array.isArray(item.transitions) ? item.transitions.length : 0}向</b>
        </button>
    `).join("");

    careerZoneCache.match = `
        <div class="career-summary">${datasetSummary}</div>
        <div class="career-metrics">
            <div class="career-metric"><b>匹配岗位</b>${matches.length}</div>
            <div class="career-metric"><b>垂直路径</b>${verticalGraph.length}</div>
            <div class="career-metric"><b>转岗路径</b>${transitionGraph.length}</div>
        </div>
        <table class="career-table">
            <thead>
                <tr>
                    <th>岗位</th>
                    <th>综合匹配</th>
                    <th>技能维度</th>
                    <th>主要缺口</th>
                </tr>
            </thead>
            <tbody>
                ${topRows || "<tr><td colspan=\"4\">暂无匹配结果</td></tr>"}
            </tbody>
        </table>
    `;

    careerZoneCache.path = `
        <div class="career-submenu">
            <div class="career-submenu-head">路径详情</div>
            <div class="career-submenu-tabs">
                <button class="career-submenu-tab active" data-tab="vertical">垂直路径</button>
                <button class="career-submenu-tab" data-tab="transition">转岗路径</button>
            </div>
            <div class="career-submenu-panel active" data-panel="vertical">
                <div class="career-submenu-body">
                    <div class="career-menu-list">${verticalMenuItems || '<div class="career-empty">暂无垂直路径</div>'}</div>
                    <div class="career-menu-detail" id="career-detail-vertical">请选择左侧岗位查看垂直成长路径。</div>
                </div>
            </div>
            <div class="career-submenu-panel" data-panel="transition">
                <div class="career-submenu-body">
                    <div class="career-menu-list">${transitionMenuItems || '<div class="career-empty">暂无转岗路径</div>'}</div>
                    <div class="career-menu-detail" id="career-detail-transition">请选择左侧岗位查看可转岗方向。</div>
                </div>
            </div>
        </div>
    `;

    if (careerMatchStatusEl) {
        careerMatchStatusEl.textContent = `匹配完成: ${matches.length} 个岗位，点击查看详情`;
    }
    if (careerPathStatusEl) {
        careerPathStatusEl.textContent = `路径完成: 垂直 ${verticalGraph.length} / 转岗 ${transitionGraph.length}`;
    }
    if (careerAdviceStatusEl && !String(data.report_markdown || "").trim()) {
        careerAdviceStatusEl.textContent = "建议生成中，稍后可点击查看详情";
    }

    refreshCareerZoneCache();

    if (data.report_markdown) {
        renderCareerAdviceText(data.report_markdown);
    }
}

function renderCareerSecondaryDetail(type, item) {
    if (!item) {
        return "暂无详情";
    }

    if (type === "match") {
        const dims = item.dimension_scores || {};
        const advantages = Array.isArray(item.advantage_skills) ? item.advantage_skills : [];
        const gaps = Array.isArray(item.gap_skills) ? item.gap_skills : [];
        return `
            <h4>${escapeHtml(item.job_title || "目标岗位")}</h4>
            <p>综合匹配: <b>${Number(item.score || 0).toFixed(1)}</b></p>
            <p>基础要求: ${Number(dims.foundation_requirements || 0).toFixed(1)} | 技能: ${Number(dims.professional_skills || 0).toFixed(1)} | 素养: ${Number(dims.professional_quality || 0).toFixed(1)} | 潜力: ${Number(dims.development_potential || 0).toFixed(1)}</p>
            <p>优势能力: ${escapeHtml(advantages.slice(0, 6).join("、") || "暂无")}</p>
            <p>主要缺口: ${escapeHtml(gaps.slice(0, 6).join("、") || "暂无")}</p>
        `;
    }

    if (type === "vertical") {
        const path = Array.isArray(item.path) ? item.path : [];
        const pathHtml = path.length
            ? `<ol>${path.map((p) => `<li>${escapeHtml(p)}</li>`).join("")}</ol>`
            : "暂无路径节点";
        return `
            <h4>${escapeHtml(item.job_title || "垂直路径")}</h4>
            <p>成长路径节点数: <b>${path.length}</b></p>
            <div>${pathHtml}</div>
        `;
    }

    const transitions = Array.isArray(item.transitions) ? item.transitions : [];
    const toHtml = transitions.length
        ? `<ul>${transitions.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>`
        : "暂无可转岗方向";
    return `
        <h4>${escapeHtml(item.job_title || "转岗路径")}</h4>
        <p>可转方向: <b>${transitions.length}</b></p>
        <div>${toHtml}</div>
    `;
}

function bindCareerSecondaryMenu(data) {
    if (!careerZoneModalBodyEl) {
        return;
    }

    const verticalGraph = Array.isArray(data.vertical_graph) ? data.vertical_graph : [];
    const transitionGraph = Array.isArray(data.transition_graph) ? data.transition_graph : [];

    const tabBtns = Array.from(careerZoneModalBodyEl.querySelectorAll(".career-submenu-tab"));
    const tabPanels = Array.from(careerZoneModalBodyEl.querySelectorAll(".career-submenu-panel"));

    tabBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
            const tab = String(btn.dataset.tab || "vertical");
            tabBtns.forEach((x) => x.classList.toggle("active", x === btn));
            tabPanels.forEach((panel) => {
                panel.classList.toggle("active", panel.dataset.panel === tab);
            });
        });
    });

    const map = {
        vertical: { list: verticalGraph, detailId: "career-detail-vertical" },
        transition: { list: transitionGraph, detailId: "career-detail-transition" },
    };

    careerZoneModalBodyEl.querySelectorAll(".career-menu-item").forEach((btn) => {
        btn.addEventListener("click", () => {
            const menu = String(btn.dataset.menu || "vertical");
            const idx = Number(btn.dataset.index || 0);
            const conf = map[menu];
            if (!conf) {
                return;
            }

            const item = conf.list[idx];
            const detailEl = careerZoneModalBodyEl.querySelector(`#${conf.detailId}`);
            if (detailEl) {
                detailEl.innerHTML = renderCareerSecondaryDetail(menu, item);
            }

            careerZoneModalBodyEl
                .querySelectorAll(`.career-menu-item[data-menu=\"${menu}\"]`)
                .forEach((x) => x.classList.remove("active"));
            btn.classList.add("active");
        });
    });

    const initConfigs = [
        { menu: "vertical", detailId: "career-detail-vertical", list: verticalGraph },
        { menu: "transition", detailId: "career-detail-transition", list: transitionGraph },
    ];

    initConfigs.forEach((cfg) => {
        if (!cfg.list.length) {
            return;
        }
        const firstBtn = careerZoneModalBodyEl.querySelector(`.career-menu-item[data-menu=\"${cfg.menu}\"][data-index=\"0\"]`);
        if (firstBtn) {
            firstBtn.classList.add("active");
        }
        const detailEl = careerZoneModalBodyEl.querySelector(`#${cfg.detailId}`);
        if (detailEl) {
            detailEl.innerHTML = renderCareerSecondaryDetail(cfg.menu, cfg.list[0]);
        }
    });
}

async function runCareerAnalyze() {
    if (!careerStudentTextEl) {
        return;
    }

    const text = careerStudentTextEl.value.trim();
    if (!text) {
        setCareerHint("请先输入简历或自我描述。", true);
        return;
    }

    setCareerHint("正在分析中，请稍候...");
    resetHomeStream("职业规划任务已启动，正在准备流式输出...");
    setHomeStreamState("岗位匹配分析中");
    setCareerProgress(true, 5, "职业规划任务启动", "准备读取岗位库并构建画像...");
    if (careerMatchStatusEl) {
        careerMatchStatusEl.textContent = "职业规划分析启动中...";
    }
    if (careerPathStatusEl) {
        careerPathStatusEl.textContent = "正在计算路径规划...";
    }
    if (careerAdviceStatusEl) {
        careerAdviceStatusEl.textContent = "建议生成中...";
    }

    try {
        const resp = await fetch("/api/career/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ student_text: text, include_report: false }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.error || "职业规划分析失败");
        }

        setCareerProgress(true, 55, "岗位匹配分析完成", "正在进入报告流式生成阶段...");
        setHomeStreamState("岗位匹配完成，开始流式报告");
        renderCareerResult(data);

        let reportText = "";
        let exportedFile = "";
        const reportPayload = {
            student_profile: data.student_profile,
            matches: data.matches,
            vertical_graph: data.vertical_graph,
            transition_graph: data.transition_graph,
            auto_export: true,
            report_name: `career_plan_${Date.now()}`,
        };

        try {
            const streamResult = await streamCareerReport(reportPayload);
            reportText = String(streamResult?.reportText || "");
            exportedFile = String(streamResult?.savedFile || "");
            if (streamResult?.warning) {
                setCareerHint(streamResult.warning, true);
            }
        } catch (streamErr) {
            console.error("流式接口异常:", streamErr);
            setCareerHint(`流式生成失败: ${streamErr.message}，已切换兜底模式`, true);
            setHomeStreamState("流式中断，改用稳定模式生成");
            setCareerProgress(true, 70, "流式中断，切换兜底", "正在改用稳定模式生成完整报告...");
            reportText = await fetchCareerReportMarkdown(reportPayload);
            appendHomeStreamText("\n\n[系统提示] 流式中断，已切换兜底模式生成完整报告。\n");
        }



        if (reportText) {
            data.report_markdown = reportText;
            latestCareerAnalysis = data;
            renderCareerAdviceText(reportText);
        }

        if (!exportedFile && reportText) {
            try {
                setCareerProgress(true, 96, "写入报告文件", "正在自动导出报告到 output...");
                exportedFile = await autoExportCareerReport(reportText);
            } catch (exportErr) {
                setCareerHint(`报告已生成，但自动导出失败: ${exportErr.message}`, true);
            }
        }

        await loadReports();

        setCareerProgress(true, 100, "职业规划完成", "职业规划报告已完成，可导出或查看报告中心。");
        setHomeStreamState("任务完成");
        if (exportedFile) {
            setCareerHint(`分析完成，已自动导出: ${exportedFile}`);
            appendHomeStreamText(`\n\n[文件已生成] ${exportedFile}\n`);
        } else {
            setCareerHint("分析完成，可直接导出报告或继续优化文本后重跑。");
        }
    } catch (err) {
        if (careerMatchStatusEl) {
            careerMatchStatusEl.textContent = "分析失败";
        }
        if (careerPathStatusEl) {
            careerPathStatusEl.textContent = "路径规划失败";
        }
        if (careerAdviceStatusEl) {
            careerAdviceStatusEl.textContent = "职业建议失败";
        }
        setCareerProgress(false, 0, "", "");
        setCareerHint(`分析失败: ${err.message}`, true);
        setHomeStreamState("任务失败");
        appendHomeStreamText(`\n\n[错误] ${err.message}\n`);
    } finally {
        careerStreamingAbortController = null;
    }
}

async function exportCareerReport() {
    const reportText = String(latestCareerAnalysis?.report_markdown || "").trim();
    if (!reportText) {
        setCareerHint("当前没有可导出的职业规划报告，请先完成分析。", true);
        return;
    }

    try {
        const reportName = `career_plan_${Date.now()}`;
        const resp = await fetch("/api/career/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ report_markdown: reportText, report_name: reportName }),
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.error || "导出失败");
        }

        const fileName = data.default_file || data.files?.pdf || "";
        if (fileName) {
            window.open(`/api/reports/${encodeURIComponent(fileName)}/raw`, "_blank");
        }
        setCareerHint(`导出成功: ${fileName || "已生成文件"}`);
        await loadReports();
    } catch (err) {
        setCareerHint(`导出失败: ${err.message}`, true);
    }
}

async function parseCareerResume(file) {
    if (!file) {
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    setCareerHint("正在解析简历文件...");

    try {
        const resp = await fetch("/api/career/resume/parse", {
            method: "POST",
            body: formData,
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) {
            throw new Error(data.error || "简历解析失败");
        }

        if (careerStudentTextEl) {
            const current = careerStudentTextEl.value.trim();
            careerStudentTextEl.value = current ? `${current}\n\n${data.text}` : data.text;
        }
        setCareerHint(`简历解析成功: ${data.filename}`);
    } catch (err) {
        setCareerHint(`简历解析失败: ${err.message}`, true);
    }
}

async function sendChatMessage(message) {
    pushMessage(message, "user");

    try {
        const resp = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });
        const data = await resp.json();

        if (!resp.ok || !data.ok) {
            pushMessage(data.message || "执行失败", "error");
            return;
        }

        activeTaskId = data.task_id;
    activeTaskLastEventId = 0;
        setTaskProgress(true, 0, "任务启动", "任务已启动，等待后端响应...");
        startReassureLoop();
        await pollTaskStatus(activeTaskId);
    } catch (err) {
        stopReassureLoop();
        setTaskProgress(false, 0, "", "");
        pushMessage(`请求失败: ${err.message}`, "error");
    }
}

function consumeTaskEvents(task) {
    const events = Array.isArray(task?.events) ? task.events : [];
    for (const evt of events) {
        const evtId = Number(evt?.id) || 0;
        if (evtId <= activeTaskLastEventId) {
            continue;
        }
        activeTaskLastEventId = evtId;
        const kind = evt?.kind === "error" ? "error" : "bot";
        pushMessage(String(evt?.text || ""), kind);
    }
}

function setTaskProgress(visible, percent, stage, msg) {
    if (!taskProgressEl) {
        return;
    }
    taskProgressEl.hidden = !visible;
    if (!visible) {
        return;
    }

    const pct = Math.max(0, Math.min(100, Number(percent) || 0));
    taskProgressStageEl.textContent = STAGE_LABELS[stage] || stage || "处理中";
    taskProgressPctEl.textContent = `${pct}%`;
    lastServerProgressMsg = msg || "";
    taskProgressMsgEl.textContent = lastServerProgressMsg;
    taskProgressBarEl.style.width = `${pct}%`;
}

function startReassureLoop() {
    stopReassureLoop();
    reassureTimer = setInterval(() => {
        if (!taskProgressEl || taskProgressEl.hidden) {
            return;
        }
        reassureIndex = (reassureIndex + 1) % REASSURE_MESSAGES.length;
        const extra = REASSURE_MESSAGES[reassureIndex];
        const base = lastServerProgressMsg || "任务处理中";
        taskProgressMsgEl.textContent = `${base} ${extra}`;
    }, 6500);
}

function stopReassureLoop() {
    if (reassureTimer) {
        clearInterval(reassureTimer);
        reassureTimer = null;
    }
}

async function pollTaskStatus(taskId) {
    let guard = 0;
    while (taskId && taskId === activeTaskId && guard < 720) {
        guard += 1;
        const resp = await fetch(`/api/chat/task/${encodeURIComponent(taskId)}`);
        const data = await resp.json();

        if (!resp.ok || !data.ok || !data.task) {
            stopReassureLoop();
            setTaskProgress(false, 0, "", "");
            pushMessage(data.message || "任务状态获取失败", "error");
            return;
        }

        const task = data.task;
        setTaskProgress(true, task.progress, task.stage, task.message);
        consumeTaskEvents(task);

        if (task.status === "done") {
            stopReassureLoop();
            setTaskProgress(true, 100, "done", "任务完成");
            const result = task.result || {};
            pushMessage(result.message || "任务完成", "bot");
            await loadReports();
            setTimeout(() => setTaskProgress(false, 0, "", ""), 1600);
            return;
        }

        if (task.status === "failed") {
            stopReassureLoop();
            setTaskProgress(false, 0, "", "");
            const message = task.result?.message || task.message || "任务失败";
            pushMessage(message, "error");
            return;
        }

        await new Promise((resolve) => setTimeout(resolve, 900));
    }

    stopReassureLoop();
    setTaskProgress(false, 0, "", "");
    pushMessage("任务轮询超时，请稍后查看报告列表。", "error");
}

function bindEvents() {
    document.getElementById("open-reports")?.addEventListener("click", async () => {
        if (!requireAccountLogin("请先登录账号后再查看报告。")) {
            return;
        }
        if (!hasBossCookie) {
            openAuthModal();
            setAuthState("请先完成 MCP 登录后再查看报告。");
            return;
        }
        openPanel("reports-panel");
        await loadReports();
    });

    document.getElementById("open-chat")?.addEventListener("click", () => {
        if (!requireAccountLogin("请先登录账号后再开始对话。")) {
            return;
        }
        if (!hasBossCookie) {
            openAuthModal();
            setAuthState("请先完成 MCP 登录后再开始对话。");
            return;
        }
        openPanel("chat-panel");
    });

    document.getElementById("open-career")?.addEventListener("click", () => {
        if (!requireAccountLogin("请先登录账号后再使用职业规划。")) {
            return;
        }
        if (!hasBossCookie) {
            openAuthModal();
            setAuthState("请先完成 MCP 登录后再使用职业规划。", "职业规划会读取你抓取的岗位数据。");
            return;
        }
        openPanel("career-panel");
    });

    document.getElementById("open-interview")?.addEventListener("click", () => {
        if (!requireAccountLogin("请先登录账号后再使用模拟面试。")) {
            return;
        }
        if (!hasBossCookie) {
            openAuthModal();
            setAuthState("请先完成 MCP 登录后再使用模拟面试。", "模拟面试会调用 AI 生成题目与反馈。");
            return;
        }
        openPanel("interview-panel");
        if (!interviewSessionId) {
            resetInterviewPanelState();
        }
    });

    document.getElementById("open-account-modal")?.addEventListener("click", () => {
        openAccountModal();
    });

    document.getElementById("top-logout-btn")?.addEventListener("click", async () => {
        await handleAccountLogout();
    });

    document.getElementById("open-mcp-auth-modal")?.addEventListener("click", () => {
        openAuthModal();
    });

    document.getElementById("account-register-btn")?.addEventListener("click", async () => {
        await handleAccountRegister();
    });

    document.getElementById("account-login-btn")?.addEventListener("click", async () => {
        await handleAccountLogin();
    });

    document.getElementById("account-logout-btn")?.addEventListener("click", async () => {
        await handleAccountLogout();
    });

    document.getElementById("close-account-modal")?.addEventListener("click", () => {
        closeAccountModal();
    });

    document.getElementById("start-mcp-login")?.addEventListener("click", async () => {
        await startMcpLoginFlow();
    });

    document.getElementById("close-auth-modal")?.addEventListener("click", () => {
        closeAuthModal();
    });

    document.querySelectorAll("[data-close]").forEach((btn) => {
        btn.addEventListener("click", () => {
            closePanel(btn.dataset.close);
        });
    });

    document.getElementById("chat-form")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const input = document.getElementById("chat-input");
        const text = input.value.trim();
        if (!text) {
            return;
        }
        input.value = "";
        await sendChatMessage(text);
    });

    document.getElementById("career-analyze-btn")?.addEventListener("click", async () => {
        await runCareerAnalyze();
    });

    document.getElementById("career-export-btn")?.addEventListener("click", async () => {
        await exportCareerReport();
    });

    document.getElementById("career-upload-btn")?.addEventListener("click", () => {
        document.getElementById("career-resume-file")?.click();
    });

    document.getElementById("career-resume-file")?.addEventListener("change", async (e) => {
        const file = e.target?.files?.[0];
        await parseCareerResume(file);
        e.target.value = "";
    });

    document.getElementById("career-to-reports-btn")?.addEventListener("click", async () => {
        openPanel("reports-panel");
        await loadReports();
    });

    document.getElementById("interview-upload-btn")?.addEventListener("click", () => {
        document.getElementById("interview-resume-file")?.click();
    });

    document.getElementById("interview-resume-file")?.addEventListener("change", async (e) => {
        const file = e.target?.files?.[0];
        await parseInterviewResume(file);
        e.target.value = "";
    });

    document.getElementById("interview-start-btn")?.addEventListener("click", async () => {
        await startInterview();
    });

    document.getElementById("interview-answer-form")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        await submitInterviewAnswer();
    });

    document.querySelectorAll("[data-zone-open]").forEach((zoneNode) => {
        zoneNode.addEventListener("click", () => {
            const zone = String(zoneNode.getAttribute("data-zone-open") || "match");
            openCareerZoneModal(zone);
            if (zone === "path" && latestCareerAnalysis) {
                bindCareerSecondaryMenu(latestCareerAnalysis);
            }
        });

        if (String(zoneNode.tagName || "").toLowerCase() === "button") {
            return;
        }

        zoneNode.addEventListener("keydown", (evt) => {
            if (evt.key === "Enter" || evt.key === " ") {
                evt.preventDefault();
                const zone = String(zoneNode.getAttribute("data-zone-open") || "match");
                openCareerZoneModal(zone);
                if (zone === "path" && latestCareerAnalysis) {
                    bindCareerSecondaryMenu(latestCareerAnalysis);
                }
            }
        });
    });

    careerZoneModalCloseEl?.addEventListener("click", () => {
        closeCareerZoneModal();
    });

    careerZoneModalEl?.addEventListener("click", (evt) => {
        if (evt.target === careerZoneModalEl) {
            closeCareerZoneModal();
        }
    });

    document.addEventListener("keydown", (evt) => {
        if (evt.key === "Escape") {
            closeCareerZoneModal();
        }
    });

}

window.addEventListener("DOMContentLoaded", async () => {
    typeTitle();
    bindEvents();
    const status = await loadStatus();

    if (!status.logged_in) {
        window.location.href = "/login";
        return;
    } else {
        await loadReports();
    }

    if (status.logged_in && status.has_cookie) {
        setAuthState("您已登录，进入首页。", "可以直接开始对话查询和生成报告。");
        pushMessage(`账号 ${status.username || ""} 已登录，可直接使用系统。`, "bot");
    } else if (status.logged_in) {
        openAuthModal();
        setAuthState(
            "检测到你尚未登录 Boss，请点击按钮开始 MCP 扫码登录。",
            "二维码会在新窗口打开，扫码后会自动关闭新窗口并回到本页面等待 Cookie 获取完成。"
        );
    }
    resetHomeStream("这里将持续显示报告流式生成内容。");
    resetInterviewPanelState();
    pushMessage("欢迎来到职探AI。你可以直接输入: 搜索北京Python开发3页并分析出报告", "bot");
});
