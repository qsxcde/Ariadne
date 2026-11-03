<script setup lang="ts">
withDefaults(
  defineProps<{
    kind: "loading" | "empty" | "error";
    title?: string;
    description?: string;
    actionLabel?: string;
    compact?: boolean;
  }>(),
  {
    title: "",
    description: "",
    actionLabel: "",
    compact: false,
  },
);

defineEmits<{
  action: [];
}>();

const LABELS = {
  loading: "LOADING",
  empty: "EMPTY",
  error: "ERROR",
} as const;
</script>

<template>
  <div
    class="state-block"
    :class="['state-block--' + kind, { 'state-block--compact': compact }]"
    :role="kind === 'error' ? 'alert' : 'status'"
    :aria-live="kind === 'loading' ? 'polite' : undefined"
  >
    <span class="state-block__eyebrow">{{ LABELS[kind] }}</span>
    <p v-if="title" class="state-block__title">{{ title }}</p>
    <p v-if="description" class="state-block__desc">{{ description }}</p>
    <div v-if="actionLabel || $slots.actions" class="state-block__actions">
      <slot name="actions">
        <button v-if="actionLabel" type="button" @click="$emit('action')">
          {{ actionLabel }}
        </button>
      </slot>
    </div>
    <slot />
  </div>
</template>

<style scoped>
.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 56px 24px;
  text-align: center;
}

.state-block--compact {
  padding: 22px 14px;
}

.state-block__eyebrow {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.16em;
}

.state-block--error .state-block__eyebrow {
  color: var(--color-danger);
}

.state-block--loading .state-block__eyebrow {
  animation: state-pulse 1.2s ease-in-out infinite;
}

.state-block__title {
  margin: 2px 0 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
}

.state-block__desc {
  max-width: 46ch;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.state-block--error .state-block__desc {
  color: var(--color-danger);
}

.state-block__actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.state-block__actions button {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 12px;
  color: var(--color-text-soft);
  font-size: 11px;
}

.state-block__actions button:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

@keyframes state-pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}
</style>
