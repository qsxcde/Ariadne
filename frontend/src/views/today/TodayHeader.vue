<script setup lang="ts">
defineProps<{
  todayLabel: string;
  paperCount: number;
}>();
</script>

<template>
  <header class="today__bar">
    <div>
      <p class="today__eyebrow">{{ todayLabel }} · 文献库 {{ paperCount }} 篇</p>
      <h1 class="today__title">今天读什么</h1>
      <p class="today__subtitle">继续上次的阅读，或从队列里挑一篇。</p>
    </div>
  </header>
</template>

<style scoped>
.today__bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}

.today__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.today__title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 650;
  letter-spacing: 0.01em;
}

.today__subtitle {
  margin: 7px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}
</style>
