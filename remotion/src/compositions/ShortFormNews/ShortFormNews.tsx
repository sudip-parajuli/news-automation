import React from 'react';
import { AbsoluteFill, Audio, Series, useVideoConfig } from 'remotion';
import { ShortFormVideoData } from '../../types';
import { resolveMediaPath } from '../../utils';
import { HookOverlay } from './HookOverlay';
import { ClipReel } from './ClipReel';
import { CaptionBurn } from './CaptionBurn';
import { LoopHook } from './LoopHook';
import { CTACard } from './CTACard';

// Stub timestamps for the caption burn preview
const STUB_TIMESTAMPS = [
  { word: 'OPEC', start: 0.0, end: 0.4 },
  { word: 'just', start: 0.4, end: 0.65 },
  { word: 'made', start: 0.65, end: 0.9 },
  { word: 'a', start: 0.9, end: 1.0 },
  { word: 'decision', start: 1.0, end: 1.5 },
  { word: 'that', start: 1.5, end: 1.75 },
  { word: 'will', start: 1.75, end: 2.0 },
  { word: 'affect', start: 2.0, end: 2.4 },
  { word: 'you.', start: 2.4, end: 2.9 },
];

export const ShortFormNews: React.FC<{ data?: ShortFormVideoData }> = ({ data }) => {
  const { fps, durationInFrames } = useVideoConfig();

  // Use stub data if none provided (for Studio preview)
  const hookText = data?.hook_text ?? "Oil prices just spiked. Here's why.";
  const loopText = data?.loop_hook ?? 'You need to see this.';
  const clips = data?.clips ?? [{ file: 'hook.mp4', duration: 5 }];
  const voiceover = data?.voiceover_file ?? '';
  const audioTrack = data?.audio_track ?? '';
  const timestamps = STUB_TIMESTAMPS;

  const HOOK_FRAMES = Math.round(1.5 * fps);
  const LOOP_FRAMES = Math.round(2 * fps);
  // CTA sits in the window [durationInFrames-10s, durationInFrames-2s]
  const ctaWindowStart = Math.max(HOOK_FRAMES, durationInFrames - Math.round(10 * fps));
  const ctaWindowEnd = durationInFrames - LOOP_FRAMES;
  const hasCTA = ctaWindowEnd > ctaWindowStart;
  const firstClipFile = clips[0]?.file ?? '';

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      {/* Audio layers */}
      {voiceover && <Audio src={resolveMediaPath(voiceover)} volume={1.0} />}
      {audioTrack && <Audio src={resolveMediaPath(audioTrack)} volume={0.12} />}

      {/* Background clip reel — runs full duration */}
      <ClipReel clips={clips} />

      {/* Hook overlay: first 1.5 seconds */}
      <Series>
        <Series.Sequence durationInFrames={HOOK_FRAMES}>
          <HookOverlay text={hookText} />
        </Series.Sequence>
      </Series>

      {/* Caption burn — always visible */}
      <CaptionBurn timestamps={timestamps} />

      {/* CTA card — appears 10s before end, only if there's room */}
      {hasCTA && (
        <Series>
          <Series.Sequence durationInFrames={ctaWindowStart} />
          <Series.Sequence durationInFrames={ctaWindowEnd - ctaWindowStart}>
            <CTACard />
          </Series.Sequence>
        </Series>
      )}

      {/* Loop hook: final 2 seconds — only render if there's room */}
      {durationInFrames > LOOP_FRAMES && (
        <Series>
          <Series.Sequence durationInFrames={durationInFrames - LOOP_FRAMES} />
          <Series.Sequence durationInFrames={LOOP_FRAMES}>
            <LoopHook firstFrame={firstClipFile} loopText={loopText} />
          </Series.Sequence>
        </Series>
      )}
    </AbsoluteFill>
  );
};
