"""
Video Generator AI - Core Package
Generación profesional de videos con IA: guiones, voz, imágenes y edición automática
"""

__version__ = "1.0.0"
__author__ = "Autonomous Trading Agent Team"

from .script_generator import ScriptGenerator
from .voice_synthesizer import VoiceSynthesizer
from .image_generator import ImageGenerator
from .video_assembler import VideoAssembler
from .trend_analyzer import TrendAnalyzer
from .youtube_optimizer import YouTubeOptimizer

__all__ = [
    "ScriptGenerator",
    "VoiceSynthesizer",
    "ImageGenerator",
    "VideoAssembler",
    "TrendAnalyzer",
    "YouTubeOptimizer",
]
