import React from 'react';
import { AbsoluteFill, Series, useVideoConfig } from 'remotion';
import { LongFormVideoData } from '../../types';
import { AudioSync } from './AudioSync';
import { ProgressBar } from './ProgressBar';
import { ScriptSection } from './ScriptSection';
import { ChapterCard } from './ChapterCard';

export const LongFormExplainer: React.FC<{ data: LongFormVideoData }> = ({ data }) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      <AudioSync voiceoverFile={data.voiceover_file} backgroundMusic={data.background_music} />
      
      <Series>
        {data.sections.map((section, index) => {
          // Calculate section duration based on its broll clips
          const sectionDurationSeconds = section.broll.reduce((acc, clip) => acc + clip.duration, 0);
          const sectionFrames = Math.max(1, Math.round(sectionDurationSeconds * fps));
          
          // Used between CONTEXT -> CONFLICT -> EVIDENCE -> TWIST only.
          const showChapterCard = ['conflict', 'evidence', 'twist'].includes(section.id.toLowerCase());
          
          return (
            <React.Fragment key={section.id}>
              {showChapterCard && (
                <Series.Sequence durationInFrames={15}>
                  <ChapterCard title={section.id} number={index} />
                </Series.Sequence>
              )}
              <Series.Sequence durationInFrames={sectionFrames}>
                <ScriptSection section={section} durationInFrames={sectionFrames} />
              </Series.Sequence>
            </React.Fragment>
          );
        })}
      </Series>

      <ProgressBar />
    </AbsoluteFill>
  );
};
