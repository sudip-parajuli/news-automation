import React from 'react';
import { AbsoluteFill, Img, Video } from 'remotion';
import { resolveMediaPath } from '../../utils';

export const LoopHook: React.FC<{
  firstFrame: string;
  loopText: string;
}> = ({ firstFrame, loopText }) => {
  const isImage = firstFrame && firstFrame.match(/\.(jpg|jpeg|png|webp)$/i);
  return (
    <AbsoluteFill>
      {firstFrame ? (
        isImage ? (
          <Img
            src={resolveMediaPath(firstFrame)}
            style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'brightness(0.5)' }}
          />
        ) : (
          <Video
            src={resolveMediaPath(firstFrame)}
            style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'brightness(0.5)' }}
          />
        )
      ) : (
        <AbsoluteFill style={{ backgroundColor: '#0d0d1a' }} />
      )}
      <AbsoluteFill
        style={{
          justifyContent: 'center',
          alignItems: 'center',
          padding: '0 80px',
        }}
      >
        <div
          style={{
            fontFamily: 'Inter, sans-serif',
            fontWeight: 900,
            fontSize: '64px',
            color: 'white',
            textAlign: 'center',
            textShadow: '0 4px 20px rgba(0,0,0,0.9)',
          }}
        >
          {loopText}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
