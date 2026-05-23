<template>
  <p class="eyebrow">{{ eyebrow }}</p>
  <h1 ref="titleEl" class="typing-title" :data-text="title">{{ title }}</h1>
  <p class="hero-subtitle">{{ subtitle }}</p>
</template>

<script setup>
import { ref } from 'vue';
import { useTypingTitle } from '../composables/useTypingTitle.js';

defineProps({
  eyebrow: { type: String, default: '' },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
});

const titleEl = ref(null);
useTypingTitle(titleEl, { stepMs: 190, holdMs: 1200 });
</script>
