import { jsonRequest, requestJson } from "@/api/client";
import type {
  AlertSettings,
  AlertSettingsUpdate,
  ModelSettings,
  ModelSettingsUpdatePayload,
} from "@/api/types";

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

export function getModelSettings(): Promise<ModelSettings> {
  return requestJson<ModelSettings>("/settings/models", "读取模型设置失败");
}

export function updateModelSettings(
  payload: ModelSettingsUpdatePayload,
): Promise<ModelSettings> {
  return requestJson<ModelSettings>("/settings/models", "保存模型设置失败", {
    method: "PATCH",
    ...jsonRequest(payload),
  });
}
