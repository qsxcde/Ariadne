<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppSidebar from "@/features/sessions/components/AppSidebar.vue";
import ChatWorkspace from "@/features/chat/components/ChatWorkspace.vue";
import PaperLibrary from "@/pages/library/LibraryPage.vue";
import PaperReader from "@/features/reader/components/PaperReader.vue";
import PaperWorkspace from "@/pages/paper/PaperPage.vue";
import SettingsView from "@/pages/settings/SettingsPage.vue";
import TodayView from "@/pages/today/TodayPage.vue";
import SynthesisView from "@/pages/synthesis/SynthesisPage.vue";
import FeedView from "@/pages/feed/FeedPage.vue";
import SourceDrawer from "@/shared/components/SourceDrawer.vue";
import { usePaperChat } from "@/features/chat/composables/usePaperChat";
import { useAuth } from "@/shared/composables/useAuth";
import { resetClientState } from "@/stores";
import { useLibrary } from "@/features/library/composables/useLibrary";
import { useSourcePreview } from "@/shared/composables/useSourcePreview";
import type { SelectionAskMode, SidebarSessionItem, SuggestedPrompt } from "@/shared/types";
import { buildSelectionPrompt } from "@/shared/utils/prompt";
import { canOpenDocument, uploadStepFromStatus } from "@/shared/utils/upload";

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
/**
 * 后端的会话文档按 created_at 升序返回，``documents[0]`` 是最早上传的那篇。
 * 阅读器必须跟随当前文档（``paperSession.docId``），否则新上传的文件会被旧文档遮住。
 */
const readerDocument = computed(() => {
  const documents_ = documents.value;
  if (!documents_.length) {
    return null;
  }
  const activeId = paperSession.value?.docId;
  const active = activeId ? documents_.find((document) => document.id === activeId) : undefined;
  return active ?? documents_[documents_.length - 1] ?? null;
});
/** 只有解析完成的文档才能进阅读器，避免打开一个空白正文。 */
const canOpenReader = computed(() =>
  readerDocument.value ? canOpenDocument(readerDocument.value.status) : false,
);
const readerProgressHint = computed(() => {
  if (canOpenReader.value) {
    return "";
  }
  const status = uploadStatus.value;
  if (status && !status.canOpen && status.phase !== "error") {
    return `${status.stageLabel} ${status.progress}%`;
  }
  const document = readerDocument.value;
  if (document) {
    const step = uploadStepFromStatus(document.status);
    return step.phase === "error"
      ? "解析失败，请重新上传"
      : `${step.stageLabel} ${step.progress}%`;
  }
  return "解析中，完成后可打开";
});
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
  if (!canOpenReader.value) {
    return;
  }
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
        v-else-if="showReader && readerDocument && activeSessionId && canOpenReader"
        :session-id="activeSessionId"
        :document-id="readerDocument.id"
        @ask="handleAsk"
        @close="closeReader"
      />

      <SettingsView v-else-if="showSettings" @back="closeSettings" />

      <ChatWorkspace
        v-if="!showLibrary && !showToday && !showSynthesis && !showFeed && !showPaper && !showReader && !showSettings"
        v-model:draft="draft"
        :can-open-reader="canOpenReader"
        :error-message="errorMessage"
        :has-paper="hasPaper"
        :is-streaming="isStreaming"
        :is-uploading="isUploading"
        :messages="messages"
        :paper-hint="currentPaperHint"
        :reader-hint="readerProgressHint"
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
