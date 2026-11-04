<script setup lang="ts">
defineProps<{
  itemCount: number;
  isRefreshing: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
}>();
</script>

<template>
  <header class="feed-view__bar">
    <div>
      <p class="feed-view__eyebrow">Feed · 未处理 {{ itemCount }} 条</p>
      <h1 class="feed-view__title">领域跟进</h1>
      <p class="feed-view__subtitle">订阅关键词 / 作者 / venue，抓取新论文并存入阅读队列。</p>
    </div>
    <div class="feed-view__actions">
      <button
        type="button"
        class="feed-view__refresh"
        :disabled="isRefreshing"
        @click="emit('refresh')"
      >
        {{ isRefreshing ? "抓取中…" : "刷新 Feed" }}
      </button>
    </div>
  </header>
</template>

<style scoped>
.feed-view__bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.feed-view__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.feed-view__title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 650;
}

.feed-view__subtitle {
  margin: 7px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.feed-view__refresh {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  padding: 8px 14px;
  color: var(--color-white);
  font-size: 12px;
}

.feed-view__refresh:disabled {
  opacity: 0.6;
}
</style>
