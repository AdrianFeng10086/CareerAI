<template>
  <span :class="['status', extraClass]">{{ display }}</span>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  status: { type: Object, default: () => null },
  loading: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  fallback: { type: String, default: '系统状态检测中...' },
  extraClass: { type: String, default: '' },
});

const display = computed(() => {
  if (props.errorMessage) return `状态异常: ${props.errorMessage}`;
  if (props.loading) return props.fallback;
  if (!props.status) return props.fallback;
  const s = props.status;
  return [
    s.logged_in ? `账号: ${s.username || ''}` : '账号: 未登录',
    s.has_cookie ? 'Boss: 已登录' : 'Boss: 未登录',
    s.ai_configured ? `AI: ${s.ai_model || ''}` : 'AI: 未配置Key(将走规则解析)',
  ].join(' | ');
});
</script>
