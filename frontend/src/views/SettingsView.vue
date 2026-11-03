<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
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
const saveMessage = ref("");
let saveMessageTimer: number | null = null;

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
    saveMessage.value = "已保存";
    if (saveMessageTimer !== null) {
      window.clearTimeout(saveMessageTimer);
    }
    saveMessageTimer = window.setTimeout(() => {
      saveMessage.value = "";
      saveMessageTimer = null;
    }, 2000);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "保存提醒设置失败";
  } finally {
    isSaving.value = false;
  }
}

onMounted(() => {
  void load();
});

onBeforeUnmount(() => {
  if (saveMessageTimer !== null) {
    window.clearTimeout(saveMessageTimer);
  }
});
</script>

<template>
  <section class="settings-view" aria-label="设置">
    <div class="settings-view__inner">
      <header class="settings-view__bar">
        <div>
          <p class="settings-view__eyebrow">PREFERENCES</p>
          <h1 class="settings-view__title">设置</h1>
          <p class="settings-view__subtitle">本地优先：论文与笔记默认保存在当前设备。</p>
        </div>
        <button type="button" class="settings-view__back" @click="$emit('back')">返回</button>
      </header>

      <div class="settings-view__layout">
        <nav class="settings-view__nav" aria-label="设置分区">
          <a href="#settings-data">数据与隐私</a>
          <a href="#settings-model">模型服务</a>
          <a href="#settings-alerts">提醒与 Digest</a>
          <a href="#settings-notifications">通知</a>
          <a href="#settings-reading">阅读偏好</a>
          <a href="#settings-about">关于 SciPal</a>
        </nav>

        <div class="settings-view__sections">
          <StateBlock
            v-if="errorMessage"
            kind="error"
            compact
            title="设置操作失败"
            :description="errorMessage"
          />

          <section id="settings-data" class="settings-section">
            <header class="settings-section__head">
              <h2>数据与隐私</h2>
              <span class="settings-section__index">01</span>
            </header>
            <p>数据目录由后端 SCIPAL_DATA_DIR 控制，默认是 backend/data。</p>
            <p>论文原文、解析产物、索引与 SQLite 数据库都保存在本地；未配置远程模型时不会上传论文内容。</p>
            <p class="settings-hint">备份：复制 backend/data 目录即可迁移整库。</p>
          </section>

          <section id="settings-model" class="settings-section">
            <header class="settings-section__head">
              <h2>模型服务</h2>
              <span class="settings-section__index">02</span>
            </header>
            <p>LLM 与 Embedding 由后端环境变量配置，前端不保存 API Key。</p>
            <p>需要在 backend/.env 中设置 DEEPSEEK_API_KEY；Embedding 可走本地模型或 OpenAI 兼容服务。</p>
            <p class="settings-hint">修改配置后重启后端生效。</p>
          </section>

          <section id="settings-alerts" class="settings-section">
            <header class="settings-section__head">
              <h2>提醒与 Digest</h2>
              <span class="settings-section__index">03</span>
            </header>
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
          </section>

          <section id="settings-notifications" class="settings-section">
            <header class="settings-section__head">
              <h2>通知</h2>
              <span class="settings-section__index">04</span>
            </header>
            <p v-if="!notifications.length" class="settings-hint">没有未读通知。</p>
            <ul v-else class="settings-notifications">
              <li v-for="notification in notifications" :key="notification.id">
                <div>
                  <strong>{{ notification.title }}</strong>
                  <p>{{ notification.body }}</p>
                </div>
                <button
                  type="button"
                  class="settings-mark"
                  @click="readNotification(notification)"
                >
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
              <button
                type="button"
                class="settings-button"
                :disabled="isDelivering"
                @click="deliver"
              >
                {{ isDelivering ? "投递中…" : "投递未读通知" }}
              </button>
            </div>
            <p class="settings-hint">支持 Webhook 推送；邮件需要另行配置 SMTP。</p>
          </section>

          <section id="settings-reading" class="settings-section">
            <header class="settings-section__head">
              <h2>阅读偏好</h2>
              <span class="settings-section__index">05</span>
            </header>
            <p>阅读状态分为：待读、队列中、速读、在读、已读、已归档。</p>
            <p>进度按滚动位置记录；关闭页面后再打开会恢复到上次位置。</p>
            <p class="settings-hint">当前版本只支持文本型 PDF。</p>
          </section>

          <section id="settings-about" class="settings-section settings-section--last">
            <header class="settings-section__head">
              <h2>关于 SciPal</h2>
              <span class="settings-section__index">06</span>
            </header>
            <p>智能论文助手 v0.1 · 个人研究生阅读工作台。</p>
            <p>当前阶段：M0 论文资产层与阅读闭环。</p>
            <p class="settings-hint">后续会加入速读卡、跨论文对比与领域跟进。</p>
          </section>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.settings-view {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: var(--color-page);
}

.settings-view__inner {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 34px 52px;
}

.settings-view__bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--color-border);
}

.settings-view__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
}

.settings-view__title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 650;
}

.settings-view__subtitle {
  margin: 7px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.settings-view__back {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 7px 13px;
  color: var(--color-text-soft);
  font-size: 12px;
}

.settings-view__back:hover {
  border-color: var(--color-border-strong);
  color: var(--color-text);
}

.settings-view__layout {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 48px;
  align-items: start;
  padding-top: 24px;
}

.settings-view__nav {
  position: sticky;
  top: 20px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--color-border);
}

.settings-view__nav a {
  border-left: 2px solid transparent;
  margin-left: -1px;
  padding: 7px 12px;
  color: var(--color-text-muted);
  font-size: 12px;
  text-decoration: none;
}

.settings-view__nav a:hover {
  border-left-color: var(--color-text);
  color: var(--color-text);
}

.settings-view__sections {
  max-width: 820px;
  min-width: 0;
}

.settings-section {
  padding-bottom: 26px;
  margin-bottom: 26px;
  border-bottom: 1px solid var(--color-border);
  scroll-margin-top: 80px;
}

.settings-section--last {
  border-bottom: 0;
  margin-bottom: 0;
}

.settings-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.settings-section__head h2 {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
}

.settings-section__index {
  color: var(--color-border-strong);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.1em;
}

.settings-section p {
  margin: 0 0 8px;
  color: var(--color-text-soft);
  font-size: 13px;
  line-height: 1.7;
}

.settings-hint {
  margin-top: 10px !important;
  color: var(--color-text-muted) !important;
  font-size: 11px !important;
}

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

.settings-field input,
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

.settings-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.settings-saved {
  color: var(--color-success);
  font-size: 11px;
}

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
  font-size: 12px;
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

@media (max-width: 960px) {
  .settings-view__layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }

  .settings-view__nav {
    display: none;
  }

  .settings-toggle-grid,
  .settings-field-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
