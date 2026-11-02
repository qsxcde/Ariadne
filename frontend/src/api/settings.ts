import { jsonRequest, requestJson } from "./client";
import type { AlertSettings, AlertSettingsUpdate, Digest } from "./types";

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

export function getDigest(): Promise<Digest> {
  return requestJson<Digest>("/digest", "读取 Digest 失败");
}
