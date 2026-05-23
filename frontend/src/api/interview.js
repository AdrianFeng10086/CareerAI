import { post, request, get } from './client.js';

export async function uploadInterviewResume(file) {
  const formData = new FormData();
  formData.append('file', file);
  return request('/api/interview/resume/parse', { method: 'POST', body: formData });
}

export function startInterview(payload) {
  return post('/api/interview/start', payload);
}

export function submitInterviewAnswer(payload) {
  return post('/api/interview/answer', payload);
}

export function fetchCameraStats(sessionId) {
  return get(`/api/interview/camera/stats/${encodeURIComponent(sessionId)}`);
}

export function stopInterview(payload) {
  return post('/api/interview/stop', payload);
}
