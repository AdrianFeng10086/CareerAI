<template>
  <BgLayers />
  <main class="page-wrap">
    <TopBar brand="ZT-AI CAREER">
      <span class="status-badge">{{ statusBadgeText }}</span>
      <button class="ghost-btn" type="button" @click="goHome">返回首页</button>
    </TopBar>

    <header class="hero">
      <HeroTitle eyebrow="职业生涯规划工作台" title="职业规划" subtitle="只需简单输入，即可为您定制求职策略与校内成长路径，双轨并行，步步为赢。" />
    </header>

    <section class="panel">
      <div class="wizard-header">
        <h2>智能问答向导</h2>
        <div class="wizard-profile-controls">
          <div class="grade-tabs" role="tablist" aria-label="年级选择">
            <button
              v-for="g in gradeOptions"
              :key="g.value"
              type="button"
              class="grade-tab"
              :class="{ active: activeGrade === g.value }"
              :data-grade="g.value"
              @click="setGrade(g.value)"
            >{{ g.label }}</button>
          </div>
          <input v-model="majorInput" class="major-input" type="text" maxlength="32" placeholder="请输入所学专业，如网络工程" @change="syncMajor" />
        </div>
      </div>
      <p>使用输入窗口完成逐轮问答采集，完成后再生成下方完整报告。</p>

      <div class="flow-steps">
        <span class="step" :class="stepClass(1)">1. 填写基础信息</span>
        <span class="step" :class="stepClass(2)">2. 确认求职意向</span>
        <span class="step" :class="stepClass(3)">3. 完善能力画像</span>
      </div>

      <div ref="dialogueLogEl" class="dialogue-log">
        <div
          v-for="(item, idx) in dialogueLog"
          :key="idx"
          :class="['dialogue-item', item.role === 'user' ? 'user' : 'bot']"
        >
          <p class="role">{{ item.role === 'user' ? '你' : '系统' }}</p>
          <p>{{ item.text }}</p>
        </div>
      </div>

      <div class="recommended-bar" :class="{ hidden: !recommendedText }">{{ recommendedText }}</div>

      <div class="chat-composer">
        <input ref="resumeFileInputEl" type="file" accept=".pdf,.docx,.doc" class="hidden" @change="onPickResume" />
        <textarea
          ref="chatInputEl"
          v-model="chatInput"
          rows="1"
          placeholder="在这里输入回答。Enter发送，Shift+Enter换行"
          @input="resizeChatInput"
          @paste="onPaste"
          @keydown="onChatKeydown"
        ></textarea>
        <button type="button" class="ghost-btn" :disabled="uploadBusy" @click="triggerUpload">上传简历</button>
        <button type="button" class="module-btn" :disabled="sendBusy" @click="sendUserMessage">发送</button>
      </div>
      <p class="input-hint">系统处理可能需要一定时间，请在发送后耐心等待。</p>

      <div class="actions">
        <button type="button" class="module-btn" :disabled="!canAnalyze" @click="analyze">生成完整《职业生涯发展报告》</button>
        <button class="ghost-btn" type="button" :disabled="!canExport" @click="exportAll">导出报告</button>
      </div>
      <p class="status">{{ statusText }}</p>
    </section>

    <section class="grid" :class="{ hidden: !analysisLoaded }">
      <article class="card full">
        <h3>学生就业能力画像</h3>
        <div v-html="studentProfileHtml"></div>
      </article>

      <article class="card full">
        <h3>职业生涯规划工具可视化</h3>
        <div v-html="careerToolsHtml"></div>
      </article>

      <article class="card full">
        <h3>人岗匹配 Top 5</h3>
        <div v-html="matchTableHtml"></div>
      </article>

      <article class="card">
        <h3>垂直岗位路径</h3>
        <div v-html="verticalGraphHtml"></div>
      </article>

      <article class="card">
        <h3>换岗路径图谱</h3>
        <div v-html="transitionGraphHtml"></div>
      </article>

      <article class="card full">
        <h3>报告预览（Markdown）</h3>
        <div class="report-meta">
          <div class="left-group">
            <span class="pill">{{ reportStage }}</span>
            <span class="typing" :class="{ hidden: !reportTyping }">流式输出中</span>
          </div>
          <button v-if="canExport" class="ghost-btn small" type="button" @click="exportPdfOnly">导出 PDF</button>
        </div>
        <div ref="reportPreviewEl" class="report markdown-body" :class="{ streaming: reportTyping }" v-html="reportPreviewHtml"></div>
      </article>
    </section>
  </main>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue';
