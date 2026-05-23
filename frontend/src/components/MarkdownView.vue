<template>
  <div ref="hostEl" :class="rootClass" v-html="html"></div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue';
import { renderMarkdown, renderMermaid } from '../utils/markdown.js';

const props = defineProps({
  source: { type: String, default: '' },
  preRendered: { type: String, default: '' },
  rootClass: { type: String, default: 'markdown-body' },
  useMarkdownIt: { type: Boolean, default: false },
  enableMermaid: { type: Boolean, default: true },
});

const hostEl = ref(null);
const html = ref('');

function rebuild() {
  if (props.preRendered && props.preRendered.trim()) {
    html.value = props.preRendered;
  } else {
    html.value = renderMarkdown(props.source || '', { useMarkdownIt: props.useMarkdownIt });
  }
}

async function afterUpdate() {
  if (!props.enableMermaid) return;
  await nextTick();
  if (hostEl.value) await renderMermaid(hostEl.value);
}

watch(() => [props.source, props.preRendered], () => {
  rebuild();
  afterUpdate();
});

onMounted(() => {
  rebuild();
  afterUpdate();
});
</script>
