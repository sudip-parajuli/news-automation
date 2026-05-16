export type BRollItem = {
  query: string;
  file_path: string;
  type: "video" | "still_image";
  duration: number; // in seconds
};

export type ScriptSectionData = {
  id: string; // "hook" | "context" | "conflict" etc.
  text: string;
  broll: BRollItem[];
};

export type LongFormVideoData = {
  sections: ScriptSectionData[];
  title: string;
  voiceover_file: string;
  background_music: string;
};

// Also define short form data to satisfy the ShortFormNews composition
export type ShortFormVideoData = {
  headline: string;
  body_text: string;
  clips: Array<{ file: string; duration: number }>;
  caption_lines: string[];
  voiceover_file: string;
  hook_text: string;
  loop_hook: string;
  audio_track?: string;
};
