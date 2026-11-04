import { jsonRequest, requestJson } from "./client";
import type { AlertSettings, AlertSettingsUpdate } from "./types";

export function getAlertSettings(): Promise<AlertSettings> {
  return requestJson<AlertSettings>("/settings/alerts", "读取提醒设置失败");
}

export function updateAlertSettings(
  payload: AlertSettingsUpdate,
): Promise<AlertSettings> {
  return requestJson<AlertSettings>("/settings/alerts", "保存提醒设置失败", {
    method: "PATCH",
    ...jsonRequest(payload),
  });
}
