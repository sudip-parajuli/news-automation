import React from 'react';
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion';

export const KeyPoint: React.FC<{
  phrase: string;
}> = ({ phrase }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    fps,
    frame,
    config: { damping: 14, stiffness: 120, mass: 1 },
  });

  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: '160px' }}>
      <div
        style={{
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '12px',
          padding: '16px 32px',
          transform: `translateY(${(1 - entrance) * 50}px) scale(${entrance})`,
          opacity: entrance,
          maxWidth: '80%',
          textAlign: 'center',
          boxShadow: '0 10px 30px rgba(0,0,0,0.5)'
        }}
      >
        <span style={{
          color: 'white',
          fontSize: 32,
          fontWeight: 700,
          fontFamily: 'sans-serif'
        }}>
          {phrase}
        </span>
      </div>
    </AbsoluteFill>
  );
};
