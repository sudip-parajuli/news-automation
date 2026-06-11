import { useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';

export const LowerThird: React.FC<{
  facts: string[];
  durationInFrames: number;
}> = ({ facts, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const totalFacts = facts.length;
  const framesPerFact = totalFacts > 0 ? Math.floor(durationInFrames / totalFacts) : durationInFrames;
  let currentFactIndex = Math.floor(frame / framesPerFact);
  
  if (currentFactIndex >= totalFacts) {
    currentFactIndex = currentFactIndex % totalFacts;
  }
  
  let currentFact = facts[currentFactIndex] || "";

  const slideIn = spring({
    fps,
    frame: Math.max(0, frame - currentFactIndex * framesPerFact),
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
        right: '80px',
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        padding: '24px 40px',
        borderRadius: '8px',
        fontFamily: 'Inter, sans-serif',
        color: 'white',
        transform: `translateX(${(1 - slideIn) * -100}%)`,
        opacity: fadeOut,
        maxWidth: 'calc(100% - 160px)',
        wordBreak: 'break-word',
        overflowWrap: 'break-word',
      }}
    >
      <div style={{ fontSize: '28px', fontWeight: 'bold', lineHeight: 1.4 }}>{currentFact}</div>
    </div>
  );
};
