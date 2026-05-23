<template>
  <BgLayers />
  <main class="page-wrap">
    <TopBar brand="ZT-AI INTERVIEW LAB">
      <span class="status-badge">{{ statusBadgeText }}</span>
      <button class="ghost-btn" type="button" @click="goHome">返回首页</button>
      <button class="ghost-btn" type="button" @click="onLogout">退出账号</button>
    </TopBar>

    <section class="hero">
      <HeroTitle eyebrow="模拟面试板块" title="面试训练营" subtitle="上传简历后自动生成结构化问题，逐题评估并输出完整反馈。" />
    </section>

    <section class="panel" aria-hidden="false">
      <div class="panel-header">
        <h3>模拟面试引擎</h3>
      </div>
      <div class="panel-body interview-layout">
        <div class="interview-toolbar">
          <button class="module-btn" type="button" @click="onClickStart">开始面试</button>
          <button class="ghost-btn" type="button" @click="onClickUpload">上传简历并解析</button>
          <input
            ref="resumeFileInputEl"
            type="file"
            accept=".pdf,.doc,.docx"
            hidden
            @change="onResumeFileChange"
          />
          <div class="interview-meta" :style="metaStyle">{{ metaText }}</div>
        </div>

        <div class="interview-resume-box">
          <label for="interview-resume-text">简历文本</label>
          <textarea id="interview-resume-text" v-model="resumeText" rows="6" placeholder="可直接粘贴简历，或使用上传按钮自动解析..."></textarea>
        </div>

        <div class="interview-question-box">
          <div class="interview-question-head">
            <span>进度: {{ progressIndex }} / {{ totalQuestions }}</span>
            <span>{{ depthFlagText }}</span>
            <span class="interview-timer" :class="timerClass" :hidden="!timerVisible">
              <span class="interview-timer-label">作答倒计时</span>
              <span class="interview-timer-value">{{ timerDisplay }}</span>
            </span>
          </div>
          <div class="interview-question-title">{{ questionTitle }}</div>
          <ul class="interview-sub-list">
            <li v-for="(s, i) in subQuestions" :key="i">{{ s }}</li>
          </ul>
        </div>

        <form class="interview-answer-form" @submit.prevent="onSubmitAnswer">
          <textarea v-model="answerText" rows="5" placeholder="请按小问题逐项回答，确保覆盖完整。"></textarea>
          <button type="submit" class="module-btn">提交回答</button>
        </form>

        <div class="camera-stats-panel" :hidden="!cameraVisible">
          <div class="camera-stats-header">
            <span class="camera-indicator" :style="{ color: cameraIndicatorColor }">●</span>
            <span>神态分析</span>
            <span class="camera-score">{{ cameraOverall }}</span>
          </div>
          <div class="camera-stats-grid">
            <div class="camera-stat-item">
              <span class="camera-stat-label">表情</span>
              <span class="camera-stat-value">{{ cameraEmotion }}</span>
            </div>
            <div class="camera-stat-item">
              <span class="camera-stat-label">屏幕注视</span>
              <span class="camera-stat-value" :style="{ color: eyeContactColor }">{{ cameraEye }}</span>
            </div>
            <div class="camera-stat-item">
              <span class="camera-stat-label">头部稳定</span>
              <span class="camera-stat-value">{{ cameraHead }}</span>
            </div>
            <div class="camera-stat-item">
              <span class="camera-stat-label">点头/摇头</span>
              <span class="camera-stat-value">{{ cameraNods }}</span>
            </div>
          </div>
        </div>

        <div ref="logEl" class="interview-log">
          <div
            v-for="(item, idx) in logItems"
            :key="idx"
            :class="['interview-log-item', item.type]"
          >{{ item.text }}</div>
        </div>

        <div class="interview-feedback" :hidden="!feedbackVisible">
          <h4>面试反馈</h4>
          <div v-if="feedback" v-html="feedbackHtml"></div>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted, onBeforeUnmount } from 'vue';
