"""
Script Generator - Generación de guiones virales con ganchos profesionales
Analiza tendencias y crea estructuras optimizadas para retención en YouTube
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """Generador de guiones virales con estructura probada"""
    
    # Ganchos virales categorizados por nicho
    VIRAL_HOOKS = {
        "motivational": [
            "¿Sabías que el 95% de las personas fracasan por esto?",
            "Esto es lo que nadie te cuenta sobre el éxito",
            "3 hábitos que cambiarán tu vida en 30 días",
            "La verdad incómoda que los millonarios no quieren que sepas",
            "Si haces esto antes de las 8 AM, tu vida cambiará"
        ],
        "finance": [
            "Cómo gané $10,000 en mi primer mes haciendo esto",
            "El error financiero que el 90% comete",
            "Esta estrategia me hizo rico en 2 años",
            "Los bancos no quieren que conozcas este secreto",
            "Invierte como los millonarios con solo $100"
        ],
        "tech": [
            "Esta IA hará tu trabajo en 5 minutos",
            "El futuro está aquí y nadie está listo",
            "3 herramientas que reemplazarán a los humanos",
            "Lo que Silicon Valley oculta sobre la tecnología",
            "Así será tu vida en 2030 según los expertos"
        ],
        "health": [
            "Los doctores no te dirán este secreto",
            "Perdí 20kg haciendo esto todos los días",
            "El alimento que está destruyendo tu salud",
            "Ciencia confirma: esto cura la ansiedad",
            "Haz esto antes de dormir y transforma tu cuerpo"
        ],
        "general": [
            "Esto cambiará tu forma de ver la vida",
            "Nadie habla de esto pero debería ser obligatorio",
            "La razón por la que sigues fracasando",
            "Si ignoras esto, te arrepentirás después",
            "Lo que aprendí después de 1000 intentos"
        ]
    }
    
    # Estructuras de guión probadas
    SCRIPT_STRUCTURES = {
        "problem_solution": {
            "hook": (0, 3),      # segundos
            "problem": (3, 15),
            "agitation": (15, 30),
            "solution": (30, 50),
            "proof": (50, 55),
            "cta": (55, 60)
        },
        "listicle": {
            "hook": (0, 3),
            "intro": (3, 8),
            "item_1": (8, 20),
            "item_2": (20, 32),
            "item_3": (32, 44),
            "bonus": (44, 52),
            "cta": (52, 60)
        },
        "story": {
            "hook": (0, 5),
            "setup": (5, 15),
            "conflict": (15, 30),
            "climax": (30, 45),
            "resolution": (45, 55),
            "lesson": (55, 60)
        },
        "transformation": {
            "before": (0, 10),
            "catalyst": (10, 20),
            "process": (20, 40),
            "after": (40, 50),
            "call_to_action": (50, 60)
        }
    }
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        """
        Inicializar generador de guiones
        
        Args:
            api_key: API key de DeepSeek u OpenAI
            model: Modelo a utilizar
        """
        self.provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()

        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        # Auto-detect provider if not set explicitly.
        if not self.provider:
            if openrouter_key:
                self.provider = "openrouter"
            elif deepseek_key:
                self.provider = "deepseek"
            elif openai_key:
                self.provider = "openai"
            else:
                self.provider = "offline"

        self.api_key = api_key or (
            openrouter_key if self.provider == "openrouter" else
            deepseek_key if self.provider == "deepseek" else
            openai_key if self.provider == "openai" else
            None
        )

        self.model = os.getenv("LLM_MODEL") or model
        fallbacks_raw = os.getenv("LLM_FALLBACK_MODELS", "")
        self.models = [m.strip() for m in [self.model, *fallbacks_raw.split(",")] if m.strip()]
        self.client = None
        
        if self.api_key and self.provider != "offline":
            self._initialize_client()
    
    def _initialize_client(self):
        """Inicializar cliente de IA"""
        try:
            from openai import OpenAI

            base_url = os.getenv("LLM_BASE_URL")
            default_headers = {}

            if not base_url:
                if self.provider == "openrouter":
                    base_url = "https://openrouter.ai/api/v1"
                    # OpenRouter recommended headers (optional)
                    referer = os.getenv("OPENROUTER_HTTP_REFERER")
                    title = os.getenv("OPENROUTER_APP_TITLE")
                    if referer:
                        default_headers["HTTP-Referer"] = referer
                    if title:
                        default_headers["X-Title"] = title
                elif self.provider == "deepseek" or "deepseek" in self.model.lower():
                    base_url = "https://api.deepseek.com/v1"

            self.client = OpenAI(api_key=self.api_key, base_url=base_url, default_headers=default_headers or None)
            logger.info("Cliente de IA inicializado correctamente")
        except ImportError:
            logger.warning("OpenAI no instalado. Usando modo offline con plantillas.")
            self.client = None
    
    def analyze_viral_patterns(self, topic: str, niche: str = "general") -> Dict[str, Any]:
        """
        Analizar patrones virales para un tema específico
        
        Args:
            topic: Tema del video
            niche: Nicho (motivational, finance, tech, health, general)
            
        Returns:
            Diccionario con patrones detectados
        """
        if not self.client:
            return self._offline_pattern_analysis(topic, niche)
        
        try:
            prompt = f"""Analiza los patrones virales de videos exitosos sobre "{topic}" en el nicho {niche}.
