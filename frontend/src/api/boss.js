import { get, post } from './client.js';

export function startMcpLogin() {
  return post('/api/boss/mcp-login/start');
}

export function fetchMcpTask(taskId) {
  return get(`/api/boss/mcp-login/task/${encodeURIComponent(taskId)}`);
}

export function mcpQrUrl(taskId) {
  return `/api/boss/mcp-login/qr/${encodeURIComponent(taskId)}`;
}
