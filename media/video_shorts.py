from moviepy.editor import TextClip, ColorClip, CompositeVideoClip, AudioFileClip, ImageClip, afx, concatenate_videoclips
import os
import random
import glob
from moviepy.audio.AudioClip import CompositeAudioClip

class VideoShortsGenerator:
    def __init__(self, size=(1080, 1920)):
        self.size = size

    def create_shorts(self, text: str, audio_path: str, output_path: str, word_offsets: list = None, image_paths: list = None):
        """
        Creates a vertical YouTube Shorts video with word-by-word karaoke highlighting and rotating backgrounds.
        """
        audio = AudioFileClip(audio_path)
        duration = audio.duration

        # 1. Background Logic (Rotating images)
        bg_clips = []
        if image_paths and len(image_paths) > 0:
            section_dur = duration / len(image_paths)
            for i, img_path in enumerate(image_paths):
                if os.path.exists(img_path):
                    try:
                        img_clip = ImageClip(img_path).set_duration(section_dur).set_start(i * section_dur)
                        
                        # Resize and crop to fill vertical screen
                        w, h = img_clip.size
                        target_ratio = self.size[0]/self.size[1]
                        if w/h > target_ratio:
                            img_clip = img_clip.resize(height=self.size[1])
                        else:
                            img_clip = img_clip.resize(width=self.size[0])
                        
                        img_clip = img_clip.set_position('center')
                        
                        # Enhanced Ken Burns Effect
                        zoom_dir = random.choice([1, -1])
                        start_scale = 1.0 if zoom_dir == 1 else 1.1
                        end_scale = 1.1 if zoom_dir == 1 else 1.0
                        img_clip = img_clip.resize(lambda t: start_scale + (end_scale - start_scale) * (t % section_dur)/section_dur)
                        
                        # Transition
                        img_clip = img_clip.crossfadein(0.5)
                        
                        bg_clips.append(img_clip)
                    except Exception as e:
                        print(f"Error processing image {img_path}: {e}")

        if not bg_clips:
            bg_clips.append(ColorClip(size=self.size, color=(15, 15, 35), duration=duration))

        # Add a subtle dark gradient at the bottom for text readability
        try:
            # Create a semi-transparent black overlay for the bottom third
            overlay = ColorClip(size=(self.size[0], 600), color=(0,0,0)).set_opacity(0.4).set_duration(duration).set_position(('center', 1350))
            bg_clips.append(overlay)
        except:
            pass

        clips = bg_clips

        # 2. Modern Karaoke Logic
        if word_offsets:
            print(f"Rendering {len(word_offsets)} points with Karaoke Sync...")
            try:
                caption_clips = self._create_karaoke_caption(word_offsets)
                clips.extend(caption_clips)
            except Exception as e:
                print(f"Caption engine error: {e}")
                # Fallback to block captions
                txt = TextClip(self._wrap_text(text, 15), fontsize=80, color='white', bg_color='black', method='caption', size=(self.size[0]-80, None)).set_duration(duration).set_position('center')
                clips.append(txt)
        else:
            print("WARNING: Falling back to block captions.")
            txt = TextClip(self._wrap_text(text, 15), fontsize=80, color='white', bg_color='black', method='caption', size=(self.size[0]-80, None)).set_duration(duration).set_position('center')
            clips.append(txt)

        # 3. Audio Mixing
        # Detection: Check multiple possible locations for music
        possible_music_paths = [
            "music",
            os.path.join(os.getcwd(), "music"),
            "international_news_automation/music",
            os.path.join(os.getcwd(), "..", "music")
        ]
        
        music_dir = None
        for p in possible_music_paths:
            if os.path.exists(p) and glob.glob(os.path.join(p, "*.*")):
                music_dir = p
                break
            
        music_files = []
        if music_dir:
            music_files = glob.glob(os.path.join(music_dir, "*.mp3")) + glob.glob(os.path.join(music_dir, "*.wav"))
        
        if music_files:
            try:
                bg_music_path = random.choice(music_files)
                print(f"Mixing music: {bg_music_path}")
                bg_music = AudioFileClip(bg_music_path).volumex(0.12)
                if bg_music.duration < duration:
                    bg_music = bg_music.fx(afx.audio_loop, duration=duration)
                else:
                    bg_music = bg_music.set_duration(duration)
                final_audio = CompositeAudioClip([audio.volumex(1.1), bg_music])
            except Exception as e:
                print(f"Music mix failed: {e}")
                final_audio = audio
        else:
            print(f"CRITICAL: No background music files found in any of {possible_music_paths}")
            final_audio = audio

        final_video = CompositeVideoClip(clips, size=self.size)
        final_video = final_video.set_audio(final_audio)
        
        print(f"Writing enhanced video to {output_path}...")
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", threads=4, preset='ultrafast', logger=None)

    def _wrap_text(self, text: str, width: int) -> str:
        words = text.split()
        lines = []
        current_line = []
        for word in words:
            if len(" ".join(current_line + [word])) <= width:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        lines.append(" ".join(current_line))
        return "\n".join(lines)

    def _create_karaoke_caption(self, word_offsets: list):
        """
        Creates a list of TextClips for karaoke effect with word-level highlighting (yellow background).
        """
        clips = []
        PHRASE_SIZE = 4
        FONT_SIZE = 80
        TEXT_Y = 1450
        
        for i in range(0, len(word_offsets), PHRASE_SIZE):
            phrase_chunk = word_offsets[i : i + PHRASE_SIZE]
            if not phrase_chunk: continue
            
            p_start = phrase_chunk[0]['start']
            p_end = phrase_chunk[-1]['start'] + phrase_chunk[-1]['duration']
            
            # Phrase container
            phrase_text = " ".join([w['word'].upper() for w in phrase_chunk])
            
            try:
                # 1. Base Phrase (White text)
                base_txt = TextClip(
                    phrase_text,
                    fontsize=FONT_SIZE,
                    color='white',
                    font='DejaVu-Sans-Bold' if os.name != 'nt' else 'Arial-Bold',
                    method='label'
                ).set_start(p_start).set_duration(p_end - p_start).set_position(('center', TEXT_Y))
                clips.append(base_txt)
                
                # 2. Individual Word Highlighting (Yellow background)
                for word_info in phrase_chunk:
                    w_text = word_info['word'].upper()
                    w_start = word_info['start']
                    w_dur = word_info['duration']
                    
                    highlight = TextClip(
                        w_text,
                        fontsize=FONT_SIZE + 10,
                        color='black',
                        bg_color='yellow',
                        font='DejaVu-Sans-Bold' if os.name != 'nt' else 'Arial-Bold',
                        method='label'
                    ).set_start(w_start).set_duration(w_dur).set_position(('center', TEXT_Y))
                    
                    clips.append(highlight)
            except Exception as e:
                print(f"Error in _create_karaoke_caption (Shorts): {e}")
                
        return clips

if __name__ == "__main__":
    pass
    # Test generation (Requires ImageMagick configured for MoviePy)
    # vgen = VideoShortsGenerator()
    # vgen.create_shorts("BREAKING NEWS: A major international event is unfolding right now. More updates to follow.", "test_narration.mp3", "test_video.mp4")