Identifica:
1. Los 3 ganchos más efectivos (primeros 3 segundos)
2. Estructura narrativa más común
3. Palabras clave de alto impacto
4. Duración óptima por sección
5. Call-to-action más efectivo

Responde SOLO en formato JSON válido con esta estructura:
{{
    "hooks": ["hook1", "hook2", "hook3"],
    "best_structure": "nombre_estructura",
    "keywords": ["palabra1", "palabra2"],
    "optimal_duration": {{
        "hook": [0, 3],
        "main_content": [3, 45],
        "cta": [45, 60]
    }},
    "cta_examples": ["cta1", "cta2"]
}}"""

            response = None
            last_error = None
            for model in self.models:
                try:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                        max_tokens=1000
                    )
                    break
                except Exception as e:
                    last_error = e
                    continue
            if response is None:
                raise last_error or RuntimeError("No se pudo consultar el LLM")
            
            content = response.choices[0].message.content.strip()
            # Extraer JSON si viene envuelto en markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Error analizando patrones virales: {e}")
            return self._offline_pattern_analysis(topic, niche)
    
    def _offline_pattern_analysis(self, topic: str, niche: str) -> Dict[str, Any]:
        """Análisis offline usando plantillas predefinidas"""
        hooks = self.VIRAL_HOOKS.get(niche, self.VIRAL_HOOKS["general"])[:3]
        return {
            "hooks": hooks,
            "best_structure": "problem_solution",
            "keywords": topic.split(),
            "optimal_duration": {
                "hook": [0, 3],
                "main_content": [3, 45],
                "cta": [45, 60]
            },
            "cta_examples": [
                "Suscríbete para más contenido como este",
                "Comenta tu experiencia abajo",
                "Comparte con alguien que necesite esto"
            ]
        }
    
    def generate_script(
        self,
        topic: str,
        duration_seconds: int = 60,
        niche: str = "general",
        style: str = "professional",
        tone: str = "inspirational",
        include_visual_cues: bool = True,
        viral_patterns: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generar guión completo para video
        
        Args:
            topic: Tema principal del video
            duration_seconds: Duración objetivo en segundos
            niche: Nicho del contenido
            style: Estilo (professional, casual, dramatic, humorous)
            tone: Tono (inspirational, informative, urgent, friendly)
            include_visual_cues: Incluir indicaciones visuales
            viral_patterns: Patrones virales detectados (opcional)
            
        Returns:
            Diccionario con guión estructurado
        """
        # Obtener o detectar patrones virales
        if not viral_patterns:
            viral_patterns = self.analyze_viral_patterns(topic, niche)
        
        # Seleccionar estructura
        structure_name = viral_patterns.get("best_structure", "problem_solution")
        structure = self.SCRIPT_STRUCTURES.get(structure_name, self.SCRIPT_STRUCTURES["problem_solution"])
        
        # Escalar estructura a duración deseada
        scaled_structure = self._scale_structure(structure, duration_seconds)
        
        if self.client:
            script = self._generate_with_ai(
                topic=topic,
                structure=scaled_structure,
                style=style,
                tone=tone,
                viral_patterns=viral_patterns,
                include_visual_cues=include_visual_cues
            )
        else:
            script = self._generate_offline(
                topic=topic,
                structure=scaled_structure,
                style=style,
                tone=tone,
                viral_patterns=viral_patterns,
                include_visual_cues=include_visual_cues
            )
        
        # Añadir metadatos
        script["metadata"] = {
            "topic": topic,
            "duration": duration_seconds,
            "niche": niche,
            "style": style,
            "tone": tone,
            "structure_used": structure_name,
            "estimated_words": self._estimate_word_count(script),
            "viral_score": self._calculate_viral_score(script, viral_patterns)
        }
        
        return script
    
    def _scale_structure(self, structure: Dict, target_duration: int) -> Dict:
        """Escalar estructura de tiempos a duración objetivo"""
        # Obtener duración total de la estructura original
        max_time = max(end for start, end in structure.values())
        scale_factor = target_duration / max_time
        
        scaled = {}
        for section, (start, end) in structure.items():
            scaled[section] = (int(start * scale_factor), int(end * scale_factor))
        
        return scaled
    
    def _generate_with_ai(
        self,
        topic: str,
        structure: Dict,
        style: str,
        tone: str,
        viral_patterns: Dict,
        include_visual_cues: bool
    ) -> Dict[str, Any]:
        """Generar guión usando IA"""
        
        structure_text = "\n".join([
            f"- {section}: {start}-{end} segundos"
            for section, (start, end) in structure.items()
        ])
        
        hooks_text = "\n".join([f"- {h}" for h in viral_patterns.get("hooks", [])])
        
        prompt = f"""Crea un guión profesional para video de YouTube sobre "{topic}".

ESTRUCTURA TEMPORAL:
{structure_text}

ESTILO: {style}
TONO: {tone}

GANCHOS VIRALES DETECTADOS (usar como inspiración):
{hooks_text}

REQUISITOS:
1. Gancho ultra-poderoso en los primeros 3 segundos
2. Lenguaje claro y directo
3. Frases cortas para facilitar subtítulos
4. Incluir pausas naturales para edición
5. Call-to-action convincente al final
{"6. Incluir indicaciones visuales entre [corchetes]" if include_visual_cues else ""}

Responde SOLO en formato JSON válido con esta estructura:
{{
    "hook": {{
        "time": [0, 3],
        "text": "texto del gancho",
        {"visual_cue": "descripción visual", "optional" if not include_visual_cues else ""}
    }},
    "sections": [
        {{
            "name": "nombre_sección",
            "time": [inicio, fin],
            "text": "contenido",
            {"visual_cue": "descripción", "optional" if not include_visual_cues else ""}
        }}
    ],
    "cta": {{
        "time": [inicio, fin],
        "text": "call to action",
        {"visual_cue": "descripción", "optional" if not include_visual_cues else ""}
    }},
    "background_music_suggestions": ["sugerencia1", "sugerencia2"],
    "thumbnail_text": "texto corto para miniatura"
}}"""

        try:
            response = None
            last_error = None
            for model in self.models:
                try:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.8,
                        max_tokens=2000
                    )
                    break
                except Exception as e:
                    last_error = e
                    continue
            if response is None:
                raise last_error or RuntimeError("No se pudo consultar el LLM")
            
            content = response.choices[0].message.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            script_data = json.loads(content)
            
            # Normalizar estructura
            return {
                "hook": script_data.get("hook", {}),
                "sections": script_data.get("sections", []),
                "cta": script_data.get("cta", {}),
                "music_suggestions": script_data.get("background_music_suggestions", []),
                "thumbnail_text": script_data.get("thumbnail_text", "")
            }
            
        except Exception as e:
            logger.error(f"Error generando guión con IA: {e}")
            return self._generate_offline(topic, structure, style, tone, viral_patterns, include_visual_cues)
    
    def _generate_offline(
        self,
        topic: str,
        structure: Dict,
        style: str,
        tone: str,
        viral_patterns: Dict,
        include_visual_cues: bool
    ) -> Dict[str, Any]:
        """Generar guión offline con plantillas"""
        
        hooks = viral_patterns.get("hooks", self.VIRAL_HOOKS["general"])
        hook_text = hooks[0] if hooks else f"Descubre todo sobre {topic}"
        
        sections = []
        section_names = list(structure.keys())[1:-1]  # Excluir hook y cta
        
        for i, section_name in enumerate(section_names):
            start, end = structure[section_name]
            duration = end - start
            
            sections.append({
                "name": section_name.replace("_", " ").title(),
                "time": [start, end],
                "text": f"Contenido sobre {topic} - punto {i+1}. Explicación detallada con ejemplos prácticos.",
                "visual_cue": f"[Escena {i+1}: Imagen relacionada con {topic}]" if include_visual_cues else None
            })
        
        return {
            "hook": {
                "time": [0, 3],
                "text": hook_text,
                "visual_cue": f"[Gancho visual impactante sobre {topic}]" if include_visual_cues else None
            },
            "sections": sections,
            "cta": {
                "time": structure.get("cta", [55, 60]),
                "text": "Si te gustó este contenido, suscríbete y activa la campanita. ¡Nos vemos en el próximo video!",
                "visual_cue": "[Botón de suscripción animado]" if include_visual_cues else None
            },
            "music_suggestions": ["upbeat motivational", "inspiring corporate"],
            "thumbnail_text": f"{topic[:20]}..." if len(topic) > 20 else topic
        }
    
    def _estimate_word_count(self, script: Dict) -> int:
        """Estimar cantidad de palabras del guión"""
        total_words = 0
        
        if "hook" in script and "text" in script["hook"]:
            total_words += len(script["hook"]["text"].split())
        
        for section in script.get("sections", []):
            if "text" in section:
                total_words += len(section["text"].split())
        
        if "cta" in script and "text" in script["cta"]:
            total_words += len(script["cta"]["text"].split())
        
        return total_words
    
    def _calculate_viral_score(self, script: Dict, patterns: Dict) -> float:
        """Calcular puntuación de viralidad potencial (0-100)"""
        score = 50.0  # Base
        
        # Bonus por gancho fuerte
        hook_text = script.get("hook", {}).get("text", "")
        if any(word in hook_text.lower() for word in ["secreto", "nadie", "verdad", "increíble"]):
            score += 15
        
        # Bonus por estructura óptima
        if len(script.get("sections", [])) >= 3:
            score += 10
        
        # Bonus por CTA claro
        cta_text = script.get("cta", {}).get("text", "")
        if any(word in cta_text.lower() for word in ["suscríbete", "comenta", "comparte"]):
            score += 10
        
        # Bonus por longitud adecuada (140-160 palabras para 60s)
        word_count = self._estimate_word_count(script)
        if 130 <= word_count <= 170:
            score += 15
        
        return min(100, max(0, score))
    
    def export_to_format(self, script: Dict, format_type: str = "teleprompter") -> str:
        """
        Exportar guión a diferentes formatos
        
        Args:
            script: Guión generado
            format_type: teleprompter, srt, markdown, plain
            
        Returns:
            String formateado
        """
        if format_type == "teleprompter":
            lines = []
            lines.append(script.get("hook", {}).get("text", ""))
            lines.append("")
            
            for section in script.get("sections", []):
                lines.append(section.get("text", ""))
                lines.append("")
            
            lines.append(script.get("cta", {}).get("text", ""))
            return "\n".join(lines)
        
        elif format_type == "srt":
            # Formato de subtítulos
            subtitles = []
            index = 1
            
            # Hook
            hook = script.get("hook", {})
            if hook:
                start, end = hook.get("time", [0, 3])
                text = hook.get("text", "")
                subtitles.append(self._format_srt_entry(index, start, end, text))
                index += 1
            
            # Sections
            for section in script.get("sections", []):
                start, end = section.get("time", [0, 0])
                text = section.get("text", "")
                subtitles.append(self._format_srt_entry(index, start, end, text))
                index += 1
            
            # CTA
            cta = script.get("cta", {})
            if cta:
                start, end = cta.get("time", [55, 60])
                text = cta.get("text", "")
                subtitles.append(self._format_srt_entry(index, start, end, text))
            
            return "\n".join(subtitles)
        
        elif format_type == "markdown":
            md = f"# Guión: {script.get('metadata', {}).get('topic', 'Video')}\n\n"
            md += f"**Duración:** {script.get('metadata', {}).get('duration', 60)}s\n"
            md += f"**Palabras estimadas:** {script.get('metadata', {}).get('estimated_words', 0)}\n"
            md += f"**Score Viral:** {script.get('metadata', {}).get('viral_score', 0):.0f}/100\n\n"
            
            md += "## 🎣 Gancho (0-3s)\n"
            md += f"{script.get('hook', {}).get('text', '')}\n\n"
            
            md += "## 📝 Contenido\n"
            for section in script.get("sections", []):
                start, end = section.get("time", [0, 0])
                md += f"### {section.get('name', 'Sección')} ({start}-{end}s)\n"
                md += f"{section.get('text', '')}\n\n"
                if section.get("visual_cue"):
                    md += f"*Visual: {section['visual_cue']}*\n\n"
            
            md += "## 🎯 Call to Action\n"
            md += f"{script.get('cta', {}).get('text', '')}\n\n"
            
            return md
        
        else:  # plain
            parts = [script.get("hook", {}).get("text", "")]
            for section in script.get("sections", []):
                parts.append(section.get("text", ""))
            parts.append(script.get("cta", {}).get("text", ""))
            return " ".join(parts)
    
    def _format_srt_entry(self, index: int, start_sec: float, end_sec: float, text: str) -> str:
        """Formatear entrada SRT"""
        def format_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int((seconds - int(seconds)) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
        
        return f"{index}\n{format_time(start_sec)} --> {format_time(end_sec)}\n{text}\n"
