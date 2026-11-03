<script setup lang="ts">
import { onMounted, ref } from "vue";
import StateBlock from "../components/StateBlock.vue";
import { getAlertSettings, updateAlertSettings } from "../api/settings";
import {
  checkCitationUpdates,
  checkVersionUpdates,
  deliverNotifications,
  listNotifications,
  markNotificationRead,
} from "../api/notifications";
import type { AlertSettings, NotificationSummary } from "../api";

defineEmits<{
  back: [];
}>();

const alertSettings = ref<AlertSettings | null>(null);
const notifications = ref<NotificationSummary[]>([]);
const webhookUrl = ref("");
const deliveryEmail = ref("");
const isSaving = ref(false);
const isDelivering = ref(false);
const isCheckingCitations = ref(false);
const isCheckingVersions = ref(false);
const errorMessage = ref("");
const deliverMessage = ref("");

async function load(): Promise<void> {
  try {
    [alertSettings.value, notifications.value] = await Promise.all([
      getAlertSettings(),
      listNotifications("unread"),
    ]);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "读取提醒设置失败";
  }
}

async function readNotification(notification: NotificationSummary): Promise<void> {
  await markNotificationRead(notification.id);
  notifications.value = notifications.value.filter((item) => item.id !== notification.id);
}

async function deliver(): Promise<void> {
  if (!webhookUrl.value.trim() && !deliveryEmail.value.trim()) return;
  isDelivering.value = true;
  deliverMessage.value = "";
  try {
    const result = await deliverNotifications(
      webhookUrl.value.trim() || undefined,
      deliveryEmail.value.trim() || undefined,
    );
    deliverMessage.value = "已投递 " + result.delivered + " 条";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "投递失败";
  } finally {
    isDelivering.value = false;
  }
}

async function checkCitations(): Promise<void> {
  isCheckingCitations.value = true;
  deliverMessage.value = "";
  try {
    const result = await checkCitationUpdates();
    const errors = result.errors ?? [];
    const suffix = errors.length ? `，${errors.length} 篇暂无数据` : "";
    deliverMessage.value = `检查 ${result.checked} 篇，新增 ${result.notified} 条引用提醒${suffix}`;
    await load();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "检查引用更新失败";
  } finally {
    isCheckingCitations.value = false;
  }
}

async function checkVersions(): Promise<void> {
  isCheckingVersions.value = true;
  deliverMessage.value = "";
  try {
    const result = await checkVersionUpdates();
    const errors = result.errors ?? [];
    const suffix = errors.length ? `，${errors.length} 篇暂无数据` : "";
    deliverMessage.value = `检查 ${result.checked} 篇，新增 ${result.notified} 条版本提醒${suffix}`;
    await load();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "检查新版本失败";
  } finally {
    isCheckingVersions.value = false;
  }
}

