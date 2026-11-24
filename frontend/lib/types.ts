export interface User {
  id: string;
  email: string;
  name: string;
  avatar_color: string;
  email_verified_at?: string | null;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan: string;
  plan_status?: string;
  plan_interval?: string;
  plan_renews_at?: string | null;
  monthly_clip_limit: number;
  monthly_render_minutes: number;
  created_at: string;
  role: string;
  member_count: number;
}

export interface Session {
  user: User;
  workspaces: Workspace[];
  active_workspace_id: string | null;
}

export type VideoStatus =
  | "uploaded"
  | "downloading"
  | "probing"
  | "ready"
  | "transcribing"
  | "analyzing"
  | "rendering"
  | "error";

export interface Video {
  id: string;
  workspace_id: string;
  project_id: string | null;
  title: string;
  description: string;
  source_type: string;
  source_url: string | null;
  original_filename: string | null;
  mime_type: string;
  size_bytes: number;
  duration_seconds: number;
  width: number;
  height: number;
  fps: number;
  has_audio: boolean;
  language: string;
  status: VideoStatus;
  progress: number;
  error_message: string | null;
  thumbnail_key: string | null;
  created_at: string;
  updated_at: string;
}

export interface VideoDetail extends Video {
  has_transcript: boolean;
  transcript_language: string | null;
  clip_count: number;
  approved_clip_count: number;
  analysis_provider: string | null;
  metadata: Record<string, unknown> | null;
}

export interface Word {
  word: string;
  start_ms: number;
  end_ms: number;
  confidence?: number | null;
}

export interface Segment {
  id: string;
  start_ms: number;
  end_ms: number;
  text: string;
  speaker_id: string | null;
  confidence: number;
  words: Word[];
}

export interface Speaker {
  id: string;
  label: string;
  display_name: string | null;
  color: string;
  method: string;
}

export interface Transcript {
  id: string;
  video_id: string;
  language: string;
  engine: string;
  model: string;
  status: string;
  full_text: string;
  word_count: number;
  error_message?: string | null;
  segments: Segment[];
  speakers: Speaker[];
}

export type ClipStatus = "suggested" | "approved" | "rejected";

export interface Clip {
  id: string;
  video_id: string;
  workspace_id: string;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  title: string;
  description: string;
  hook: string;
  transcript_text: string;
  explanation: string;
  virality_score: number;
  engagement_potential: number;
  signals: Record<string, number>;
  aspect_ratio: string;
  source: string;
  status: ClipStatus;
  created_at: string;
  video_title?: string;
  video_duration_seconds?: number;
  has_editing_project?: boolean;
  editing_project_id?: string | null;
  render_count?: number;
  comment_count?: number;
  open_comment_count?: number;
}

export interface ClipComment {
  id: string;
  clip_id: string;
  user_id: string;
  author_name: string;
  author_email: string;
  body: string;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  mine: boolean;
}

export interface ShareLink {
  id: string;
  token: string;
  url: string;
  has_password: boolean;
  expires_at: string | null;
  view_count: number;
  created_at: string;
}

export interface PublicShare {
  locked: boolean;
  token?: string;
  has_password: boolean;
  expires_at: string | null;
  access?: string;
  title?: string;
  filename?: string;
  format?: string;
  width?: number;
  height?: number;
  duration_ms?: number;
  size_bytes?: number;
  created_at?: string;
  media_url?: string;
  download_url?: string;
  thumbnail_url?: string;
}

export interface ClipContent {
  titles: string[];
  hooks: string[];
  descriptions: string[];
  hashtags: string[];
  captions: Record<string, string>;
  thumbnail_ideas: string[];
  calls_to_action: string[];
  summary: string;
  provider: string;
  model: string;
}

export interface CaptionStyle {
  id: string;
  name: string;
  is_builtin: boolean;
  config: Record<string, unknown>;
}

export interface EditorProject {
  id: string;
  workspace_id: string;
  video_id: string;
  clip_id: string | null;
  name: string;
  aspect_ratio: string;
  width: number;
  height: number;
  trim_start_ms: number;
  trim_end_ms: number;
  focus_x: number;
  focus_y: number;
  caption_style_id: string | null;
  captions_enabled: boolean;
  caption_overrides: Record<string, unknown>;
  overlays: Overlay[];
  music: { asset_key?: string; volume?: number } | null;
  audio: { volume?: number; muted?: boolean };
  operations: unknown[];
  status: string;
  created_at: string;
  updated_at: string;
  video_title?: string;
  video_duration_seconds?: number;
  video_width?: number;
  video_height?: number;
  transcript?: Transcript | null;
  latest_render?: RenderJob | null;
}

export interface Overlay {
  id?: string;
  type: "text" | "image";
  text?: string;
  asset_key?: string;
  start_ms: number;
  end_ms: number;
  x: number;
  y: number;
  width?: number;
  font_size?: number;
  color?: string;
  background?: string;
  background_opacity?: number;
  animation?: string;
}

