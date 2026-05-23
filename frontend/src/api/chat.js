import { post } from './client.js';

export function submitChat(message) {
  return post('/api/chat', { message });
}
