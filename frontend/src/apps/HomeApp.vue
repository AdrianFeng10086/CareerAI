<template>
  <BgLayers />
  <main class="page-wrap">
    <TopBar brand="ZT-AI CORE">
      <StatusBadge
        class="status"
        :status="status"
        :loading="statusLoading"
        :error-message="statusError"
        fallback="系统状态检测中..."
      />
      <button class="ghost-btn" type="button" @click="onLogout">退出账号</button>
      <button class="ghost-btn" type="button" @click="openMcpModal">MCP 登录</button>
    </TopBar>

    <section class="hero">
      <HeroTitle eyebrow="智能求职作战台" title="职探AI" subtitle="智能求职平台，助力职业发展与决策。" />
    </section>

    <section class="module-grid">
      <article class="module-card">
        <h2>查看报告</h2>
        <p>浏览历史分析报告，追踪市场变化与个人策略。</p>
        <button class="module-btn" type="button" @click="openReports">进入报告中心</button>
      </article>

      <article class="module-card">
        <h2>开始对话</h2>
        <p>通过自然语言下达任务: 搜索岗位、分析数据、生成报告。</p>
        <button class="module-btn" type="button" @click="goJob">进入求职作战台</button>
      </article>

      <article class="module-card">
        <h2>职业规划</h2>
        <p>基于岗位数据，生成人岗匹配、路径规划与行动建议。</p>
        <button class="module-btn" type="button" @click="goCareer">进入职业规划</button>
      </article>

      <article class="module-card">
        <h2>模拟面试</h2>
        <p>上传简历后由 AI 担任面试官，围绕目标岗位进行结构化面试与反馈。</p>
        <button class="module-btn" type="button" @click="goInterview">进入面试训练营</button>
      </article>
    </section>
  </main>

  <section
    class="panel"
    :class="{ open: reportsPanelOpen }"
    :aria-hidden="!reportsPanelOpen"
  >
    <div class="panel-header">
      <h3>历史报告中心</h3>
      <button class="panel-close" type="button" @click="closeReportsPanel">关闭</button>
    </div>
    <div class="panel-body reports-layout">
      <div class="report-list">
        <template v-if="reportsLoading">正在加载报告...</template>
        <template v-else-if="reportsError">加载失败: {{ reportsError }}</template>
        <template v-else-if="!reports.length">暂无历史报告</template>
        <button
          v-else
          v-for="item in reports"
          :key="item.name"
          class="report-item"
          :class="{ active: currentReport.name === item.name }"
          type="button"
          @click="onSelectReport(item)"
        >
          {{ stripSuffix(item.name) }}
          <small>{{ formatTime(item.mtime) }} | {{ Math.round(item.size / 1024) }} KB</small>
        </button>
      </div>
    </div>
  </section>

  <section
    class="report-preview-modal"
    :class="{}"
    :hidden="!reportPreviewOpen"
    :aria-hidden="!reportPreviewOpen"
    @click.self="closeReportPreview"
  >
    <div class="report-preview-dialog">
      <div class="report-preview-head">
        <h4>{{ currentReport.title || '报告预览' }}</h4>
        <div class="report-preview-actions">
          <button
            v-if="currentReport.name"
            class="ghost-btn"
            type="button"
            style="margin-right: 10px; padding: 4px 10px; font-size: 13px;"
            @click="exportCurrentPdf"
          >导出 PDF</button>
          <button class="panel-close" type="button" @click="closeReportPreview">关闭</button>
        </div>
      </div>
      <article class="report-viewer" :class="viewerClass">
        <template v-if="viewerState === 'idle'">请选择报告进行预览。</template>
        <template v-else-if="viewerState === 'loading'">
          <div class="report-loading">正在加载报告内容...</div>
        </template>
        <template v-else-if="viewerState === 'error'">
          <div class="report-error">读取失败: {{ viewerError }}</div>
        </template>
        <iframe
          v-else-if="viewerState === 'pdf'"
          class="report-iframe"
          :src="viewerPdfUrl"
        ></iframe>
        <iframe
          v-else-if="viewerState === 'html'"
          class="report-iframe"
          sandbox="allow-same-origin allow-scripts allow-popups allow-popups-to-escape-sandbox"
          :srcdoc="viewerHtml"
        ></iframe>
        <MarkdownView
          v-else-if="viewerState === 'markdown'"
          :source="currentReport.content"
          :pre-rendered="currentReport.renderedHtml"
          root-class="report-rendered markdown-body"
          use-markdown-it
        />
      </article>
    </div>
  </section>

  <section
    class="panel auth-modal"
    :class="{ open: mcpModalOpen }"
    :aria-hidden="!mcpModalOpen"
    @click.self="closeMcpModal"
  >
    <div class="panel-header">
      <h3>MCP 扫码登录</h3>
      <button class="panel-close" type="button" @click="closeMcpModal">关闭</button>
    </div>
    <div class="panel-body auth-layout">
      <div class="auth-state">{{ mcpState }}</div>
      <div class="auth-actions">
        <button
          type="button"
          class="module-btn"
          :disabled="mcpPolling"
          @click="startMcpFlow"
        >打开二维码并开始登录</button>
      </div>
      <div class="auth-hint">{{ mcpHint }}</div>
    </div>
  </section>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import BgLayers from '../components/BgLayers.vue';
