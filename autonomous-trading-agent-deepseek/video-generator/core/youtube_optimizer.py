"""
YouTube Optimizer - Optimización para algoritmo de YouTube
Genera títulos, descripciones, tags y miniaturas optimizadas para SEO y viralidad
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class YouTubeOptimizer:
    """Optimizador de contenido para YouTube"""
    
    # Palabras de poder para títulos
    POWER_WORDS = [
        "Increíble", "Secreto", "Verdad", "Nadie", "Prohibido", "Revelado",
        "Impactante", "Sorprendente", "Definitivo", "Esencial", "Crítico",
        "Urgente", "Exclusivo", "Limitado", "Garantizado", "Comprobado"
    ]
    
    # Emojis efectivos por categoría
    EMOJIS_BY_CATEGORY = {
        "motivational": ["🔥", "💪", "🎯", "⭐", "🚀", "💯"],
        "finance": ["💰", "💵", "📈", "💎", "🏆", "💸"],
        "tech": ["🤖", "💻", "🚀", "⚡", "🔮", "💡"],
        "health": ["💪", "🥗", "🏃", "💤", "🧘", "❤️"],
        "general": ["🔥", "😱", "🎯", "💡", "⭐", "🚀"]
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializar optimizador
        
        Args:
            api_key: API key de YouTube (opcional para algunas funciones)
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
    
    def generate_title_variations(
        self,
        topic: str,
        niche: str = "general",
        include_numbers: bool = True,
        include_question: bool = True,
        max_length: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Generar variaciones de título optimizadas
        
        Args:
            topic: Tema del video
            niche: Nicho del contenido
            include_numbers: Incluir títulos con números
            include_question: Incluir títulos como pregunta
            max_length: Longitud máxima en caracteres
            
        Returns:
            Lista de títulos con score预测
        """
        titles = []
        
        # Títulos con números (listicles)
        if include_numbers:
            for num in [3, 5, 7]:
                power_word = self._get_power_word(niche)
                title = f"{num} {power_word} {topic.capitalize()} Que {self._get_action_phrase(niche)}"
                if len(title) <= max_length:
                    titles.append({
                        "text": title,
                        "type": "numbered_list",
                        "predicted_ctr": self._predict_ctr(title),
                        "length": len(title)
                    })
        
        # Títulos como pregunta
        if include_question:
            question_words = ["Por qué", "Cómo", "Qué pasa si", "Cuándo", "Dónde"]
            for qw in question_words:
                title = f"{qw} {self._generate_question_about(topic, niche)}?"
                if len(title) <= max_length:
                    titles.append({
                        "text": title,
                        "type": "question",
                        "predicted_ctr": self._predict_ctr(title),
                        "length": len(title)
                    })
        
        # Títulos con palabras de poder
        for power_word in self.POWER_WORDS[:5]:
            title = f"La {power_word} {topic.capitalize()} Que {self._get_revelation(niche)}"
            if len(title) <= max_length:
                titles.append({
                    "text": title,
                    "type": "power_word",
                    "predicted_ctr": self._predict_ctr(title),
                    "length": len(title)
                })
        
        # Títulos con resultado/transformación
        transformation_templates = [
            f"Cómo {self._get_result_verb(niche)} en {topic} en 30 Días",
            f"De Cero a Experto en {topic}: Mi Método",
            f"Lo Que Nadie Te Dice Sobre {topic}",
            f"El Secreto de {topic} Que Los Expertos Ocultan"
        ]
        
        for template in transformation_templates:
            if len(template) <= max_length:
                titles.append({
                    "text": template,
                    "type": "transformation",
                    "predicted_ctr": self._predict_ctr(template),
                    "length": len(template)
                })
        
        # Ordenar por CTR预测 más alto
        titles.sort(key=lambda x: x["predicted_ctr"], reverse=True)
        
        return titles[:10]  # Retornar top 10
    
    def generate_description(
        self,
        title: str,
        script: Dict,
        niche: str = "general",
        include_timestamps: bool = True,
        include_links: bool = True
    ) -> str:
        """
        Generar descripción optimizada para SEO
        
        Args:
            title: Título del video
            script: Guión del video
            niche: Nicho del contenido
            include_timestamps: Incluir marcas de tiempo
            include_links: Incluir placeholders para links
            
        Returns:
            Descripción formateada
        """
        description_parts = []
        
        # Primera línea (lo que se ve antes de "mostrar más")
        hook_line = f"🔥 {title}\n\n"
        description_parts.append(hook_line)
        
        # Resumen del video (2-3 líneas)
        summary = self._generate_summary(script, niche)
        description_parts.append(f"{summary}\n\n")
        
        # Timestamps/capítulos
        if include_timestamps and "sections" in script:
            description_parts.append("⏱️ CAPÍTULOS:\n")
            
            # Hook
            hook_time = script.get("hook", {}).get("time", [0, 3])
            description_parts.append(f"0:00 - {script.get('hook', {}).get('text', 'Introducción')[:50]}...\n")
            
            # Secciones
            for i, section in enumerate(script.get("sections", [])):
                start_sec = section.get("time", [0, 0])[0]
                minutes = start_sec // 60
                seconds = start_sec % 60
                time_str = f"{minutes}:{seconds:02d}"
                
                section_name = section.get("name", f"Punto {i+1}")
                description_parts.append(f"{time_str} - {section_name}\n")
            
            # CTA
            cta_time = script.get("cta", {}).get("time", [55, 60])
            if cta_time:
                minutes = cta_time[0] // 60
                seconds = cta_time[0] % 60
                description_parts.append(f"{minutes}:{seconds:02d} - Conclusión y llamado a la acción\n")
            
            description_parts.append("\n")
        
        # Links importantes
        if include_links:
            description_parts.append("🔗 ENLACES IMPORTANTES:\n")
            description_parts.append("→ Suscríbete: [TU_LINK_DE_SUSCRIPCIÓN]\n")
            description_parts.append("→ Sígueme en Instagram: [TU_INSTAGRAM]\n")
            description_parts.append("→ Únete a mi comunidad: [TU_COMUNIDAD]\n\n")
        
        # Hashtags
        hashtags = self._generate_hashtags(niche, topic_from_title=title)
        description_parts.append(f"\n{' '.join(hashtags)}\n")
        
        # Keywords para SEO (ocultas pero indexables)
        seo_keywords = self._generate_seo_keywords(niche, topic_from_title=title)
        description_parts.append(f"\nPalabras clave: {', '.join(seo_keywords)}\n")
        
        return "".join(description_parts)
    
    def generate_tags(self, niche: str, topic: str, competitor_tags: Optional[List[str]] = None) -> List[str]:
        """
        Generar tags optimizados
        
        Args:
            niche: Nicho del contenido
            topic: Tema específico
            competitor_tags: Tags de competidores (opcional)
            
        Returns:
            Lista de tags ordenados por relevancia
        """
        tags = []
        
        # Tags específicos del tema
        tags.append(topic.lower())
        tags.append(f"cómo {topic.lower()}")
        tags.append(f"{topic.lower()} tutorial")
        tags.append(f"{topic.lower()} español")
        tags.append(f"{topic.lower()} 2024")
        
        # Tags de nicho
        niche_tags = {
            "motivational": ["motivación", "éxito", "productividad", "hábitos", "mentalidad", "crecimiento personal"],
            "finance": ["finanzas personales", "inversión", "dinero", "ingresos pasivos", "libertad financiera"],
            "tech": ["tecnología", "inteligencia artificial", "IA", "automatización", "herramientas digitales"],
            "health": ["salud", "bienestar", "fitness", "nutrición", "vida saludable"]
        }
        
        tags.extend(niche_tags.get(niche, [])[:5])
        
        # Tags de competencia si existen
        if competitor_tags:
            tags.extend(competitor_tags[:5])
        
        # Tags generales de YouTube
        general_tags = ["video", "youtube", "tutorial", "consejos", "guía", "tips"]
        tags.extend(general_tags[:3])
        
        # Eliminar duplicados manteniendo orden
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        
        return unique_tags[:20]  # YouTube permite hasta 500 caracteres
    
    def generate_thumbnail_prompt(
        self,
        title: str,
        niche: str = "general",
        style: str = "vibrant"
    ) -> str:
        """
        Generar prompt para crear miniatura con IA
        
        Args:
            title: Título del video
            niche: Nicho del contenido
            style: Estilo visual
            
        Returns:
            Prompt detallado para generación de imagen
        """
        emoji = self.EMOJIS_BY_CATEGORY.get(niche, self.EMOJIS_BY_CATEGORY["general"])[0]
        
        base_prompts = {
            "motivational": "persona exitosa, energía positiva, luz dorada, expresión determinada, fondo inspirador",
            "finance": "símbolos de dinero, gráficos ascendentes, persona confiada, ambiente profesional",
            "tech": "elementos futuristas, luces neón, tecnología avanzada, ambiente digital",
            "health": "persona saludable, naturaleza, colores vibrantes, sensación de bienestar"
        }
        
        base = base_prompts.get(niche, "composición atractiva, colores vibrantes, expresión emocional fuerte")
        
        # Extraer palabras clave del título
        keywords = [word for word in title.split() if len(word) > 4][:3]
        keyword_text = ", ".join(keywords)
        
        prompt = f"YouTube thumbnail, {base}, {keyword_text}, {style} style, high contrast, eye-catching, professional design, trending on youtube, {emoji}, bold text space, rule of thirds, 8k quality"
        
        return prompt
    
    def _get_power_word(self, niche: str) -> str:
        """Obtener palabra de poder según nicho"""
        niche_specific = {
            "motivational": ["Secreto", "Verdad", "Poderoso"],
            "finance": ["Estrategia", "Método", "Sistema"],
            "tech": ["Herramienta", "Tecnología", "Innovación"],
            "health": ["Método", "Secreto", "Técnica"]
        }
        
        options = niche_specific.get(niche, self.POWER_WORDS[:3])
        import random
        return random.choice(options)
    
    def _get_action_phrase(self, niche: str) -> str:
        """Obtener frase de acción según nicho"""
        phrases = {
            "motivational": ["Cambiarán Tu Vida", "Te Harán Exitoso", "Nadie Te Cuenta"],
            "finance": ["Para Hacerte Rico", "Que Los Bancos Ocultan", "Para Multiplicar Tu Dinero"],
            "tech": ["Que Usan Los Expertos", "Para Automatizar Todo", "Del Futuro"],
            "health": ["Para Transformar Tu Cuerpo", "Que Los Doctores Callan", "Para Vivir Más"]
        }
        
        import random
        return random.choice(phrases.get(niche, phrases["motivational"]))
    
    def _get_revelation(self, niche: str) -> str:
        """Obtener frase de revelación"""
        revelations = [
            "Los Expertos Ocultan",
            "Nadie Quiere Que Sepas",
            "Cambia Todo Lo Que Sabías",
            "Que Pocas Personas Conocen"
        ]
        
        import random
        return random.choice(revelations)
    
    def _get_result_verb(self, niche: str) -> str:
        """Verbo de resultado según nicho"""
        verbs = {
            "motivational": ["tener éxito", "ser productivo", "alcanzar tus metas"],
            "finance": ["ganar dinero", "hacerte rico", "generar ingresos"],
            "tech": ["dominar la tecnología", "automatizar tu trabajo", "ser más eficiente"],
            "health": ["perder peso", "ganar músculo", "mejorar tu salud"]
        }
        
        import random
        return random.choice(verbs.get(niche, verbs["motivational"]))
    
    def _generate_question_about(self, topic: str, niche: str) -> str:
        """Generar pregunta sobre el tema"""
        questions = [
            f"funciona realmente {topic}",
            f"puedes empezar con {topic}",
            f"es lo mejor de {topic}",
            f"evitar errores en {topic}",
            f"aprender {topic} rápido"
        ]
        
        import random
        return random.choice(questions)
    
    def _predict_ctr(self, title: str) -> float:
        """Predecir CTR potencial del título (0-100)"""
        score = 50.0  # Base
        
        # Bonus por longitud óptima (45-60 chars)
        if 45 <= len(title) <= 60:
            score += 15
        elif 40 <= len(title) <= 65:
            score += 8
        
        # Bonus por números
        if any(char.isdigit() for char in title):
            score += 10
        
        # Bonus por pregunta
        if "?" in title:
            score += 8
        
        # Bonus por palabras de poder
        if any(word.lower() in title.lower() for word in self.POWER_WORDS):
            score += 12
        
        # Bonus por mayúsculas estratégicas
        words = title.split()
        if sum(1 for w in words if w.isupper()) >= 2:
            score += 5
        
        return min(100, max(0, score))
    
    def _generate_summary(self, script: Dict, niche: str) -> str:
        """Generar resumen del video"""
        hook_text = script.get("hook", {}).get("text", "")[:100]
        
        summary = f"En este video descubrirás {hook_text.lower()}. "
        
        sections = script.get("sections", [])
        if sections:
            summary += f"Analizamos {len(sections)} puntos clave que te ayudarán a entender todo sobre el tema. "
        
        summary += "¡No te pierdas el último consejo porque es el más importante!"
        
        return summary
    
    def _generate_hashtags(self, niche: str, topic_from_title: str = "") -> List[str]:
        """Generar hashtags relevantes"""
        base_hashtags = {
            "motivational": ["#motivación", "#éxito", "#productividad", "#mentalidad", "#crecimiento"],
            "finance": ["#finanzas", "#inversión", "#dinero", "#libertadfinanciera", "#emprendimiento"],
            "tech": ["#tecnología", "#ia", "#inteligenciaartificial", "#innovación", "#futuro"],
            "health": ["#salud", "#bienestar", "#fitness", "#vidasaludable", "#nutrición"]
        }
        
        hashtags = base_hashtags.get(niche, base_hashtags["motivational"])
        
        # Agregar hashtag específico del tema si existe
        if topic_from_title:
            topic_word = topic_from_title.split()[0].lower()
            custom_tag = f"#{topic_word}"
            if custom_tag not in hashtags:
                hashtags.append(custom_tag)
        
        return hashtags[:10]  # YouTube recomienda máximo 15
    
    def _generate_seo_keywords(self, niche: str, topic_from_title: str = "") -> List[str]:
        """Generar keywords para SEO"""
        keywords = []
        
        # Keywords base por nicho
        base_keywords = {
            "motivational": ["motivación", "éxito personal", "desarrollo personal", "superación", "metas"],
            "finance": ["finanzas personales", "educación financiera", "invertir", "ahorrar", "riqueza"],
            "tech": ["tecnología 2024", "herramientas digitales", "automatización", "productividad digital"],
            "health": ["salud integral", "bienestar", "hábitos saludables", "vida fitness"]
        }
        
        keywords.extend(base_keywords.get(niche, base_keywords["motivational"]))
        
        # Agregar variaciones del tema
        if topic_from_title:
            topic_lower = topic_from_title.lower()
            keywords.append(topic_lower)
            keywords.append(f"cómo {topic_lower}")
            keywords.append(f"{topic_lower} tutorial")
        
        return keywords
    
    def optimize_for_shorts(self, script: Dict) -> Dict[str, Any]:
        """
        Optimizar contenido para YouTube Shorts
        
        Args:
            script: Guión original
            
        Returns:
            Configuración optimizada para Shorts
        """
        return {
            "max_duration": 60,
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "title_suggestion": self.generate_title_variations(
                script.get("metadata", {}).get("topic", "Video"),
                max_length=100  # Shorts permiten títulos más largos
            )[0],
            "description_template": f"{script.get('hook', {}).get('text', '')}\n\n#Shorts #Viral",
            "hashtags": ["#Shorts", "#Viral", "#Trending", "#YouTubeShorts"],
            "thumbnail_note": "Seleccionar frame más impactante del video vertical"
        }
