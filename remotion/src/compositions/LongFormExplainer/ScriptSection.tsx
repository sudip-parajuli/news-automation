import { Series, Video, Img, useVideoConfig, AbsoluteFill } from 'remotion';
import { ScriptSectionData, BRollItem } from '../../types';
import { resolveMediaPath } from '../../utils';
import { LowerThird } from './LowerThird';
import { KenBurnsImage } from '../../components/KenBurnsImage';
import { StatCard } from './StatCard';
import { NameTag } from './NameTag';
import { KeyPoint } from './KeyPoint';
import React from 'react';

export const ScriptSection: React.FC<{
  section: ScriptSectionData;
  durationInFrames: number;
  topicType?: string;
  metadata?: any;
}> = ({ section, durationInFrames, topicType, metadata }) => {
  const { fps } = useVideoConfig();
  
  // LowerThird facts (legacy)
  const sentences = section.text.split(/[.?!]/).filter(s => s.trim().length > 0).map(s => s.trim());
  const fallbackFact = [section.id.toUpperCase()];
  const factsToDisplay = sentences.length > 0 ? sentences : fallbackFact;

  const totalClipFrames = section.broll.reduce((sum, c) => sum + Math.round(c.duration * fps), 0);

  if (totalClipFrames === 0) {
    return (
      <AbsoluteFill style={{backgroundColor: '#1a1a2e'}}>
        {topicType === 'narrative' && <LowerThird facts={factsToDisplay} durationInFrames={durationInFrames} />}
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

  // NameTag logic
  let nameTag = null;
  if (topicType === 'listicle' && section.id.startsWith("entry_")) {
    const rank = parseInt(section.id.split("_")[1]);
    const index = 10 - rank;
    if (metadata && metadata.entries && metadata.entries[index]) {
      nameTag = <NameTag name={metadata.entries[index]} rank={rank} />;
    }
  }

  // KeyPhrases logic (cycle through them if any)
  const keyPhrases = section.key_phrases || [];

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
                  volume={0}
                />
              ) : (
                <KenBurnsImage src={resolveMediaPath(clip.file_path)} />
              )}
            </Series.Sequence>
          );
        })}
      </Series>
      
      {topicType === 'narrative' && (
        <LowerThird
          facts={factsToDisplay}
          durationInFrames={durationInFrames}
        />
      )}

      {nameTag}

      {section.stat_card && (
        <StatCard label={section.stat_card.label} value={section.stat_card.value} />
      )}

      {keyPhrases.length > 0 && !section.stat_card && (
        <AbsoluteFill>
          <Series>
            {keyPhrases.map((phrase, idx) => {
              const phraseFrames = Math.floor(durationInFrames / keyPhrases.length);
              return (
                <Series.Sequence key={idx} durationInFrames={phraseFrames}>
                  <KeyPoint phrase={phrase} />
                </Series.Sequence>
              );
            })}
          </Series>
        </AbsoluteFill>
      )}
    </div>
  );
};
