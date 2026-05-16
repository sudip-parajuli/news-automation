import { Series, Video, Img, useVideoConfig, useCurrentFrame } from 'remotion';
import { ScriptSectionData } from '../../types';
import { resolveMediaPath } from '../../utils';
import { LowerThird } from './LowerThird';
import { KenBurnsImage } from '../../components/KenBurnsImage';

export const ScriptSection: React.FC<{
  section: ScriptSectionData;
  durationInFrames: number;
}> = ({ section, durationInFrames }) => {
  const { fps } = useVideoConfig();
  
  // Extract a 1-line key fact from the script text for the lower third
  const sentences = section.text.split(/[.?!]/).filter(s => s.trim().length > 0);
  const keyFact = sentences.length > 0 ? sentences[0].trim() : section.id.toUpperCase();

  return (
    <div style={{ flex: 1, backgroundColor: 'black' }}>
      <Series>
        {section.broll.map((clip, index) => {
          const clipFrames = Math.round(clip.duration * fps);
          return (
            <Series.Sequence key={index} durationInFrames={clipFrames}>
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
        mainText={keyFact.length > 80 ? keyFact.substring(0, 80) + '...' : keyFact}
        durationInFrames={durationInFrames}
      />
    </div>
  );
};
