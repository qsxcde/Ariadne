import { jsonRequest, requestJson } from "./client";
import type {
  NotificationDeliverResult,
  NotificationSummary,
} from "./types";

export function listNotifications(status?: string): Promise<NotificationSummary[]> {
  const query = status ? "?status=" + encodeURIComponent(status) : "";
  return requestJson<NotificationSummary[]>("/notifications" + query, "读取通知失败");
}

export function markNotificationRead(id: string): Promise<NotificationSummary> {
  return requestJson<NotificationSummary>("/notifications/" + id + "/read", "标记通知失败", {
    method: "POST",
  });
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
