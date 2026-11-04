<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{
  running: boolean;
  hasRun: boolean;
}>();

const emit = defineEmits<{
  submit: [goal: string];
  stop: [];
}>();

const draft = ref("");

function submit(): void {
  const goal = draft.value.trim();
  if (!goal || props.running) {
    return;
  }
  draft.value = "";
  emit("submit", goal);
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
    return;
  }
  event.preventDefault();
  submit();
}
</script>

<template>
  <div class="run-composer">
    <textarea
      v-model="draft"
      rows="2"
      class="run-composer__input"
      :placeholder="hasRun ? '继续追问，或换一个研究目标…' : '提出需要多步检索的问题…'"
      @keydown="handleKeydown"
    />
    <div class="run-composer__actions">
      <span class="run-composer__hint">Enter 发送 · Shift+Enter 换行</span>
      <span class="run-composer__spacer" />
      <button
        v-if="running"
        type="button"
        class="run-composer__button run-composer__button--quiet"
        @click="emit('stop')"
      >
        停止
      </button>
      <button
        v-else
        type="button"
        class="run-composer__button"
        :disabled="!draft.trim()"
        @click="submit"
      >
        {{ hasRun ? "继续研究" : "开始研究" }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.run-composer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-top: 1px solid var(--color-border);
  padding: 10px 16px 12px;
}

.run-composer__input {
  width: 100%;
  resize: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 7px 9px;
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 12px;
  line-height: 1.5;
}

.run-composer__input:focus {
  border-color: var(--color-border-strong);
  outline: none;
}

.run-composer__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.run-composer__hint {
  color: var(--color-text-muted);
  font-size: 10px;
}

.run-composer__spacer {
  flex: 1;
}

.run-composer__button {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  padding: 4px 10px;
  color: var(--color-white);
  font-size: 11px;
}

.run-composer__button:disabled {
  border-color: var(--color-border);
  background: var(--color-border);
  color: var(--color-text-muted);
}

.run-composer__button--quiet {
  border-color: var(--color-border);
  background: transparent;
  color: var(--color-text-soft);
}
</style>