export interface RenderJob {
  id: string;
  editing_project_id: string;
  preset: string;
  format: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  attempts: number;
  error_message: string | null;
  output_size_bytes: number;
  render_seconds: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  export_id?: string | null;
  download_url?: string | null;
  thumbnail_url?: string | null;
  project_name?: string;
  video_title?: string;
}

export interface ExportItem {
  id: string;
  render_job_id: string;
  clip_id: string | null;
  title: string;
  filename: string;
  format: string;
  width: number;
  height: number;
  duration_ms: number;
  size_bytes: number;
  created_at: string;
  download_url: string;
  thumbnail_url: string | null;
}

export interface Job {
  id: string;
  video_id: string | null;
  kind: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  stage: string;
  progress: number;
  attempts: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ProjectItem {
  id: string;
  name: string;
  description: string;
  created_at: string;
  video_count: number;
}

export interface Activity {
  id: string;
  action: string;
  target_type: string;
  target_id: string;
  user_email: string | null;
  created_at: string;
  meta: Record<string, unknown>;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

export interface Dashboard {
  counts: {
    videos: number;
    clips: number;
    approved_clips: number;
    processing: number;
    published: number;
    renders: number;
    exports: number;
    scheduled_posts: number;
  };
  storage_bytes: number;
  processing: Job[];
  recent_videos: Video[];
  recent_clips: Clip[];
  recent_activity: Activity[];
  usage: {
    transcription_seconds: number;
    ai_units: number;
    render_seconds: number;
    storage_gb: number;
    recent_storage_bytes: number;
  };
  renders: RenderJob[];
  notifications: NotificationItem[];
}

export interface SocialAccount {
  id: string;
  platform: string;
  account_name: string;
  external_id: string;
  status: string;
  scopes: string;
  token_expires_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface PublishingJob {
  id: string;
  exported_video_id: string;
  social_account_id: string;
  platform: string;
  title: string;
  caption: string;
  hashtags: string;
  privacy: string;
  scheduled_for: string | null;
  status: string;
  external_post_id: string | null;
  external_url: string | null;
  attempts: number;
  error_message: string | null;
  published_at: string | null;
  created_at: string;
  account_name: string;
  video_title: string;
}

export interface AnalyticsOverview {
  totals: Record<string, number>;
  platform_breakdown: Array<Record<string, number | string>>;
  series: Array<{ date: string; views: number; engagement: number }>;
  top_posts: Array<Record<string, string | number | null>>;
  data_sources: string[];
  notes: string[];
}

export interface AIProvider {
  provider: string;
  label: string;
  model: string;
  base_url: string;
  configured: boolean;
  has_workspace_key: boolean;
  enabled: boolean;
  is_default: boolean;
  capabilities: string[];
  local: boolean;
}

export interface SystemStatus {
  ffmpeg: boolean;
  ffmpeg_version: string;
  transcription_engines: Record<string, { available: boolean; model: string; local: boolean; note: string | null }>;
  ai_providers: Record<string, { label: string; configured: boolean; model: string; local: boolean }>;
  redis: boolean;
  storage: string;
  database: string;
  job_runner: string;
  ytdlp: boolean;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  name: string;
  role: string;
  created_at: string;
}

export interface ApiKeyItem {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface LiveStream {
  id: string;
  platform: string;
  url: string;
  title: string;
  status: string;
  recording_video_id: string | null;
  started_at: string | null;
  ended_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface ConnectStart {
  platform: string;
  configured: boolean;
  authorize_url: string | null;
  message: string;
}
export interface BillingPlan {
  id: string;
  name: string;
  tagline: string;
  monthly: number;
  yearly: number;
  clips: number;
  minutes: number;
  features: string[];
}

export interface BillingInvoice {
  id: string;
  number: string;
  status: string;
  amount_cents: number;
  currency: string;
  hosted_url: string;
  pdf_url: string;
  period_start: string | null;
  period_end: string | null;
  created_at: string;
}

export interface BillingOverview {
  plan: string;
  plan_name: string;
  status: string;
  interval: string;
  renews_at: string | null;
  limits: { clips_per_month: number; render_minutes_per_month: number };
  usage: {
    clips_this_month: number;
    render_minutes_this_month: number;
    breakdown: Array<{ kind: string; provider: string; quantity: number }>;
    storage_bytes: number;
    upload_bytes: number;
    export_bytes: number;
  };
  plans: BillingPlan[];
  payment_provider: { available: boolean; provider: string | null; publishable_key: string | null; message: string };
  invoices: BillingInvoice[];
}

export interface WebhookEndpoint {
  id: string;
  url: string;
  description: string;
  events: string[];
  enabled: boolean;
  secret: string;
  created_at: string;
}

export interface WebhookDelivery {
  id: string;
  event: string;
  ok: boolean;
  status_code: number;
  error: string;
  duration_ms: number;
  created_at: string;
}

export interface WorkspaceInvite {
  id: string;
  email: string;
  role: string;
  invited_by: string;
  expires_at: string;
  created_at: string;
  expired: boolean;
}