import BgLayers from '../components/BgLayers.vue';
import TopBar from '../components/TopBar.vue';
import HeroTitle from '../components/HeroTitle.vue';
import { fetchStatus, logout } from '../api/auth.js';
import {
  uploadInterviewResume,
  startInterview as apiStartInterview,
  submitInterviewAnswer as apiSubmitAnswer,
  fetchCameraStats,
  stopInterview,
} from '../api/interview.js';
import { escapeHtml } from '../utils/escapeHtml.js';
import { formatTimerDisplay } from '../utils/format.js';

const ANSWER_TIME_LIMIT_SECONDS = 5 * 60;

const statusBadgeText = ref('状态检测中...');
let isLoggedIn = false;
let hasBossCookie = false;

const metaText = ref('请先上传简历，然后点击"开始面试"。');
const metaIsError = ref(false);
const metaStyle = computed(() => ({ color: metaIsError.value ? '#ffc4c4' : '' }));

const resumeText = ref('');
const answerText = ref('');

const sessionId = ref('');
const totalQuestions = ref(0);
const progressIndex = ref(0);
const depthFlagText = ref('普通问题');
const questionTitle = ref('等待开始面试...');
const subQuestions = ref([]);

const logItems = ref([]);
const logEl = ref(null);
const resumeFileInputEl = ref(null);

const feedback = ref(null);
const feedbackVisible = computed(() => !!feedback.value);
const feedbackHtml = computed(() => buildFeedbackHtml(feedback.value));

const timerVisible = ref(false);
const timerDisplay = ref('05:00');
const timerLevel = ref('');
const timerClass = computed(() => timerLevel.value);

const cameraVisible = ref(false);
const cameraIndicatorColor = ref('#ffb347');
const cameraOverall = ref('--');
const cameraEmotion = ref('--');
const cameraEye = ref('--');
const eyeContactColor = ref('#ff6b6b');
const cameraHead = ref('--');
const cameraNods = ref('--');

let answerTimerInterval = null;
let answerTimerDeadline = 0;
let answerTimerExpired = false;
let isSubmittingAnswer = false;
let cameraPollTimer = null;
let currentQuestionIndex = 0;
let answeredCount = 0;

function setMeta(text, isError = false) {
  metaText.value = text || '';
  metaIsError.value = !!isError;
}

function appendLog(text, type = 'bot') {
  logItems.value.push({ text: String(text || ''), type });
  nextTick(() => {
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight;
  });
}

function clearLog() {
  logItems.value = [];
}

function updateAnswerTimerDisplay() {
  const remaining = (answerTimerDeadline - Date.now()) / 1000;
  timerDisplay.value = formatTimerDisplay(Math.max(0, Math.ceil(remaining)));
  timerLevel.value = '';
  if (remaining <= 30) timerLevel.value = 'danger';
  else if (remaining <= 60) timerLevel.value = 'warning';
}

function clearAnswerTimer() {
  if (answerTimerInterval) {
    clearInterval(answerTimerInterval);
    answerTimerInterval = null;
  }
}

function hideAnswerTimer() {
  clearAnswerTimer();
  timerVisible.value = false;
  timerLevel.value = '';
}

function startAnswerTimer() {
  clearAnswerTimer();
  answerTimerExpired = false;
  answerTimerDeadline = Date.now() + ANSWER_TIME_LIMIT_SECONDS * 1000;
  timerVisible.value = true;
  updateAnswerTimerDisplay();
  answerTimerInterval = setInterval(() => {
    updateAnswerTimerDisplay();
    if (Date.now() >= answerTimerDeadline) {
      clearAnswerTimer();
      handleAnswerTimeout();
    }
  }, 500);
}

async function handleAnswerTimeout() {
  if (answerTimerExpired || isSubmittingAnswer) return;
  answerTimerExpired = true;
  appendLog('⏱ 作答倒计时结束，已自动提交当前回答。', 'bot');
  setMeta('作答倒计时结束，系统已自动提交当前回答。', true);
  await submitAnswer({ timedOut: true });
}

