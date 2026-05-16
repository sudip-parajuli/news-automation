import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring } from 'remotion';

export const HookOverlay: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({
    fps,
    frame,
    config: { damping: 14, stiffness: 200 },
    durationInFrames: 12,
    from: 0.85,
    to: 1.0,
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        alignItems: 'center',
        padding: '0 80px', // safe zone margin
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          textAlign: 'center',
          fontFamily: 'Inter, sans-serif',
          fontWeight: 900,
          fontSize: '72px',
          color: 'white',
          lineHeight: 1.15,
          textShadow: '0 4px 20px rgba(0,0,0,0.8), 0 0 60px rgba(0,0,0,0.6)',
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
