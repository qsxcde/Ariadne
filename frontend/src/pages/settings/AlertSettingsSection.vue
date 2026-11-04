<script setup lang="ts">
import SettingsSection from "@/pages/settings/SettingsSection.vue";
import { useAlertSettings } from "@/pages/settings/useAlertSettings";

const { alertSettings, isSaving, saveMessage, save } = useAlertSettings();
</script>

<template>
  <SettingsSection id="settings-alerts" title="提醒与 Digest" index="03">
    <div v-if="alertSettings" class="settings-toggle-grid">
      <label class="settings-toggle">
        <input v-model="alertSettings.new_paper" type="checkbox" />
        新论文提醒
      </label>
      <label class="settings-toggle">
        <input v-model="alertSettings.new_version" type="checkbox" />
        新版本提醒
      </label>
      <label class="settings-toggle">
        <input v-model="alertSettings.new_citation" type="checkbox" />
        新引用提醒
      </label>
      <label class="settings-toggle">
        <input v-model="alertSettings.digest_enabled" type="checkbox" />
        启用 Digest
      </label>
    </div>
    <label v-if="alertSettings" class="settings-field settings-field--inline">
      Digest 频率
      <select v-model="alertSettings.digest_frequency">
        <option value="daily">每日</option>
        <option value="weekly">每周</option>
        <option value="off">关闭</option>
      </select>
    </label>
    <div class="settings-actions">
      <button
        type="button"
        class="settings-button settings-button--primary"
        :disabled="isSaving"
        @click="save"
      >
        {{ isSaving ? "保存中…" : "保存提醒设置" }}
      </button>
      <span v-if="saveMessage" class="settings-saved">{{ saveMessage }}</span>
    </div>
    <p class="settings-hint">Webhook 立即投递；邮件需在后端配置 SMTP 环境变量。</p>
  </SettingsSection>
</template>

<style scoped>
.settings-toggle-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 24px;
  margin-bottom: 10px;
}

.settings-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-soft);
  font-size: 12px;
}

.settings-toggle input {
  margin: 0;
  accent-color: var(--color-accent);
}

.settings-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.settings-field--inline {
  flex-direction: row;
  align-items: center;
  gap: 10px;
  margin: 4px 0 12px;
}

.settings-field select,
.settings-field--inline select {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 8px;
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
}

.settings-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.settings-button {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 12px;
  color: var(--color-text-soft);
  font-size: 12px;
}

.settings-button:hover:not(:disabled) {
  border-color: var(--color-border-strong);
  color: var(--color-text);
}

.settings-button--primary {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: var(--color-white);
}

.settings-button--primary:hover:not(:disabled) {
  border-color: var(--color-accent-strong);
  background: var(--color-accent-strong);
  color: var(--color-white);
}

.settings-saved {
  color: var(--color-success);
  font-size: 11px;
}

.settings-hint {
  margin-top: 10px !important;
  color: var(--color-text-muted) !important;
  font-size: 11px !important;
}
</style>
