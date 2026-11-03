<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";
import MarkdownContent from "../../../components/MarkdownContent.vue";
import SourceCitationList from "../../chat/components/SourceCitationList.vue";
import { usePaperChat } from "../../../composables/usePaperChat";
import { useSourcePreview } from "../../../composables/useSourcePreview";
import type { SourceRef } from "../../../api";

const props = defineProps<{
  sessionId: string;
}>();

const {
  messages,
  isStreaming,
  errorMessage,
  openSession,
  regenerateLast,
  sendMessage,
  stopStreaming,
} = usePaperChat();
const { openCitation } = useSourcePreview();

const draft = ref("");
const ready = ref(false);
const listRef = ref<HTMLElement | null>(null);
let openedFor = "";

const SUGGESTIONS = ["总结本文方法", "这篇的局限是什么？", "实验用了哪些数据集？"];

async function ensureSession(): Promise<void> {
  if (!props.sessionId || openedFor === props.sessionId) {
    return;
  }
  openedFor = props.sessionId;
  ready.value = false;
  await openSession(props.sessionId);
  ready.value = true;
  await scrollToBottom();
}

async function scrollToBottom(): Promise<void> {
  await nextTick();
  const element = listRef.value;
  if (element) {
    element.scrollTop = element.scrollHeight;
  }
}

function ask(text: string): void {
  const value = text.trim();
  if (!value || isStreaming.value) {
    return;
  }
  draft.value = "";
  void sendMessage(value);
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
    return;
  }
  event.preventDefault();
  ask(draft.value);
}

function handleSource(source: SourceRef, index: number): void {
  void openCitation(source, index);
}

onMounted(() => {
  void ensureSession();
});

watch(
  () => props.sessionId,
  () => {
    openedFor = "";
    void ensureSession();
  },
);

watch(
  () => [messages.value.length, isStreaming.value, messages.value.at(-1)?.text.length],
  () => {
    void scrollToBottom();
  },
);
</script>

<template>
  <div class="ask-panel">
    <div ref="listRef" class="ask-panel__list">
      <p v-if="!ready" class="ask-panel__state">正在载入对话…</p>

      <div v-else-if="!messages.length" class="ask-panel__empty">
        <p>针对本文提问，回答会带 chunk 引用。</p>
        <button
          v-for="suggestion in SUGGESTIONS"
          :key="suggestion"
          type="button"
          class="ask-panel__suggestion"
          @click="ask(suggestion)"
        >
          {{ suggestion }}
        </button>
      </div>

      <template v-else>
        <article
          v-for="message in messages"
          :key="message.id"
          class="ask-message"
          :class="'ask-message--' + message.role"
        >
          <p v-if="message.role === 'user'" class="ask-message__text">{{ message.text }}</p>
          <MarkdownContent
            v-else
            :text="message.text || (isStreaming ? '正在检索论文并生成回答…' : '回答生成失败')"
          />
          <SourceCitationList
            v-if="message.role === 'assistant' && message.sources?.length"
            :sources="message.sources"
            @select="handleSource"
          />
        </article>
      </template>
    </div>

    <p v-if="errorMessage" class="ask-panel__error">{{ errorMessage }}</p>

    <div class="ask-panel__composer">
      <textarea
        v-model="draft"
        rows="2"
        placeholder="针对本文提问，Enter 发送…"
        @keydown="handleKeydown"
      />
      <div class="ask-panel__actions">
        <button
          v-if="messages.length && !isStreaming"
          type="button"
          class="ask-panel__link"
          @click="regenerateLast"
        >
          重新生成
        </button>
        <span class="ask-panel__spacer" />
        <button
          v-if="isStreaming"
          type="button"
          class="ask-panel__send"
          @click="stopStreaming"
        >
          停止
        </button>
        <button
          v-else
          type="button"
          class="ask-panel__send"
          :disabled="!draft.trim()"
          @click="ask(draft)"
        >
          发送
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ask-panel {
  display: flex;
  min-height: 0;
  height: 100%;
  flex: 1;
  flex-direction: column;
  overflow: hidden;
}

.ask-panel__list {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
  padding: 14px 16px;
}

.ask-panel__state,
.ask-panel__empty {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.ask-panel__empty p {
  margin: 0 0 10px;
}

.ask-panel__suggestion {
  display: block;
  width: 100%;
  margin-bottom: 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 7px 9px;
  color: var(--color-text-soft);
  font-size: 12px;
  text-align: left;
}

.ask-panel__suggestion:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.ask-message {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12.5px;
  line-height: 1.62;
}

.ask-message--user {
  align-items: flex-end;
}

.ask-message--user .ask-message__text {
  max-width: 90%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-user);
  padding: 7px 10px;
  color: var(--color-text);
}

.ask-message--assistant {
  border-left: 2px solid var(--color-accent);
  padding-left: 10px;
}

.ask-panel__error {
  margin: 0;
  padding: 0 16px 6px;
  color: var(--color-danger);
  font-size: 11px;
}

.ask-panel__composer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-top: 1px solid var(--color-border);
  padding: 10px 12px;
}

.ask-panel__composer textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 7px 9px;
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
}

.ask-panel__actions {
  display: flex;
  align-items: center;
}

.ask-panel__spacer {
  flex: 1;
}

.ask-panel__link {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--color-text-muted);
  font-size: 11px;
}

.ask-panel__link:hover {
  color: var(--color-accent);
}

.ask-panel__send {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  padding: 5px 12px;
  color: var(--color-white);
  font-size: 11px;
}

.ask-panel__send:disabled {
  opacity: 0.5;
}
</style>
