<script setup lang="ts">
import type { SelectionAskMode } from "@/shared/types";

defineProps<{
  menu: { text: string; x: number; y: number };
}>();

const emit = defineEmits<{
  note: [];
  ask: [mode: SelectionAskMode];
}>();

const ASK_ACTIONS: { mode: SelectionAskMode; label: string }[] = [
  { mode: "explain", label: "解释" },
  { mode: "translate", label: "翻译" },
  { mode: "simplify", label: "简化" },
  { mode: "followup", label: "追问" },
];
</script>

<template>
  <div class="paper-selection" :style="{ left: `${menu.x}px`, top: `${menu.y}px` }">
    <button type="button" class="paper-selection__action" @click="emit('note')">记笔记</button>
    <button
      v-for="action in ASK_ACTIONS"
      :key="action.mode"
      type="button"
      class="paper-selection__action"
      @click="emit('ask', action.mode)"
    >
      {{ action.label }}
    </button>
  </div>
</template>

<style scoped>
.paper-selection {
  position: fixed;
  z-index: var(--z-selection);
  display: flex;
  gap: 2px;
  padding: 4px;
  background: var(--color-text);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-float);
  transform: translate(-50%, calc(-100% - 10px));
}

.paper-selection__action {
  padding: 5px 10px;
  color: var(--color-on-dark);
  font-size: 12px;
  background: none;
  border: 0;
  border-radius: var(--radius-xs);
}

.paper-selection__action:hover {
  color: var(--color-text);
  background: var(--color-white);
}
</style>
