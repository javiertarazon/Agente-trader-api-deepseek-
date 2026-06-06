"""
Video Assembler - Ensamblaje y edición automática de videos
Combina audio, imágenes y transiciones usando MoviePy
"""

import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class VideoAssembler:
    """Ensamblador de videos con edición automática"""
    
    def __init__(
        self,
        resolution: str = "1920x1080",
        fps: int = 30,
        audio_bitrate: str = "192k",
        video_bitrate: str = "5000k"
    ):
        """
        Inicializar ensamblador de video
        
        Args:
            resolution: Resolución del video (ej: "1920x1080")
            fps: Frames por segundo
            audio_bitrate: Bitrate de audio
            video_bitrate: Bitrate de video
        """
        self.resolution = resolution
        self.width, self.height = map(int, resolution.split("x"))
        self.fps = fps
        self.audio_bitrate = audio_bitrate
        self.video_bitrate = video_bitrate
    
    def assemble_video(
        self,
        script: Dict,
        audio_files: List[str],
        image_files: List[str],
        output_path: str,
        background_music: Optional[str] = None,
        music_volume: float = 0.15,
        add_subtitles: bool = True
    ) -> Dict[str, Any]:
        """
        Ensamblar video completo
        
        Args:
            script: Guión estructurado
            audio_files: Lista de archivos de audio
            image_files: Lista de archivos de imagen
            output_path: Ruta de salida del video
            background_music: Música de fondo opcional
            music_volume: Volumen de música (0-1)
            add_subtitles: Añadir subtítulos automáticos
            
        Returns:
            Diccionario con resultado
        """
        result = {
            "success": False,
            "video_path": None,
            "duration": 0,
            "error": None
        }
        
        try:
            from moviepy.editor import (
                ImageClip, AudioFileClip, CompositeVideoClip,
                CompositeAudioClip, concatenate_videoclips, TextClip
            )
            from moviepy.video.fx.all import fadein, fadeout
            
            # Crear clips de video para cada imagen
            clips = []
            
            # Asegurar que tenemos igual cantidad de audios e imágenes
            num_segments = min(len(audio_files), len(image_files))
            
            for i in range(num_segments):
                # Cargar imagen
                img_clip = ImageClip(image_files[i]).set_duration(
                    AudioFileClip(audio_files[i]).duration
                )
                
                # Aplicar resize si es necesario
                if img_clip.w != self.width or img_clip.h != self.height:
                    img_clip = img_clip.resize(newsize=(self.width, self.height))
                
                # Cargar audio
                audio_clip = AudioFileClip(audio_files[i])
                img_clip = img_clip.set_audio(audio_clip)
                
                # Añadir fade in/out suave
                if i > 0:
                    img_clip = img_clip.fadein(0.5)
                if i < num_segments - 1:
                    img_clip = img_clip.fadeout(0.5)
                
                clips.append(img_clip)
            
            # Concatenar todos los clips
            final_video = concatenate_videoclips(clips, method="compose")
            
            # Añadir música de fondo si existe
            if background_music:
                music_clip = AudioFileClip(background_music)
                
                # Loop si la música es más corta que el video
                while music_clip.duration < final_video.duration:
                    music_clip = music_clip.with_effects([
                        lambda c: c.set_start(c.duration)
                    ])
                
                # Recortar al tamaño del video
                music_clip = music_clip.subclip(0, final_video.duration)
                
                # Ajustar volumen
                music_clip = music_clip.volumex(music_volume)
                
                # Combinar con narración
                final_audio = CompositeAudioClip([
                    final_video.audio,
                    music_clip
                ])
                
                final_video = final_video.set_audio(final_audio)
            
            # Añadir subtítulos si se solicita
            if add_subtitles:
                subtitles = self._generate_subtitle_clips(script, final_video.duration)
                if subtitles:
                    final_video = CompositeVideoClip([final_video] + subtitles)
            
            # Exportar video
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            final_video.write_videofile(
                output_path,
                fps=self.fps,
                codec='libx264',
                audio_codec='aac',
                bitrate=self.video_bitrate,
                audio_bitrate=self.audio_bitrate,
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                write_logfile=False,
                logger=None  # Silenciar progreso
            )
            
            result["video_path"] = output_path
            result["duration"] = final_video.duration
            result["success"] = True
            
            logger.info(f"Video exportado exitosamente: {output_path}")
            logger.info(f"Duración: {result['duration']:.2f} segundos")
            
            # Limpieza
            final_video.close()
            for clip in clips:
                clip.close()
            
        except ImportError as e:
            logger.error(f"MoviePy no instalado: {e}")
            result["error"] = "Instala moviepy: pip install moviepy"
        except Exception as e:
            logger.error(f"Error ensamblando video: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result
    
    def _generate_subtitle_clips(self, script: Dict, video_duration: float) -> List:
        """Generar clips de subtítulos"""
        try:
            from moviepy.editor import TextClip
            
            subtitle_clips = []
            
            # Hook subtitle
            if "hook" in script and "text" in script["hook"]:
                hook = script["hook"]
                start, end = hook.get("time", [0, 3])
                
                txt_clip = TextClip(
                    hook["text"],
                    fontsize=48,
                    color='white',
                    font='Arial-Bold',
                    stroke_color='black',
                    stroke_width=2,
                    size=(self.width * 0.9, None),
                    method='caption'
                )
                
                txt_clip = txt_clip.set_position(('center', 'bottom'))
                txt_clip = txt_clip.set_start(start)
                txt_clip = txt_clip.set_end(end)
                
                subtitle_clips.append(txt_clip)
            
            # Section subtitles
            for section in script.get("sections", []):
                if "text" in section:
                    start, end = section.get("time", [0, 0])
                    
                    # Dividir texto largo en líneas múltiples
                    text = section["text"][:200]  # Limitar longitud
                    
                    txt_clip = TextClip(
                        text,
                        fontsize=42,
                        color='white',
                        font='Arial-Bold',
                        stroke_color='black',
                        stroke_width=2,
                        size=(self.width * 0.9, None),
                        method='caption'
                    )
                    
                    txt_clip = txt_clip.set_position(('center', 'bottom'))
                    txt_clip = txt_clip.set_start(start)
                    txt_clip = txt_clip.set_end(end)
                    
                    subtitle_clips.append(txt_clip)
            
            # CTA subtitle
            if "cta" in script and "text" in script["cta"]:
                cta = script["cta"]
                start, end = cta.get("time", [55, 60])
                
                txt_clip = TextClip(
                    cta["text"][:150],
                    fontsize=44,
                    color='yellow',
                    font='Arial-Bold',
                    stroke_color='black',
                    stroke_width=2,
                    size=(self.width * 0.9, None),
                    method='caption'
                )
                
                txt_clip = txt_clip.set_position(('center', 'bottom'))
                txt_clip = txt_clip.set_start(start)
                txt_clip = txt_clip.set_end(end)
                
                subtitle_clips.append(txt_clip)
            
            return subtitle_clips
            
        except Exception as e:
            logger.warning(f"No se pudieron generar subtítulos: {e}")
            return []
    
    def create_transition(
        self,
        type: str = "fade",
        duration: float = 0.5,
        color: str = "black"
    ):
        """Crear transición entre escenas"""
        # Implementación futura para transiciones personalizadas
        pass
    
    def add_watermark(
        self,
        video_path: str,
        logo_path: str,
        output_path: str,
        position: str = "bottom-right",
        opacity: float = 0.7
    ) -> Dict[str, Any]:
        """Añadir marca de agua al video"""
        result = {"success": False, "video_path": None, "error": None}
        
        try:
            from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
            
            video = VideoFileClip(video_path)
            logo = ImageClip(logo_path).set_opacity(opacity)
            
            # Calcular posición
            if position == "bottom-right":
                logo = logo.set_position(('right', 'bottom'), relative=True)
            elif position == "top-left":
                logo = logo.set_position(('left', 'top'), relative=True)
            elif position == "top-right":
                logo = logo.set_position(('right', 'top'), relative=True)
            elif position == "bottom-left":
                logo = logo.set_position(('left', 'bottom'), relative=True)
            else:
                logo = logo.set_position(position)
            
            # Logo durante todo el video
            logo = logo.set_duration(video.duration)
            
            # Composicionar
            final = CompositeVideoClip([video, logo])
            
            # Exportar
            final.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                bitrate=self.video_bitrate
            )
            
            result["video_path"] = output_path
            result["success"] = True
            
            video.close()
            logo.close()
            final.close()
            
        except Exception as e:
            logger.error(f"Error añadiendo watermark: {e}")
            result["error"] = str(e)
        
        return result
    
    def extract_highlights(
        self,
        video_path: str,
        timestamps: List[tuple],
        output_path: str
    ) -> Dict[str, Any]:
        """Extraer momentos destacados del video"""
        result = {"success": False, "video_path": None, "error": None}
        
        try:
            from moviepy.editor import VideoFileClip, concatenate_videoclips
            
            video = VideoFileClip(video_path)
            highlights = []
            
            for start, end in timestamps:
                highlight = video.subclip(start, end)
                highlights.append(highlight)
            
            # Unir highlights
            compilation = concatenate_videoclips(highlights)
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            compilation.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac'
            )
            
            result["video_path"] = output_path
            result["success"] = True
            
            video.close()
            compilation.close()
            
        except Exception as e:
            logger.error(f"Error extrayendo highlights: {e}")
            result["error"] = str(e)
        
        return result
