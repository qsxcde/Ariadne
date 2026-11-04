import { ref } from "vue";
import { fetchFeatures } from "@/api";

const agentEnabled = ref(false);
let loaded = false;
let inflight: Promise<void> | null = null;

async function ensureLoaded(): Promise<void> {
  if (loaded) {
    return;
  }
  inflight ??= fetchFeatures()
    .then((flags) => {
      agentEnabled.value = flags.agent_enabled;
    })
    .catch(() => {
      agentEnabled.value = false;
    })
    .finally(() => {
      loaded = true;
      inflight = null;
    });
  return inflight;
}

function resetFeatures(): void {
  agentEnabled.value = false;
  loaded = false;
  inflight = null;
}

export function useFeatures() {
  return { agentEnabled, ensureLoaded };
}

export { resetFeatures };
