<script setup lang="ts">
import SettingsSection from "@/pages/settings/SettingsSection.vue";
import { useAlertSettings } from "@/pages/settings/useAlertSettings";

const {
  notifications,
  webhookUrl,
  deliveryEmail,
  isDelivering,
  isCheckingCitations,
  isCheckingVersions,
  deliverMessage,
  readNotification,
  deliver,
  checkCitations,
  checkVersions,
} = useAlertSettings();
</script>

<template>
  <SettingsSection id="settings-notifications" title="通知" index="04">
    <p v-if="!notifications.length" class="settings-hint">没有未读通知。</p>
    <ul v-else class="settings-notifications">
      <li v-for="notification in notifications" :key="notification.id">
        <div>
          <strong>{{ notification.title }}</strong>
          <p>{{ notification.body }}</p>
        </div>
        <button type="button" class="settings-mark" @click="readNotification(notification)">
          已读
        </button>
      </li>
    </ul>
    <div class="settings-actions">
      <button
        type="button"
        class="settings-button"
        :disabled="isCheckingCitations"
        @click="checkCitations"
      >
        {{ isCheckingCitations ? "检查中…" : "检查引用更新" }}
      </button>
      <button
        type="button"
        class="settings-button"
        :disabled="isCheckingVersions"
        @click="checkVersions"
      >
        {{ isCheckingVersions ? "检查中…" : "检查新版本" }}
      </button>
      <span v-if="deliverMessage" class="settings-saved">{{ deliverMessage }}</span>
    </div>
    <div class="settings-field-grid">
      <label class="settings-field">
        Webhook URL
        <input v-model="webhookUrl" type="url" placeholder="https://…" />
      </label>
      <label class="settings-field">
        邮件地址（需后端配置 SMTP）
        <input v-model="deliveryEmail" type="email" placeholder="you@example.com" />
      </label>
    </div>
    <div class="settings-actions">
      <button type="button" class="settings-button" :disabled="isDelivering" @click="deliver">
        {{ isDelivering ? "投递中…" : "投递未读通知" }}
      </button>
    </div>
    <p class="settings-hint">支持 Webhook 推送；邮件需要另行配置 SMTP。</p>
  </SettingsSection>
</template>

<style scoped>
.settings-notifications {
  margin: 0 0 4px;
  padding: 0;
  list-style: none;
}

.settings-notifications li {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 10px 0;
}

.settings-notifications p {
  margin: 3px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.settings-mark {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--color-text-muted);
  font-size: 11px;
}

.settings-mark:hover {
  color: var(--color-text);
}

.settings-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.settings-field input {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 8px;
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
}

.settings-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.settings-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.settings-saved {
  color: var(--color-success);
  font-size: 11px;
}

</style>
