<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";

import StateBlock from "@/shared/components/StateBlock.vue";
import FeedHeader from "@/pages/feed/FeedHeader.vue";
import FeedInbox from "@/pages/feed/FeedInbox.vue";
import FeedSubscriptions from "@/pages/feed/FeedSubscriptions.vue";
import { useFeed } from "@/pages/feed/useFeed";
import type { FeedItemSummary } from "@/api";

const emit = defineEmits<{
  open: [paperId: string];
}>();

const {
  items,
  isRefreshing,
  errorMessage,
  selectedIndex,
  load,
  save,
  ignore,
  selectRow,
  refresh,
} = useFeed();

async function saveAndOpen(item: FeedItemSummary): Promise<void> {
  const paperId = await save(item);
  if (paperId) {
    emit("open", paperId);
  }
}

function handleKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null;
  if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
    return;
  }
  if (event.metaKey || event.ctrlKey || event.altKey || !items.value.length) {
    return;
  }
  const key = event.key.toLowerCase();
  if (key === "j" || key === "k") {
    event.preventDefault();
    const delta = key === "j" ? 1 : -1;
    selectRow(Math.max(0, Math.min(items.value.length - 1, selectedIndex.value + delta)));
    return;
  }
  if (key === "s" || key === "x") {
    const item = items.value[selectedIndex.value];
    if (!item || item.status !== "new") return;
    event.preventDefault();
    void (key === "s" ? saveAndOpen(item) : ignore(item));
    return;
  }
  if (event.key === "Enter") {
    const item = items.value[selectedIndex.value];
    if (!item) return;
    event.preventDefault();
    if (item.paper_id) {
      emit("open", item.paper_id);
    } else if (item.status === "new") {
      void saveAndOpen(item);
    }
  }
}

onMounted(() => {
  void load();
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <section class="feed-view" aria-label="领域跟进">
    <FeedHeader
      :item-count="items.length"
      :is-refreshing="isRefreshing"
      @refresh="refresh"
    />

    <StateBlock
      v-if="errorMessage"
      kind="error"
      title="读取 Feed 失败"
      :description="errorMessage"
      action-label="重试"
      compact
      @action="load"
    />

    <div class="feed-view__grid">
      <FeedSubscriptions />
      <FeedInbox @open="emit('open', $event)" />
    </div>
  </section>
</template>

<style scoped>
.feed-view {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  padding: 26px max(30px, calc((100% - 1320px) / 2)) 40px;
  overflow-y: auto;
  background: var(--color-page);
}

.feed-view__grid {
  display: grid;
  grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
  gap: 30px;
}

@media (max-width: 1000px) {
  .feed-view__grid {
    grid-template-columns: 1fr;
  }
}
</style>
