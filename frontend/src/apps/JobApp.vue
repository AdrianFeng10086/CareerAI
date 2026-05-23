<template>
  <BgLayers />
  <main class="page-wrap">
    <TopBar brand="ZT-AI JOB OPS">
      <StatusBadge
        class="status-badge"
        :status="status"
        :loading="statusLoading"
        :error-message="statusError"
      />
      <button class="ghost-btn" type="button" @click="goHome">返回首页</button>
      <button class="ghost-btn" type="button" @click="onLogout">退出账号</button>
    </TopBar>

    <section class="hero">
      <HeroTitle eyebrow="求职板块" title="求职作战台" subtitle="一句话下达任务，自动执行搜索、分析与报告生成流程。" />
    </section>

    <section class="panel" aria-hidden="false">
      <div class="panel-header">
        <h3>AI 求职执行引擎</h3>
        <div class="quick-actions">
          <button
            v-for="action in quickActions"
            :key="action.prompt"
            type="button"
            class="quick-action"
            :data-prompt="action.prompt"
            @click="useQuickAction(action.prompt)"
          >{{ action.label }}</button>
        </div>
      </div>

      <div class="panel-body chat-layout">
        <div class="task-progress" :hidden="!progress.visible">
          <div class="task-progress-head">
            <span>{{ progressStageText }}</span>
            <span>{{ progress.percent }}%</span>
          </div>
          <div class="task-progress-track">
            <div class="task-progress-bar" :style="{ width: progress.percent + '%' }"></div>
          </div>
          <div class="task-progress-msg">{{ progressMsgDisplay }}</div>
        </div>

        <div ref="messagesEl" class="chat-messages">
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            :class="['msg', msg.type]"
          >
            <template v-if="msg.type === 'user'">{{ msg.text }}</template>
            <MarkdownView
              v-else
              :source="msg.text"
              root-class="msg-markdown markdown-body"
              use-markdown-it
            />
          </div>
        </div>

        <form class="chat-form" @submit.prevent="onSubmit">
          <textarea v-model="inputText" rows="3" placeholder="例如：帮我搜索杭州Java开发3页并分析出报告"></textarea>
          <button type="submit" class="module-btn">发送并执行</button>
        </form>
      </div>
    </section>
  </main>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted, onBeforeUnmount } from 'vue';
import BgLayers from '../components/BgLayers.vue';
import TopBar from '../components/TopBar.vue';
import HeroTitle from '../components/HeroTitle.vue';
import StatusBadge from '../components/StatusBadge.vue';
import MarkdownView from '../components/MarkdownView.vue';
import { fetchStatus, logout } from '../api/auth.js';
import { submitChat } from '../api/chat.js';
import { get } from '../api/client.js';

const STAGE_LABELS = {
  queued: '任务排队中',
  'intent.parse': '解析语义意图',
  'intent.done': '意图解析完成',
  'profile.extract': '提取简历画像',
  'profile.rule': '简历规则匹配',
  'profile.done': '画像建模完成',
  'scraper.init': '启动爬虫引擎',
  'cache.check': '检查历史缓存',
  'cache.match': '匹配近期记录',
  'cache.hit': '命中本地缓存',
  'scraping.start': '远程实时采集',
  'scraping.page': '采集职位详情',
  'save-data': '保存数据快照',
  'save.career': '更新职业数据集',
  'analyzing.init': '分配AI分析算力',
  'ai.aggregate': '统计聚合数据',
  'ai.deep': 'AI模型深度分析',
  'report.html': '生成预览报告',
  'report.pdf': '排版离线PDF',
  'pdf.init': '初始化PDF引擎',
  'pdf.summary': '撰写岗位摘录',
  'pdf.table': '绘制统计图表',
  'pdf.ai': '排版AI专家分析',
  'storage.upsert': '更新向量数据库索引',
  'retry.wind-control': '风控触发自动重试',
  finalizing: '整理分析结果',
  done: '任务全部完成',
  failed: '分析任务失败',
};

const REASSURE_MESSAGES = [
  '任务仍在正常执行中。',
  '抓取与分析阶段较慢属于正常现象。',
  '请保持页面打开，完成后会自动推送结果。',
  '报告排版阶段耗时会更长，请稍候。',
];

const quickActions = [
  { label: '北京 Python 3页', prompt: '帮我搜索北京Python开发3页并分析出报告' },
  { label: '上海 前端 2页', prompt: '帮我搜索上海前端工程师2页并分析出报告' },
  { label: '深圳 数据分析 2页', prompt: '帮我搜索深圳数据分析师2页并分析出报告' },
];

const status = ref(null);
const statusLoading = ref(true);
const statusError = ref('');
const isLoggedIn = computed(() => !!status.value?.logged_in);
const hasBossCookie = computed(() => !!status.value?.has_cookie);

const messages = ref([]);
const inputText = ref('');
const messagesEl = ref(null);

const progress = reactive({ visible: false, percent: 0, stage: '', msg: '' });
const progressStageText = computed(() => STAGE_LABELS[progress.stage] || progress.stage || '处理中');
const progressMsgDisplay = ref('');

