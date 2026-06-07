#!/usr/bin/env python3
"""
Video Generator AI - Script Principal CLI
Genera videos completos desde texto con IA: guión, voz, imágenes y edición
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Asegurar imports desde el root del proyecto aunque se ejecute desde otro CWD
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VideoGenerator")


async def generate_video(
    text: str,
    duration: int = 60,
    style: str = "motivational",
    voice: str = "rachel",
    visual_style: str = "cinematic",
    output_name: str = None,
    add_music: bool = True,
    add_subtitles: bool = True,
    analyze_trends: bool = True,
    dry_run: bool = False
):
    """
    Generar video completo desde texto
    
    Args:
        text: Texto o tema del video
        duration: Duración en segundos
        style: Estilo/nicho (motivational, finance, tech, health)
        voice: Voz para narración
        visual_style: Estilo visual para imágenes
        output_name: Nombre del archivo de salida
        add_music: Añadir música de fondo
        add_subtitles: Añadir subtítulos
        analyze_trends: Analizar tendencias virales primero
    """
    
    logger.info("=" * 60)
    logger.info("🎬 VIDEO GENERATOR AI - Iniciando generación")
    logger.info("=" * 60)
    
    # Importar módulos core
    from core.script_generator import ScriptGenerator
    from core.voice_synthesizer import VoiceSynthesizer
    from core.image_generator import ImageGenerator
    from core.video_assembler import VideoAssembler
    from core.trend_analyzer import TrendAnalyzer
    from core.youtube_optimizer import YouTubeOptimizer
    
    # Inicializar componentes
    logger.info("\n📝 Paso 1/6: Inicializando generador de guiones...")
    script_gen = ScriptGenerator()
    
    # Analizar tendencias si se solicita
    viral_patterns = None
    if analyze_trends:
        logger.info("🔍 Analizando tendencias virales...")
        trend_analyzer = TrendAnalyzer()
        trends_result = trend_analyzer.search_viral_videos(text, niche=style, max_results=5)
        
        if trends_result.get("patterns"):
            viral_patterns = trends_result["patterns"]
            logger.info(f"✅ Patrones detectados: {viral_patterns.get('hook_patterns', [])}")
    
    # Generar guión
    logger.info("\n✍️  Paso 2/6: Generando guión viral...")
    script = script_gen.generate_script(
        topic=text,
        duration_seconds=duration,
        niche=style,
        include_visual_cues=True,
        viral_patterns=viral_patterns
    )
    
    viral_score = script.get("metadata", {}).get("viral_score", 0)
    word_count = script.get("metadata", {}).get("estimated_words", 0)
    logger.info(f"✅ Guión generado: {word_count} palabras, Score Viral: {viral_score:.0f}/100")
    
    # Exportar guión a markdown para revisión
    script_md = script_gen.export_to_format(script, "markdown")
    script_path = "temp/script.md"
    Path(script_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_md)
    logger.info(f"📄 Guión guardado en: {script_path}")
    
    # Generar audio
    logger.info("\n🎙️  Paso 3/6: Generando narración con voz humana...")
    voice_synth = VoiceSynthesizer(voice_id=voice)
    
    audio_result = voice_synth.generate_from_script(script, output_dir="temp/audio")
    
    if not audio_result.get("success"):
        logger.error(f"❌ Error generando audio: {audio_result.get('errors', [])}")
        return None
    
    audio_files = audio_result.get("audio_files", [])
    total_duration = audio_result.get("total_duration", 0)
    logger.info(f"✅ Audio generado: {len(audio_files)} segmentos, {total_duration:.1f}s total")
    
    # Generar imágenes
    logger.info("\n🎨 Paso 4/6: Generando imágenes para cada escena...")
    image_gen = ImageGenerator(default_style=visual_style)
    
    image_result = image_gen.generate_scene_images(script, output_dir="temp/images")
    
    if not image_result.get("success"):
        logger.warning(f"⚠️  Algunas imágenes fallaron: {image_result.get('errors', [])}")
    
    image_files = []
    for scene_name, scene_data in image_result.get("scenes", {}).items():
        image_files.extend(scene_data.get("image_paths", []))
    
    logger.info(f"✅ Imágenes generadas: {len(image_files)} escenas")
    
    # Ordenar archivos por nombre para asegurar sincronización
    audio_files.sort()
    image_files.sort()
    
    # Ensamblar video
    logger.info("\n🎬 Paso 5/6: Ensamblando video final...")
    assembler = VideoAssembler()
    
    # Determinar ruta de salida
    if not output_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = text[:30].replace(" ", "_").replace("/", "_")
        output_name = f"output/video_{safe_topic}_{timestamp}.mp4"
    
    if dry_run:
        logger.info("🧪 Dry-run activo: omitiendo ensamblaje de video")
        video_result = {"success": True, "duration": total_duration, "video_path": None}
    else:
        video_result = assembler.assemble_video(
            script=script,
            audio_files=audio_files,
            image_files=image_files,
            output_path=output_name,
            background_music=None,  # Se puede agregar música después
            music_volume=0.15 if add_music else 0,
            add_subtitles=add_subtitles
        )
        
        if not video_result.get("success"):
            logger.error(f"❌ Error ensamblando video: {video_result.get('error')}")
            return None
        
        logger.info(f"✅ Video ensamblado: {output_name}")
        logger.info(f"📊 Duración final: {video_result.get('duration', 0):.2f}s")
    
    # Optimizar para YouTube
    logger.info("\n📈 Paso 6/6: Generando optimización para YouTube...")
    optimizer = YouTubeOptimizer()
    
    # Generar títulos optimizados
    title_variations = optimizer.generate_title_variations(text, niche=style)
    best_title = title_variations[0] if title_variations else {"text": text}
    
    # Generar descripción
    description = optimizer.generate_description(best_title["text"], script, niche=style)
    
    # Generar tags
    tags = optimizer.generate_tags(style, text)
    
    # Guardar metadata de YouTube
    metadata = {
        "title": best_title["text"],
        "title_variations": [t["text"] for t in title_variations[:5]],
        "description": description,
        "tags": tags,
        "predicted_ctr": best_title.get("predicted_ctr", 0),
        "thumbnail_prompt": optimizer.generate_thumbnail_prompt(best_title["text"], style),
        "category": style,
        "language": "es"
    }
    
    metadata_path = output_name.replace(".mp4", "_metadata.txt")
    Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("📺 YOUTUBE OPTIMIZATION DATA\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"TÍTULO RECOMENDADO ({best_title.get('predicted_ctr', 0):.0f}% CTR预测):\n")
        f.write(f"{metadata['title']}\n\n")
        f.write("OTRAS OPCIONES:\n")
        for i, title in enumerate(metadata['title_variations'][1:], 2):
            f.write(f"{i}. {title}\n")
        f.write(f"\nDESCRIPCIÓN:\n{metadata['description']}\n")
        f.write(f"\nTAGS: {', '.join(tags)}\n")
        f.write(f"\nPROMPT PARA MINIATURA:\n{metadata['thumbnail_prompt']}\n")
    
    logger.info(f"✅ Metadata guardada en: {metadata_path}")
    
    # Resumen final
    logger.info("\n" + "=" * 60)
    logger.info("🎉 ¡VIDEO GENERADO EXITOSAMENTE!")
    logger.info("=" * 60)
    logger.info(f"📁 Archivo: {output_name}")
    logger.info(f"⏱️  Duración: {video_result.get('duration', 0):.2f}s")
    logger.info(f"🎯 Título recomendado: {best_title['text']}")
    logger.info(f"📊 CTR预测: {best_title.get('predicted_ctr', 0):.0f}%")
    logger.info(f"🔥 Score Viral: {viral_score:.0f}/100")
    logger.info("=" * 60)
    
    return {
        "video_path": output_name,
        "metadata_path": metadata_path,
        "script_path": script_path,
        "duration": video_result.get("duration", 0),
        "viral_score": viral_score,
        "predicted_ctr": best_title.get("predicted_ctr", 0)
    }


def main():
    parser = argparse.ArgumentParser(
        description="🎬 Video Generator AI - Crea videos profesionales desde texto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  %(prog)s --text "3 hábitos matutinos para el éxito" --duration 60
  %(prog)s --text "Cómo invertir en cripto desde cero" --style finance --voice adam
  %(prog)s --text "IA que reemplazará trabajos" --style tech --visual-style futuristic
        """
    )
    
    parser.add_argument(
        "--text", "-t",
        required=True,
        help="Texto o tema del video a generar"
    )
    
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=60,
        help="Duración del video en segundos (default: 60)"
    )
    
    parser.add_argument(
        "--style", "-s",
        choices=["motivational", "finance", "tech", "health", "general"],
        default="motivational",
        help="Estilo/nicho del contenido (default: motivational)"
    )
    
    parser.add_argument(
        "--voice", "-v",
        choices=["rachel", "adam", "antoni", "emma", "josh", "arnold"],
        default="rachel",
        help="Voz para narración (default: rachel)"
    )
    
    parser.add_argument(
        "--visual-style",
        choices=["cinematic", "minimalist", "vibrant", "dark", "professional", "artistic", "motivational", "tech"],
        default="cinematic",
        help="Estilo visual para imágenes (default: cinematic)"
    )
    
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Nombre del archivo de salida (default: auto-generado)"
    )
    
    parser.add_argument(
        "--no-music",
        action="store_true",
        help="No añadir música de fondo"
    )
    
    parser.add_argument(
        "--no-subtitles",
        action="store_true",
        help="No añadir subtítulos automáticos"
    )
    
    parser.add_argument(
        "--no-trends",
        action="store_true",
        help="No analizar tendencias virales"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecuta hasta guión/voz/imágenes pero NO ensambla el video"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar logs detallados"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Ejecutar generación
    result = asyncio.run(generate_video(
        text=args.text,
        duration=args.duration,
        style=args.style,
        voice=args.voice,
        visual_style=args.visual_style,
        output_name=args.output,
        add_music=not args.no_music,
        add_subtitles=not args.no_subtitles,
        analyze_trends=not args.no_trends,
        dry_run=args.dry_run
    ))
    
    # Retornar código de salida apropiado
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
