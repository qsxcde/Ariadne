<script setup lang="ts">
import { useToday } from "@/pages/today/useToday";
import { formatDuration } from "@/shared/utils/format";

const {
  stats,
  weeklyNote,
  isSavingNote,
  readThisWeek,
  notesThisWeek,
  openQuestions,
  saveNote,
} = useToday();
</script>

<template>
  <aside class="today__week">
    <header class="today__section-head">
      <h2>本周</h2>
      <span>目标 3 篇</span>
    </header>

    <p class="today__metric">{{ readThisWeek }}<small> / 3 篇读完</small></p>

    <dl class="today__stats">
      <div>
        <dt>笔记</dt>
        <dd>{{ notesThisWeek }}</dd>
      </div>
      <div>
        <dt>开放问题</dt>
        <dd>{{ openQuestions }}</dd>
      </div>
      <div>
        <dt>本周阅读</dt>
        <dd>{{ formatDuration(stats?.reading_seconds_week ?? 0) }}</dd>
      </div>
      <div>
        <dt>今日阅读</dt>
        <dd>{{ formatDuration(stats?.reading_seconds_today ?? 0) }}</dd>
      </div>
    </dl>

    <label class="today__note">
      <span>本周复盘</span>
      <textarea
        v-model="weeklyNote"
        rows="5"
        maxlength="5000"
        placeholder="这周读完什么、卡在哪里、下周读什么…"
      />
    </label>
    <button type="button" class="today__save" :disabled="isSavingNote" @click="saveNote">
      {{ isSavingNote ? "保存中…" : "保存复盘" }}
    </button>
  </aside>
</template>

<style scoped>
.today__week {
  min-width: 0;
  border-left: 1px solid var(--color-border);
  padding-left: 28px;
}

.today__metric {
  margin: 4px 0 14px;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 38px;
  font-weight: 650;
  line-height: 1;
}

.today__metric small {
  color: var(--color-text-muted);
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 400;
}

.today__stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 18px;
  margin: 0 0 18px;
}

.today__stats div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.today__stats dt {
  color: var(--color-text-muted);
  font-size: 10px;
}

.today__stats dd {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-mono);
  font-size: 13px;
}

.today__note {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.today__note textarea {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 8px 9px;
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
  line-height: 1.6;
  resize: vertical;
}

.today__save {
  margin-top: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 12px;
  color: var(--color-text-soft);
  font-size: 11px;
}

.today__save:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.today__save:disabled {
  opacity: 0.6;
}

@media (max-width: 1100px) {
  .today__week {
    border-left: 0;
    border-top: 1px solid var(--color-border);
    padding: 18px 0 0;
  }
}
</style>
