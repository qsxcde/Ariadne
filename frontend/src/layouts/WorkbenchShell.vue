<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import TopBar from "../components/TopBar.vue";
import WorkbenchRail from "../components/WorkbenchRail.vue";
import PaperLibrary from "../features/library/components/PaperLibrary.vue";
import PaperWorkspace from "../features/reader/components/PaperWorkspace.vue";
import SettingsView from "../views/SettingsView.vue";
import SynthesisView from "../views/SynthesisView.vue";
import FeedView from "../views/FeedView.vue";
import TodayView from "../views/TodayView.vue";
import { listCollections } from "../api/collections";
import type { CollectionSummary } from "../api";
import { useAuth } from "../composables/useAuth";
import { resetClientState } from "../stores";

const route = useRoute();
const router = useRouter();
const { logout, user } = useAuth();

const collections = ref<CollectionSummary[]>([]);

const SECTION_LABELS: Record<string, string> = {
  today: "今天",
  library: "文献库",
  synthesis: "课题综合",
  feed: "领域跟进",
  paper: "论文工作台",
  settings: "设置",
};

const section = computed(() => SECTION_LABELS[String(route.name)] ?? "工作台");
const routePaperId = computed(() =>
  typeof route.params.paperId === "string" ? route.params.paperId : "",
);

async function loadCollections(): Promise<void> {
  try {
    collections.value = await listCollections();
  } catch {
    collections.value = [];
  }
}

function navigate(name: string): void {
  void router.push({ name });
}

function openLibrary(): void {
  void router.push({ name: "library" });
}

function openPaper(paperId: string): void {
  void router.push({ name: "paper", params: { paperId } });
}

function openCollection(collectionId: string): void {
  void router.push({ name: "library", query: { collection: collectionId } });
}

function search(query: string): void {
  void router.push({ name: "library", query: { q: query } });
}

function importPaper(): void {
  void router.push({ name: "library", query: { import: "1" } });
}

function handleLogout(): void {
  resetClientState();
  logout();
  void router.push({ name: "login" });
}

onMounted(() => {
  void loadCollections();
});

watch(
  () => route.name,
  (name) => {
    if (name === "library" || name === "paper") {
      void loadCollections();
    }
  },
);
</script>

<template>
  <main class="workbench" aria-label="SciPal 研究工作台">
    <WorkbenchRail
      :active="String(route.name)"
      :collections="collections"
      :username="user?.username"
      @navigate="navigate"
      @open-collection="openCollection"
      @logout="handleLogout"
    />

    <div class="workbench__main">
      <TopBar :section="section" @search="search" @import="importPaper" />

      <div class="workbench__body">
        <PaperLibrary
          v-if="route.name === 'library'"
          @open="openPaper"
          @today="navigate('today')"
          @synthesis="navigate('synthesis')"
          @feed="navigate('feed')"
          @settings="navigate('settings')"
        />

        <TodayView
          v-else-if="route.name === 'today'"
          @open="openPaper"
          @library="openLibrary"
          @settings="navigate('settings')"
        />

        <SynthesisView
          v-else-if="route.name === 'synthesis'"
          @library="openLibrary"
          @open="openPaper"
        />

        <FeedView
          v-else-if="route.name === 'feed'"
          @library="openLibrary"
          @open="openPaper"
        />

        <PaperWorkspace
          v-else-if="route.name === 'paper' && routePaperId"
          :paper-id="routePaperId"
          @back="openLibrary"
        />

        <SettingsView v-else-if="route.name === 'settings'" @back="openLibrary" />
      </div>
    </div>
  </main>
</template>

<style scoped>
.workbench {
  display: flex;
  width: 100vw;
  height: 100vh;
  min-width: 960px;
  overflow: hidden;
  background: var(--color-page);
}

.workbench__main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.workbench__body {
  display: flex;
  min-height: 0;
  flex: 1;
  overflow: hidden;
}
</style>
