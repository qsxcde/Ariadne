<script setup lang="ts">
import { ArrowLeft, EditPen, Expand, Fold, Refresh } from "@element-plus/icons-vue";
import type { PaperDetail } from "@/api";
import { PAPER_STATUS_OPTIONS } from "@/shared/constants/paper";

defineProps<{
  paper: PaperDetail | null;
  isLoading: boolean;
  statusSaving: boolean;
  statusFeedback: string;
  inspectorCollapsed: boolean;
  shortcutHint: string;
}>();

const emit = defineEmits<{
  back: [];
  toggleInspector: [];
  editMetadata: [];
  refresh: [];
  changeStatus: [status: string];
}>();

function progressPercent(value: number): number {
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

function handleStatusChange(event: Event): void {
  emit("changeStatus", (event.target as HTMLSelectElement).value);
}
</script>

<template>
  <header class="paper-workspace__bar">
    <button type="button" class="paper-workspace__back" title="返回文献库" @click="emit('back')">
      <ArrowLeft class="paper-workspace__icon" />
      <span class="paper-workspace__action-label">返回</span>
    </button>
    <div class="paper-workspace__meta">
      <h1 class="paper-workspace__title">{{ paper?.title || "正在载入论文…" }}</h1>
      <p class="paper-workspace__sub">
        <span v-if="(paper?.authors ?? []).length">{{ (paper?.authors ?? []).join("、") }}</span>
        <span v-if="paper?.year"> · {{ paper.year }}</span>
        <span v-if="paper?.venue"> · {{ paper.venue }}</span>
        <span v-if="(paper?.collections ?? []).length">
          · {{ paper?.collections?.[0]?.name }}
        </span>
      </p>
    </div>
    <div class="paper-workspace__actions">
      <label v-if="paper" class="paper-workspace__status-field">
        <span>状态</span>
        <select
          class="paper-workspace__status"
          :value="paper.reading_status"
          :disabled="statusSaving"
          aria-label="阅读状态"
          @change="handleStatusChange"
        >
          <option v-for="option in PAPER_STATUS_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <span
        v-if="paper"
        class="paper-workspace__progress-inline"
        :title="`阅读进度 ${progressPercent(paper.progress)}%`"
      >
        <span class="paper-workspace__progress-track" aria-hidden="true">
          <span
            class="paper-workspace__progress-fill"
            :style="{ width: `${progressPercent(paper.progress)}%` }"
          />
        </span>
        <span class="paper-workspace__progress-pct">{{ progressPercent(paper.progress) }}%</span>
      </span>
      <span v-if="statusFeedback" class="paper-workspace__saved">{{ statusFeedback }}</span>
      <button
        type="button"
        class="paper-workspace__icon-button"
        :aria-pressed="!inspectorCollapsed"
        :title="shortcutHint"
        @click="emit('toggleInspector')"
      >
        <Expand v-if="inspectorCollapsed" />
        <Fold v-else />
        <span class="paper-workspace__action-label">
          {{ inspectorCollapsed ? "显示面板" : "隐藏面板" }}
        </span>
      </button>
      <button
        type="button"
        class="paper-workspace__icon-button"
        :disabled="!paper"
        title="编辑论文信息"
        @click="emit('editMetadata')"
      >
        <EditPen />
        <span class="paper-workspace__action-label">编辑信息</span>
      </button>
      <button
        type="button"
        class="paper-workspace__icon-button"
        :disabled="isLoading"
        title="刷新论文数据"
        @click="emit('refresh')"
      >
        <Refresh />
        <span class="paper-workspace__action-label">刷新</span>
      </button>
    </div>
  </header>
</template>

<style scoped>
.paper-workspace__bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-panel);
}

.paper-workspace__back,
.paper-workspace__icon-button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-soft);
  cursor: pointer;
  font-size: 11px;
  padding: 0 8px;
  height: 30px;
}

.paper-workspace__back {
  flex: 0 0 auto;
  border-color: transparent;
  background: transparent;
  padding: 0 6px;
}

.paper-workspace__back:hover,
.paper-workspace__icon-button:hover {
  border-color: var(--color-border-strong);
  color: var(--color-text);
}

.paper-workspace__icon-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.paper-workspace__icon-button svg {
  width: 14px;
  height: 14px;
}

.paper-workspace__icon {
  width: 14px;
  height: 14px;
}

.paper-workspace__meta {
  min-width: 0;
  flex: 1;
}

.paper-workspace__title {
  margin: 0;
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 19px;
  font-weight: 650;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-workspace__sub {
  margin: 3px 0 0;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-workspace__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
}

.paper-workspace__status-field {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.paper-workspace__status {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  background: var(--color-surface);
  color: var(--color-text);
  font-size: 11px;
  padding: 5px 7px;
}

.paper-workspace__progress-inline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
}

.paper-workspace__progress-track {
  display: block;
  width: 54px;
  height: 3px;
  overflow: hidden;
  background: var(--color-border);
}

.paper-workspace__progress-fill {
  display: block;
  height: 100%;
  background: var(--color-aqua);
}

.paper-workspace__progress-pct {
  width: 30px;
  text-align: right;
}

.paper-workspace__saved {
  color: var(--color-success);
  font-size: 10px;
  white-space: nowrap;
}

@media (max-width: 1280px) {
  .paper-workspace__action-label {
    display: none;
  }

  .paper-workspace__bar {
    padding: 10px 16px;
  }

  .paper-workspace__status-field > span {
    display: none;
  }
}
</style>
