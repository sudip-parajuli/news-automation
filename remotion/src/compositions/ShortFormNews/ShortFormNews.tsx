import React from 'react';
import { AbsoluteFill, Audio, Series, useVideoConfig, useCurrentFrame } from 'remotion';
import { ShortFormVideoData } from '../../types';
import { resolveMediaPath } from '../../utils';
import { HookOverlay } from './HookOverlay';
import { ClipReel } from './ClipReel';
import { CaptionBurn } from './CaptionBurn';
import { LoopHook } from './LoopHook';
import { CTACard } from './CTACard';
import { HighlightCard } from './HighlightCard';

// Stub timestamps for the Remotion Studio preview only.
// In production these are overridden by real word timestamps from the pipeline.
const STUB_TIMESTAMPS = [
  { word: 'Breaking', start: 0.0, end: 0.4 },
  { word: 'news', start: 0.4, end: 0.65 },
  { word: 'preview', start: 0.65, end: 1.0 },
  { word: 'only.', start: 1.0, end: 1.5 },
];

export const ShortFormNews: React.FC<{ data?: ShortFormVideoData }> = ({ data }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Use stub data if none provided (for Studio preview)
  const hookText = data?.hook_text ?? "Breaking news preview.";
  const loopText = data?.loop_hook ?? 'Stay updated.';
  const clips = data?.clips ?? [{ file: 'hook.mp4', duration: 5 }];
  const voiceover = data?.voiceover_file ?? '';
  const audioTrack = data?.audio_track ?? '';
  // Use real word timestamps from pipeline; fall back to stubs only in Studio preview
  const timestamps = (data?.timestamps && data.timestamps.length > 0)
    ? data.timestamps
    : STUB_TIMESTAMPS;

  const HOOK_FRAMES = Math.round(1.5 * fps);
  const LOOP_FRAMES = Math.round(2 * fps);
  // CTA sits in the window [durationInFrames-10s, durationInFrames-2s]
  const ctaWindowStart = Math.max(HOOK_FRAMES, durationInFrames - Math.round(10 * fps));
  const ctaWindowEnd = durationInFrames - LOOP_FRAMES;
  const hasCTA = ctaWindowEnd > ctaWindowStart;
  const firstClipFile = clips[0]?.file ?? '';

  const progressBarWidth = (frame / durationInFrames) * 100;

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      {/* Dynamic gradient progress bar at the top */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: `${progressBarWidth}%`,
          height: '10px',
          background: 'linear-gradient(90deg, #E84545, #ec4899, #3b82f6)',
          zIndex: 100,
          boxShadow: '0 0 10px rgba(232, 69, 69, 0.6)',
        }}
      />

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

      {/* Highlight/Data Card overlay */}
      <HighlightCard card={data?.highlight_card} />

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