function renderInterviewQuestion(current, total) {
  const previousIndex = currentQuestionIndex;
  currentQuestionIndex = current ? Number(current.index || 0) : 0;
  totalQuestions.value = Number(total || totalQuestions.value || 0);

  if (!current) {
    progressIndex.value = 0;
    depthFlagText.value = '普通问题';
    questionTitle.value = '等待开始面试...';
    subQuestions.value = [];
    hideAnswerTimer();
    return;
  }

  const index = Number(current.index || 1);
  progressIndex.value = index;
  depthFlagText.value = current.is_deep ? '深度问题' : '普通问题';
  questionTitle.value = String(current.question || '');
  subQuestions.value = Array.isArray(current.sub_questions) ? current.sub_questions : [];

  if (index !== previousIndex) {
    startAnswerTimer();
  }
}

function buildFeedbackHtml(fb) {
  if (!fb) return '';
  const summary = fb.summary || {};
  const strengths = Array.isArray(fb.strengths) ? fb.strengths : [];
  const gaps = Array.isArray(fb.gaps) ? fb.gaps : [];
  const actions = Array.isArray(fb.action_items) ? fb.action_items : [];
  return `
    <div class="interview-feedback-grid">
      <div><b>目标岗位</b> ${escapeHtml(String(summary.target_role || '-'))}</div>
      <div><b>题目数量</b> ${Number(summary.total_questions || 0)}</div>
      <div><b>完整回答</b> ${Number(summary.complete_answers || 0)}</div>
      <div><b>回答欠缺</b> ${Number(summary.incomplete_answers || 0)}</div>
      <div><b>超时未答</b> ${Number(summary.timeout_questions || 0)}</div>
      <div><b>深度题完成</b> ${Number(summary.deep_complete || 0)} / ${Number(summary.deep_questions || 0)}</div>
      <div><b>平均分</b> ${Number(summary.average_score || 0)}</div>
    </div>
    <p class="interview-overall">${escapeHtml(String(fb.overall_comment || ''))}</p>
    <div class="interview-feedback-columns">
      <div>
        <h5>优势</h5>
        <ul>${strengths.map((x) => `<li>${escapeHtml(String(x || ''))}</li>`).join('')}</ul>
      </div>
      <div>
        <h5>待补齐</h5>
        <ul>${gaps.map((x) => `<li>${escapeHtml(String(x || ''))}</li>`).join('')}</ul>
      </div>
      <div>
        <h5>行动建议</h5>
        <ul>${actions.map((x) => `<li>${escapeHtml(String(x || ''))}</li>`).join('')}</ul>
      </div>
    </div>
  `;
}

function startCameraPolling() {
  stopCameraPolling();
  pollCameraStats();
  cameraPollTimer = setInterval(pollCameraStats, 1500);
}

function stopCameraPolling() {
  if (cameraPollTimer) {
    clearInterval(cameraPollTimer);
    cameraPollTimer = null;
  }
  cameraVisible.value = false;
}

async function pollCameraStats() {
  if (!sessionId.value) return;
  try {
    const data = await fetchCameraStats(sessionId.value);
    if (!data || !data.ok || !data.camera_active) {
      cameraVisible.value = false;
      return;
    }
    renderCameraStats(data);
  } catch { /* non-critical */ }
}

function renderCameraStats(data) {
  const snap = data.snapshot || {};
  const stats = data.stats || {};
  cameraVisible.value = true;
  cameraIndicatorColor.value = snap.face_detected ? '#3fef6f' : '#ffb347';
  cameraOverall.value = stats.overall_score != null ? String(Math.round(stats.overall_score)) : '--';
  if (snap.emotion) {
    const conf = snap.emotion_confidence != null ? Math.round(snap.emotion_confidence * 100) : 0;
    cameraEmotion.value = `${snap.emotion} ${conf}%`;
  } else {
    cameraEmotion.value = '--';
  }
  const ec = snap.eye_contact_score != null ? Math.round(snap.eye_contact_score * 100) : null;
  cameraEye.value = ec != null ? `${ec}%` : '--';
  eyeContactColor.value = ec != null && ec >= 60 ? '#3fef6f' : ec != null && ec >= 35 ? '#ffb347' : '#ff6b6b';
  const hs = stats.head_stability != null ? Math.round(stats.head_stability * 100) : null;
  cameraHead.value = hs != null ? `${hs}%` : '--';
  const nod = stats.nod_count != null ? stats.nod_count : 0;
  const shake = stats.shake_count != null ? stats.shake_count : 0;
  cameraNods.value = `${nod}/${shake}`;
}

