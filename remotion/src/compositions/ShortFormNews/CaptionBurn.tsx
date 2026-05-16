import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { buildCaptionChunks, normalizeTimestamps, CaptionChunk, NormalizedWord } from '../../utils';

export const CaptionBurn: React.FC<{
  timestamps: any[];
}> = ({ timestamps }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words: NormalizedWord[] = normalizeTimestamps(timestamps, fps);
  const chunks: CaptionChunk[] = buildCaptionChunks(words);

  // Find the active chunk for the current frame
  const activeChunk = chunks.find(
    (c) => frame >= c.startFrame && frame < c.endFrame
  ) ?? chunks[0];

  if (!activeChunk) return null;

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingBottom: '220px', // safe zone — above 75% of frame height
        paddingLeft: '80px',
        paddingRight: '80px',
      }}
    >
      <div
        style={{
          backgroundColor: 'rgba(0, 0, 0, 0.65)',
          borderRadius: '12px',
          padding: '16px 28px',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '10px',
          justifyContent: 'center',
          maxWidth: '920px',
        }}
      >
        {activeChunk.words.map((w, i) => {
          const isActive = frame >= w.startFrame && frame < w.endFrame;
          return (
            <span
              key={i}
              style={{
                fontFamily: 'Inter, sans-serif',
                fontWeight: 700,
                fontSize: '52px',
                color: isActive ? '#FFFFFF' : 'rgba(255,255,255,0.6)',
                lineHeight: 1.2,
                transition: 'color 0s', // instant, no lerp — hard snap
              }}
            >
              {w.word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
