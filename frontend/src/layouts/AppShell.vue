<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppSidebar from "../features/sessions/components/AppSidebar.vue";
import ChatWorkspace from "../features/chat/components/ChatWorkspace.vue";
import PaperLibrary from "../features/library/components/PaperLibrary.vue";
import PaperReader from "../features/reader/components/PaperReader.vue";
import PaperWorkspace from "../features/reader/components/PaperWorkspace.vue";
import SettingsView from "../views/SettingsView.vue";
import TodayView from "../views/TodayView.vue";
import SynthesisView from "../views/SynthesisView.vue";
import FeedView from "../views/FeedView.vue";
import SourceDrawer from "../components/SourceDrawer.vue";
import { usePaperChat } from "../composables/usePaperChat";
import { useAuth } from "../composables/useAuth";
import { resetClientState } from "../stores";
import { useLibrary } from "../composables/useLibrary";
import { useSourcePreview } from "../composables/useSourcePreview";
import type { SelectionAskMode, SidebarSessionItem, SuggestedPrompt } from "../types";
import { buildSelectionPrompt } from "../utils/prompt";

const route = useRoute();
const router = useRouter();
const { logout, user } = useAuth();

const {
  currentPaperHint,
  currentSessionTitle,
  draft,
  errorMessage,
  hasPaper,
  indexedChunks,
  isStreaming,
  isUploading,
  uploadStatus,
  messages,
  paperSession,
  sessions,
  documents,
  createEmptySession,
  deleteSession,
  focusComposer,
  handleUpload,
  initializeSessions,
  openSession,
  regenerateLast,
  renameSession,
  sendMessage,
  stopStreaming,
  togglePinSession,
  useDemoPaper,
} = usePaperChat();

const isSidebarCollapsed = ref(false);

const { setActiveSession } = useSourcePreview();

const activeSessionId = computed(() => paperSession.value?.sessionId ?? "");
const readerDocument = computed(() => documents.value[0] ?? null);
const showReader = computed(() => route.name === "session-reader");
const showToday = computed(() => route.name === "today");
const showSynthesis = computed(() => route.name === "synthesis");
const showFeed = computed(() => route.name === "feed");
const showPaper = computed(() => route.name === "paper");
const showLibrary = computed(() => route.name === "library");
const showSettings = computed(() => route.name === "settings");
const { invalidate: invalidateLibrary } = useLibrary();
const routeSessionId = computed(() =>
  typeof route.params.sessionId === "string" ? route.params.sessionId : null,
);
const routePaperId = computed(() =>
  typeof route.params.paperId === "string" ? route.params.paperId : null,
);

// 引用抽屉与阅读器都依赖当前会话才能换算原文
watch(
  () => paperSession.value?.sessionId ?? null,
  (sessionId) => setActiveSession(sessionId),
  { immediate: true },
);

const recentSessions = computed<SidebarSessionItem[]>(() =>
  sessions.value.map((session) => ({
    id: session.id,
    isPinned: session.is_pinned,
    title: session.title,
    description: `${session.document_count} 篇论文 · ${session.message_count} 条消息`,
    active: session.active,
  })),
);

const suggestedPrompts: SuggestedPrompt[] = [
  { id: "summary", text: "用 5 个要点总结本文核心贡献" },
  { id: "compare", text: "把本文方法和标准 RAG 做对比" },
];

/** 阅读路由带 sessionId；对话路由只做一次性初始化。 */
async function syncFromRoute(): Promise<void> {
  const sessionId = routeSessionId.value;
  if (showReader.value && sessionId) {
    if (paperSession.value?.sessionId !== sessionId) {
      await openSession(sessionId);
    }
    return;
  }
  if (!sessions.value.length && !showPaper.value) {
    await initializeSessions();
  }
}

async function uploadPaper(file: File): Promise<void> {
  await handleUpload(file);
  invalidateLibrary();
}

function openLibrary(): void {
  void router.push({ name: "library" });
}

function openPaper(paperId: string): void {
  void router.push({ name: "paper", params: { paperId } });
}

function openToday(): void {
  void router.push({ name: "today" });
}

function openSynthesis(): void {
  void router.push({ name: "synthesis" });
}

