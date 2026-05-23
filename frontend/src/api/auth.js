import { get, post } from './client.js';

export function fetchStatus() {
  return get('/api/status');
}

export function login(username, password) {
  return post('/api/auth/login', { username, password });
}

export function register(username, password) {
  return post('/api/auth/register', { username, password });
}

export function logout() {
  return post('/api/auth/logout');
}
