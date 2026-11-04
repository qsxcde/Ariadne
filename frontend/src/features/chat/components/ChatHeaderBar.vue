<script setup lang="ts">
import { Document } from "@element-plus/icons-vue";

defineProps<{
  paperHint: string;
  sessionTitle: string;
  canOpenReader: boolean;
  /** 阅读器被解析阻塞时的说明，例如「正在解析 PDF 35%」 */
  readerHint?: string;
}>();

const emit = defineEmits<{
  openReader: [];
}>();
</script>

<template>
  <header class="chat-header-bar">
    <div class="chat-header-bar__content">
      <h2 class="chat-header-bar__title">
        {{ sessionTitle || "新对话" }}
      </h2>
      <p v-if="paperHint" class="chat-header-bar__hint">
        {{ paperHint }}
      </p>
      <p v-else class="chat-header-bar__hint">暂未关联论文</p>
    </div>

    <div class="chat-header-bar__reader-area">
      <span v-if="!canOpenReader && readerHint" class="chat-header-bar__reader-hint">
        {{ readerHint }}
      </span>
      <el-button
        class="chat-header-bar__reader"
        :icon="Document"
        :disabled="!canOpenReader"
        :title="canOpenReader ? '打开原文阅读器' : readerHint || '解析完成后可打开'"
        text
        size="small"
        @click="emit('openReader')"
      >
        原文
      </el-button>
    </div>
  </header>
</template>

<style scoped>
.chat-header-bar {
  display: flex;
  width: min(100%, 1080px);
  align-items: center;
  gap: 10px;
  justify-content: space-between;
  margin: 0 auto;
  padding: 0 0 14px;
}

.chat-header-bar__content {
  min-width: 0;
}

.chat-header-bar__title {
  overflow: hidden;
  color: var(--color-text);
  font-size: 20px;
  font-weight: 850;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-header-bar__hint {
  margin-top: 3px;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-header-bar__reader-area {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.chat-header-bar__reader-hint {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.chat-header-bar__reader {
  flex: 0 0 auto;
  color: var(--color-text-soft);
  font-size: 12px;
}

@media (max-width: 1200px) {
  .chat-header-bar {
    width: min(100%, 900px);
  }
}

@media (max-width: 1100px) {
  .chat-header-bar__title {
    max-width: 320px;
    font-size: 18px;
  }

  .chat-header-bar__reader-hint {
    display: none;
  }
}
</style>
