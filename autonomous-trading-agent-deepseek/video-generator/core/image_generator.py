"""
Image Generator - Generación de imágenes y escenarios con IA
Usa Stable Diffusion vía Replicate para crear visuales coherentes
"""

import os
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ImageGenerator:
    """Generador de imágenes con Stable Diffusion vía Replicate"""
    
    # Estilos visuales predefinidos
    VISUAL_STYLES = {
        "cinematic": "cinematic lighting, dramatic shadows, film grain, 35mm, professional photography",
        "minimalist": "clean, minimal, white background, simple composition, modern design",
        "vibrant": "vibrant colors, high saturation, energetic, dynamic lighting, bold",
        "dark": "dark mood, low key lighting, mysterious, shadows, noir aesthetic",
        "professional": "corporate style, clean, professional lighting, business aesthetic",
        "artistic": "painterly style, artistic composition, creative lighting, gallery quality",
        "motivational": "uplifting, bright, inspiring, golden hour, positive energy",
        "tech": "futuristic, neon accents, high-tech, digital aesthetic, cyberpunk elements"
    }
    
    # Prompts base por tipo de escena
    SCENE_PROMPTS = {
        "hook": "powerful visual metaphor, attention-grabbing composition, bold statement",
        "problem": "visual representation of struggle, challenge, obstacle, dramatic tension",
        "solution": "light at end of tunnel, breakthrough moment, clarity, resolution",
        "example": "practical demonstration, real-world application, clear illustration",
        "proof": "evidence, data visualization, testimonial imagery, credibility markers",
        "cta": "call to action visual, arrow pointing, button-like composition, urgency"
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "stability-ai/sdxl",
        default_style: str = "cinematic"
    ):
        """
        Inicializar generador de imágenes
        
        Args:
            api_key: API key de Replicate
            model: Modelo de Stable Diffusion
            default_style: Estilo visual por defecto
        """
        self.api_key = api_key or os.getenv("REPLICATE_API_TOKEN")
        self.model = model
        self.default_style = default_style
        self.client = None
        
        if self.api_key:
            self._initialize_client()
    
    def _initialize_client(self):
        """Inicializar cliente de Replicate"""
        try:
            import replicate
            os.environ["REPLICATE_API_TOKEN"] = self.api_key
            self.client = replicate
            logger.info(f"Replicate inicializado con modelo: {self.model}")
        except ImportError:
            logger.warning("Replicate no instalado. pip install replicate")
            self.client = None
        except Exception as e:
            logger.error(f"Error inicializando Replicate: {e}")
            self.client = None
    
    def generate_image(
        self,
        prompt: str,
        output_path: Optional[str] = None,
        style: Optional[str] = None,
        negative_prompt: str = "blurry, low quality, distorted, ugly, deformed, watermark, text",
        width: int = 1920,
        height: int = 1080,
        num_outputs: int = 1,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 50
    ) -> Dict[str, Any]:
        """
        Generar imagen desde prompt
        
        Args:
            prompt: Descripción de la imagen
            output_path: Ruta para guardar (opcional)
            style: Estilo visual a aplicar
            negative_prompt: Lo que queremos evitar
            width: Ancho en píxeles
            height: Alto en píxeles
            num_outputs: Cantidad de variantes
            guidance_scale: Qué tanto seguir el prompt (1-20)
            num_inference_steps: Calidad (más = mejor pero más lento)
            
        Returns:
            Diccionario con resultado
        """
        result = {
            "success": False,
            "image_paths": [],
            "image_urls": [],
            "error": None
        }
        
        # Construir prompt completo
        style_modifier = self.VISUAL_STYLES.get(style or self.default_style, "")
        full_prompt = f"{prompt}, {style_modifier}"
        
        if not self.client:
            # Modo offline: generar placeholder local para no romper el pipeline.
            try:
                if output_path:
                    from PIL import Image, ImageDraw, ImageFont

                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    img = Image.new("RGB", (width, height), color=(20, 20, 20))
                    draw = ImageDraw.Draw(img)
                    text = (prompt[:120] + "...") if len(prompt) > 120 else prompt
                    draw.text((40, 40), "OFFLINE PLACEHOLDER", fill=(255, 255, 255))
                    draw.text((40, 100), text, fill=(220, 220, 220))
                    img.save(output_path, format="JPEG", quality=85)
                    result["image_paths"].append(output_path)
                    result["success"] = True
                    return result
            except Exception as e:
                result["error"] = f"Replicate no configurado y falló placeholder: {e}"
                return result

            result["error"] = "Replicate no configurado. Agrega tu API key en .env"
            return result
        
        try:
            # Generar con Stable Diffusion XL
            output = self.client.run(
                self.model,
                input={
                    "prompt": full_prompt,
                    "negative_prompt": negative_prompt,
                    "width": width,
                    "height": height,
                    "num_outputs": num_outputs,
                    "guidance_scale": guidance_scale,
                    "num_inference_steps": num_inference_steps,
                    "scheduler": "DPMSolverMultistep"
                }
            )
            
            # Procesar resultados
            for i, image_url in enumerate(output):
                result["image_urls"].append(image_url)
                
                if output_path:
                    # Descargar y guardar
                    import requests
                    img_data = requests.get(image_url).content
                    
                    if num_outputs == 1:
                        save_path = output_path
                    else:
                        base, ext = os.path.splitext(output_path)
                        save_path = f"{base}_{i}{ext}"
                    
                    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(save_path, "wb") as f:
                        f.write(img_data)
                    
                    result["image_paths"].append(save_path)
                    logger.info(f"Imagen guardada en: {save_path}")
            
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Error generando imagen: {e}")
            result["error"] = str(e)
        
        return result
    
    def generate_scene_images(
        self,
        script: Dict,
        output_dir: str = "temp/images",
        style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generar imágenes para cada escena del guión
        
        Args:
            script: Guión estructurado
            output_dir: Directorio de salida
            style: Estilo visual
            
        Returns:
            Diccionario con imágenes por escena
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        result = {
            "success": True,
            "scenes": {},
            "errors": []
        }
        
        # Generar para hook
        if "hook" in script:
            hook_text = script["hook"].get("text", "")[:100]
            hook_visual = script["hook"].get("visual_cue", "")
            
            prompt = f"{self.SCENE_PROMPTS['hook']}, {hook_visual or hook_text}"
            
            output_path = os.path.join(output_dir, "00_hook.jpg")
            img_result = self.generate_image(prompt, output_path, style)
            
            if img_result["success"]:
                result["scenes"]["hook"] = img_result
            else:
                result["errors"].append(f"Hook: {img_result.get('error')}")
                result["success"] = False
        
        # Generar para cada sección
        for i, section in enumerate(script.get("sections", []), 1):
            section_name = section.get("name", f"section_{i}").lower().replace(" ", "_")
            section_text = section.get("text", "")[:150]
            section_visual = section.get("visual_cue", "")
            
            scene_type = self._detect_scene_type(section_name)
            base_prompt = self.SCENE_PROMPTS.get(scene_type, section_text)
            
            prompt = f"{base_prompt}, {section_visual or section_text}"
            
            output_path = os.path.join(output_dir, f"{i:02d}_{section_name}.jpg")
            img_result = self.generate_image(prompt, output_path, style)
            
            if img_result["success"]:
                result["scenes"][section_name] = img_result
            else:
                result["errors"].append(f"{section_name}: {img_result.get('error')}")
        
        # Generar para CTA
        if "cta" in script:
            cta_text = script["cta"].get("text", "")[:100]
            cta_visual = script["cta"].get("visual_cue", "")
            
            prompt = f"{self.SCENE_PROMPTS['cta']}, {cta_visual or cta_text}"
            
            output_path = os.path.join(output_dir, "99_cta.jpg")
            img_result = self.generate_image(prompt, output_path, style)
            
            if img_result["success"]:
                result["scenes"]["cta"] = img_result
            else:
                result["errors"].append(f"CTA: {img_result.get('error')}")
                result["success"] = False
        
        return result
    
    def _detect_scene_type(self, section_name: str) -> str:
        """Detectar tipo de escena basado en nombre"""
        name_lower = section_name.lower()
        
        if any(word in name_lower for word in ["problem", "challenge", "obstacle"]):
            return "problem"
        elif any(word in name_lower for word in ["solution", "answer", "fix"]):
            return "solution"
        elif any(word in name_lower for word in ["example", "demonstration"]):
            return "example"
        elif any(word in name_lower for word in ["proof", "evidence", "result"]):
            return "proof"
        else:
            return "hook"  # Default
    
    def create_thumbnail(
        self,
        title: str,
        subtitle: str = "",
        style: str = "vibrant",
        output_path: str = "output/thumbnail.jpg"
    ) -> Dict[str, Any]:
        """
        Crear miniatura atractiva para YouTube
        
        Args:
            title: Título principal (corto, <30 chars)
            subtitle: Subtítulo opcional
            style: Estilo visual
            output_path: Ruta de salida
            
        Returns:
            Resultado de generación
        """
        # Prompt optimizado para miniaturas
        prompt = f"YouTube thumbnail, {title}, eye-catching, high contrast, professional design, trending on youtube"
        
        result = self.generate_image(
            prompt=prompt,
            output_path=output_path,
            style=style,
            width=1280,
            height=720,
            guidance_scale=9,
            num_inference_steps=60
        )
        
        # Añadir texto a la imagen (requiere PIL)
        if result["success"] and result["image_paths"]:
            try:
                from PIL import Image, ImageDraw, ImageFont
                
                img = Image.open(result["image_paths"][0])
                draw = ImageDraw.Draw(img)
                
                # Intentar cargar fuente grande
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
                    small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
                except:
                    font = ImageFont.load_default()
                    small_font = font
                
                # Sombra para mejor legibilidad
                shadow_offset = 3
                
                # Dibujar título
                bbox = draw.textbbox((0, 0), title, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                x = (img.width - text_width) // 2
                y = img.height // 2 - text_height
                
                # Sombra
                draw.text((x+shadow_offset, y+shadow_offset), title, fill="black", font=font)
                # Texto principal
                draw.text((x, y), title, fill="white", font=font)
                
                # Subtítulo si existe
                if subtitle:
                    bbox = draw.textbbox((0, 0), subtitle, font=small_font)
                    text_width = bbox[2] - bbox[0]
                    x = (img.width - text_width) // 2
                    
                    draw.text((x+shadow_offset, y+text_height+shadow_offset), subtitle, fill="black", font=small_font)
                    draw.text((x, y+text_height), subtitle, fill="yellow", font=small_font)
                
                img.save(result["image_paths"][0])
                logger.info("Texto añadido a miniatura")
                
            except Exception as e:
                logger.warning(f"No se pudo añadir texto a miniatura: {e}")
        
        return result
    
    def get_stock_image(
        self,
        query: str,
        provider: str = "pexels",
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Buscar imagen de stock gratuita
        
        Args:
            query: Término de búsqueda
            provider: Proveedor (pexels, pixabay)
            output_path: Ruta para guardar
            
        Returns:
            Resultado con URL o path
        """
        result = {
            "success": False,
            "image_url": None,
            "image_path": None,
            "error": None
        }
        
        api_key = os.getenv(f"{provider.upper()}_API_KEY")
        
        if not api_key:
            result["error"] = f"API key de {provider} no configurada"
            return result
        
        try:
            import requests
            
            if provider == "pexels":
                url = "https://api.pexels.com/v1/search"
                headers = {"Authorization": api_key}
                params = {"query": query, "per_page": 1, "orientation": "landscape"}
                
                response = requests.get(url, headers=headers, params=params)
                data = response.json()
                
                if data.get("photos"):
                    photo = data["photos"][0]
                    result["image_url"] = photo["src"]["large2x"]
            
            elif provider == "pixabay":
                url = "https://pixabay.com/api/"
                params = {
                    "key": api_key,
                    "q": query,
                    "image_type": "photo",
                    "orientation": "horizontal",
                    "per_page": 1
                }
                
                response = requests.get(url, params=params)
                data = response.json()
                
                if data.get("hits"):
                    photo = data["hits"][0]
                    result["image_url"] = photo["largeImageURL"]
            
            # Descargar si hay URL
            if result["image_url"] and output_path:
                img_data = requests.get(result["image_url"]).content
                
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, "wb") as f:
                    f.write(img_data)
                
                result["image_path"] = output_path
                result["success"] = True
                logger.info(f"Stock image guardada en: {output_path}")
            
        except Exception as e:
            logger.error(f"Error buscando stock image: {e}")
            result["error"] = str(e)
        
        return result
