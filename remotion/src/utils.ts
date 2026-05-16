export function resolveMediaPath(file_path: string): string {
  if (file_path.startsWith('http') || file_path.startsWith('file://')) {
    return file_path;
  }
  
  // If it's a relative path just referencing a file in public/, return it
  if (!file_path.includes(':') && !file_path.startsWith('/')) {
    return file_path;
  }
  
  const normalizedPath = file_path.replace(/\\/g, '/');
  // For Windows, do NOT prepend a slash if it's already an absolute path like C:/
  if (/^[a-zA-Z]:\//.test(normalizedPath)) {
    return normalizedPath;
  }
  
  const absolutePath = normalizedPath.startsWith('/') ? normalizedPath : `/${normalizedPath}`;
  return absolutePath;
}

// ─── Caption timestamp types ─────────────────────────────────────────────────

export type NormalizedWord = {
  word: string;
  startFrame: number;
  endFrame: number;
};

export type CaptionChunk = {
  words: NormalizedWord[];
  startFrame: number; // frame the chunk becomes visible
  endFrame: number;   // frame the chunk disappears
};

/**
 * Normalizes timestamps from either:
 *   - edge-tts:          [{word, start, offset}]
 *   - Google Cloud TTS:  [{word, start, end}]
 * into [{word, startFrame, endFrame}] using the provided fps.
 */
export function normalizeTimestamps(timestamps: any[], fps: number): NormalizedWord[] {
  if (!timestamps || timestamps.length === 0) return [];

  return timestamps.map((t, i) => {
    const startSec: number = typeof t.start === 'number' ? t.start : 0;
    // Google Cloud TTS has `end`; edge-tts has no `end` — infer from next word
    let endSec: number;
    if (typeof t.end === 'number') {
      endSec = t.end;
    } else if (i + 1 < timestamps.length && typeof timestamps[i + 1].start === 'number') {
      endSec = timestamps[i + 1].start;
    } else {
      endSec = startSec + 0.3; // fallback: 300ms per word
    }

    return {
      word: String(t.word ?? ''),
      startFrame: Math.round(startSec * fps),
      endFrame: Math.round(endSec * fps),
    };
  });
}

const PUNCTUATION_SPLIT = /[,.\-–—!?;:]$/;

/**
 * Splits NormalizedWord[] into CaptionChunks of 4-5 words.
 * Prefers splitting after punctuation within the window.
 * Falls back to splitting at exactly 4 words.
 */
export function buildCaptionChunks(words: NormalizedWord[]): CaptionChunk[] {
  const chunks: CaptionChunk[] = [];
  let i = 0;

  while (i < words.length) {
    const window = words.slice(i, i + 5); // look ahead up to 5 words
    let splitAt = -1;

    // Prefer splitting after punctuation within window (positions 3 or 4)
    for (let j = Math.min(3, window.length - 1); j >= 2; j--) {
      if (PUNCTUATION_SPLIT.test(window[j].word)) {
        splitAt = j + 1;
        break;
      }
    }

    // Fallback: split at 4 words
    if (splitAt === -1) {
      splitAt = Math.min(4, window.length);
    }

    const chunkWords = words.slice(i, i + splitAt);
    chunks.push({
      words: chunkWords,
      startFrame: chunkWords[0].startFrame,
      endFrame: chunkWords[chunkWords.length - 1].endFrame,
    });

    i += splitAt;
  }

  return chunks;
}