function openFeed(): void {
  void router.push({ name: "feed" });
}

function openSettings(): void {
  void router.push({ name: "settings" });
}

function closePaper(): void {
  void router.push({ name: "library" });
}

function closeSettings(): void {
  void router.push({ name: "library" });
}

function handlePromptClick(text: string): void {
  draft.value = text;
}

function toggleSidebarCollapse(): void {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
}

function openReader(): void {
  const paperId = readerDocument.value?.paper_id;
  if (paperId) {
    void router.push({ name: "paper", params: { paperId } });
    return;
  }
  const sessionId = paperSession.value?.sessionId;
  if (!sessionId) {
    return;
  }
  void router.push({ name: "session-reader", params: { sessionId } });
}

function closeReader(): void {
  void router.push({ name: "chat" });
}

/** 阅读器选区 → 注入 composer 并聚焦，由用户决定是否发送。 */
function handleAsk(text: string, mode: SelectionAskMode): void {
  draft.value = buildSelectionPrompt(text, mode);
  focusComposer();
}

function handleLogout(): void {
  resetClientState();
  logout();
  void router.push({ name: "login" });
}

onMounted(() => {
  void syncFromRoute();
});

watch(routeSessionId, () => {
  void syncFromRoute();
});

// 阅读路由但当前会话没有文档时，退回对话态，避免停在空白分栏
watch([showReader, () => documents.value.length, () => paperSession.value?.sessionId], () => {
  if (showReader.value && paperSession.value && documents.value.length === 0) {
    void router.replace({ name: "chat" });
  }
});
</script>

<template>
  <main class="page-shell">
    <section
      class="app-frame"
      :class="{ 'app-frame--reader': showPaper || (showReader && readerDocument && activeSessionId) }"
      aria-label="SciPal 论文智能助手"
    >
      <AppSidebar
        :collapsed="isSidebarCollapsed"
        :indexed-chunks="indexedChunks"
        :is-uploading="isUploading"
        :recent-sessions="recentSessions"
        :username="user?.username"
        @delete-session="deleteSession"
        @create-session="createEmptySession"
        @pin-session="togglePinSession"
        @rename-session="renameSession"
        @select-session="openSession"
        @toggle-collapse="toggleSidebarCollapse"
        @open-library="openLibrary"
        @logout="handleLogout"
      />

      <PaperLibrary
        v-if="showLibrary"
        @open="openPaper"
        @today="openToday"
        @synthesis="openSynthesis"
        @feed="openFeed"
        @settings="openSettings"
      />

      <TodayView
        v-else-if="showToday"
        @open="openPaper"
        @library="openLibrary"
        @settings="openSettings"
      />

      <SynthesisView
        v-else-if="showSynthesis"
        @library="openLibrary"
        @open="openPaper"
      />

      <FeedView
        v-else-if="showFeed"
        @library="openLibrary"
        @open="openPaper"
      />

      <PaperWorkspace
        v-else-if="showPaper && routePaperId"
        :paper-id="routePaperId"
        @back="closePaper"
        @open-library="openLibrary"
      />

      <PaperReader
        v-else-if="showReader && readerDocument && activeSessionId"
        :session-id="activeSessionId"
        :document-id="readerDocument.id"
        @ask="handleAsk"
        @close="closeReader"
      />

      <SettingsView v-else-if="showSettings" @back="closeSettings" />

      <ChatWorkspace
        v-if="!showLibrary && !showToday && !showSynthesis && !showFeed && !showPaper && !showReader && !showSettings"
        v-model:draft="draft"
        :can-open-reader="Boolean(readerDocument)"
        :error-message="errorMessage"
        :has-paper="hasPaper"
        :is-streaming="isStreaming"
        :is-uploading="isUploading"
        :messages="messages"
        :paper-hint="currentPaperHint"
        :session-title="currentSessionTitle"
        :suggested-prompts="suggestedPrompts"
        :upload-status="uploadStatus"
        @demo-paper="useDemoPaper"
        @open-reader="openReader"
        @prompt-click="handlePromptClick"
        @regenerate="regenerateLast"
        @send="sendMessage"
        @stop="stopStreaming"
        @upload-paper="uploadPaper"
      />
    </section>
    <SourceDrawer />
  </main>
</template>
