from moviepy.editor import TextClip, ColorClip, CompositeVideoClip, AudioFileClip, ImageClip, concatenate_videoclips, afx
import os
import random
import glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.audio.AudioClip import CompositeAudioClip
import gc


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
        clips = []

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
                    # Use a simpler font size for blocks
                    txt = self.create_text_clip_pil(
                        section['text'], 
                        fontsize=40, # Smaller font for 720p
                        color='white', 
                        bg_color='black',
                        size=(self.size[0]-100, None),
                        font='arial.ttf' if os.name == 'nt' else 'DejaVuSans-Bold.ttf'
                    ).set_duration(section_duration).set_position(('center', 0.8), relative=True) # Relative positioning
                    clips.append(CompositeVideoClip([bg, txt], size=self.size))
                except:
                    clips.append(bg)
            
            # Explicit Garbage Collection to prevent OOM
            if i % 2 == 0:
                gc.collect()

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


    def create_text_clip_pil(self, text, fontsize, color, bg_color=None, font="arial.ttf", size=None):
        """
        Creates a MoviePy ImageClip using PIL for text rendering (bypassing ImageMagick).
        """
        try:
            pil_font = ImageFont.truetype(font, fontsize)
        except:
            pil_font = ImageFont.load_default()
            
        dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        bbox = dummy_draw.textbbox((0, 0), text, font=pil_font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        # Add some padding
        w += 20
        h += 20
        
        if size and size[0] is not None:
            max_width = size[0]
            words = text.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = " ".join(current_line + [word])
                bbox = dummy_draw.textbbox((0, 0), test_line, font=pil_font)
                if bbox[2] - bbox[0] <= max_width:
                    current_line.append(word)
                else:
                    lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
            
            text = "\n".join(lines)
            
            # Recalculate size with wrapped text
            bbox = dummy_draw.textbbox((0, 0), text, font=pil_font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if w < max_width: w = max_width # Ensure it's at least max_width for centering if desired, or just fit.
            w += 40
            h += 40
        else:
             w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
             w += 20
             h += 20
        
        img = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0) if not bg_color else bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw text centered
        # PIL multiline text support
        left, top, right, bottom = dummy_draw.textbbox((0, 0), text, font=pil_font)
        # For centering, we might need to calculate position line by line or use align parameter (works for multiline)
        
        # Center in the image
        text_x = w / 2
        text_y = h / 2
        
        draw.multiline_text((text_x, text_y), text, font=pil_font, fill=color, anchor="mm", align="center")
        
        return ImageClip(np.array(img))

    def _create_karaoke_caption(self, word_offsets: list, duration: float):
        """
        Creates a list of CompositeVideoClips for karaoke effect, ensuring proper alignment.
        """
        clips = []
        PHRASE_SIZE = 8 # Words per screen
        FONT_SIZE = 50 # Adjusted for 720p
        TEXT_Y = 550 # Adjusted for 720p (approx 75% down)
        FONT = 'arial.ttf' if os.name == 'nt' else 'DejaVuSans-Bold.ttf'
        
        for i in range(0, len(word_offsets), PHRASE_SIZE):
            phrase_chunk = word_offsets[i : i + PHRASE_SIZE]
            if not phrase_chunk: continue
            
            # 1. Measure all words first to calculate total width and offsets
            word_clips_data = []
            total_width = 0
            SPACING = 20
            
            for w in phrase_chunk:
                txt = w['word'].upper()
                # Create a temp clip to get size using PIL helper
                temp = self.create_text_clip_pil(txt, fontsize=FONT_SIZE, font=FONT, color='white')
                w_w, w_h = temp.size
                word_clips_data.append({
                    'word': txt,
                    'width': w_w,
                    'height': w_h,
                    'start_time': w['start'],
                    'duration': w['duration'],
                    'x': total_width # Relative x from start of phrase
                })
                total_width += w_w + SPACING
            
            total_width -= SPACING # Remove last spacing
            start_x = (self.size[0] - total_width) / 2
            
            # Phrase start and end time
            p_start = phrase_chunk[0]['start']
            p_end = phrase_chunk[-1]['start'] + phrase_chunk[-1]['duration']
            
            # 2. Create clips for each word "event"
            for active_idx, active_w in enumerate(word_clips_data):
                current_time = active_w['start_time']
                current_dur = active_w['duration']
                
                # Build the composite for this timeframe
                sub_clips = []
                
                for idx, w_data in enumerate(word_clips_data):
                    abs_x = start_x + w_data['x']
                    
                    if idx == active_idx:
                        # Highlighted Word -> Black text on Yellow BG
                        # We can generate this as a single image with BG
                        txt_img = self.create_text_clip_pil(
                            w_data['word'], 
                            fontsize=FONT_SIZE, 
                            font=FONT, 
                            color='black',
                            bg_color='yellow'
                        )
                        txt_img = txt_img.set_position((abs_x, TEXT_Y))
                        sub_clips.append(txt_img)
                    else:
                        # Normal Word -> White text, transparent BG
                        txt_img = self.create_text_clip_pil(
                            w_data['word'], 
                            fontsize=FONT_SIZE, 
                            font=FONT, 
                            color='white'
                        )
                        txt_img = txt_img.set_position((abs_x, TEXT_Y))
                        sub_clips.append(txt_img)
                        
                # Create the composite for this word's duration
                if sub_clips:
                    comp = CompositeVideoClip(sub_clips, size=self.size).set_start(current_time).set_duration(current_dur)
                    clips.append(comp)
        
        return clips

if __name__ == "__main__":

    pass
    # vgen = VideoLongGenerator()
    # sections = [{'text': 'Story 1 summary', 'image_path': None}, {'text': 'Story 2 summary', 'image_path': None}]
    # vgen.create_daily_summary(sections, "test_audio.mp3", "test_long.mp4")
