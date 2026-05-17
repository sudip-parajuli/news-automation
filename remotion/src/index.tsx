import { registerRoot, AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { Composition } from 'remotion';
import { LongFormExplainer } from './compositions/LongFormExplainer/LongFormExplainer';
import { ShortFormNews } from './compositions/ShortFormNews/ShortFormNews';
import { LongFormVideoData, ShortFormVideoData } from './types';
import { ProgressBar } from './compositions/LongFormExplainer/ProgressBar';

const publicDir = "C:/Users/Acer/Desktop/newstrendingtoday/news-automation/remotion/public";

const longFormStub: LongFormVideoData = {
  title: "Test Explainer",
  voiceover_file: `${publicDir}/voiceover.mp3`,
  background_music: `${publicDir}/bgm.mp3`,
  voiceover_duration_seconds: 10,
  sections: [
    {
      id: "HOOK",
      text: "The world runs on oil.",
      word_count: 5,
      broll: [
        { query: "oil pump", file_path: `${publicDir}/hook.mp4`, type: "video", duration: 5 }
      ]
    },
    {
      id: "CONTEXT",
      text: "OPEC met in Vienna.",
      word_count: 4,
      broll: [
        { query: "vienna", file_path: `${publicDir}/context.jpg`, type: "still_image", duration: 5 }
      ]
    }
  ]
};

const shortFormStub: ShortFormVideoData = {
  headline: "Oil prices spiking globally",
  body_text: "OPEC made a decision that affects everyone. Here is what you need to know.",
  clips: [
    { file: `${publicDir}/hook.mp4`, duration: 5 },
  ],
  caption_lines: ["OPEC just made a decision that will affect you."],
  voiceover_file: `${publicDir}/voiceover.mp3`,
  hook_text: "Oil prices just spiked. Here's why.",
  loop_hook: "You need to see this.",
  audio_track: `${publicDir}/bgm.mp3`,
};

const TestShortComp: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: 'white', justifyContent: 'center', alignItems: 'center' }}>
      <h1 style={{ fontSize: 80, fontFamily: 'sans-serif', color: 'black' }}>Test Render</h1>
      <ProgressBar />
    </AbsoluteFill>
  );
};

export const RemotionRoot = () => {
	return (
		<>
			<Composition
				id="TestShort"
				component={TestShortComp}
				durationInFrames={90}
				fps={30}
				width={1920}
				height={1080}
			/>
			<Composition
				id="LongFormExplainer"
				component={LongFormExplainer}
				durationInFrames={300}
				fps={30}
				width={1920}
				height={1080}
				defaultProps={{ data: longFormStub }}
				calculateMetadata={({ props }) => {
					return {
						durationInFrames: Math.max(1, Math.ceil((props.data.voiceover_duration_seconds || 10) * 30))
					};
				}}
			/>
			<Composition
				id="ShortFormNews"
				component={ShortFormNews}
				durationInFrames={300}
				fps={30}
				width={1080}
				height={1920}
				defaultProps={{ data: shortFormStub }}
			/>
		</>
	);
};

registerRoot(RemotionRoot);
