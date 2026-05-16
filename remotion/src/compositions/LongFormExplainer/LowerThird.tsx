import { useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';

export const LowerThird: React.FC<{
  mainText: string;
  subText?: string;
  durationInFrames: number;
}> = ({ mainText, subText, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const slideIn = spring({
    fps,
    frame,
    config: { damping: 14 },
    durationInFrames: 20,
  });

  const fadeOut = interpolate(
    frame,
    [durationInFrames - 20, durationInFrames],
    [1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '80px',
        left: '80px',
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        padding: '20px 40px',
        borderRadius: '8px',
        fontFamily: 'Inter, sans-serif',
        color: 'white',
        transform: `translateX(${(1 - slideIn) * -100}%)`,
        opacity: fadeOut,
        maxWidth: '70%',
      }}
    >
      <div style={{ fontSize: '28px', fontWeight: 'bold' }}>{mainText}</div>
      {subText && <div style={{ fontSize: '20px', marginTop: '8px', color: '#ccc' }}>{subText}</div>}
    </div>
  );
};
