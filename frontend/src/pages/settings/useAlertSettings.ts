import { onBeforeUnmount, ref } from "vue";

import { getAlertSettings, updateAlertSettings } from "@/api/settings";
import {
  checkCitationUpdates,
  checkVersionUpdates,
  deliverNotifications,
  listNotifications,
  markNotificationRead,
} from "@/api/notifications";
import type { AlertSettings, NotificationSummary } from "@/api";

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

function dispose(): void {
  if (saveMessageTimer !== null) {
    window.clearTimeout(saveMessageTimer);
    saveMessageTimer = null;
  }
}

export function useAlertSettings() {
  onBeforeUnmount(dispose);

  return {
    alertSettings,
    notifications,
    webhookUrl,
    deliveryEmail,
    isSaving,
    isDelivering,
    isCheckingCitations,
    isCheckingVersions,
    errorMessage,
    deliverMessage,
    saveMessage,
    load,
    readNotification,
    deliver,
    checkCitations,
    checkVersions,
    save,
  };
}
