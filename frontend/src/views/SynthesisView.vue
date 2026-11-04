<script setup lang="ts">
import { onMounted, ref } from "vue";

import StateBlock from "../components/StateBlock.vue";
import SynthesisAskPanel from "./synthesis/SynthesisAskPanel.vue";
import SynthesisHeader from "./synthesis/SynthesisHeader.vue";
import SynthesisMatrixPanel from "./synthesis/SynthesisMatrixPanel.vue";
import { SYNTHESIS_TABS, useSynthesis } from "../composables/useSynthesis";

const emit = defineEmits<{
  open: [paperId: string];
}>();

const {
  collections,
  selectedCollectionId,
  selectedCollection,
  papers,
  comparison,
  isLoading,
  errorMessage,
  loadCollections,
  loadPapers,
  exportComparison,
  exportMatrixMarkdown,
} = useSynthesis();

const activeTab = ref<"ask" | "compare" | "matrix">("matrix");

function handleCollectionSelect(collectionId: string): void {
  selectedCollectionId.value = collectionId;
  void loadPapers();
}

onMounted(() => {
  void loadCollections();
});
</script>

<template>
  <section class="synthesis" aria-label="跨论文综合">
    <SynthesisHeader
      :collections="collections"
      :selected-id="selectedCollectionId"
      :paper-count="papers.length"
      @select="handleCollectionSelect"
    />

    <div v-if="selectedCollection" class="synthesis__meta">
      <span>{{ selectedCollection.description || "按论文片段回答，引用保留 section 与 chunk。" }}</span>
      <span class="synthesis__counts">
        已读 {{ selectedCollection.by_status?.read ?? 0 }} · 在读
        {{ selectedCollection.by_status?.reading ?? 0 }} · 待读
        {{
          (selectedCollection.by_status?.inbox ?? 0) +
          (selectedCollection.by_status?.queued ?? 0)
        }}
      </span>
    </div>

    <div class="synthesis__tabs-row">
      <div class="synthesis__tabs" role="tablist" aria-label="综合作业">
        <button
          v-for="tab in SYNTHESIS_TABS"
          :key="tab.value"
          type="button"
          role="tab"
          class="synthesis__tab"
          :class="{ 'is-active': activeTab === tab.value }"
          :aria-selected="activeTab === tab.value"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>
      <div v-if="comparison.length" class="synthesis__exports">
        <button v-if="activeTab === 'compare'" type="button" @click="exportComparison">
          导出 CSV
        </button>
        <button v-if="activeTab === 'matrix'" type="button" @click="exportMatrixMarkdown">
          导出 Markdown
        </button>
      </div>
    </div>

    <StateBlock
      v-if="errorMessage"
      kind="error"
      title="读取集合失败"
      :description="errorMessage"
      action-label="重试"
      @action="loadCollections"
    />
    <StateBlock v-else-if="isLoading" kind="loading" description="正在读取集合…" />
    <StateBlock
      v-else-if="!collections.length"
      kind="empty"
      title="还没有集合"
      description="先在文献库里创建集合并加入论文，再回到这里做跨论文综合。"
    />

    <div v-else class="synthesis__body" :class="{ 'synthesis__body--single': activeTab === 'ask' }">
      <SynthesisAskPanel v-if="activeTab === 'ask'" />
      <SynthesisMatrixPanel
        v-else
        :mode="activeTab === 'matrix' ? 'matrix' : 'compare'"
        @open="emit('open', $event)"
      />
    </div>
  </section>
</template>

<style scoped>
.synthesis {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  padding: 26px max(30px, calc((100% - 1320px) / 2)) 40px;
  overflow-y: auto;
  background: var(--color-page);
}

.synthesis__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 10px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.synthesis__counts {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
}

.synthesis__tabs-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
}

.synthesis__tabs {
  display: flex;
  gap: 18px;
}

.synthesis__tab {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  padding: 8px 2px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.synthesis__tab.is-active {
  border-bottom-color: var(--color-text);
  color: var(--color-text);
  font-weight: 600;
}

.synthesis__exports {
  display: flex;
  gap: 10px;
}

.synthesis__exports button {
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 11px;
}

.synthesis__exports button:hover {
  color: var(--color-text);
}

.synthesis__body {
  display: grid;
  min-height: 0;
  grid-template-columns: minmax(240px, 280px) minmax(0, 1fr);
  gap: 28px;
}

.synthesis__body--single {
  grid-template-columns: minmax(0, 1fr);
}

@media (max-width: 1100px) {
  .synthesis__body {
    grid-template-columns: 1fr;
  }
}
</style>