import TopBar from '../components/TopBar.vue';
import HeroTitle from '../components/HeroTitle.vue';
import StatusBadge from '../components/StatusBadge.vue';
import MarkdownView from '../components/MarkdownView.vue';
import { fetchStatus, logout } from '../api/auth.js';
import { listReports, fetchReport, downloadReportPdf, reportPdfUrl } from '../api/reports.js';
import { startMcpLogin, fetchMcpTask, mcpQrUrl } from '../api/boss.js';

const status = ref(null);
const statusLoading = ref(true);
const statusError = ref('');
const isLoggedIn = computed(() => !!status.value?.logged_in);
const hasBossCookie = computed(() => !!status.value?.has_cookie);

const reportsPanelOpen = ref(false);
const reportPreviewOpen = ref(false);
const reports = ref([]);
const reportsLoading = ref(false);
const reportsError = ref('');

const currentReport = reactive({ name: '', title: '', content: '', renderedHtml: '' });
const viewerState = ref('idle');
const viewerError = ref('');
const viewerPdfUrl = ref('');
const viewerHtml = ref('');

const mcpModalOpen = ref(false);
const mcpState = ref('正在检测登录状态...');
const mcpHint = ref('将在新窗口打开 Boss 二维码，请使用手机扫码。检测到扫码后会自动关闭二维码窗口，并在本页等待 Cookie 获取完成。');
const mcpPolling = ref(false);
let mcpTaskId = '';
let mcpScanHandled = false;
let mcpQrWindow = null;
let pollAbort = false;

const viewerClass = computed(() => {
  if (viewerState.value === 'pdf' || viewerState.value === 'html') return 'viewer-html';
  if (viewerState.value === 'markdown') return 'viewer-markdown';
  return '';
});

function stripSuffix(name) {
  return String(name || '').replace(/\.[^/.]+$/, '');
}

function formatTime(mtime) {
  if (!mtime) return '';
  return new Date(mtime * 1000).toLocaleString();
}

async function refreshStatus() {
  statusLoading.value = true;
  try {
    const data = await fetchStatus();
    status.value = data;
    statusError.value = '';
    return data;
  } catch (err) {
    statusError.value = err.message || String(err);
    status.value = { ok: false, has_cookie: false, logged_in: false };
    return status.value;
  } finally {
    statusLoading.value = false;
  }
}

function requireLogin(reasonText = '请先登录账号。') {
  if (isLoggedIn.value) return true;
  alert(reasonText + '\n正在跳转到登录页...');
  window.location.href = '/login';
  return false;
}

async function onLogout() {
  try {
    await logout();
  } catch { /* ignore */ }
  window.location.href = '/login';
}

function openMcpModal() {
  mcpModalOpen.value = true;
}

function closeMcpModal() {
  mcpModalOpen.value = false;
}

function setMcpState(text, hint) {
  if (text !== undefined) mcpState.value = text || '';
  if (hint !== undefined && hint) mcpHint.value = hint;
}

function closeQrWindow() {
  if (mcpQrWindow && !mcpQrWindow.closed) {
    try { mcpQrWindow.close(); } catch { /* ignore */ }
  }
  mcpQrWindow = null;
}

function openQrWindow(url) {
  if (!url) return;
  const win = window.open(url, 'boss_mcp_qr', 'width=420,height=540,resizable=yes,scrollbars=yes');
  if (win) mcpQrWindow = win;
}

async function pollMcpTask(taskId) {
  mcpPolling.value = true;
  pollAbort = false;
  let guard = 0;
  try {
    while (taskId && taskId === mcpTaskId && guard < 720 && !pollAbort) {
      guard += 1;
      const data = await fetchMcpTask(taskId);
      if (!data || !data.ok || !data.task) {
        throw new Error(data?.message || '登录状态获取失败');
      }
      const task = data.task;
      const step = String(task.step || '');
      const msg = String(task.message || '登录进行中...');
      setMcpState(msg);

      if (step === 'scanned' && !mcpScanHandled) {
        mcpScanHandled = true;
        closeQrWindow();
        setMcpState('已检测到扫码，二维码窗口已关闭。', '正在回到主界面继续等待登录凭证写入，请稍候。');
      }

      if (task.status === 'done' && step === 'logged_in') {
        closeQrWindow();
        await refreshStatus();
        setMcpState('您已登录，进入首页。', '现在可以直接使用所有板块。');
        closeMcpModal();
        return;
      }

      if (task.status === 'failed') {
        closeQrWindow();
        throw new Error(msg || 'MCP 登录失败');
      }

      await new Promise((r) => setTimeout(r, 1000));
    }
    if (!pollAbort) throw new Error('登录轮询超时，请重试');
  } catch (err) {
    setMcpState(`MCP 登录失败: ${err.message}`);
  } finally {
    mcpPolling.value = false;
  }
}

