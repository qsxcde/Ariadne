<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";

import { getCitations, getGlossary } from "@/api/papers";
import { usePapers } from "@/features/library/composables/usePapers";
import PaperAskPanel from "@/features/reader/components/PaperAskPanel.vue";
import PaperBriefPanel from "@/features/reader/components/PaperBriefPanel.vue";
import PaperNotesPanel from "@/features/reader/components/PaperNotesPanel.vue";
import type { AnnotationSummary, CitationGraph, GlossaryResponse } from "@/api";

const props = defineProps<{
  paperId: string;
  sessionId: string;
}>();

const emit = defineEmits<{
  jumpSection: [title: string];
  locate: [annotation: AnnotationSummary];
}>();

const INSPECTOR_TABS = [
  { value: "brief", label: "速读" },
  { value: "ask", label: "问答" },
  { value: "notes", label: "笔记" },
  { value: "terms", label: "术语" },
  { value: "citations", label: "引用" },
] as const;

const { currentPaper } = usePapers();

const activeTab = ref<(typeof INSPECTOR_TABS)[number]["value"]>("brief");
const glossary = ref<GlossaryResponse | null>(null);
const citations = ref<CitationGraph | null>(null);
const isGlossaryLoading = ref(false);
const isCitationsLoading = ref(false);

const annotations = computed<AnnotationSummary[]>(() => currentPaper.value?.annotations ?? []);

async function loadCitations(): Promise<void> {
  isCitationsLoading.value = true;
  try {
    citations.value = await getCitations(props.paperId);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "读取引用关系失败");
  } finally {
    isCitationsLoading.value = false;
  }
}

async function generateGlossary(): Promise<void> {
  isGlossaryLoading.value = true;
  try {
    glossary.value = await getGlossary(props.paperId);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "生成术语表失败");
  } finally {
    isGlossaryLoading.value = false;
  }
}
</script>

<template>
  <div class="paper-workspace__inspector-inner">
    <div class="paper-workspace__tabs" role="tablist" aria-label="论文检查器">
      <button
        v-for="tab in INSPECTOR_TABS"
        :key="tab.value"
        type="button"
        role="tab"
        class="paper-workspace__tab"
        :class="{ 'is-active': activeTab === tab.value }"
        :aria-selected="activeTab === tab.value"
        @click="activeTab = tab.value"
      >
        {{ tab.label }}
        <span v-if="tab.value === 'notes' && annotations.length" class="paper-workspace__tab-count">
          {{ annotations.length }}
        </span>
      </button>
    </div>

    <div
      class="paper-workspace__inspector-body"
      :class="{ 'paper-workspace__inspector-body--flush': activeTab === 'ask' }"
    >
      <PaperAskPanel v-if="activeTab === 'ask'" :session-id="sessionId" />
      <PaperBriefPanel
        v-show="activeTab === 'brief'"
        :paper-id="paperId"
        @jump-section="emit('jumpSection', $event)"
      />

      <section v-show="activeTab === 'terms'" class="paper-workspace__brief">
        <header class="paper-workspace__brief-head">
          <span class="paper-workspace__eyebrow">术语表</span>
          <button
            type="button"
            class="paper-workspace__secondary"
            :disabled="isGlossaryLoading"
            @click="generateGlossary"
          >
            {{ isGlossaryLoading ? "生成中…" : "生成术语表" }}
          </button>
        </header>
        <p v-if="!glossary" class="paper-workspace__empty">提取关键术语与一句话解释。</p>
        <ul v-else class="paper-workspace__brief-list">
          <li v-for="term in glossary.terms ?? []" :key="term.term">
            <strong>{{ term.term }}</strong>：{{ term.definition }}
          </li>
        </ul>
      </section>

      <section v-show="activeTab === 'citations'" class="paper-workspace__brief">
        <header class="paper-workspace__brief-head">
          <span class="paper-workspace__eyebrow">引用关系</span>
          <button
            type="button"
            class="paper-workspace__secondary"
            :disabled="isCitationsLoading"
            @click="loadCitations"
          >
            {{ isCitationsLoading ? "读取中…" : "查询 OpenAlex" }}
          </button>
        </header>
        <p v-if="!citations" class="paper-workspace__empty">
          通过 DOI / arXiv 查询被引与参考文献。
        </p>
        <div v-else class="paper-workspace__brief-body">
          <p>
            被引 {{ citations.cited_by_count }} 次 · 参考文献
            {{ citations.reference_count }} 篇
          </p>
          <ul class="paper-workspace__brief-list">
            <li
              v-for="reference in (citations.references ?? []).slice(0, 5)"
              :key="reference.openalex_id"
            >
              {{ reference.title }}<span v-if="reference.year">（{{ reference.year }}）</span>
            </li>
          </ul>
        </div>
      </section>

      <PaperNotesPanel
        v-show="activeTab === 'notes'"
        :paper-id="paperId"
        @locate="emit('locate', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.paper-workspace__inspector-inner {
  display: flex;
  min-height: 0;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
}

.paper-workspace__tabs {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--color-border);
  padding: 0 10px;
}

.paper-workspace__tab {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  padding: 10px 8px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.paper-workspace__tab.is-active {
  border-bottom-color: var(--color-text);
  color: var(--color-text);
  font-weight: 600;
}

.paper-workspace__tab-count {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
}

.paper-workspace__inspector-body {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  overflow-y: auto;
}

.paper-workspace__inspector-body--flush {
  overflow: hidden;
}

.paper-workspace__eyebrow {
  margin: 0 0 4px;
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.paper-workspace__secondary {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  background: var(--color-surface);
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 11px;
  padding: 4px 8px;
}

.paper-workspace__secondary:hover {
  border-color: var(--color-border-strong);
  color: var(--color-text);
}

.paper-workspace__brief {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}

.paper-workspace__brief-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.paper-workspace__brief-body {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.55;
}

.paper-workspace__brief-body p {
  margin: 0 0 6px;
}

.paper-workspace__brief-list {
  margin: 0 0 6px;
  padding-left: 18px;
}

.paper-workspace__empty {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}
</style>
