<script setup lang="ts">
import katex from "katex";
import "katex/dist/katex.min.css";
import { onMounted, ref, watch } from "vue";

const props = defineProps<{
  text: string;
  display: boolean;
}>();

const host = ref<HTMLElement | null>(null);

/**
 * KaTeX 只在本地把 LaTeX 串编译成受控 HTML（不执行脚本），
 * trust: false 关闭 \href、\htmlClass 等可注入面。
 */
function compile(): string {
  if (!props.text.trim()) {
    return "";
  }
  return katex.renderToString(props.text, {
    displayMode: props.display,
    throwOnError: false,
    strict: false,
    trust: false,
  });
}

function paint(): void {
  if (host.value) {
    host.value.innerHTML = compile();
  }
}

onMounted(paint);
watch(() => [props.text, props.display], paint);
</script>

<template>
  <span v-if="!display" ref="host" class="math-content math-content--inline" />
  <div v-else ref="host" class="math-content math-content--block" />
</template>

<style scoped>
.math-content--inline {
  display: inline-block;
  max-width: 100%;
  overflow-x: auto;
  vertical-align: middle;
}

.math-content--block {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 0;
}

.math-content--block :deep(.katex-display) {
  margin: 8px 0;
  text-align: left;
}

.math-content :deep(.katex) {
  font-size: 1.04em;
}
</style>