function formatMissingSubQuestions(evaluation) {
  const missing = Array.isArray(evaluation?.missing_sub_questions) ? evaluation.missing_sub_questions : [];
  if (!missing.length) return '';
  return `未覆盖小问题: ${missing.join('；')}`;
}

function requireBossCookie() {
  if (hasBossCookie) return true;
  setMeta('请先在首页完成 MCP 登录，再返回模拟面试页。', true);
  appendLog('未检测到 Boss 登录凭证，请先回首页完成 MCP 登录。', 'bot');
  return false;
}

async function refreshStatus() {
  try {
    const data = await fetchStatus();
    if (!data || !data.ok) throw new Error(data?.error || '状态读取失败');
    isLoggedIn = !!data.logged_in;
    hasBossCookie = !!data.has_cookie;
    const userText = isLoggedIn ? `账号: ${data.username || '用户'}` : '账号: 未登录';
    const bossText = hasBossCookie ? 'Boss: 已登录' : 'Boss: 未登录';
    statusBadgeText.value = `${userText} | ${bossText}`;
    return data;
  } catch {
    isLoggedIn = false;
    hasBossCookie = false;
    statusBadgeText.value = '状态异常';
    return { ok: false, logged_in: false, has_cookie: false };
  }
}

async function parseResumeFile(file) {
  if (!file) return;
  setMeta('正在解析简历...');
  try {
    const data = await uploadInterviewResume(file);
    if (!data || !data.ok) throw new Error(data?.error || '简历解析失败');
    const cur = resumeText.value.trim();
    resumeText.value = cur ? `${cur}\n\n${data.text || ''}` : String(data.text || '');
    setMeta(`简历解析成功: ${data.filename}`);
  } catch (err) {
    setMeta(`简历解析失败: ${err.message}`, true);
  }
}

function onClickUpload() {
  if (!requireBossCookie()) return;
  resumeFileInputEl.value?.click();
}

async function onResumeFileChange(evt) {
  const file = evt.target.files && evt.target.files[0];
  if (file && requireBossCookie()) {
    await parseResumeFile(file);
  }
  evt.target.value = '';
}

async function startInterview() {
  const text = resumeText.value.trim();
  if (!text) {
    setMeta('请先上传或粘贴简历文本。', true);
    return;
  }
  if (sessionId.value) {
    stopCameraPolling();
    try {
      navigator.sendBeacon(
        '/api/interview/stop',
        new Blob([JSON.stringify({ session_id: sessionId.value })], { type: 'application/json' }),
      );
    } catch { /* ignore */ }
    sessionId.value = '';
  }
  try {
    setMeta('正在生成面试题...');
    clearLog();
    feedback.value = null;
    const data = await apiStartInterview({ resume_text: text, question_count: 10 });
    if (!data || !data.ok) throw new Error(data?.error || '面试启动失败');
    sessionId.value = String(data.session_id || '');
    totalQuestions.value = Number(data.total_questions || 0);
    answeredCount = 0;
    renderInterviewQuestion(data.current, totalQuestions.value);
    appendLog(`面试开始，目标岗位: ${data.target_role || '目标岗位'}`);
    appendLog(`第1题: ${data.current?.question || ''}`);
    appendLog(data.camera_active ? '摄像头神态分析已同步开启。' : '摄像头神态分析未启动（可能未检测到摄像头）。');
    setMeta(`已生成 ${totalQuestions.value} 题（深度题 ${Number(data.deep_questions || 0)} 题）。`);
    if (data.camera_active) startCameraPolling();
  } catch (err) {
    setMeta(`面试启动失败: ${err.message}`, true);
  }
}