async function save(): Promise<void> {
  if (!alertSettings.value) return;
  isSaving.value = true;
  errorMessage.value = "";
  try {
    alertSettings.value = await updateAlertSettings({
      new_paper: alertSettings.value.new_paper,
      new_version: alertSettings.value.new_version,
      new_citation: alertSettings.value.new_citation,
      digest_enabled: alertSettings.value.digest_enabled,
      digest_frequency: alertSettings.value.digest_frequency,
    });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "保存提醒设置失败";
  } finally {
    isSaving.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <section class="settings-view" aria-label="设置">
    <header class="settings-view__bar">
      <div>
        <p class="settings-view__eyebrow">Preferences</p>
        <h1 class="settings-view__title">设置</h1>
        <p class="settings-view__subtitle">本地优先：论文与笔记默认保存在当前设备。</p>
      </div>
      <button type="button" class="settings-view__back" @click="$emit('back')">返回</button>
    </header>

    <div class="settings-view__grid">
      <article class="settings-card">
        <h2>数据与隐私</h2>
        <p>数据目录由后端 SCIPAL_DATA_DIR 控制，默认是 backend/data。</p>
        <p>论文原文、解析产物、索引与 SQLite 数据库都保存在本地；未配置远程模型时不会上传论文内容。</p>
        <p class="settings-card__hint">备份：复制 backend/data 目录即可迁移整库。</p>
      </article>

      <article class="settings-card">
        <h2>模型服务</h2>
        <p>LLM 与 Embedding 由后端环境变量配置，前端不保存 API Key。</p>
        <p>需要在 backend/.env 中设置 DEEPSEEK_API_KEY；Embedding 可走本地模型或 OpenAI 兼容服务。</p>
        <p class="settings-card__hint">修改配置后重启后端生效。</p>
      </article>

      <article v-if="alertSettings" class="settings-card">
        <h2>提醒与 Digest</h2>
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
        <label class="settings-toggle">
          Digest 频率
          <select v-model="alertSettings.digest_frequency" class="settings-select">
            <option value="daily">每日</option>
            <option value="weekly">每周</option>
            <option value="off">关闭</option>
          </select>
        </label>
        <StateBlock
          v-if="errorMessage"
          kind="error"
          compact
          :description="errorMessage"
        />
        <button type="button" class="settings-save" :disabled="isSaving" @click="save">
          {{ isSaving ? "保存中…" : "保存提醒设置" }}
        </button>
        <p class="settings-card__hint">Webhook 立即投递；邮件需在后端配置 SMTP 环境变量。</p>
      </article>

      <article class="settings-card">
        <h2>通知</h2>
        <p v-if="!notifications.length" class="settings-card__hint">没有未读通知。</p>
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
        <button
          type="button"
          class="settings-save"
          :disabled="isCheckingCitations"
          @click="checkCitations"
        >
          {{ isCheckingCitations ? "检查中…" : "检查引用更新" }}
        </button>
        <button
          type="button"
          class="settings-save"
          :disabled="isCheckingVersions"
          @click="checkVersions"
        >
          {{ isCheckingVersions ? "检查中…" : "检查新版本" }}
        </button>
        <label class="settings-field">
          Webhook URL
          <input v-model="webhookUrl" class="settings-select" type="url" placeholder="https://…" />
        </label>
        <label class="settings-field">
          邮件地址（需后端配置 SMTP）
          <input v-model="deliveryEmail" class="settings-select" type="email" placeholder="you@example.com" />
        </label>
        <button type="button" class="settings-save" :disabled="isDelivering" @click="deliver">
          {{ isDelivering ? "投递中…" : "投递未读通知" }}
        </button>
        <p v-if="deliverMessage" class="settings-card__hint">{{ deliverMessage }}</p>
        <p class="settings-card__hint">支持 Webhook 推送；邮件需要另行配置 SMTP。</p>
      </article>

      <article class="settings-card">
        <h2>阅读偏好</h2>
        <p>阅读状态分为：待读、队列中、速读、在读、已读、已归档。</p>
        <p>进度按滚动位置记录；关闭页面后再打开会恢复到上次位置。</p>
        <p class="settings-card__hint">当前版本只支持文本型 PDF。</p>
      </article>

      <article class="settings-card">
        <h2>关于 SciPal</h2>
        <p>智能论文助手 v0.1 · 个人研究生阅读工作台。</p>
        <p>当前阶段：M0 论文资产层与阅读闭环。</p>
        <p class="settings-card__hint">后续会加入速读卡、跨论文对比与领域跟进。</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.settings-view {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 20px;
  padding: 28px 34px;
  overflow-y: auto;
  background: var(--color-bg);
}

.settings-view__bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.settings-view__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.settings-view__title {
  margin: 0;
  font-size: 28px;
  font-weight: 650;
}

.settings-view__subtitle {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.settings-view__back {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-panel);
  color: var(--color-text);
  cursor: pointer;
  font-size: 13px;
  padding: 8px 12px;
}

.settings-view__back:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.settings-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}

.settings-card {
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-panel);
}

.settings-card h2 {
  margin: 0 0 10px;
  font-size: 15px;
}

.settings-card p {
  margin: 0 0 8px;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.55;
}

.settings-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.settings-select {
  border: 1px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-bg);
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
  padding: 5px 8px;
}

.settings-save {
  border: 1px solid var(--color-accent);
  border-radius: 7px;
  background: var(--color-accent);
  color: #fff;
  cursor: pointer;
  font-size: 12px;
  padding: 7px 10px;
}

.settings-notifications {
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
}

.settings-notifications li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 12px;
}

.settings-notifications p {
  margin: 3px 0 0;
  color: var(--color-text-muted);
}

.settings-mark {
  border: 0;
  background: transparent;
  color: var(--color-accent);
  cursor: pointer;
  font-size: 11px;
}

.settings-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.settings-error {
  color: var(--color-danger);
  font-size: 12px;
}

.settings-card__hint {
  margin-top: 12px !important;
  padding-top: 10px;
  border-top: 1px solid var(--color-border);
  font-size: 12px !important;
}
</style>
