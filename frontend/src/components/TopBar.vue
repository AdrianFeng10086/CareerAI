<template>
  <header class="top-bar">
    <div class="brand-chip">{{ brand }}</div>
    <div class="top-right">
      <slot />
    </div>
  </header>
</template>

<script setup>
defineProps({
  brand: { type: String, required: true },
});
</script>
