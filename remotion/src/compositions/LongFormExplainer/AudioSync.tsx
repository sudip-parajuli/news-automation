import { Audio } from 'remotion';
import { resolveMediaPath } from '../../utils';

export const AudioSync: React.FC<{
  voiceoverFile: string;
  backgroundMusic: string;
}> = ({ voiceoverFile, backgroundMusic }) => {
  return (
    <>
      {voiceoverFile && <Audio src={resolveMediaPath(voiceoverFile)} volume={1.0} />}
      {backgroundMusic && <Audio src={resolveMediaPath(backgroundMusic)} volume={0.12} />}
    </>
  );
};
