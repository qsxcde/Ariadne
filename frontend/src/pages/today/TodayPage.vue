<script setup lang="ts">
import { onMounted } from "vue";

import StateBlock from "@/shared/components/StateBlock.vue";
import TodayHeader from "@/pages/today/TodayHeader.vue";
import TodayQueue from "@/pages/today/TodayQueue.vue";
import TodayReading from "@/pages/today/TodayReading.vue";
import TodayWeek from "@/pages/today/TodayWeek.vue";
import { usePapers } from "@/features/library/composables/usePapers";
import { useToday } from "@/pages/today/useToday";

const emit = defineEmits<{
  open: [paperId: string];
  library: [];
  settings: [];
}>();

const { papers, todayLabel, load } = useToday();
const { isLoading, errorMessage } = usePapers();

onMounted(() => {
  void load();
});
</script>

<template>
  <section class="today" aria-label="Today">
    <TodayHeader :today-label="todayLabel" :paper-count="papers.length" />

    <StateBlock
      v-if="errorMessage"
      kind="error"
      title="读取失败"
      :description="errorMessage"
      compact
    />
    <StateBlock
      v-if="isLoading && !papers.length"
      kind="loading"
      description="正在读取阅读进度…"
    />

    <div class="today__columns">
      <TodayReading @open="emit('open', $event)" @library="emit('library')" />
      <TodayWeek />
    </div>

    <TodayQueue @open="emit('open', $event)" />
  </section>
</template>

<style scoped>
.today {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 26px;
  padding: 26px max(30px, calc((100% - 1320px) / 2)) 40px;
  overflow-y: auto;
  background: var(--color-page);
}

.today__columns {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 1fr);
  gap: 34px;
}

@media (max-width: 1100px) {
  .today__columns {
    grid-template-columns: 1fr;
  }
}
</style>
