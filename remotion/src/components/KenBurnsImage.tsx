import React from 'react';
import { Img, useCurrentFrame } from 'remotion';

export const KenBurnsImage: React.FC<{ src: string }> = ({ src }) => {
  const frame = useCurrentFrame();
  
  // Approximate the FFmpeg zoompan=z='min(zoom+0.0015,1.5)' filter
  const zoom = Math.min(1 + frame * 0.0015, 1.5);
  
  return (
    <Img
      src={src}
      style={{
        width: '100%',
        height: '100%',
        objectFit: 'cover',
        transform: `scale(${zoom})`,
        transformOrigin: 'center center',
      }}
    />
  );
};
