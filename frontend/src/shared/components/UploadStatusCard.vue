<script setup lang="ts">
import { computed } from "vue";
import type { UploadStatus } from "@/shared/types";

const props = defineProps<{
  status: UploadStatus;
}>();

const isFailed = computed(() => props.status.phase === "error");
const isReady = computed(() => props.status.phase === "ready");
const isRunning = computed(() => !isReady.value && !isFailed.value);
</script>

<template>
  <div
    class="upload-status-card"
    :class="{ 'is-error': isFailed, 'is-ready': isReady }"
    data-testid="upload-status-card"
  >
    <div class="upload-status-card__head">
      <strong class="upload-status-card__name" :title="status.fileName">{{ status.fileName }}</strong>
      <span class="upload-status-card__pct">{{ status.progress }}%</span>
    </div>

    <div
      class="upload-status-card__track"
      role="progressbar"
      :aria-valuenow="status.progress"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="status.stageLabel"
    >
      <span
        class="upload-status-card__fill"
        :class="{ 'is-running': isRunning }"
        :style="{ width: `${status.progress}%` }"
      />
    </div>

    <p class="upload-status-card__meta">
      <span class="upload-status-card__stage">{{ status.errorMessage || status.stageLabel }}</span>
      <span v-if="isReady" class="upload-status-card__hint">{{ status.fileSizeLabel }}</span>
      <span v-else-if="isRunning" class="upload-status-card__hint">解析完成后可打开</span>
    </p>
  </div>
</template>

<style scoped>
.upload-status-card {
  display: flex;
  width: min(360px, 100%);
  flex-direction: column;
  gap: 6px;
  padding: 9px 11px;
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  border-radius: 11px;
}

.upload-status-card.is-error {
  border-color: var(--color-danger);
}

.upload-status-card__head {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 8px;
}

.upload-status-card__name {
  overflow: hidden;
  flex: 1;
  color: var(--color-text);
  font-size: 12px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-status-card__pct {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.upload-status-card__track {
  position: relative;
  width: 100%;
  height: 4px;
  overflow: hidden;
  background: var(--color-border);
  border-radius: 999px;
}

.upload-status-card__fill {
  display: block;
  height: 100%;
  background: var(--color-accent);
  border-radius: inherit;
  transition: width 0.4s ease;
}

.upload-status-card__fill.is-running {
  background-image: linear-gradient(
    90deg,
    var(--color-accent) 0%,
    var(--color-border-accent) 50%,
    var(--color-accent) 100%
  );
  background-size: 200% 100%;
  animation: upload-sweep 1.6s linear infinite;
}

.upload-status-card.is-error .upload-status-card__fill {
  background: var(--color-danger);
}

.upload-status-card__meta {
  display: flex;
  min-width: 0;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 11px;
}

.upload-status-card__stage {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-status-card__hint {
  flex: 0 0 auto;
  color: var(--color-text-muted);
  font-size: 10px;
}

@keyframes upload-sweep {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .upload-status-card__fill.is-running {
    animation: none;
  }
}

@media (max-width: 1100px) {
  .upload-status-card {
    width: min(300px, 100%);
  }
}
</style>
