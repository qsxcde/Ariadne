<script setup lang="ts">
import StateBlock from "@/shared/components/StateBlock.vue";
import {
  KIND_OPTIONS,
  SOURCE_OPTIONS,
  useFeed,
} from "@/pages/feed/useFeed";

const {
  subscriptions,
  kind,
  source,
  value,
  kindLabel,
  sourceLabel,
  addSubscription,
  removeSubscription,
} = useFeed();
</script>

<template>
  <aside class="feed-view__subscriptions">
    <header class="feed-view__section-head">
      <h2>订阅</h2>
      <span>{{ subscriptions.length }} 个</span>
    </header>

    <div class="feed-view__form">
      <div class="feed-view__form-row">
        <select v-model="source" class="feed-view__select">
          <option v-for="option in SOURCE_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <select v-model="kind" class="feed-view__select">
          <option v-for="option in KIND_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>
      <input
        v-model="value"
        class="feed-view__input"
        type="text"
        placeholder="RAG / Vaswani / NeurIPS"
        @keyup.enter="addSubscription"
      />
      <button type="button" class="feed-view__add" @click="addSubscription">添加订阅</button>
    </div>

    <StateBlock
      v-if="!subscriptions.length"
      kind="empty"
      compact
      description="还没有订阅。添加关键词或作者后刷新。"
    />
    <ul v-else class="feed-view__subs">
      <li v-for="subscription in subscriptions" :key="subscription.id">
        <span class="feed-view__sub-value">{{ subscription.value }}</span>
        <small>{{ sourceLabel(subscription.source) }} · {{ kindLabel(subscription.kind) }}</small>
        <button type="button" class="feed-view__link" @click="removeSubscription(subscription)">
          删除
        </button>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.feed-view__section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.feed-view__section-head h2 {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
}

.feed-view__section-head span {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.feed-view__form {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-bottom: 14px;
}

.feed-view__form-row {
  display: flex;
  gap: 6px;
}

.feed-view__input,
.feed-view__select {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 8px;
  color: var(--color-text);
  font: inherit;
  font-size: 11px;
}

.feed-view__form-row .feed-view__select {
  flex: 1;
}

.feed-view__add {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 10px;
  color: var(--color-text-soft);
  font-size: 11px;
}

.feed-view__add:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.feed-view__subs {
  margin: 0;
  padding: 0;
  list-style: none;
}

.feed-view__subs li {
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--color-border);
  padding: 8px 0;
  font-size: 11px;
}

.feed-view__sub-value {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  color: var(--color-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-view__subs small {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
}

.feed-view__link {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--color-text-muted);
  font-size: 10px;
}

.feed-view__link:hover {
  color: var(--color-accent);
}
</style>
