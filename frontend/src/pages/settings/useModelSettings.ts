import { computed, onBeforeUnmount, ref, watch } from "vue";

import { getModelSettings, updateModelSettings } from "@/api/settings";
import type { ModelSettings, ModelSettingsUpdatePayload } from "@/api";
import { toErrorMessage } from "@/shared/utils/error";

const settings = ref<ModelSettings | null>(null);
const llmProvider = ref("deepseek");
const llmModel = ref("");
const llmApiKeyInput = ref("");
const embeddingProvider = ref("siliconflow");
const embeddingModel = ref("");
const embeddingApiKeyInput = ref("");
const rerankProvider = ref("siliconflow");
const rerankModel = ref("");
const rerankApiKeyInput = ref("");
const isLoading = ref(false);
const isSaving = ref(false);
const errorMessage = ref("");
const saveMessage = ref("");
let saveTimer: number | null = null;

function providerList(kind: "llm" | "embedding" | "rerank") {
  return settings.value?.catalog[kind] ?? [];
}

const llmProviders = computed(() => providerList("llm"));
const embeddingProviders = computed(() => providerList("embedding"));
const rerankProviders = computed(() => providerList("rerank"));

const llmProviderEntry = computed(
  () => llmProviders.value.find((provider) => provider.id === llmProvider.value) ?? null,
);
const embeddingProviderEntry = computed(
  () =>
    embeddingProviders.value.find((provider) => provider.id === embeddingProvider.value) ??
    null,
);
const rerankProviderEntry = computed(
  () =>
    rerankProviders.value.find((provider) => provider.id === rerankProvider.value) ?? null,
);

const llmModels = computed(() => llmProviderEntry.value?.models ?? []);
const embeddingModels = computed(() => embeddingProviderEntry.value?.models ?? []);
const rerankModels = computed(() => rerankProviderEntry.value?.models ?? []);

function apply(next: ModelSettings): void {
  settings.value = next;
  llmProvider.value = next.llm.provider;
  llmModel.value = next.llm.model;
  llmApiKeyInput.value = "";
  embeddingProvider.value = next.embedding.provider;
  embeddingModel.value = next.embedding.model;
  embeddingApiKeyInput.value = "";
  rerankProvider.value = next.rerank.provider;
  rerankModel.value = next.rerank.model;
  rerankApiKeyInput.value = "";
}

async function load(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    apply(await getModelSettings());
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "读取模型设置失败");
  } finally {
    isLoading.value = false;
  }
}

function flashSaved(message = "已保存"): void {
  saveMessage.value = message;
  if (saveTimer !== null) {
    window.clearTimeout(saveTimer);
  }
  saveTimer = window.setTimeout(() => {
    saveMessage.value = "";
    saveTimer = null;
  }, 2400);
}

async function save(): Promise<void> {
  isSaving.value = true;
  errorMessage.value = "";
  try {
    const previousEmbedding = settings.value?.embedding;
    const llmKey = llmApiKeyInput.value.trim();
    const embeddingKey = embeddingApiKeyInput.value.trim();
    const rerankKey = rerankApiKeyInput.value.trim();
    const next = await updateModelSettings({
      llm_provider: llmProvider.value,
      llm_model: llmModel.value,
      ...(llmKey ? { llm_api_key: llmKey } : {}),
      embedding_provider: embeddingProvider.value,
      embedding_model: embeddingModel.value,
      ...(embeddingKey ? { embedding_api_key: embeddingKey } : {}),
      rerank_provider: rerankProvider.value,
      rerank_model: rerankModel.value,
      ...(rerankKey ? { rerank_api_key: rerankKey } : {}),
    });
    apply(next);
    const embeddingChanged =
      previousEmbedding !== undefined &&
      (previousEmbedding.provider !== next.embedding.provider ||
        previousEmbedding.model !== next.embedding.model);
    flashSaved(embeddingChanged ? "已保存，请重建已有索引" : "已保存");
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "保存模型设置失败");
  } finally {
    isSaving.value = false;
  }
}

async function clearPersonalKey(
  kind: "llm" | "embedding" | "rerank",
): Promise<void> {
  isSaving.value = true;
  errorMessage.value = "";
  try {
    const payload: ModelSettingsUpdatePayload =
      kind === "llm"
        ? { llm_api_key: "" }
        : kind === "embedding"
          ? { embedding_api_key: "" }
          : { rerank_api_key: "" };
    apply(await updateModelSettings(payload));
    flashSaved("已清除个人 Key");
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "清除个人 Key 失败");
  } finally {
    isSaving.value = false;
  }
}

function syncModel(
  options: { id: string }[],
  current: { value: string },
): void {
  if (!options.some((model) => model.id === current.value)) {
    current.value = options[0]?.id ?? "";
  }
}

watch(llmProvider, () => syncModel(llmModels.value, llmModel));
watch(embeddingProvider, () => syncModel(embeddingModels.value, embeddingModel));
watch(rerankProvider, () => syncModel(rerankModels.value, rerankModel));

function dispose(): void {
  if (saveTimer !== null) {
    window.clearTimeout(saveTimer);
    saveTimer = null;
  }
}

export function useModelSettings() {
  onBeforeUnmount(dispose);
  return {
    settings,
    llmProvider,
    llmModel,
    llmApiKeyInput,
    embeddingProvider,
    embeddingModel,
    embeddingApiKeyInput,
    rerankProvider,
    rerankModel,
    rerankApiKeyInput,
    isLoading,
    isSaving,
    errorMessage,
    saveMessage,
    llmProviders,
    embeddingProviders,
    rerankProviders,
    llmModels,
    embeddingModels,
    rerankModels,
    load,
    save,
    clearPersonalKey,
  };
}
