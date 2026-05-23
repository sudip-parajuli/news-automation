export type BRollItem = {
  query: string;
  file_path: string;
  type: "video" | "still_image";
  duration: number; // in seconds
};

export type StatCardData = {
  value: string;
  label: string;
};

export type ScriptSectionData = {
  id: string; // "hook" | "context" | "conflict" | "entry_N" etc.
  text: string;
  word_count: number;
  broll: BRollItem[];
  key_phrases?: string[];
  stat_card?: StatCardData | null;
};

export type LongFormVideoData = {
  title: string;
  topic_type?: string;
  metadata?: any;
  sections: ScriptSectionData[];
  voiceover_file: string;
  background_music: string;
  voiceover_duration_seconds: number;
};

export type WordTimestamp = {
  word: string;
  start: number;
  end?: number;
};

// Also define short form data to satisfy the ShortFormNews composition
export type HighlightCardData = {
  label: string;
  value: string;
  description: string;
  startTime: number;
  endTime: number;
};

export type ShortFormVideoData = {
  headline: string;
  body_text: string;
  clips: Array<{
    file: string;
    duration: number;
    type?: "video" | "still_image";
    label?: string;
  }>;
  caption_lines: string[];
  voiceover_file: string;
  hook_text: string;
  loop_hook: string;
  audio_track?: string;
  timestamps?: WordTimestamp[];
  /** Voiceover duration in seconds — used by calculateMetadata to set composition length */
  voiceover_duration_seconds?: number;
  highlight_card?: HighlightCardData;
};
