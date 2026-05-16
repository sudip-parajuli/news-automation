import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate } from 'remotion';

export const CTACard: React.FC = () => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 10], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingBottom: '300px', // Adjusted for safe zone (above channel name/Subscribe button)
        opacity,
      }}
    >
      <div
        style={{
          backgroundColor: 'rgba(232, 69, 69, 0.95)',
          borderRadius: '16px',
          padding: '20px 40px',
          fontFamily: 'Inter, sans-serif',
          color: 'white',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: '36px', fontWeight: 900 }}>Full story on the channel ↑</div>
        <div style={{ fontSize: '24px', marginTop: '8px', fontWeight: 400, opacity: 0.85 }}>
          Subscribe for the full explainer
        </div>
      </div>
    </AbsoluteFill>
  );
};
