<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";

import { fetchBlockCrop } from "@/api";

const props = withDefaults(
  defineProps<{
    sessionId: string;
    documentId: string;
    blockId: string;
    alt?: string;
    scale?: number;
  }>(),
  { alt: "论文原图", scale: 2 },
);

const emit = defineEmits<{ error: [] }>();

const src = ref("");
const failed = ref(false);
let objectUrl: string | null = null;
let loadToken = 0;

function release(): void {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
}

async function load(): Promise<void> {
  const token = ++loadToken;
  release();
  src.value = "";
  failed.value = false;
  if (!props.blockId) {
    return;
  }
  try {
    const blob = await fetchBlockCrop(
      props.sessionId,
      props.documentId,
      props.blockId,
      props.scale,
    );
    if (token !== loadToken) {
      return;
    }
    objectUrl = URL.createObjectURL(blob);
    src.value = objectUrl;
  } catch {
    if (token === loadToken) {
      failed.value = true;
      emit("error");
    }
  }
}

watch(
  () => [props.sessionId, props.documentId, props.blockId, props.scale],
  load,
  { immediate: true },
);

onBeforeUnmount(() => {
  loadToken += 1;
  release();
});
</script>

<template>
  <img v-if="src" :src="src" :alt="alt" class="block-crop" loading="lazy" />
  <span v-else-if="!failed" class="block-crop block-crop--loading" aria-hidden="true" />
</template>

<style scoped>
.block-crop {
  display: block;
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-sm);
}

.block-crop--loading {
  width: 100%;
  min-height: 64px;
  background: var(--color-surface-alt);
}
</style>
