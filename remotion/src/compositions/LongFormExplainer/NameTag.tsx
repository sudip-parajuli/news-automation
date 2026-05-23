import React from 'react';
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion';

export const NameTag: React.FC<{
  name: string;
  rank?: string | number;
}> = ({ name, rank }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    fps,
    frame,
    config: { damping: 14, stiffness: 120, mass: 1 },
  });

  return (
    <AbsoluteFill style={{ justifyContent: 'flex-start', alignItems: 'flex-start', padding: '60px 40px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '12px',
          padding: '12px 24px',
          transform: `translateX(${(1 - entrance) * -100}px)`,
          opacity: entrance,
          boxShadow: '0 10px 30px rgba(0,0,0,0.5)'
        }}
      >
        {rank !== undefined && (
          <div style={{
            color: '#E84545',
            fontSize: 40,
            fontWeight: 900,
            marginRight: 16,
            fontFamily: 'sans-serif'
          }}>
            #{rank}
          </div>
        )}
        <div style={{
          color: 'white',
          fontSize: 36,
          fontWeight: 700,
          fontFamily: 'sans-serif'
        }}>
          {name}
        </div>
      </div>
    </AbsoluteFill>
  );
};
