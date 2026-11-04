import { useLibrary } from "@/features/library/composables/useLibrary";
import { resetPaperChat } from "@/features/chat/composables/usePaperChat";
import { resetAgentRuns } from "@/features/agent/composables/useAgentRuns";
import { usePaperReader } from "@/features/reader/composables/usePaperReader";
import { resetFeatures } from "@/shared/composables/useFeatures";
import { useSourcePreview } from "@/shared/composables/useSourcePreview";

/**
 * Clear every module-scoped store that survives the login route.
 *
 * The chat, library, reader and citation stores are shared singletons, so a new
 * account would otherwise see the previous account's sessions and paper text.
 * Call this before clearing the token.
 */
export function resetClientState(): void {
  resetPaperChat();
  resetAgentRuns();
  resetFeatures();
  useLibrary().reset();
  usePaperReader().reset();
  useSourcePreview().reset();
}
