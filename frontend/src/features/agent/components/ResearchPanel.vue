<script setup lang="ts">
import { computed, ref } from "vue";
import ModeSwitch from "@/features/agent/components/ModeSwitch.vue";
import RunPanel from "@/features/agent/components/RunPanel.vue";
import { useAgentRuns } from "@/features/agent/composables/useAgentRuns";
import PaperAskPanel from "@/features/reader/components/PaperAskPanel.vue";

const props = defineProps<{
  sessionId: string;
  paperId: string;
  focused: boolean;
}>();

const emit = defineEmits<{
  focusChange: [focused: boolean];
}>();

const mode = ref<"fast" | "agent">("fast");
const { currentRun, latestRunForSession, loadRun, setActive } = useAgentRuns();

const run = computed(() => {
  const current = currentRun.value;
  if (current && current.sessionId === props.sessionId) {
    return current;
  }
  return latestRunForSession(props.sessionId);
});

function changeMode(value: "fast" | "agent"): void {
  mode.value = value;
  if (value === "agent") {
    const latest = latestRunForSession(props.sessionId);
    if (latest) {
      setActive(latest.localId);
    }
  }
}

async function viewRun(runId: string): Promise<void> {
  const loaded = await loadRun(props.sessionId, runId);
  if (loaded) {
    mode.value = "agent";
  }
}
</script>

<template>
  <div class="research-panel">
    <div class="research-panel__head">
      <ModeSwitch :model-value="mode" @update:model-value="changeMode" />
    </div>

    <PaperAskPanel
      v-if="mode === 'fast'"
      :session-id="sessionId"
      @view-run="viewRun"
    />
    <RunPanel
      v-else
      :run="run"
      :session-id="sessionId"
      :paper-id="paperId"
      :focused="focused"
      @focus="emit('focusChange', !focused)"
    />
  </div>
</template>

<style scoped>
.research-panel {
  display: flex;
  min-height: 0;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
}

.research-panel__head {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  border-bottom: 1px solid var(--color-border);
  padding: 6px 10px;
}
</style>
