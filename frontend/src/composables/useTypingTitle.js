import { onMounted, onBeforeUnmount } from 'vue';

export function useTypingTitle(targetRef, { stepMs = 80, holdMs = 700 } = {}) {
  let cancelled = false;
  let timer = null;

  function clear() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function type(el, text, idx = 0) {
    if (cancelled) return;
    if (idx > text.length) {
      timer = setTimeout(() => {
        if (cancelled) return;
        el.textContent = '';
        type(el, text, 0);
      }, holdMs);
      return;
    }
    el.textContent = text.slice(0, idx);
    timer = setTimeout(() => type(el, text, idx + 1), stepMs);
  }

  onMounted(() => {
    const el = targetRef.value;
    if (!el) return;
    const text = el.dataset.text || el.textContent || '';
    el.textContent = '';
    el.dataset.text = text;
    type(el, text, 0);
  });

  onBeforeUnmount(() => {
    cancelled = true;
    clear();
  });
}
