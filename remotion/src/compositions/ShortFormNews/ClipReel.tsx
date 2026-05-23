import React from 'react';
import { Series, Video, Img, useVideoConfig, useCurrentFrame, interpolate, spring, AbsoluteFill } from 'remotion';
import { resolveMediaPath } from '../../utils';

type Clip = {
  file: string;
  duration: number;
  type?: "video" | "still_image";
  label?: string;
};

const ClipReelItem: React.FC<{ clip: Clip; durationFrames: number }> = ({ clip, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Ken Burns zoom ONLY for still_image type
  const isStillImage = clip.type === 'still_image' || !!clip.file.match(/\.(jpg|jpeg|png|webp)$/i);
  
  const scale = isStillImage
    ? interpolate(frame, [0, durationFrames], [1.05, 1.18], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    : 1.0;

  // Corner tag slide-in from right over 12 frames
  const tagSlide = spring({
    fps,
    frame,
    config: { damping: 14, stiffness: 150 },
    durationInFrames: 12,
    from: 80,
    to: 0,
  });

  const tagOpacity = interpolate(
    frame,
    [0, 8, durationFrames - 10, durationFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  const displayLabel = clip.label || '';

  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      {/* Zoomed clip container */}
      <div style={{ width: '100%', height: '100%', transform: `scale(${scale})` }}>
        {isStillImage ? (
          <Img
            src={resolveMediaPath(clip.file)}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <Video
            src={resolveMediaPath(clip.file)}
            endAt={durationFrames}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        )}
      </div>

      {/* Floating glassmorphic corner tag/label */}
      {displayLabel && (
        <div
          style={{
            position: 'absolute',
            top: '80px',
            right: '50px',
            transform: `translateX(${tagSlide}px)`,
            opacity: tagOpacity,
            backgroundColor: 'rgba(0, 0, 0, 0.45)',
            backdropFilter: 'blur(12px)',
            borderRadius: '20px',
            padding: '8px 18px',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            display: 'flex',
            alignItems: 'center',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          }}
        >
          {/* Clean red dot div */}
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: '#E84545',
              marginRight: 6,
            }}
          />
          <span
            style={{
              fontFamily: 'Inter, sans-serif',
              fontWeight: 800,
              fontSize: '18px',
              color: 'white',
              letterSpacing: '1px',
              textTransform: 'uppercase',
            }}
          >
            {displayLabel}
          </span>
        </div>
      )}
    </AbsoluteFill>
  );
};

export const ClipReel: React.FC<{ clips: Clip[] }> = ({ clips }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const MAX_CLIP_FRAMES = fps * 2; // hard 2-second cap per clip

  if (!clips || clips.length === 0) {
    return null;
  }

  // Loop clips to fill durationInFrames exactly
  const reelClips: { clip: Clip; durationFrames: number }[] = [];
  let accumulatedFrames = 0;
  let clipIndex = 0;

  while (accumulatedFrames < durationInFrames) {
    const clip = clips[clipIndex % clips.length];
    const clipFrames = Math.min(Math.round(clip.duration * fps), MAX_CLIP_FRAMES);

    const remainingFrames = durationInFrames - accumulatedFrames;
    const durationForReel = Math.min(clipFrames, remainingFrames);

    reelClips.push({ clip, durationFrames: durationForReel });
    accumulatedFrames += durationForReel;
    clipIndex++;
  }

  return (
    <Series>
      {reelClips.map((item, i) => (
        <Series.Sequence key={i} durationInFrames={item.durationFrames}>
          <ClipReelItem clip={item.clip} durationFrames={item.durationFrames} />
        </Series.Sequence>
      ))}
    </Series>
  );
};
