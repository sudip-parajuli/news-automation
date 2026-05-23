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

  const sortedSections = [...data.sections].sort((a, b) => {
    const getOrder = (id: string) => id.startsWith("entry_")
      ? 100 - parseInt(id.split("_")[1])  // entry_10=90, entry_1=99
      : id === "hook" ? 0 : id === "cta" ? 200 : 50;
    return getOrder(a.id) - getOrder(b.id);
  });

  // Build entry name lookup from metadata for listicle chapter cards
  const entries: string[] = data.metadata?.entries ?? [];

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      <AudioSync voiceoverFile={data.voiceover_file} backgroundMusic={data.background_music} />
      
      <Series>
        {sortedSections.map((section, index) => {
          // Calculate section duration based on proportional word count
          const safeWordCount = Math.max(section.word_count, 10);
          const sectionFrames = Math.max(1, Math.ceil((safeWordCount / totalWordCount) * totalVoiceoverFrames));
          
          // Show chapter card between sections (narrative: CONFLICT/EVIDENCE/TWIST, listicle: all entries)
          const showChapterCard = ['conflict', 'evidence', 'twist'].includes(section.id.toLowerCase()) || section.id.startsWith("entry_");

          // Compute human-readable title for the chapter card
          let chapterTitle = section.id.replace(/_/g, ' ').toUpperCase();
          let chapterRank: number | undefined = undefined;
          if (section.id.startsWith("entry_")) {
            const rank = parseInt(section.id.split("_")[1]);
            chapterRank = rank;
            // entries array is ordered countdown: index 0 = entry_10, index 9 = entry_1
            const entryIndex = 10 - rank;
            const entryName = entries[entryIndex] ?? '';
            chapterTitle = entryName ? entryName : `#${rank}`;
          }
          
          return (
            <React.Fragment key={section.id}>
              {showChapterCard && (
                <Series.Sequence durationInFrames={15}>
                  <ChapterCard title={chapterTitle} number={index} rank={chapterRank} />
                </Series.Sequence>
              )}
              <Series.Sequence durationInFrames={sectionFrames}>
                <ScriptSection section={section} durationInFrames={sectionFrames} topicType={data.topic_type} metadata={data.metadata} />
              </Series.Sequence>
            </React.Fragment>
          );
        })}
      </Series>

      <ProgressBar />
    </AbsoluteFill>
  );
};
