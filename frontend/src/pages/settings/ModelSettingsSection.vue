<script setup lang="ts">
import { computed, onMounted } from "vue";

import SettingsSection from "@/pages/settings/SettingsSection.vue";
import { useModelSettings } from "@/pages/settings/useModelSettings";

const {
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
} = useModelSettings();

const usesPersonalLlmKey = computed(() => settings.value?.llm.key_source === "user");
const usesPersonalEmbeddingKey = computed(
  () => settings.value?.embedding.key_source === "user",
);
const usesPersonalRerankKey = computed(
  () => settings.value?.rerank.key_source === "user",
);

const llmKeyPlaceholder = computed(() =>
  usesPersonalLlmKey.value
    ? `已设置 ${settings.value?.llm.api_key_hint ?? ""}，留空保持不变`
    : "填写你的 DeepSeek API Key（可选）",
);

const embeddingKeyPlaceholder = computed(() =>
  usesPersonalEmbeddingKey.value
    ? `已设置 ${settings.value?.embedding.api_key_hint ?? ""}，留空保持不变`
    : "填写硅基流动 API Key（可选）",
);

const rerankKeyPlaceholder = computed(() =>
  usesPersonalRerankKey.value
    ? `已设置 ${settings.value?.rerank.api_key_hint ?? ""}，留空保持不变`
    : "填写硅基流动 API Key（可选）",
);

const embeddingSourceLabel = computed(() => {
  const embedding = settings.value?.embedding;
  if (!embedding) return "";
  if (embedding.key_source === "user") return "个人 Key";
  if (embedding.key_source === "env") return "系统默认 Key";
  return "本地模型";
});

const rerankSourceLabel = computed(() => {
  const rerank = settings.value?.rerank;
  if (!rerank) return "";
  if (!rerank.enabled) return "已禁用";
  if (rerank.key_source === "user") return "个人 Key";
  if (rerank.key_source === "env") return "系统默认 Key";
  return "本地重排模型";
});

onMounted(() => {
  void load();
});
</script>

