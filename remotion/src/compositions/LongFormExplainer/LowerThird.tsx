import { useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';

export const LowerThird: React.FC<{
  facts: string[];
  durationInFrames: number;
}> = ({ facts, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Determine which fact to show based on 8-second rotation
  const framesPerFact = 8 * fps;
  let currentFactIndex = Math.floor(frame / framesPerFact);
  
  // Cap the index so we don't go out of bounds if the section is very long
  if (currentFactIndex >= facts.length) {
    currentFactIndex = currentFactIndex % facts.length;
  }
  
  let currentFact = facts[currentFactIndex] || "";
  // Truncate if too long to fit nicely
  if (currentFact.length > 100) {
    currentFact = currentFact.substring(0, 100) + '...';
  }

  // Animate slide-in at the very beginning of the section
  const slideIn = spring({
    fps,
    frame,
    config: { damping: 14 },
    durationInFrames: 20,
  });

  // Fade out only at the very end of the section
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
      <div style={{ fontSize: '28px', fontWeight: 'bold' }}>{currentFact}</div>
    </div>
  );
};
