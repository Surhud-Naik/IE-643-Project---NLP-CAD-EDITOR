export interface ExampleItem {
  id: string;
  title: string;
  category: string;
  instruction: string;
  script: string;
  description: string;
}

export interface ParameterChange {
  name: string;
  old_value: any;
  new_value: any;
}

export interface ChangeSummary {
  parameters_changed: ParameterChange[];
  lines_added: number;
  lines_removed: number;
  lines_touched: number;
  output_tokens: number;
  full_program_tokens: number;
  token_savings_pct: number;
}

export interface GeometryMetrics {
  validity: boolean;
  original_volume: number;
  edited_volume: number;
  volume_change_pct: number;
  bbox_diagonal_original: number;
  bbox_diagonal_edited: number;
  chamfer_distance_relative: number;
  volumetric_iou: number;
}

export interface JobResult {
  job_id: string;
  status: string;
  original_script: string;
  edited_script?: string;
  patch_text?: string;
  raw_patch?: string;
  attempts_used: number;
  metrics?: GeometryMetrics;
  change_summary?: ChangeSummary;
  download_urls: Record<string, string>;
  created_at: number;
  completed_at?: number;
  execution_time_seconds?: number;
  error?: string;
}

export interface JobEvent {
  job_id: string;
  status: string;
  current_attempt: number;
  max_attempts: number;
  message: string;
  error?: string;
  raw_patch?: string;
  result?: JobResult;
}

export interface HistoryItem {
  id: string;
  timestamp: string;
  instruction: string;
  script: string;
  patchText?: string;
  volumeChangePct?: number;
}