async function startMcpFlow() {
  if (mcpPolling.value) return;
  try {
    setMcpState('正在启动 MCP 登录流程...');
    const data = await startMcpLogin();
    if (!data || !data.ok) {
      throw new Error(data?.message || 'MCP 登录启动失败');
    }
    if (data.already_logged_in) {
      await refreshStatus();
      setMcpState('您已登录，进入首页。', '可以直接开始对话查询和生成报告。');
      closeMcpModal();
      return;
    }
    mcpTaskId = data.task_id;
    mcpScanHandled = false;
    openQrWindow(data.qr_url || mcpQrUrl(mcpTaskId));
    setMcpState('二维码已在新窗口打开，请使用 Boss 直聘 APP 扫码。', '检测到扫码后将自动关闭二维码窗口，并继续等待登录凭证写入。');
    await pollMcpTask(mcpTaskId);
  } catch (err) {
    setMcpState(`登录启动失败: ${err.message}`);
  }
}

async function loadReports() {
  reportsLoading.value = true;
  reportsError.value = '';
  try {
    const data = await listReports();
    if (!data || !data.ok) {
      throw new Error(data?.message || '报告加载失败');
    }
    reports.value = Array.isArray(data.reports) ? data.reports : [];
  } catch (err) {
    reports.value = [];
    reportsError.value = err.message || String(err);
  } finally {
    reportsLoading.value = false;
  }
}

function openReports() {
  if (!requireLogin('请先登录账号后再查看报告。')) return;
  if (!hasBossCookie.value) {
    openMcpModal();
    setMcpState('请先完成 MCP 登录后再查看报告。');
    return;
  }
  reportsPanelOpen.value = true;
  loadReports();
}

function closeReportsPanel() {
  reportsPanelOpen.value = false;
  closeReportPreview();
}

function closeReportPreview() {
  reportPreviewOpen.value = false;
}

async function onSelectReport(item) {
  currentReport.name = item.name;
  currentReport.title = stripSuffix(item.name);
  currentReport.content = '';
  currentReport.renderedHtml = '';
  reportPreviewOpen.value = true;
  viewerState.value = 'loading';
  viewerError.value = '';
  try {
    const data = await fetchReport(item.name);
    if (!data || !data.ok) {
      throw new Error(data?.message || '读取报告失败');
    }
    if (data.is_binary && data.suffix === '.pdf') {
      viewerPdfUrl.value = data.view_url || '';
      viewerState.value = 'pdf';
      return;
    }
    const lower = String(data.name || '').toLowerCase();
    if (lower.endsWith('.html')) {
      viewerHtml.value = String(data.content || '');
      viewerState.value = 'html';
      return;
    }
    currentReport.content = data.content || '';
    currentReport.renderedHtml = data.rendered_html || '';
    viewerState.value = 'markdown';
  } catch (err) {
    viewerError.value = err.message || String(err);
    viewerState.value = 'error';
  }
}

function exportCurrentPdf() {
  if (!currentReport.name) return;
  window.open(reportPdfUrl(currentReport.name), '_blank');
}

function goJob() {
  if (!requireLogin('请先登录账号后再使用求职板块。')) return;
  if (!hasBossCookie.value) {
    openMcpModal();
    setMcpState('请先完成 MCP 登录后再进入求职板块。');
    return;
  }
  window.location.href = '/job';
}

function goCareer() {
  if (!requireLogin('请先登录账号后再使用职业规划。')) return;
  window.location.href = '/career';
}

function goInterview() {
  if (!requireLogin('请先登录账号后再使用模拟面试。')) return;
  if (!hasBossCookie.value) {
    openMcpModal();
    setMcpState('请先完成 MCP 登录后再进入模拟面试。', '模拟面试会调用 AI 生成题目与反馈。');
    return;
  }
  window.location.href = '/interview';
}

function onKeyDown(evt) {
  if (evt.key === 'Escape') {
    closeReportPreview();
    closeMcpModal();
  }
}

onMounted(async () => {
  document.addEventListener('keydown', onKeyDown);
  const data = await refreshStatus();
  if (!data || !data.logged_in) {
    window.location.href = '/login';
    return;
  }
  if (data.logged_in && !data.has_cookie) {
    openMcpModal();
    setMcpState('检测到你尚未登录 Boss，请点击按钮开始 MCP 扫码登录。', '二维码会在新窗口打开，扫码后会自动关闭并回到本页面。');
  }
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeyDown);
  pollAbort = true;
  closeQrWindow();
});
</script>
