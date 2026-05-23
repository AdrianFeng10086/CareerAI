import { post, request } from './client.js';

export function startDialogue(context) {
  return post('/api/career/dialogue/start', context);
}

export function turnDialogue(payload) {
  return post('/api/career/dialogue/turn', payload);
}

export function analyzeCareer(payload) {
  return post('/api/career/analyze', payload);
}

export async function streamCareerReport(payload, { onMessage, onError, onClose }) {
  try {
    const resp = await request('/api/career/report/stream', {
      method: 'POST',
      body: payload,
      raw: true,
    });
    if (!resp.ok || !resp.body) {
      throw new Error('报告流式接口不可用');
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';
      for (const block of blocks) {
        parseBlock(block, onMessage);
      }
    }
    if (buffer.trim()) {
      parseBlock(buffer, onMessage);
    }
    if (onClose) onClose();
  } catch (err) {
    if (onError) onError(err);
  }
}

function parseBlock(block, onMessage) {
  const line = block.split('\n').find((x) => x.trim().startsWith('data:'));
  if (!line) return;
  const payload = line.replace(/^data:\s*/, '');
  try {
    const event = JSON.parse(payload);
    if (onMessage) onMessage(event);
  } catch { /* ignore parse errors */ }
}

export function exportCareerReport(payload) {
  return post('/api/career/export', payload);
}

export async function uploadCareerResume(file) {
  const formData = new FormData();
  formData.append('file', file);
  return request('/api/career/resume/parse', { method: 'POST', body: formData });
}
