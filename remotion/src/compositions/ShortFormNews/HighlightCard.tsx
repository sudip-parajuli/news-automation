import React from 'react';
import { useCurrentFrame, useVideoConfig, spring, interpolate, AbsoluteFill } from 'remotion';
import { HighlightCardData } from '../../types';

export const HighlightCard: React.FC<{ card?: HighlightCardData }> = ({ card }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!card) return null;

  const startFrame = Math.round(card.startTime * fps);
  const endFrame = Math.round(card.endTime * fps);

  // Only render during the specified active window
  if (frame < startFrame || frame > endFrame) {
    return null;
  }

  const duration = endFrame - startFrame;
  const relativeFrame = frame - startFrame;

  // Elastic pop-in transition using spring
  const scale = spring({
    fps,
    frame: relativeFrame,
    config: { damping: 12, stiffness: 120 },
    durationInFrames: 15,
    from: 0.75,
    to: 1.0,
  });

  // Fade-in/out transition
  const opacity = interpolate(
    relativeFrame,
    [0, 10, duration - 10, duration],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  // Subtle floating offset
  const floatOffset = Math.sin(relativeFrame / 10) * 4;

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        alignItems: 'center',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '40px',
          right: '40px',
          transform: `translateY(-50%) scale(${scale}) translateY(${floatOffset}px)`,
          opacity,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          backdropFilter: 'blur(12px)',
          borderRadius: '16px',
          padding: '16px 20px',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.4)',
          textAlign: 'center',
        }}
      >
        <span
          style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '18px',
            fontWeight: 800,
            color: '#E84545', // channel red
            letterSpacing: '2px',
            textTransform: 'uppercase',
            marginBottom: '6px',
          }}
        >
          {card.label}
        </span>
        <span
          style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '60px',
            fontWeight: 900,
            color: '#FFFFFF', // white value text
            lineHeight: 1.1,
            margin: '6px 0',
          }}
        >
          {card.value}
        </span>
        <span
          style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: '20px',
            fontWeight: 500,
            color: 'rgba(255, 255, 255, 0.85)',
            lineHeight: 1.3,
            marginTop: '2px',
          }}
        >
          {card.description}
        </span>
      </div>
    </AbsoluteFill>
  );
};