import BgLayers from '../components/BgLayers.vue';
import TopBar from '../components/TopBar.vue';
import HeroTitle from '../components/HeroTitle.vue';
import { fetchStatus } from '../api/auth.js';
import {
  startDialogue as apiStartDialogue,
  turnDialogue as apiTurnDialogue,
  analyzeCareer,
  streamCareerReport,
  exportCareerReport,
  uploadCareerResume,
} from '../api/career.js';
import { renderMarkdown } from '../utils/markdown.js';
import { escapeHtml } from '../utils/escapeHtml.js';

const CHAT_INPUT_MAX_HEIGHT = 220;

const gradeOptions = [
  { value: '', label: '未选' },
  { value: '大一', label: '大一' },
  { value: '大二', label: '大二' },
  { value: '大三', label: '大三' },
  { value: '大四', label: '大四' },
  { value: '研一', label: '研一' },
  { value: '研二', label: '研二' },
  { value: '研三', label: '研三' },
];

const statusBadgeText = ref('状态检测中...');

const activeGrade = ref('');
const majorInput = ref('');
const chatInput = ref('');
const dialogueLog = ref([]);
const recommendedText = ref('');
const statusText = ref('等待输入...');
const stepProgress = ref(1);
const sendBusy = ref(false);
const uploadBusy = ref(false);

const analysisLoaded = ref(false);
const studentProfileHtml = ref('');
const careerToolsHtml = ref('');
const matchTableHtml = ref('');
const verticalGraphHtml = ref('');
const transitionGraphHtml = ref('');
const reportPreviewHtml = ref('');
const reportStage = ref('等待生成');
const reportTyping = ref(false);

const dialogueLogEl = ref(null);
const chatInputEl = ref(null);
const resumeFileInputEl = ref(null);
const reportPreviewEl = ref(null);

let dialogueState = null;
let finalStudentText = '';
let currentReportMarkdown = '';

const canAnalyze = computed(() => !!dialogueState?.ready);
const canExport = computed(() => !!currentReportMarkdown);

function stepClass(n) {
  if (n < stepProgress.value) return 'done';
  if (n === stepProgress.value) return 'active';
  return '';
}

function setGrade(value) {
  activeGrade.value = value;
  if (dialogueState && typeof dialogueState === 'object') dialogueState.grade = value;
}

function syncMajor() {
  if (dialogueState && typeof dialogueState === 'object') {
    dialogueState.major = majorInput.value.trim();
  }
}

function getDialogueUserContext() {
  return { grade: activeGrade.value, major: majorInput.value.trim() };
}

function mergeUserContextIntoState(stateObj) {
  const ctx = getDialogueUserContext();
  if (stateObj && typeof stateObj === 'object') {
    stateObj.grade = ctx.grade;
    stateObj.major = ctx.major;
  }
  return ctx;
}

function syncUserContextFromState(stateObj) {
  if (!stateObj || typeof stateObj !== 'object') return;
  const grade = String(stateObj.grade || '').trim();
  if (grade) activeGrade.value = grade;
  const major = String(stateObj.major || '').trim();
  if (major && !majorInput.value.trim()) majorInput.value = major;
}

function addDialogue(role, text) {
  dialogueLog.value.push({ role, text: String(text || '') });
  nextTick(() => {
    if (dialogueLogEl.value) {
      dialogueLogEl.value.scrollTop = dialogueLogEl.value.scrollHeight;
    }
  });
}

function resizeChatInput() {
  const ta = chatInputEl.value;
  if (!ta) return;
  ta.style.height = 'auto';
  const next = Math.min(ta.scrollHeight, CHAT_INPUT_MAX_HEIGHT);
  ta.style.height = `${Math.max(44, next)}px`;
}

function onChatKeydown(evt) {
  if (evt.key !== 'Enter' || evt.shiftKey) return;
  evt.preventDefault();
  sendUserMessage();
}

function onPaste() {
  requestAnimationFrame(resizeChatInput);
}

function setStatusText(msg) {
  statusText.value = msg;
}

function encodePathParts(p) {
  return String(p || '').split('/').map((s) => encodeURIComponent(s)).join('/');
}

function toListHtml(items) {
  if (!items || !items.length) return '<p>暂无</p>';
  return `<ul>${items.map((x) => `<li>${escapeHtml(x)}</li>`).join('')}</ul>`;
}

