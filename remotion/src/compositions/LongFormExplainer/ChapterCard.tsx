import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring } from 'remotion';

export const ChapterCard: React.FC<{
  title: string;
  number: number;
  rank?: number; // present for listicle entry sections
}> = ({ title, number, rank }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    fps,
    frame,
    config: { damping: 12 },
  });

  const isListicle = rank !== undefined;

  if (isListicle) {
    return (
      <AbsoluteFill
        style={{
          background: 'linear-gradient(135deg, #0f0c29, #302b63, #24243e)',
          justifyContent: 'center',
          alignItems: 'center',
          flexDirection: 'column',
          fontFamily: 'Inter, sans-serif',
          opacity: entrance,
          transform: `scale(${0.92 + entrance * 0.08})`,
        }}
      >
        {/* Big rank number */}
        <div style={{
          fontSize: '180px',
          fontWeight: 900,
          color: 'transparent',
          WebkitTextStroke: '3px rgba(255,255,255,0.15)',
          lineHeight: 1,
          position: 'absolute',
          userSelect: 'none',
        }}>
          {rank}
        </div>

        {/* Rank badge */}
        <div style={{
          background: 'rgba(232, 69, 69, 0.9)',
          borderRadius: '50px',
          padding: '10px 32px',
          marginBottom: '20px',
          zIndex: 2,
        }}>
          <span style={{ fontSize: '28px', fontWeight: 800, color: 'white', letterSpacing: '2px' }}>
            #{rank}
          </span>
        </div>

        {/* Entry name */}
        <h1 style={{
          fontSize: '56px',
          fontWeight: 700,
          color: 'white',
          margin: 0,
          textAlign: 'center',
          maxWidth: '80%',
          zIndex: 2,
          textShadow: '0 2px 20px rgba(0,0,0,0.5)',
        }}>
          {title}
        </h1>
      </AbsoluteFill>
    );
  }

  // Narrative chapter card (original style)
  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#111',
        justifyContent: 'center',
        alignItems: 'center',
        color: 'white',
        fontFamily: 'Inter, sans-serif',
        opacity: entrance,
        transform: `scale(${0.9 + entrance * 0.1})`,
      }}
    >
      <h2 style={{ fontSize: '40px', margin: 0, color: '#888' }}>PART {number}</h2>
      <h1 style={{ fontSize: '80px', margin: '20px 0', textAlign: 'center', maxWidth: '80%' }}>
        {title.toUpperCase()}
      </h1>
    </AbsoluteFill>
  );
};
