import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring } from 'remotion';

export const ChapterCard: React.FC<{
  title: string;
  number: number;
}> = ({ title, number }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = spring({
    fps,
    frame,
    config: { damping: 12 },
  });

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