let activeTaskId = '';
let activeTaskLastEventId = 0;
let reassureTimer = null;
let reassureIndex = 0;
let pollAbort = false;

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

function pushMessage(text, type = 'bot') {
  messages.value.push({ text: String(text || ''), type });
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
    }
  });
}

function setTaskProgress(visible, percent, stage, msg) {
  progress.visible = !!visible;
  if (!visible) return;
  progress.percent = Math.max(0, Math.min(100, Number(percent) || 0));
  progress.stage = stage || '';
  progress.msg = String(msg || '');
  progressMsgDisplay.value = progress.msg;
}

function startReassureLoop() {
  stopReassureLoop();
  reassureTimer = setInterval(() => {
    if (!progress.visible) return;
    reassureIndex = (reassureIndex + 1) % REASSURE_MESSAGES.length;
    const base = progress.msg || '任务处理中';
    progressMsgDisplay.value = `${base} ${REASSURE_MESSAGES[reassureIndex]}`;
  }, 6500);
}

function stopReassureLoop() {
  if (reassureTimer) {
    clearInterval(reassureTimer);
    reassureTimer = null;
  }
}

function consumeTaskEvents(task) {
  const events = Array.isArray(task?.events) ? task.events : [];
  for (const evt of events) {
    const evtId = Number(evt?.id) || 0;
    if (evtId <= activeTaskLastEventId) continue;
    activeTaskLastEventId = evtId;
    const text = String(evt?.text || '');
    if (text.startsWith('执行参数: ')) continue;
    const kind = evt?.kind === 'error' ? 'error' : 'bot';
    pushMessage(text, kind);
  }
}

async function pollTaskStatus(taskId) {
  let guard = 0;
  while (taskId && taskId === activeTaskId && guard < 720 && !pollAbort) {
    guard += 1;
    try {
      const data = await get(`/api/chat/task/${encodeURIComponent(taskId)}`);
      if (!data || !data.ok || !data.task) {
        stopReassureLoop();
        setTaskProgress(false, 0, '', '');
        pushMessage(data?.message || '任务状态获取失败', 'error');
        return;
      }
      const task = data.task;
      setTaskProgress(true, task.progress, task.stage, task.message);
      consumeTaskEvents(task);

      if (task.status === 'done') {
        stopReassureLoop();
        setTaskProgress(true, 100, 'done', '任务完成');
        const result = task.result || {};
        pushMessage(result.message || '任务完成', 'bot');
        setTimeout(() => setTaskProgress(false, 0, '', ''), 1600);
        return;
      }
      if (task.status === 'failed') {
        stopReassureLoop();
        setTaskProgress(false, 0, '', '');
        const message = task.result?.message || task.message || '任务失败';
        pushMessage(message, 'error');
        return;
      }
    } catch (err) {
      stopReassureLoop();
      setTaskProgress(false, 0, '', '');
      pushMessage(`任务状态获取失败: ${err.message || err}`, 'error');
      return;
    }
    await new Promise((r) => setTimeout(r, 900));
  }
  if (!pollAbort) {
    stopReassureLoop();
    setTaskProgress(false, 0, '', '');
    pushMessage('任务轮询超时，请稍后重试。', 'error');
  }
}

function requireBossCookie() {
  if (hasBossCookie.value) return true;
  pushMessage('请先在首页完成 MCP 登录，再返回求职页执行任务。', 'error');
  return false;
}

async function sendChatMessage(message) {
  const text = String(message || '').trim();
  if (!text) return;
  pushMessage(text, 'user');
  try {
    const data = await submitChat(text);
    if (!data || !data.ok) {
      pushMessage(data?.message || '执行失败', 'error');
      return;
    }
    activeTaskId = data.task_id;
    activeTaskLastEventId = 0;
    setTaskProgress(true, 0, 'queued', '任务已启动，等待后端响应...');
    startReassureLoop();
    await pollTaskStatus(activeTaskId);
  } catch (err) {
    stopReassureLoop();
    setTaskProgress(false, 0, '', '');
    pushMessage(`请求失败: ${err.message}`, 'error');
  }
}

async function onSubmit() {
  const text = inputText.value.trim();
  if (!text) return;
  if (!requireBossCookie()) return;
  inputText.value = '';
  await sendChatMessage(text);
}

async function useQuickAction(prompt) {
  if (!prompt) return;
  if (!requireBossCookie()) return;
  inputText.value = '';
  await sendChatMessage(prompt);
}

function goHome() { window.location.href = '/'; }

async function onLogout() {
  try { await logout(); } catch { /* ignore */ }
  window.location.href = '/login';
}

onMounted(async () => {
  const data = await refreshStatus();
  if (!data.logged_in) {
    window.location.href = '/login';
    return;
  }
  if (data.logged_in && !data.has_cookie) {
    pushMessage('提示：你当前未完成 Boss 登录，请先回首页点击 MCP 登录。', 'bot');
  }
  pushMessage('欢迎来到求职作战台。你可以直接输入职位关键词与页数来执行任务。', 'bot');
});

onBeforeUnmount(() => {
  pollAbort = true;
  stopReassureLoop();
});
</script>
