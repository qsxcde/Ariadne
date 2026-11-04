<script setup lang="ts">
defineProps<{
  id: string;
  title: string;
  index: string;
  last?: boolean;
}>();
</script>

<template>
  <section :id="id" class="settings-section" :class="{ 'settings-section--last': last }">
    <header class="settings-section__head">
      <h2>{{ title }}</h2>
      <span class="settings-section__index">{{ index }}</span>
    </header>
    <slot />
  </section>
</template>

<style scoped>
.settings-section {
  padding-bottom: 26px;
  margin-bottom: 26px;
  border-bottom: 1px solid var(--color-border);
  scroll-margin-top: 80px;
}

.settings-section--last {
  border-bottom: 0;
  margin-bottom: 0;
}

.settings-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.settings-section__head h2 {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
}

.settings-section__index {
  color: var(--color-border-strong);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.1em;
}

:slotted(p) {
  margin: 0 0 8px;
  color: var(--color-text-soft);
  font-size: 13px;
  line-height: 1.7;
}
</style>