<template>
  <SettingsSection id="settings-model" title="模型服务" index="02">
    <p v-if="isLoading" class="settings-hint">正在读取模型设置…</p>

    <template v-else-if="settings">
      <h3 class="settings-model-group">对话模型</h3>
      <p class="settings-model-status" :class="{ 'is-personal': usesPersonalLlmKey }">
        <strong>{{ usesPersonalLlmKey ? "个人 Key" : "系统默认 Key" }}</strong>
        <span v-if="usesPersonalLlmKey">（{{ settings.llm.api_key_hint }}）</span>
        <span v-else>· 未填写个人 Key，使用后端 env 配置</span>
      </p>

      <div class="settings-field-grid">
        <label class="settings-field">
          供应商
          <select v-model="llmProvider">
            <option v-for="provider in llmProviders" :key="provider.id" :value="provider.id">
              {{ provider.label }}
            </option>
          </select>
        </label>
        <label class="settings-field">
          模型
          <select v-model="llmModel">
            <option v-for="model in llmModels" :key="model.id" :value="model.id">
              {{ model.label }}
            </option>
          </select>
        </label>
      </div>

      <label class="settings-field settings-field--key">
        API Key
        <input
          v-model="llmApiKeyInput"
          type="password"
          autocomplete="off"
          spellcheck="false"
          :placeholder="llmKeyPlaceholder"
        />
      </label>

      <div v-if="usesPersonalLlmKey" class="settings-actions">
        <button
          type="button"
          class="settings-button"
          :disabled="isSaving"
          @click="clearPersonalKey('llm')"
        >
          清除对话模型 Key
        </button>
      </div>

      <h3 class="settings-model-group">Embedding（向量化）</h3>
      <p
        class="settings-model-status"
        :class="{ 'is-personal': usesPersonalEmbeddingKey }"
      >
        <strong>{{ embeddingSourceLabel }}</strong>
        <span v-if="usesPersonalEmbeddingKey">
          （{{ settings.embedding.api_key_hint }}）
        </span>
        <span v-else-if="settings.embedding.key_source === 'env'">
          · 未填写个人 Key，使用后端 env 配置
        </span>
        <span v-else>· 未配置远程 Key，当前使用后端本地模型</span>
        <span class="settings-model-dim">· {{ settings.embedding.dim ?? "自动" }} 维</span>
      </p>

      <div class="settings-field-grid">
        <label class="settings-field">
          供应商
          <select v-model="embeddingProvider">
            <option
              v-for="provider in embeddingProviders"
              :key="provider.id"
              :value="provider.id"
            >
              {{ provider.label }}
            </option>
          </select>
        </label>
        <label class="settings-field">
          模型
          <select v-model="embeddingModel">
            <option v-for="model in embeddingModels" :key="model.id" :value="model.id">
              {{ model.label }}
            </option>
          </select>
        </label>
      </div>

      <label class="settings-field settings-field--key">
        API Key
        <input
          v-model="embeddingApiKeyInput"
          type="password"
          autocomplete="off"
          spellcheck="false"
          :placeholder="embeddingKeyPlaceholder"
        />
      </label>

      <div v-if="usesPersonalEmbeddingKey" class="settings-actions">
        <button
          type="button"
          class="settings-button"
          :disabled="isSaving"
          @click="clearPersonalKey('embedding')"
        >
          清除 Embedding Key
        </button>
      </div>

      <p class="settings-hint">
        修改 Embedding 供应商或模型后，已有论文索引会被标记为过期，需在阅读页点击「重建索引」。
        仅更换 Key、保持同一模型时无需重建。
      </p>

      <h3 class="settings-model-group">重排模型</h3>
      <p class="settings-model-status" :class="{ 'is-personal': usesPersonalRerankKey }">
        <strong>{{ rerankSourceLabel }}</strong>
        <span v-if="usesPersonalRerankKey">
          （{{ settings.rerank.api_key_hint }}）
        </span>
        <span v-else-if="settings.rerank.key_source === 'env'">
          · 未填写个人 Key，使用后端 env 配置
        </span>
        <span v-else-if="settings.rerank.enabled">· 当前使用本地重排模型</span>
      </p>

      <div class="settings-field-grid">
        <label class="settings-field">
          供应商
          <select v-model="rerankProvider">
            <option
              v-for="provider in rerankProviders"
              :key="provider.id"
              :value="provider.id"
            >
              {{ provider.label }}
            </option>
          </select>
        </label>
        <label class="settings-field">
          模型
          <select v-model="rerankModel">
            <option v-for="model in rerankModels" :key="model.id" :value="model.id">
              {{ model.label }}
            </option>
          </select>
        </label>
      </div>

      <label class="settings-field settings-field--key">
        API Key
        <input
          v-model="rerankApiKeyInput"
          type="password"
          autocomplete="off"
          spellcheck="false"
          :placeholder="rerankKeyPlaceholder"
        />
      </label>

      <div v-if="usesPersonalRerankKey" class="settings-actions">
        <button
          type="button"
          class="settings-button"
          :disabled="isSaving"
          @click="clearPersonalKey('rerank')"
        >
          清除重排模型 Key
        </button>
      </div>

      <p class="settings-hint">
        重排只影响检索结果的排序，修改后立即生效，无需重建索引。
      </p>

      <div class="settings-actions settings-actions--save">
        <button
          type="button"
          class="settings-button settings-button--primary"
          :disabled="isSaving"
          @click="save"
        >
          {{ isSaving ? "保存中…" : "保存模型设置" }}
        </button>
        <span v-if="saveMessage" class="settings-saved">{{ saveMessage }}</span>
      </div>

      <p v-if="errorMessage" class="settings-error">{{ errorMessage }}</p>
      <p class="settings-hint">
        个人 Key 与账号绑定并加密存储，保存后立即生效，无需重启。
      </p>
    </template>

    <p v-else class="settings-error">{{ errorMessage || "模型设置暂不可用。" }}</p>
  </SettingsSection>
</template>

<style scoped>
.settings-model-group {
  margin: 18px 0 8px;
  padding-top: 14px;
  border-top: 1px solid var(--color-border);
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 650;
}

.settings-model-group:first-of-type {
  margin-top: 0;
  padding-top: 0;
  border-top: 0;
}

.settings-model-status {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 0 0 12px;
  color: var(--color-text-muted);
  font-size: 12px;
  flex-wrap: wrap;
}

.settings-model-status strong {
  color: var(--color-text-soft);
  font-weight: 600;
}

.settings-model-status.is-personal strong {
  color: var(--color-success);
}

.settings-model-dim {
  font-family: var(--font-mono);
  font-size: 10px;
}

.settings-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.settings-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.settings-field--key {
  margin-top: 14px;
}

.settings-field select,
.settings-field input {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 8px;
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
}

.settings-field select:focus,
.settings-field input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.settings-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.settings-actions--save {
  margin-top: 20px;
  padding-top: 14px;
  border-top: 1px solid var(--color-border);
}

.settings-saved {
  color: var(--color-success);
  font-size: 11px;
}

.settings-error {
  margin: 8px 0 0;
  color: var(--color-danger);
  font-size: 12px;
}

@media (max-width: 760px) {
  .settings-field-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
