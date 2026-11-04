import { jsonRequest, requestJson } from "@/api/client";
import type {
  NotificationDeliverResult,
  NotificationSummary,
  UpdateCheckResult,
} from "@/api/types";

export function listNotifications(status?: string): Promise<NotificationSummary[]> {
  const query = status ? "?status=" + encodeURIComponent(status) : "";
  return requestJson<NotificationSummary[]>("/notifications" + query, "读取通知失败");
}

export function markNotificationRead(id: string): Promise<NotificationSummary> {
  return requestJson<NotificationSummary>("/notifications/" + id + "/read", "标记通知失败", {
    method: "POST",
  });
}

export function checkCitationUpdates(): Promise<UpdateCheckResult> {
  return requestJson<UpdateCheckResult>(
    "/notifications/check-citations",
    "检查引用更新失败",
    { method: "POST" },
  );
}

export function checkVersionUpdates(): Promise<UpdateCheckResult> {
  return requestJson<UpdateCheckResult>(
    "/notifications/check-versions",
    "检查新版本失败",
    { method: "POST" },
  );
}

export function deliverNotifications(
  webhookUrl?: string,
  emailTo?: string,
): Promise<NotificationDeliverResult> {
  return requestJson<NotificationDeliverResult>("/notifications/deliver", "投递通知失败", {
    method: "POST",
    ...jsonRequest({
      webhook_url: webhookUrl || undefined,
      email_to: emailTo || undefined,
    }),
  });
}