function renderMatches(matches) {
  if (!matches || !matches.length) return '<p>暂无匹配结果</p>';
  const fmt = (v) => {
    const num = Number(v);
    if (Number.isNaN(num)) return escapeHtml(v);
    return num.toFixed(1);
  };
  const rows = matches.slice(0, 5).map((m) => {
    const rowClass = m.score >= 80 ? 'score-high' : m.score >= 60 ? 'score-mid' : 'score-low';
    const ds = m.dimension_scores || {};
    return `
    <tr class="${rowClass}">
      <td class="job">${escapeHtml(m.job_title || '未知岗位')}</td>
      <td class="num">${fmt(m.score)}</td>
      <td class="num">${fmt(ds.foundation_requirements)}</td>
      <td class="num">${fmt(ds.professional_skills)}</td>
      <td class="num">${fmt(ds.professional_quality)}</td>
      <td class="num">${fmt(ds.development_potential)}</td>
    </tr>`;
  }).join('');
  return `
    <table class="match-table">
      <thead>
        <tr>
          <th>岗位</th><th>匹配度</th><th>基础要求</th><th>职业技能</th><th>职业素养</th><th>发展潜力</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function buildHollandRadar(sp) {
  const labels = { R: '现实型 R', I: '研究型 I', A: '艺术型 A', S: '社会型 S', E: '企业型 E', C: '传统型 C' };
  const order = ['R', 'I', 'A', 'S', 'E', 'C'];
  const scores = sp.holland_scores || {};
  const size = 340; const cx = 170; const cy = 170; const radius = 110;
  const toPoint = (idx, value) => {
    const angle = (-Math.PI / 2) + (idx * (Math.PI * 2 / order.length));
    const r = Math.max(0, Math.min(100, Number(value || 0))) / 100 * radius;
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  };
  const axisLines = order.map((k, i) => {
    const p = toPoint(i, 100);
    return `<line x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}" stroke="rgba(16,33,47,0.20)" />`;
  }).join('');
  const levelPolygons = [20, 40, 60, 80, 100].map((lv) => {
    const pts = order.map((_, i) => {
      const p = toPoint(i, lv);
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    }).join(' ');
    return `<polygon points="${pts}" fill="none" stroke="rgba(16,33,47,0.16)" />`;
  }).join('');
  const valuePoints = order.map((k, i) => {
    const p = toPoint(i, scores[k] || 0);
    return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }).join(' ');
  const marks = order.map((k, i) => {
    const p = toPoint(i, 114);
    const score = Number(scores[k] || 0);
    return `<text x="${p.x.toFixed(1)}" y="${p.y.toFixed(1)}" text-anchor="middle">${labels[k]} (${score})</text>`;
  }).join('');
  return `
    <svg class="radar" viewBox="0 0 ${size} ${size}" role="img" aria-label="霍兰德六维雷达图">
      ${levelPolygons}
      ${axisLines}
      <polygon points="${valuePoints}" fill="rgba(0,119,182,0.38)" stroke="#0077b6" stroke-width="2" />
      ${marks}
    </svg>`;
}

