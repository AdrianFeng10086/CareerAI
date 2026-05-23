import { ref, onMounted, onBeforeUnmount } from 'vue';
import { fetchStatus } from '../api/auth.js';

export function useStatus({ pollIntervalMs = 0 } = {}) {
  const isLoggedIn = ref(false);
  const username = ref('');
  const hasBossCookie = ref(false);
  const cookieAvailable = ref(false);
  const errorMessage = ref('');
  const lastChecked = ref(null);

  let timer = null;

  async function refresh() {
    try {
      const data = await fetchStatus();
      isLoggedIn.value = !!data.logged_in;
      username.value = data.username || '';
      hasBossCookie.value = !!data.has_cookie;
      cookieAvailable.value = !!data.has_cookie;
      errorMessage.value = '';
    } catch (err) {
      errorMessage.value = err.message || String(err);
      isLoggedIn.value = false;
      hasBossCookie.value = false;
      cookieAvailable.value = false;
    } finally {
      lastChecked.value = Date.now();
    }
  }

  onMounted(() => {
    refresh();
    if (pollIntervalMs > 0) {
      timer = setInterval(refresh, pollIntervalMs);
    }
  });

  onBeforeUnmount(() => {
    if (timer) clearInterval(timer);
  });

  return { isLoggedIn, username, hasBossCookie, cookieAvailable, errorMessage, lastChecked, refresh };
}
