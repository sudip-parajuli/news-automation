import React from 'react';
import { AbsoluteFill, Series, useVideoConfig } from 'remotion';
import { LongFormVideoData } from '../../types';
import { AudioSync } from './AudioSync';
import { ProgressBar } from './ProgressBar';
import { ScriptSection } from './ScriptSection';
import { ChapterCard } from './ChapterCard';

export const LongFormExplainer: React.FC<{ data: LongFormVideoData }> = ({ data }) => {
  const { fps } = useVideoConfig();

  const totalVoiceoverFrames = Math.ceil(data.voiceover_duration_seconds * fps);
  
  // Calculate total word count safely
  const totalWordCount = data.sections.reduce((acc, section) => {
    return acc + Math.max(section.word_count, 10);
  }, 0);

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      <AudioSync voiceoverFile={data.voiceover_file} backgroundMusic={data.background_music} />
      
      <Series>
        {data.sections.map((section, index) => {
          // Calculate section duration based on proportional word count
          const safeWordCount = Math.max(section.word_count, 10);
          const sectionFrames = Math.max(1, Math.ceil((safeWordCount / totalWordCount) * totalVoiceoverFrames));
          
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