function renderCareerToolsHtml(sp) {
  const hollandCode = sp.holland_code || '';
  const hollandDetail = sp.holland_detail || {};
  const hollandMeanings = (hollandDetail.meanings || []).map((x) => `<li>${escapeHtml(x)}</li>`).join('');
  const hollandFitRoles = (hollandDetail.fit_roles || []).map((x) => `<li>${escapeHtml(x)}</li>`).join('');
  const hollandWatchouts = (hollandDetail.watchouts || []).map((x) => `<li>${escapeHtml(x)}</li>`).join('');
  const mbtiDetail = sp.mbti_detail || {};
  const dimensionNotes = (mbtiDetail.dimension_notes || []).map((x) => `<li>${escapeHtml(x)}</li>`).join('');
  const strengths = (mbtiDetail.strengths || []).map((x) => `<li>${escapeHtml(x)}</li>`).join('');
  const watchouts = (mbtiDetail.watchouts || []).map((x) => `<li>${escapeHtml(x)}</li>`).join('');
  const iceberg = sp.iceberg_model || {};
  const icebergFields = [
    ['知识', iceberg.knowledge],
    ['技能', iceberg.skills],
    ['自我概念', iceberg.self_concept],
    ['特质', iceberg.traits],
    ['动机', iceberg.motivation],
  ];
  const hasHollandData = sp.holland_scores && Object.keys(sp.holland_scores).length > 0;
  const icebergCards = icebergFields
    .filter(([, v]) => v)
    .map(([k, v]) => `<div class="iceberg-item"><div class="k">${k}</div><div class="v">${escapeHtml(v)}</div></div>`)
    .join('');
  return `
    <div class="career-tools-wrap">
      <section class="career-panel">
        <h4 class="career-title">霍兰德兴趣类型雷达</h4>
        ${hasHollandData ? buildHollandRadar(sp) : '<p class="empty-note">暂无霍兰德分数，可在对话中补充或从简历中自动提取。</p>'}
        <p class="holland-meta">霍兰德代码<span class="holland-code">${escapeHtml(hollandCode || '未提供')}</span></p>
        <p class="mbti-sub">代码解释</p>
        ${hollandMeanings ? `<ul class="mbti-list">${hollandMeanings}</ul>` : '<p class="empty-note">暂无解释</p>'}
        <p class="mbti-sub">匹配场景建议</p>
        ${hollandFitRoles ? `<ul class="mbti-list">${hollandFitRoles}</ul>` : '<p class="empty-note">暂无建议</p>'}
        <p class="mbti-sub">使用提醒</p>
        ${hollandWatchouts ? `<ul class="mbti-list">${hollandWatchouts}</ul>` : '<p class="empty-note">暂无提醒</p>'}
      </section>
      <section class="career-panel">
        <h4 class="career-title">MBTI解释与能力素质冰山模型</h4>
        <div class="mbti-detail-box">
          <p class="mbti-head">${escapeHtml(sp.mbti_type || '未提供')} ${mbtiDetail.label ? `- ${escapeHtml(mbtiDetail.label)}` : ''}</p>
          <p class="mbti-sub">维度解释</p>
          ${dimensionNotes ? `<ul class="mbti-list">${dimensionNotes}</ul>` : '<p class="empty-note">暂无MBTI维度解释</p>'}
          <div class="mbti-two-col">
            <div>
              <p class="mbti-sub">优势特征</p>
              ${strengths ? `<ul class="mbti-list">${strengths}</ul>` : '<p class="empty-note">暂无</p>'}
            </div>
            <div>
              <p class="mbti-sub">风险提醒</p>
              ${watchouts ? `<ul class="mbti-list">${watchouts}</ul>` : '<p class="empty-note">暂无</p>'}
            </div>
          </div>
          <p class="mbti-advice">发展建议：${escapeHtml(mbtiDetail.development_advice || '结合项目反馈持续校准MBTI结果')}</p>
        </div>
        <h4 class="career-title">冰山分层详情</h4>
        <div class="iceberg-grid">
          ${icebergCards || '<p class="empty-note">暂无冰山模型补充信息。你可在第三轮对话补充“知识/技能/特质/动机”等描述。</p>'}
        </div>
      </section>
    </div>`;
}

function renderAnalysis(data) {
  analysisLoaded.value = true;
  const sp = data.student_profile || {};
  const hollandScores = sp.holland_scores
    ? Object.entries(sp.holland_scores).map(([k, v]) => `${k}:${v}`).join('、')
    : '';
  const iceberg = sp.iceberg_model || {};
  const icebergSummary = [iceberg.knowledge, iceberg.skills, iceberg.self_concept, iceberg.traits, iceberg.motivation].filter(Boolean).join('；');
  studentProfileHtml.value = `
    <div class="student-profile-grid">
      <div class="profile-col">
        <div class="profile-item"><span class="k">完整度评分</span><span class="v">${escapeHtml(sp.completeness_score ?? '-')}</span></div>
        <div class="profile-item"><span class="k">竞争力评分</span><span class="v">${escapeHtml(sp.competitiveness_score ?? '-')}</span></div>
        <div class="profile-item"><span class="k">求职意向</span><span class="v">${escapeHtml(sp.employment_intention || '未明确')}</span></div>
        <div class="profile-item"><span class="k">MBTI</span><span class="v">${escapeHtml(sp.mbti_type || '未提供')}</span></div>
        <div class="profile-item"><span class="k">霍兰德代码</span><span class="v">${escapeHtml(sp.holland_code || '未提供')}</span></div>
        <div class="profile-item"><span class="k">霍兰德分数</span><span class="v">${escapeHtml(hollandScores || '未提供')}</span></div>
      </div>
      <div class="profile-col">
        <div class="profile-item"><span class="k">冰山模型补充</span><span class="v">${escapeHtml(icebergSummary || '未提供')}</span></div>
        <div class="profile-item"><span class="k">画像摘要</span><span class="v">${escapeHtml(sp.summary || '暂无')}</span></div>
        <div class="profile-item"><span class="k">技能</span><span class="v">${escapeHtml((sp.skills || []).join('、') || '暂无')}</span></div>
        <div class="profile-item"><span class="k">证书</span><span class="v">${escapeHtml((sp.certificates || []).join('、') || '暂无')}</span></div>
      </div>
    </div>`;
  careerToolsHtml.value = renderCareerToolsHtml(sp);
  matchTableHtml.value = renderMatches(data.matches || []);
  verticalGraphHtml.value = toListHtml((data.vertical_graph || []).slice(0, 8).map((x) => `${x.job_title}: ${(x.path || []).join(' -> ')}`));
  transitionGraphHtml.value = toListHtml((data.transition_graph || []).map((x) => `${x.job_title} -> ${(x.transitions || []).join(' / ')}`));
}