async function onClickStart() {
  if (!requireBossCookie()) return;
  await startInterview();
}

async function submitAnswer({ timedOut = false } = {}) {
  if (!sessionId.value) {
    setMeta('请先开始面试。', true);
    return;
  }
  if (isSubmittingAnswer) return;
  const rawAnswer = answerText.value.trim();
  if (!timedOut && !rawAnswer) {
    setMeta('请输入回答内容后再提交。', true);
    return;
  }
  const answerToSend = rawAnswer || (timedOut ? '（倒计时结束，未作答）' : '');
  isSubmittingAnswer = true;
  clearAnswerTimer();
  try {
    if (timedOut) {
      appendLog(`我的回答(超时自动提交): ${rawAnswer || '（无内容）'}`, 'user');
    } else {
      appendLog(`我的回答: ${answerToSend}`, 'user');
    }
    const data = await apiSubmitAnswer({
      session_id: sessionId.value,
      answer: answerToSend,
      timed_out: timedOut,
    });
    if (!data || !data.ok) throw new Error(data?.error || '回答提交失败');
    const evalResult = data.evaluation || {};
    const quality = Number(evalResult.quality_score || 0);
    let statusText;
    if (evalResult.timed_out) statusText = '超时未答（计入评分）';
    else statusText = evalResult.status === 'complete' ? '回答完整' : '回答不完全/回答欠缺';
    const missingText = formatMissingSubQuestions(evalResult);
    appendLog(`评估: ${statusText}（质量分: ${quality}）${missingText ? ` | ${missingText}` : ''}`);

    if (data.status === 'needs_completion') {
      renderInterviewQuestion(data.current, totalQuestions.value);
      setMeta('请先补充当前题缺失的小问题，再继续下一题。', true);
      appendLog('请继续补充当前题答案。', 'bot');
      answerText.value = '';
      return;
    }
    if (data.status === 'next_question') {
      answeredCount = Number(data.progress?.answered || answeredCount + 1);
      renderInterviewQuestion(data.current, totalQuestions.value);
      appendLog(`下一题: ${data.current?.question || ''}`, 'bot');
      setMeta(`当前进度 ${answeredCount} / ${totalQuestions.value}`);
      answerText.value = '';
      return;
    }
    if (data.status === 'finished') {
      answeredCount = Number(data.progress?.answered || totalQuestions.value);
      stopCameraPolling();
      hideAnswerTimer();
      renderInterviewQuestion(null, totalQuestions.value);
      feedback.value = data.feedback || {};
      setMeta('模拟面试已完成，已生成反馈。');
      appendLog('面试结束，反馈已生成。', 'bot');
      answerText.value = '';
      return;
    }
    setMeta('已提交回答。');
  } catch (err) {
    setMeta(`提交失败: ${err.message}`, true);
  } finally {
    isSubmittingAnswer = false;
  }
}

async function onSubmitAnswer() {
  if (!requireBossCookie()) return;
  await submitAnswer();
}

function goHome() { window.location.href = '/'; }

async function onLogout() {
  try { await logout(); } catch { /* ignore */ }
  window.location.href = '/login';
}

function onBeforeUnload() {
  if (sessionId.value) {
    try {
      navigator.sendBeacon(
        '/api/interview/stop',
        new Blob([JSON.stringify({ session_id: sessionId.value })], { type: 'application/json' }),
      );
    } catch { /* ignore */ }
  }
}

onMounted(async () => {
  window.addEventListener('beforeunload', onBeforeUnload);
  const data = await refreshStatus();
  if (!data.logged_in) {
    window.location.href = '/login';
    return;
  }
  if (data.logged_in && !data.has_cookie) {
    setMeta('提示：你当前未完成 Boss 登录，请先回首页点击 MCP 登录。', true);
  }
  appendLog('欢迎进入模拟面试训练营。请先上传或粘贴简历，然后点击"开始面试"。');
});

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload);
  clearAnswerTimer();
  stopCameraPolling();
  if (sessionId.value) {
    try { stopInterview({ session_id: sessionId.value }); } catch { /* ignore */ }
  }
});
</script>
