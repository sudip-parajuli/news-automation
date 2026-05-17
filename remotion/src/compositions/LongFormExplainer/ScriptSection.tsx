import { Series, Video, Img, useVideoConfig, AbsoluteFill } from 'remotion';
import { ScriptSectionData, BRollItem } from '../../types';
import { resolveMediaPath } from '../../utils';
import { LowerThird } from './LowerThird';
import { KenBurnsImage } from '../../components/KenBurnsImage';

export const ScriptSection: React.FC<{
  section: ScriptSectionData;
  durationInFrames: number;
}> = ({ section, durationInFrames }) => {
  const { fps } = useVideoConfig();
  
  // Extract key facts from the script text for the lower third
  const sentences = section.text.split(/[.?!]/).filter(s => s.trim().length > 0).map(s => s.trim());
  const fallbackFact = [section.id.toUpperCase()];
  const factsToDisplay = sentences.length > 0 ? sentences : fallbackFact;

  const totalClipFrames = section.broll.reduce((sum, c) => sum + Math.round(c.duration * fps), 0);

  if (totalClipFrames === 0) {
    return (
      <AbsoluteFill style={{backgroundColor: '#1a1a2e'}}>
        <LowerThird facts={factsToDisplay} durationInFrames={durationInFrames} />
      </AbsoluteFill>
    );
  }

  const loopCount = Math.ceil(durationInFrames / totalClipFrames);
  const loopedClips: BRollItem[] = Array.from({length: loopCount}, () => section.broll).flat();

  let framesUsed = 0;
  const clipsToRender = loopedClips.map((clip) => {
    const clipFrames = Math.round(clip.duration * fps);
    const remaining = durationInFrames - framesUsed;
    const actualFrames = Math.min(clipFrames, remaining);
    framesUsed += actualFrames;
    return { ...clip, actualFrames };
  }).filter(c => c.actualFrames > 0);

  return (
    <div style={{ flex: 1, backgroundColor: 'black' }}>
      <Series>
        {clipsToRender.map((clip, index) => {
          return (
            <Series.Sequence key={index} durationInFrames={clip.actualFrames}>
              {clip.type === 'video' ? (
                <Video
                  src={resolveMediaPath(clip.file_path)}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <KenBurnsImage src={resolveMediaPath(clip.file_path)} />
              )}
            </Series.Sequence>
          );
        })}
      </Series>
      
      <LowerThird
        facts={factsToDisplay}
        durationInFrames={durationInFrames}
      />
    </div>
  );
};