function setReportMarkdown(md) {
  reportPreviewHtml.value = renderMarkdown(md || '');
}

function syncDialogueTurn(turn) {
  dialogueState = turn.state;
  finalStudentText = turn.final_student_text || finalStudentText;
  syncUserContextFromState(dialogueState);
  const recommended = Array.isArray(dialogueState?.recommended_jobs) ? dialogueState.recommended_jobs.filter(Boolean) : [];
  recommendedText.value = recommended.length ? `当前推荐岗位：${recommended.slice(0, 8).join('、')}` : '';
  stepProgress.value = Number(turn.step || 1);
  addDialogue('bot', turn.assistant_message || '继续说说你的想法吧。');
  setStatusText(turn.ready ? '三轮采集完成，可生成报告。' : `第${turn.step || 1}轮进行中，请继续回答。`);
}

async function startDialogueFlow() {
  try {
    const ctx = getDialogueUserContext();
    const data = await apiStartDialogue(ctx);
    if (!data || !data.ok) throw new Error(data?.error || data?.message || '对话启动失败');
    dialogueState = data.state;
    syncUserContextFromState(dialogueState);
    stepProgress.value = Number(data.step || 1);
    addDialogue('bot', data.assistant_message || '我们开始吧。');
    setStatusText('第1轮进行中，请回答问题。');
  } catch (err) {
    setStatusText(`对话初始化失败: ${err.message}`);
  }
}

async function sendUserMessage() {
  const answer = chatInput.value.trim();
  if (!answer) {
    setStatusText('请输入内容后再发送。');
    return;
  }
  chatInput.value = '';
  resizeChatInput();
  addDialogue('user', answer);
  sendBusy.value = true;
  setStatusText('正在认真分析你的回答，可能需要一定时间，请稍等...');
  try {
    const statePayload = (dialogueState && typeof dialogueState === 'object') ? dialogueState : {};
    const ctx = mergeUserContextIntoState(statePayload);
    const data = await apiTurnDialogue({
      state: statePayload,
      user_message: answer,
      grade: ctx.grade,
      major: ctx.major,
    });
    if (!data || !data.ok) throw new Error(data?.error || data?.message || '对话处理失败');
    syncDialogueTurn(data);
  } catch (err) {
    setStatusText(`失败: ${err.message}`);
  } finally {
    sendBusy.value = false;
  }
}

function triggerUpload() {
  resumeFileInputEl.value?.click();
}

async function onPickResume(evt) {
  const file = evt.target.files && evt.target.files[0];
  if (!file) return;
  setStatusText('正在读取简历文件...');
  uploadBusy.value = true;
  sendBusy.value = true;
  try {
    const data = await uploadCareerResume(file);
    if (!data || !data.ok) throw new Error(data?.error || data?.message || '简历解析失败');
    addDialogue('bot', `已读取文件：${data.filename}，已提取文本。`);
    chatInput.value = data.text || '';
    nextTick(resizeChatInput);
    if (dialogueState?.node === 'r1_resume') {
      setStatusText('简历已提取，正在自动发送给系统分析...');
      await sendUserMessage();
    } else {
      setStatusText('简历已提取到输入框，可编辑后发送。');
    }
  } catch (err) {
    setStatusText(`简历上传失败: ${err.message}`);
  } finally {
    uploadBusy.value = false;
    sendBusy.value = false;
    if (resumeFileInputEl.value) resumeFileInputEl.value.value = '';
  }
}

