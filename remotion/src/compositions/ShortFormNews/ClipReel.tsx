import React from 'react';
import { Series, Video, Img, useVideoConfig } from 'remotion';
import { resolveMediaPath } from '../../utils';

type Clip = { file: string; duration: number };

export const ClipReel: React.FC<{ clips: Clip[] }> = ({ clips }) => {
  const { fps } = useVideoConfig();
  const MAX_CLIP_FRAMES = fps * 2; // hard 2-second cap per clip

  return (
    <Series>
      {clips.map((clip, i) => {
        const clipFrames = Math.min(Math.round(clip.duration * fps), MAX_CLIP_FRAMES);
        const isImage = clip.file.match(/\.(jpg|jpeg|png|webp)$/i);
        return (
          <Series.Sequence key={i} durationInFrames={clipFrames}>
            {isImage ? (
              <Img
                src={resolveMediaPath(clip.file)}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <Video
                src={resolveMediaPath(clip.file)}
                endAt={MAX_CLIP_FRAMES}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            )}
          </Series.Sequence>
        );
      })}
    </Series>
  );
};
