from moviepy.editor import TextClip, ColorClip, CompositeVideoClip, AudioFileClip, ImageClip, concatenate_videoclips, afx
import os
import random
import glob
from moviepy.audio.AudioClip import CompositeAudioClip

class VideoLongGenerator:
    def __init__(self, size=(1920, 1080)):
        self.size = size

    def create_daily_summary(self, sections: list, audio_path: str, output_path: str, word_offsets: list = None):
        """
        Creates a long-form video for daily summaries with dynamic backgrounds.
        """
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration
        section_duration = total_duration / len(sections) if sections else 0
        
        for i, section in enumerate(sections):
            # Background Logic
            if section.get('image_path') and os.path.exists(section['image_path']):
                bg = ImageClip(section['image_path']).set_duration(section_duration)
                # Resize and crop to fill 16:9 screen
                w, h = bg.size
                aspect_ratio = w/h
                target_ratio = self.size[0]/self.size[1]
                
                if aspect_ratio > target_ratio:
                    bg = bg.resize(height=self.size[1])
                else:
                    bg = bg.resize(width=self.size[0])
                
                bg = bg.set_position('center')
                # Enhanced Ken Burns Effect
                zoom_dir = random.choice([1, -1])
                start_scale = 1.0 if zoom_dir == 1 else 1.1
                end_scale = 1.1 if zoom_dir == 1 else 1.0
                bg = bg.resize(lambda t: start_scale + (end_scale - start_scale) * t/section_duration)
            else:
                bg = ColorClip(size=self.size, color=(20, 20, 60), duration=section_duration)
            
            # Transition
            bg = bg.crossfadein(0.5)

            # Caption Logic
            if word_offsets:
                # Filter offsets that belong to this section's time range
                section_start = i * section_duration
                section_end = (i + 1) * section_duration
                relevant_offsets = [
                    {**w, 'start': w['start'] - section_start} 
                    for w in word_offsets 
                    if section_start <= w['start'] < section_end
                ]
                
                if relevant_offsets:
                    try:
                        caption_clips = self._create_karaoke_caption(relevant_offsets, duration=section_duration)
                        clips.append(CompositeVideoClip([bg] + caption_clips, size=self.size))
                    except Exception as e:
                        print(f"Error creating karaoke caption: {e}")
                        clips.append(bg)
                else:
                    clips.append(bg)
            else:
                try:
                    # Fallback to static block captions
                    txt = TextClip(
                        section['text'], 
                        fontsize=50, 
                        color='white', 
                        font='DejaVu-Sans-Bold' if os.name != 'nt' else 'Arial-Bold', 
                        method='caption', 
                        size=(self.size[0]-200, None),
                        bg_color='black',
                        align='Center'
                    ).set_duration(section_duration).set_position(('center', 850))
                    clips.append(CompositeVideoClip([bg, txt], size=self.size))
                except:
                    clips.append(bg)

        if not clips: return

        final_video = concatenate_videoclips(clips, method="compose")
        
        # Audio Mixing (Randomized from music/ folder)
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
                print(f"Mixing music (long video): {bg_music_path}")
                bg_music = AudioFileClip(bg_music_path)
                if bg_music.duration < total_duration:
                    bg_music = bg_music.fx(afx.audio_loop, duration=total_duration)
                else:
                    bg_music = bg_music.set_duration(total_duration)
                bg_music = bg_music.volumex(0.1)
                final_audio = CompositeAudioClip([audio.volumex(1.1), bg_music])
            except Exception as e:
                print(f"Failed to load background music: {e}")
                final_audio = audio
        else:
            print(f"CRITICAL: No background music files found in any of {possible_music_paths}")
            final_audio = audio

        final_video = final_video.set_audio(final_audio)
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", threads=4)
        print(f"Enhanced daily summary video saved to {output_path}")


    def _create_karaoke_caption(self, word_offsets: list, duration: float):
        """
        Creates a list of TextClips for karaoke effect.
        """
        clips = []
        PHRASE_SIZE = 5
        FONT_SIZE = 60
        TEXT_Y = 850
        
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
                        fontsize=FONT_SIZE + 5,
                        color='black',
                        bg_color='yellow',
                        font='DejaVu-Sans-Bold' if os.name != 'nt' else 'Arial-Bold',
                        method='label'
                    ).set_start(w_start).set_duration(w_dur).set_position(('center', TEXT_Y))
                    
                    clips.append(highlight)
            except Exception as e:
                print(f"Error in _create_karaoke_caption chunk: {e}")
                
        return clips

if __name__ == "__main__":

    pass
    # vgen = VideoLongGenerator()
    # sections = [{'text': 'Story 1 summary', 'image_path': None}, {'text': 'Story 2 summary', 'image_path': None}]
    # vgen.create_daily_summary(sections, "test_audio.mp3", "test_long.mp4")