async function streamReportAll(analysis) {
  reportTyping.value = true;
  let assembled = '';
  await new Promise((resolve, reject) => {
    let errored = false;
    streamCareerReport({
      student_profile: analysis.student_profile,
      matches: analysis.matches,
      vertical_graph: analysis.vertical_graph,
      transition_graph: analysis.transition_graph,
    }, {
      onMessage(event) {
        if (event.type === 'stage') {
          reportStage.value = event.message || '处理中';
        } else if (event.type === 'chunk') {
          assembled += event.content || '';
          currentReportMarkdown = assembled;
          setReportMarkdown(assembled);
        } else if (event.type === 'done') {
          reportStage.value = event.mode === 'ai' ? '报告已完成（AI）' : '报告已完成（流式）';
        } else if (event.type === 'warn') {
          setStatusText(`提示: ${event.message || '已完成但存在警告'}`);
        } else if (event.type === 'error') {
          errored = true;
          reject(new Error(event.message || '流式生成失败'));
        }
      },
      onError(err) {
        if (!errored) reject(err);
      },
      onClose() {
        if (!errored) resolve();
      },
    });
  });
  reportTyping.value = false;
}

async function analyze() {
  if (!dialogueState?.ready) {
    setStatusText('请先完成三轮对话采集。');
    return;
  }
  setStatusText('正在汇总并生成分析，可能需要几分钟，请稍候...');
  try {
    const data = await analyzeCareer({ student_text: finalStudentText, include_report: false });
    if (!data || !data.ok) throw new Error(data?.error || data?.message || '分析失败');
    renderAnalysis(data);
    currentReportMarkdown = '';
    setReportMarkdown('### 正在生成报告\n\n已完成三轮采集，正在流式输出完整报告内容。');
    reportStage.value = '正在排队生成';
    setStatusText('匹配结果已完成，正在生成完整报告，请稍候...');
    await streamReportAll(data);
    if (!currentReportMarkdown) throw new Error('报告内容为空');
    setStatusText('报告已生成，可导出PDF。');
  } catch (err) {
    reportTyping.value = false;
    reportStage.value = '生成失败';
    setStatusText(`失败: ${err.message}`);
  }
}

async function exportAll() {
  if (!currentReportMarkdown) {
    setStatusText('当前没有可导出的报告。');
    return;
  }
  setStatusText('正在导出报告...');
  try {
    const data = await exportCareerReport({
      report_markdown: currentReportMarkdown,
      report_name: `career_report_${Date.now()}`,
    });
    if (!data || !data.ok) throw new Error(data?.error || data?.message || '导出失败');
    const mdUrl = `/api/reports/${encodePathParts(data.files.markdown)}/raw`;
    const htmlUrl = `/api/reports/${encodePathParts(data.files.html)}/raw`;
    const pdfUrl = `/api/reports/${encodePathParts(data.files.pdf)}/raw`;
    setStatusText(`导出完成: ${data.files.pdf} | ${data.files.html} | ${data.files.markdown}`);
    window.open(pdfUrl, '_blank');
    window.open(htmlUrl, '_blank');
    window.open(mdUrl, '_blank');
  } catch (err) {
    setStatusText(`导出失败: ${err.message}`);
  }
}

async function exportPdfOnly() {
  if (!currentReportMarkdown) return;
  setStatusText('正在导出 PDF...');
  try {
    const data = await exportCareerReport({
      report_markdown: currentReportMarkdown,
      report_name: `career_report_${Date.now()}`,
    });
    if (!data || !data.ok) throw new Error(data?.error || data?.message || '导出失败');
    const pdfUrl = `/api/reports/${encodePathParts(data.files.pdf)}/raw`;
    window.location.href = pdfUrl;
    setStatusText(`PDF 报告已导出: ${data.files.pdf}`);
  } catch (err) {
    setStatusText(`导出 PDF 失败: ${err.message}`);
  }
}

async function refreshStatusBadge() {
  try {
    const data = await fetchStatus();
    if (!data || !data.ok) throw new Error(data?.error || '获取状态失败');
    const username = String(data.username || '').trim() || '用户';
    statusBadgeText.value = data.logged_in ? `已登录: ${username}` : '未登录';
  } catch {
    statusBadgeText.value = '状态获取失败';
  }
}

function goHome() {
  window.location.href = '/';
}

onMounted(async () => {
  stepProgress.value = 1;
  resizeChatInput();
  await refreshStatusBadge();
  await startDialogueFlow();
});
</script>
