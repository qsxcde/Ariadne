/**
 * 后端契约类型。
 *
 * 全部由 contracts/openapi.json 生成（npm run gen），不要手改；
 * 视图模型放 src/types/view.ts。
 */
import type { components } from "@/shared/contracts/openapi";

type Schemas = components["schemas"];

export type UserSummary = Schemas["UserResponse"];
export type AuthResult = Schemas["AuthResponse"];

export type SourceRef = Schemas["SourceRef"];
export type SourceBlockBox = Schemas["SourceBlockBox"];
export type SourceChunk = Schemas["SourceChunkResponse"];

export type PaperDocument = Schemas["DocumentSummary"];
export type DocumentUploadResult = Schemas["DocumentIntakeResponse"];
export type LibraryDocument = Schemas["LibraryDocumentSummary"];

export type SessionSummary = Schemas["SessionSummary"];
export type SessionSnapshot = Schemas["SessionSnapshot"];
export type SessionUpdatePayload = Schemas["SessionUpdateRequest"];
export type IndexRebuildResult = Schemas["IndexRebuildResponse"];

export type PaperBlock = Schemas["PaperBlock"];
export type PaperContent = Schemas["DocumentContentResponse"];

export type ModelSettings = Schemas["ModelSettingsResponse"];
export type ModelSettingsUpdatePayload = Schemas["ModelSettingsUpdate"];

export type PaperSummary = Schemas["PaperSummary"];
export type PaperDetail = Schemas["PaperDetail"];
export type PaperDocumentSummary = Schemas["PaperDocumentSummary"];
export type PaperBrief = Schemas["PaperBrief"];
export type WeeklyReview = Schemas["WeeklyReview"];
export type SubscriptionSummary = Schemas["SubscriptionSummary"];
export type SubscriptionCreatePayload = Schemas["SubscriptionCreateRequest"];
export type FeedItemSummary = Schemas["FeedItemSummary"];
export type FeedRefreshResult = Schemas["FeedRefreshResponse"];
export type NotificationSummary = Schemas["NotificationSummary"];
export type NotificationDeliverResult = Schemas["NotificationDeliverResponse"];
export type UpdateCheckResult = Schemas["UpdateCheckResponse"];
export type AlertSettings = Schemas["AlertSettings"];
export type AlertSettingsUpdate = Schemas["AlertSettingsUpdate"];
export type Digest = Schemas["DigestResponse"];
export type ExplainResponse = Schemas["ExplainResponse"];
export type GlossaryResponse = Schemas["GlossaryResponse"];
export type CitationGraph = Schemas["CitationGraph"];
export type LibraryStats = Schemas["LibraryStats"];
export type PaperUpdatePayload = Schemas["PaperUpdateRequest"];
export type PaperUploadResult = Schemas["PaperUploadResponse"];
export type PaperImportPayload = Schemas["PaperImportRequest"];
export type PaperImportResult = Schemas["PaperImportResponse"];

export type AnnotationSummary = Schemas["AnnotationSummary"];
export type AnnotationCreatePayload = Schemas["AnnotationCreateRequest"];

export type CollectionSummary = Schemas["CollectionSummary"];
export type CollectionCreatePayload = Schemas["CollectionCreateRequest"];
export type CollectionAskResult = Schemas["CollectionAskResponse"];
export type PaperComparison = Schemas["PaperComparison"];

/** SSE 事件载荷：六类事件的判别联合，同样来自 OpenAPI components。 */
export type MessageChunk = Schemas["ChatStreamEvent"];
