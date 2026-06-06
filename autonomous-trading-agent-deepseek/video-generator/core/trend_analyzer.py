"""
Trend Analyzer - Búsqueda y análisis de contenido viral en YouTube
Detecta patrones, ganchos y tendencias para replicar éxitos
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Analizador de tendencias virales en YouTube"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializar analizador de tendencias
        
        Args:
            api_key: API key de YouTube Data API v3
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    def search_viral_videos(
        self,
        query: str,
        niche: str = "general",
        max_results: int = 10,
        publish_after: Optional[str] = None,
        min_views: int = 100000,
        sort_by: str = "relevance"
    ) -> Dict[str, Any]:
        """
        Buscar videos virales por tema
        
        Args:
            query: Término de búsqueda
            niche: Nicho (motivational, finance, tech, health)
            max_results: Cantidad máxima de resultados
            publish_after: Fecha mínima de publicación (YYYY-MM-DD)
            min_views: Vistas mínimas para considerar viral
            sort_by: Ordenamiento (relevance, date, viewCount, rating)
            
        Returns:
            Lista de videos virales con metadata
        """
        result = {
            "success": False,
            "videos": [],
            "patterns": {},
            "error": None
        }
        
        if not self.api_key:
            result["error"] = "YouTube API key no configurada"
            return self._offline_trend_analysis(query, niche, max_results)
        
        try:
            import requests
            
            # Calcular fecha (últimos 3 meses por defecto)
            if not publish_after:
                publish_after = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")
            else:
                publish_after = f"{publish_after}T00:00:00Z"
            
            # Búsqueda inicial
            search_url = f"{self.base_url}/search"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": sort_by,
                "publishedAfter": publish_after,
                "maxResults": min(max_results * 2, 50),  # Pedir más para filtrar después
                "key": self.api_key
            }
            
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            search_data = response.json()
            
            # Obtener IDs de videos
            video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]
            
            if not video_ids:
                result["error"] = "No se encontraron videos"
                return result
            
            # Obtener estadísticas detalladas
            stats_url = f"{self.base_url}/videos"
            stats_params = {
                "part": "statistics,snippet",
                "id": ",".join(video_ids),
                "key": self.api_key
            }
            
            stats_response = requests.get(stats_url, params=stats_params)
            stats_response.raise_for_status()
            stats_data = stats_response.json()
            
            # Filtrar por vistas mínimas y procesar
            viral_videos = []
            
            for item in stats_data.get("items", []):
                stats = item.get("statistics", {})
                view_count = int(stats.get("viewCount", 0))
                
                if view_count >= min_views:
                    video_info = {
                        "id": item["id"],
                        "title": item["snippet"]["title"],
                        "description": item["snippet"]["description"][:500],
                        "channel": item["snippet"]["channelTitle"],
                        "published_at": item["snippet"]["publishedAt"],
                        "views": view_count,
                        "likes": int(stats.get("likeCount", 0)),
                        "comments": int(stats.get("commentCount", 0)),
                        "engagement_rate": self._calculate_engagement(
                            view_count,
                            int(stats.get("likeCount", 0)),
                            int(stats.get("commentCount", 0))
                        ),
                        "thumbnail": item["snippet"]["thumbnails"]["high"]["url"]
                    }
                    
                    viral_videos.append(video_info)
            
            # Ordenar por engagement rate
            viral_videos.sort(key=lambda x: x["engagement_rate"], reverse=True)
            
            # Limitar a max_results
            result["videos"] = viral_videos[:max_results]
            result["success"] = True
            
            # Analizar patrones comunes
            result["patterns"] = self._analyze_patterns(result["videos"])
            
            logger.info(f"Encontrados {len(result['videos'])} videos virales")
            
        except Exception as e:
            logger.error(f"Error buscando videos virales: {e}")
            result["error"] = str(e)
        
        return result
    
    def _calculate_engagement(self, views: int, likes: int, comments: int) -> float:
        """Calcular tasa de engagement"""
        if views == 0:
            return 0
        return ((likes + comments * 2) / views) * 100
    
    def _analyze_patterns(self, videos: List[Dict]) -> Dict[str, Any]:
        """Analizar patrones comunes en videos virales"""
        patterns = {
            "avg_duration_estimate": 0,
            "common_keywords": [],
            "hook_patterns": [],
            "title_patterns": [],
            "thumbnail_colors": [],
            "best_publish_times": [],
            "avg_title_length": 0
        }
        
        if not videos:
            return patterns
        
        # Analizar títulos
        titles = [v["title"] for v in videos]
        patterns["avg_title_length"] = sum(len(t) for t in titles) / len(titles)
        
        # Extraer primeras palabras (ganchos potenciales)
        first_words = []
        for title in titles:
            words = title.split()[:4]
            first_words.extend(words)
        
        # Palabras más comunes en ganchos
        from collections import Counter
        word_counts = Counter(first_words)
        patterns["hook_patterns"] = [word for word, count in word_counts.most_common(5)]
        
        # Palabras clave comunes en todo el título
        all_words = []
        for title in titles:
            all_words.extend(title.lower().split())
        
        # Filtrar palabras vacías
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "how", "what", "why", "when", "where", "this", "that", "these", "those", "is", "are", "was", "were", "be", "been", "being"}
        filtered_words = [w for w in all_words if w not in stop_words and len(w) > 3]
        
        word_counts = Counter(filtered_words)
        patterns["common_keywords"] = [word for word, count in word_counts.most_common(10)]
        
        # Patrones de títulos observados
        title_templates = []
        for title in titles:
            if "?" in title:
                title_templates.append("question")
            elif ":" in title:
                title_templates.append("colon_split")
            elif any(char.isdigit() for char in title):
                title_templates.append("numbered_list")
            elif "!" in title:
                title_templates.append("exclamation")
            else:
                title_templates.append("statement")
        
        patterns["title_patterns"] = dict(Counter(title_templates))
        
        return patterns
    
    def _offline_trend_analysis(
        self,
        query: str,
        niche: str,
        max_results: int
    ) -> Dict[str, Any]:
        """Análisis offline sin API key"""
        
        # Patrones genéricos basados en nicho
        niche_patterns = {
            "motivational": {
                "hooks": ["El secreto que", "Nadie te dice", "Por qué fracasas", "La verdad sobre"],
                "keywords": ["éxito", "hábitos", "mentalidad", "productividad", "motivación"]
            },
            "finance": {
                "hooks": ["Cómo gané", "El error que", "Invierte como", "Los ricos saben"],
                "keywords": ["dinero", "inversión", "ingresos", "riqueza", "finanzas"]
            },
            "tech": {
                "hooks": ["Esta IA va", "El futuro es", "Reemplazará a", "Nadie está listo"],
                "keywords": ["inteligencia artificial", "tecnología", "futuro", "automatización"]
            },
            "health": {
                "hooks": ["Los doctores ocultan", "Perdí peso", "Cura natural", "Ciencia confirma"],
                "keywords": ["salud", "peso", "dieta", "ejercicio", "bienestar"]
            }
        }
        
        patterns = niche_patterns.get(niche, niche_patterns["motivational"])
        
        result = {
            "success": True,
            "videos": [],
            "patterns": {
                "hook_patterns": patterns["hooks"],
                "common_keywords": patterns["keywords"],
                "title_patterns": {"numbered_list": 3, "question": 2, "statement": 1},
                "avg_title_length": 55,
                "recommendations": [
                    "Usa números en títulos (3, 5, 7)",
                    "Incluye preguntas provocativas",
                    "Palabras de poder: secreto, verdad, nadie, increíble",
                    "Títulos entre 45-65 caracteres"
                ]
            },
            "note": "Análisis offline basado en patrones conocidos. Configura YouTube API para datos reales."
        }
        
        return result
    
    def analyze_competitor_channel(
        self,
        channel_id: str,
        max_videos: int = 20
    ) -> Dict[str, Any]:
        """
        Analizar canal competidor
        
        Args:
            channel_id: ID del canal de YouTube
            max_videos: Cantidad de videos a analizar
            
        Returns:
            Análisis del canal
        """
        result = {
            "success": False,
            "channel_info": {},
            "top_videos": [],
            "avg_performance": {},
            "error": None
        }
        
        if not self.api_key:
            result["error"] = "YouTube API key requerida"
            return result
        
        try:
            import requests
            
            # Obtener info del canal
            channel_url = f"{self.base_url}/channels"
            channel_params = {
                "part": "snippet,statistics",
                "id": channel_id,
                "key": self.api_key
            }
            
            channel_response = requests.get(channel_url, params=channel_params)
            channel_data = channel_response.json()
            
            if not channel_data.get("items"):
                result["error"] = "Canal no encontrado"
                return result
            
            channel_item = channel_data["items"][0]
            result["channel_info"] = {
                "name": channel_item["snippet"]["title"],
                "subscribers": channel_item["statistics"].get("subscriberCount", "N/A"),
                "total_views": channel_item["statistics"].get("viewCount", 0),
                "video_count": channel_item["statistics"].get("videoCount", 0)
            }
            
            # Obtener videos del canal
            search_url = f"{self.base_url}/search"
            search_params = {
                "part": "snippet",
                "channelId": channel_id,
                "order": "date",
                "type": "video",
                "maxResults": min(max_videos, 50),
                "key": self.api_key
            }
            
            search_response = requests.get(search_url, params=search_params)
            search_data = search_response.json()
            
            video_ids = [item["id"]["videoId"] for item in search_data.get("items", [])]
            
            if video_ids:
                # Obtener estadísticas
                stats_url = f"{self.base_url}/videos"
                stats_params = {
                    "part": "statistics",
                    "id": ",".join(video_ids),
                    "key": self.api_key
                }
                
                stats_response = requests.get(stats_url, params=stats_params)
                stats_data = stats_response.json()
                
                # Procesar videos
                for item in stats_data.get("items", []):
                    stats = item.get("statistics", {})
                    result["top_videos"].append({
                        "id": item["id"],
                        "views": int(stats.get("viewCount", 0)),
                        "likes": int(stats.get("likeCount", 0)),
                        "comments": int(stats.get("commentCount", 0))
                    })
                
                # Calcular promedios
                if result["top_videos"]:
                    total_views = sum(v["views"] for v in result["top_videos"])
                    total_likes = sum(v["likes"] for v in result["top_videos"])
                    
                    result["avg_performance"] = {
                        "avg_views": total_views / len(result["top_videos"]),
                        "avg_likes": total_likes / len(result["top_videos"]),
                        "avg_engagement": self._calculate_engagement(
                            total_views, total_likes,
                            sum(v["comments"] for v in result["top_videos"])
                        )
                    }
                
                result["success"] = True
                
        except Exception as e:
            logger.error(f"Error analizando canal: {e}")
            result["error"] = str(e)
        
        return result
    
    def get_trending_topics(self, category: str = "all") -> List[str]:
        """Obtener temas trending actuales"""
        # Implementación futura con YouTube Trends API
        trending_by_category = {
            "motivational": [
                "disciplina matutina",
                "hábitos de millonarios",
                "productividad extrema",
                "mentalidad de éxito"
            ],
            "finance": [
                "ingresos pasivos 2024",
                "invertir desde cero",
                "criptomonedas principiantes",
                "libertad financiera"
            ],
            "tech": [
                "herramientas IA 2024",
                "automatización negocios",
                "chatgpt trucos",
                "tecnología futurista"
            ]
        }
        
        return trending_by_category.get(category, [])
