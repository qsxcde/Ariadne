<script setup lang="ts">
import { useSynthesis } from "../../composables/useSynthesis";

const { papers, question, answer, isAsking, selectedCollectionId, ask } = useSynthesis();
</script>

<template>
  <section class="synthesis__ask-pane">
    <header class="synthesis__pane-head">
      <h2>集合问答</h2>
      <span>{{ papers.length }} 篇论文</span>
    </header>
    <textarea
      v-model="question"
      class="synthesis__textarea"
      rows="3"
      placeholder="问一个跨论文的问题，例如：这几篇的方法差异是什么？"
    />
    <div class="synthesis__ask-actions">
      <span>回答保留 [Section | Chunk] 引用</span>
      <button
        type="button"
        class="synthesis__primary"
        :disabled="isAsking || !selectedCollectionId || !question.trim()"
        @click="ask"
      >
        {{ isAsking ? "回答中…" : "提问" }}
      </button>
    </div>
    <article v-if="answer" class="synthesis__answer">
      <p>{{ answer.answer }}</p>
      <p class="synthesis__answer-meta">
        引用 {{ answer.sources?.length ?? 0 }} 段 · 覆盖 {{ answer.paper_ids?.length ?? 0 }} 篇论文
      </p>
    </article>
  </section>
</template>

<style scoped>
.synthesis__ask-pane {
  max-width: 820px;
}

.synthesis__pane-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
  margin-bottom: 10px;
}

.synthesis__pane-head h2 {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
}

.synthesis__pane-head span {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.synthesis__textarea {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 9px 10px;
  color: var(--color-text);
  font: inherit;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
}

.synthesis__ask-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.synthesis__primary {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  padding: 7px 14px;
  color: var(--color-white);
  font-size: 12px;
}

.synthesis__primary:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.synthesis__answer {
  margin-top: 18px;
  border-left: 2px solid var(--color-accent);
  padding: 2px 0 2px 14px;
}

.synthesis__answer p {
  margin: 0;
  color: var(--color-text-body);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.synthesis__answer-meta {
  margin-top: 8px !important;
  color: var(--color-text-muted) !important;
  font-family: var(--font-mono);
  font-size: 10px !important;
}
</style>
