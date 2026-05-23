import React from 'react';
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from 'remotion';

export const StatCard: React.FC<{
  label: string;
  value: string;
}> = ({ label, value }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    fps,
    frame,
    config: { damping: 14, stiffness: 120, mass: 1 },
  });

  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div
        style={{
          width: 'calc(100% - 40px)',
          padding: '16px 20px',
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '16px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          transform: `scale(${entrance})`,
          opacity: entrance,
        }}
      >
        <span style={{ color: '#E84545', fontSize: 32, fontWeight: 700, fontFamily: 'sans-serif', textTransform: 'uppercase', letterSpacing: 1.5 }}>
          {label}
        </span>
        <span style={{ color: 'white', fontSize: 80, fontWeight: 900, fontFamily: 'sans-serif', lineHeight: 1.1, marginTop: 8 }}>
          {value}
        </span>
      </div>
    </AbsoluteFill>
  );
};
