"""
Voice Synthesizer - Síntesis de voz ultra-realista con ElevenLabs
Genera audio humano natural con control de emoción y tono
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
import subprocess
import wave

load_dotenv()

logger = logging.getLogger(__name__)


class VoiceSynthesizer:
    """Sintetizador de voz con ElevenLabs para audio ultra-realista"""
    
    # Voces disponibles en ElevenLabs (IDs reales)
    AVAILABLE_VOICES = {
        "rachel": {"id": "21m00Tcm4TlvDq8ikWAM", "description": "Profesional, clara, femenina"},
        "adam": {"id": "pNInz6obpgDQGcFmaJgB", "description": "Autoritaria, masculina, narrativa"},
        "antoni": {"id": "ErXwobaYiN019PkySvjV", "description": "Amigable, masculina, conversacional"},
        "emma": {"id": "MF3mGyEYCl7XYWbV9V6O", "description": "Suave, femenina, empática"},
        "josh": {"id": "TxGEqnHWrfWFTfGW9XjX", "description": "Profunda, masculina, seria"},
        "arnold": {"id": "VR6AewLTigWG4xSOukaG", "description": "Dramática, masculina, intensa"},
        "daniel": {"id": "onwK4e9ZLuTAKqWW03F9", "description": "Británica, masculina, formal"},
        "charlie": {"id": "IKne3meq5aSn9XLyUdCD", "description": "Juvenil, masculina, energética"}
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: str = "rachel",
        model: str = "eleven_multilingual_v2",
        stability: float = 0.75,
        similarity_boost: float = 0.85
    ):
        """
        Inicializar sintetizador de voz
        
        Args:
            api_key: API key de ElevenLabs
            voice_id: ID de la voz a usar
            model: Modelo de ElevenLabs
            stability: Estabilidad de voz (0-1), más alto = más consistente
            similarity_boost: Similaridad al original (0-1)
        """
        self.provider = (os.getenv("TTS_PROVIDER") or "elevenlabs").strip().lower()
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = self.AVAILABLE_VOICES.get(voice_id, {}).get("id", voice_id)
        self.model = model
        self.stability = stability
        self.similarity_boost = similarity_boost
        self.client = None
        
        if self.provider == "elevenlabs" and self.api_key:
            self._initialize_client()

    def _initialize_client(self):
        """Inicializar cliente de ElevenLabs"""
        try:
            from elevenlabs import ElevenLabs
            self.client = ElevenLabs(api_key=self.api_key)
            logger.info(f"ElevenLabs inicializado con voz: {self.voice_id}")
        except ImportError:
            logger.warning("ElevenLabs no instalado. pip install elevenlabs")
            self.client = None
        except Exception as e:
            logger.error(f"Error inicializando ElevenLabs: {e}")
            self.client = None
    
    def set_voice(self, voice_name: str):
        """
        Cambiar la voz
        
        Args:
            voice_name: Nombre de la voz (rachel, adam, antoni, etc.)
        """
        if voice_name in self.AVAILABLE_VOICES:
            self.voice_id = self.AVAILABLE_VOICES[voice_name]["id"]
            logger.info(f"Voz cambiada a: {voice_name}")
        else:
            logger.warning(f"Voz '{voice_name}' no encontrada. Usando voz actual.")
    
    def generate_speech(
        self,
        text: str,
        output_path: Optional[str] = None,
        emotion: Optional[str] = None,
        speed_multiplier: float = 1.0
    ) -> Dict[str, Any]:
        """
        Generar audio a partir de texto
        
        Args:
            text: Texto a convertir a voz
            output_path: Ruta para guardar el archivo (opcional)
            emotion: Emoción a aplicar (si el modelo lo soporta)
            speed_multiplier: Multiplicador de velocidad (0.5-2.0)
            
        Returns:
            Diccionario con resultado y metadata
        """
        result = {
            "success": False,
            "audio_path": None,
            "duration_seconds": 0,
            "error": None
        }

        if self.provider == "mock":
            return self._generate_mock_audio(text, output_path)

        if self.provider == "piper":
            return self._generate_with_piper(text, output_path)

        if self.provider == "minimax":
            return self._generate_with_minimax(text, output_path)

        if self.provider != "elevenlabs":
            result["error"] = f"TTS_PROVIDER inválido: {self.provider}"
            return result

        if not self.client:
            # Modo offline - retornar error informativo
            result["error"] = "ElevenLabs no configurado. Configura ELEVENLABS_API_KEY o usa TTS_PROVIDER=mock"
            return result
        
        try:
            # Generar audio con ElevenLabs
            audio_generator = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                model_id=self.model,
                text=text,
                voice_settings={
                    "stability": self.stability,
                    "similarity_boost": self.similarity_boost,
                    "speed": speed_multiplier
                }
            )
            
            # Guardar o devolver audio
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, "wb") as f:
                    for chunk in audio_generator:
                        f.write(chunk)
                
                result["audio_path"] = output_path
                logger.info(f"Audio guardado en: {output_path}")
                
                # Calcular duración aproximada (150 palabras/minuto promedio)
                word_count = len(text.split())
                result["duration_seconds"] = (word_count / 150) * 60
                
            else:
                # Devolver bytes
                audio_data = b"".join(audio_generator)
                result["audio_bytes"] = audio_data
                result["duration_seconds"] = (len(text.split()) / 150) * 60
            
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Error generando speech: {e}")
            result["error"] = str(e)
        
        return result

    def _generate_mock_audio(self, text: str, output_path: Optional[str]) -> Dict[str, Any]:
        """Genera un WAV de silencio para permitir pruebas end-to-end sin servicios externos."""
        result = {"success": False, "audio_path": None, "duration_seconds": 0, "error": None}
        if not output_path:
            result["error"] = "output_path requerido en modo mock"
            return result

        try:
            word_count = max(1, len(text.split()))
            duration_seconds = max(1.0, (word_count / 150) * 60)

            wav_path = os.path.splitext(output_path)[0] + ".wav"
            Path(wav_path).parent.mkdir(parents=True, exist_ok=True)

            sample_rate = 22050
            n_frames = int(duration_seconds * sample_rate)
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(b"\x00\x00" * n_frames)

            result["success"] = True
            result["audio_path"] = wav_path
            result["duration_seconds"] = duration_seconds
            return result
        except Exception as e:
            result["error"] = f"Mock TTS error: {e}"
            return result

    def _generate_with_piper(self, text: str, output_path: Optional[str]) -> Dict[str, Any]:
        """
        TTS open source vía Piper (CLI). Requiere:
        - PIPER_BIN (default: piper)
        - PIPER_MODEL (ruta al .onnx)
        """
        result = {"success": False, "audio_path": None, "duration_seconds": 0, "error": None}
        if not output_path:
            result["error"] = "output_path requerido para piper"
            return result

        piper_bin = os.getenv("PIPER_BIN", "piper")
        piper_model = os.getenv("PIPER_MODEL")
        if not piper_model:
            result["error"] = "PIPER_MODEL no configurado"
            return result

        wav_path = os.path.splitext(output_path)[0] + ".wav"
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run(
                [piper_bin, "--model", piper_model, "--output_file", wav_path],
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if proc.returncode != 0:
                result["error"] = proc.stderr.decode("utf-8", errors="ignore")[:500]
                return result

            # Convertir WAV -> MP3 si pydub está disponible
            try:
                from pydub import AudioSegment

                audio = AudioSegment.from_wav(wav_path)
                audio.export(output_path, format="mp3", bitrate="192k")
                result["duration_seconds"] = len(audio) / 1000.0
                result["audio_path"] = output_path
                result["success"] = True
                return result
            except Exception:
                result["audio_path"] = wav_path
                result["success"] = True
                return result
        except Exception as e:
            result["error"] = f"Piper TTS error: {e}"
            return result

    def _generate_with_minimax(self, text: str, output_path: Optional[str]) -> Dict[str, Any]:
        """
        TTS vía MiniMax. Para evitar hardcode de endpoints, se configura vía env:
        - MINIMAX_API_KEY
        - MINIMAX_TTS_URL (URL completa)
        """
        result = {"success": False, "audio_path": None, "duration_seconds": 0, "error": None}
        if not output_path:
            result["error"] = "output_path requerido para minimax"
            return result

        api_key = os.getenv("MINIMAX_API_KEY")
        url = os.getenv("MINIMAX_TTS_URL")
        if not api_key or not url:
            result["error"] = "MINIMAX_API_KEY o MINIMAX_TTS_URL no configurados"
            return result

        try:
            import requests

            payload = {
                "text": text,
                "voice": os.getenv("MINIMAX_VOICE", "female-1"),
                "format": "mp3",
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            if resp.status_code != 200:
                result["error"] = f"HTTP {resp.status_code}: {resp.text[:300]}"
                return result

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(resp.content)

            result["success"] = True
            result["audio_path"] = output_path
            word_count = max(1, len(text.split()))
            result["duration_seconds"] = max(1.0, (word_count / 150) * 60)
            return result
        except Exception as e:
            result["error"] = f"MiniMax TTS error: {e}"
            return result
    
    def generate_from_script(self, script: Dict, output_dir: str = "temp/audio") -> Dict[str, Any]:
        """
        Generar audio completo desde un guión estructurado
        
        Args:
            script: Guión generado por ScriptGenerator
            output_dir: Directorio para archivos de audio
            
        Returns:
            Diccionario con paths de audio por sección
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        result = {
            "success": True,
            "sections": {},
            "full_audio_path": None,
            "total_duration": 0,
            "errors": []
        }
        
        audio_files = []
        total_duration = 0
        
        # Procesar hook
        if "hook" in script and "text" in script["hook"]:
            hook_path = os.path.join(output_dir, "00_hook.mp3")
            hook_result = self.generate_speech(script["hook"]["text"], hook_path)
            
            if hook_result["success"]:
                result["sections"]["hook"] = hook_result
                audio_files.append(hook_result.get("audio_path") or hook_path)
                total_duration += hook_result.get("duration_seconds", 0)
            else:
                result["errors"].append(f"Hook: {hook_result.get('error')}")
                result["success"] = False
        
        # Procesar secciones
        for i, section in enumerate(script.get("sections", []), 1):
            if "text" in section:
                section_name = section.get("name", f"section_{i}").lower().replace(" ", "_")
                section_path = os.path.join(output_dir, f"{i:02d}_{section_name}.mp3")
                
                section_result = self.generate_speech(section["text"], section_path)
                
                if section_result["success"]:
                    result["sections"][section_name] = section_result
                    audio_files.append(section_result.get("audio_path") or section_path)
                    total_duration += section_result.get("duration_seconds", 0)
                else:
                    result["errors"].append(f"{section_name}: {section_result.get('error')}")
        
        # Procesar CTA
        if "cta" in script and "text" in script["cta"]:
            cta_path = os.path.join(output_dir, "99_cta.mp3")
            cta_result = self.generate_speech(script["cta"]["text"], cta_path)
            
            if cta_result["success"]:
                result["sections"]["cta"] = cta_result
                audio_files.append(cta_result.get("audio_path") or cta_path)
                total_duration += cta_result.get("duration_seconds", 0)
            else:
                result["errors"].append(f"CTA: {cta_result.get('error')}")
                result["success"] = False
        
        result["total_duration"] = total_duration
        result["audio_files"] = audio_files
        
        # Unir todos los audios si hay múltiples secciones
        if len(audio_files) > 1 and result["success"]:
            full_audio_path = os.path.join(output_dir, "full_narration.mp3")
            self.concatenate_audio(audio_files, full_audio_path)
            result["full_audio_path"] = full_audio_path
        
        return result
    
    def concatenate_audio(self, audio_files: list, output_path: str, gap_seconds: float = 0.3):
        """
        Concatenar múltiples archivos de audio
        
        Args:
            audio_files: Lista de paths de archivos MP3
            output_path: Path de salida
            gap_seconds: Pausa entre segmentos
        """
        try:
            from pydub import AudioSegment
            
            combined = AudioSegment.empty()
            
            for audio_file in audio_files:
                audio = AudioSegment.from_file(audio_file)
                combined += audio
                
                # Agregar pausa (excepto después del último)
                if audio_file != audio_files[-1]:
                    silence = AudioSegment.silent(duration=int(gap_seconds * 1000))
                    combined += silence
            
            # Si se solicita MP3, requiere ffmpeg; si falla, exportar WAV.
            try:
                combined.export(output_path, format="mp3", bitrate="192k")
            except Exception:
                wav_path = os.path.splitext(output_path)[0] + ".wav"
                combined.export(wav_path, format="wav")
                output_path = wav_path
            logger.info(f"Audio concatenado guardado en: {output_path}")
            
        except ImportError:
            logger.warning("pydub no instalado. pip install pydub")
        except Exception as e:
            logger.error(f"Error concatenando audio: {e}")
    
    def get_available_voices(self) -> Dict[str, Dict]:
        """Retornar lista de voces disponibles"""
        return self.AVAILABLE_VOICES.copy()
    
    def preview_voice(self, voice_name: str, sample_text: str = "Hola, esta es una prueba de voz") -> Optional[bytes]:
        """
        Previsualizar una voz antes de usarla
        
        Args:
            voice_name: Nombre de la voz a previsualizar
            sample_text: Texto de ejemplo
            
        Returns:
            Bytes del audio o None si falla
        """
        original_voice = self.voice_id
        
        try:
            self.set_voice(voice_name)
            result = self.generate_speech(sample_text)
            return result.get("audio_bytes")
        finally:
            # Restaurar voz original
            self.voice_id = original_voice
