<script setup lang="ts">
type Mode = "fast" | "agent";

const props = defineProps<{
  modelValue: Mode;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: Mode];
}>();

const OPTIONS: { value: Mode; label: string; title: string }[] = [
  { value: "fast", label: "快速", title: "单次检索后直接回答" },
  { value: "agent", label: "Agent", title: "多步检索，展示过程与来源" },
];

function select(value: Mode): void {
  if (value !== props.modelValue) {
    emit("update:modelValue", value);
  }
}
</script>

<template>
  <div class="mode-switch" role="group" aria-label="回答模式">
    <button
      v-for="option in OPTIONS"
      :key="option.value"
      type="button"
      class="mode-switch__option"
      :class="{ 'is-active': modelValue === option.value }"
      :aria-pressed="modelValue === option.value"
      :title="option.title"
      @click="select(option.value)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
.mode-switch {
  display: inline-flex;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 2px;
}

.mode-switch__option {
  border: 0;
  border-radius: calc(var(--radius-sm) - 2px);
  background: transparent;
  padding: 3px 9px;
  color: var(--color-text-muted);
  font-size: 11px;
  line-height: 1.6;
  transition:
    background 0.14s ease,
    color 0.14s ease;
}

.mode-switch__option.is-active {
  background: var(--color-text);
  color: var(--color-white);
}
</style>
