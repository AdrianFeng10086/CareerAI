const statusEl = document.getElementById("app-status");
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
let currentReport = { name: "", content: "", mode: "render" };
let activeTaskId = "";
let activeTaskLastEventId = 0;
let reassureTimer = null;
let reassureIndex = 0;
let lastServerProgressMsg = "";
let hasBossCookie = false;
let mcpLoginTaskId = "";
let mcpLoginPolling = false;
let mcpQrWindow = null;
let mcpScanHandled = false;

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
    document.querySelectorAll(".panel").forEach((panel) => {
        panel.classList.remove("open");
        panel.setAttribute("aria-hidden", "true");
    });
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
        hasBossCookie = !!data.has_cookie;
        statusEl.textContent = [
            data.has_cookie ? "Boss: 已登录" : "Boss: 未登录",
            data.ai_configured ? `AI: ${data.ai_model}` : "AI: 未配置Key(将走规则解析)",
        ].join(" | ");
        return data;
    } catch (err) {
        statusEl.textContent = `状态异常: ${err.message}`;
        return { ok: false, has_cookie: false };
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
    reportViewerEl.classList.remove("viewer-html");
    reportViewerEl.classList.add("viewer-markdown");

    const toolbar = `
        <div class="md-toolbar">
            <button class="md-tool-btn active" data-md-mode="render">渲染视图</button>
            <button class="md-tool-btn" data-md-mode="raw">原文视图</button>
        </div>
    `;

    // 优先使用后端渲染结果，确保离线/CDN不可达时仍可展示。
    if (renderedHtml) {
        const tableWrappedHtml = wrapTables(renderedHtml);
        const safeHtml = window.DOMPurify
            ? window.DOMPurify.sanitize(tableWrappedHtml)
            : tableWrappedHtml;
        reportViewerEl.innerHTML = `${toolbar}<article class="report-rendered markdown-body">${safeHtml}</article>`;
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
        const rawHtml = md.render(source);
        const tableWrappedHtml = wrapTables(rawHtml);
        const safeHtml = window.DOMPurify
            ? window.DOMPurify.sanitize(tableWrappedHtml)
            : tableWrappedHtml;
        reportViewerEl.innerHTML = `${toolbar}<article class=\"report-rendered markdown-body\">${safeHtml}</article>`;
        bindMdToolbar();
        return;
    }

    if (window.marked && typeof window.marked.parse === "function") {
        window.marked.setOptions({ gfm: true, breaks: true, mangle: false, headerIds: false });
        const rawHtml = window.marked.parse(source);
        const tableWrappedHtml = wrapTables(rawHtml);
        const safeHtml = window.DOMPurify
            ? window.DOMPurify.sanitize(tableWrappedHtml)
            : tableWrappedHtml;
        reportViewerEl.innerHTML = `${toolbar}<article class=\"report-rendered markdown-body\">${safeHtml}</article>`;
        bindMdToolbar();
        return;
    }

    reportViewerEl.innerHTML = `${toolbar}<pre class=\"report-plain\">${escapeHtml(source)}</pre>`;
    bindMdToolbar();
}

function wrapTables(html) {
    return html
        .replace(/<table>/g, '<div class="table-wrap"><table>')
        .replace(/<\/table>/g, "</table></div>");
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
        if (!hasBossCookie) {
            openAuthModal();
            setAuthState("请先完成 MCP 登录后再查看报告。");
            return;
        }
        openPanel("reports-panel");
        await loadReports();
    });

    document.getElementById("open-chat")?.addEventListener("click", () => {
        if (!hasBossCookie) {
            openAuthModal();
            setAuthState("请先完成 MCP 登录后再开始对话。");
            return;
        }
        openPanel("chat-panel");
    });

    document.getElementById("open-auth-modal")?.addEventListener("click", () => {
        openAuthModal();
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

}

window.addEventListener("DOMContentLoaded", async () => {
    typeTitle();
    bindEvents();
    const status = await loadStatus();
    await loadReports();
    if (status.has_cookie) {
        setAuthState("您已登录，进入首页。", "可以直接开始对话查询和生成报告。");
        pushMessage("您已登录，进入首页。", "bot");
    } else {
        openAuthModal();
        setAuthState(
            "检测到你尚未登录 Boss，请点击按钮开始 MCP 扫码登录。",
            "二维码会在新窗口打开，扫码后会自动关闭新窗口并回到本页面等待 Cookie 获取完成。"
        );
    }
    pushMessage("欢迎来到职探AI。你可以直接输入: 搜索北京Python开发3页并分析出报告", "bot");
});
