# Video Generator AI - Requisitos e Instalación

## 🎯 Objetivo
Aplicación profesional que genera videos completos a partir de texto con:
- Guión estructurado con ganchos virales
- Voz humana realista (TTS)
- Imágenes/escenarios generados por IA
- Edición automática de escenas
- Análisis de tendencias virales
- Optimización para filtros de YouTube

## 📦 Dependencias Principales

### Core AI
- `openai>=1.0` o `anthropic` - Generación de guiones y análisis viral
- `elevenlabs>=0.2` - Voz humana ultra-realista
- `replicate>=0.20` - Generación de video/imagen (Stable Diffusion, Runway)
- `pillow>=10.0` - Procesamiento de imágenes
- `moviepy>=1.0.3` - Edición de video programática
- `yt-dlp>=2023.0` - Búsqueda de tendencias virales

### Procesamiento
- `numpy>=1.24`
- `pandas>=2.0`
- `requests>=2.31`
- `aiohttp>=3.8`
- `beautifulsoup4>=4.12`

### Audio
- `pydub>=0.25`
- `speechrecognition>=3.10` (opcional)

### Utilidades
- `python-dotenv>=1.0`
- `tqdm>=4.65`
- `colorama>=0.4`

## 🔑 APIs Requeridas

| Servicio | Función | URL Registro | Costo Aproximado |
|----------|---------|--------------|------------------|
| **ElevenLabs** | Voz humana TTS | https://elevenlabs.io | $5-22/mes |
| **OpenAI/DeepSeek** | Guiones + Análisis Viral | https://platform.openai.com o https://platform.deepseek.com | $0.01-0.03/video |
| **Replicate** | Generación Imagen/Video | https://replicate.com | $0.01-0.10/imagen |
| **YouTube Data API** | Búsqueda tendencias | https://console.cloud.google.com | Gratis (hasta 10k queries/día) |
| **Pexels/Pixabay** | Stock footage gratis | https://pexels.com/api | Gratis |

## 🚀 Instalación

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys
```

## 📁 Estructura del Proyecto

```
video-generator/
├── core/
│   ├── __init__.py
│   ├── script_generator.py      # Guiones con ganchos virales
│   ├── voice_synthesizer.py     # TTS con ElevenLabs
│   ├── image_generator.py       # Imágenes con Stable Diffusion
│   ├── video_assembler.py       # Ensamblaje de escenas
│   ├── trend_analyzer.py        # Búsqueda de contenido viral
│   └── youtube_optimizer.py     # Optimización para algoritmo YT
├── scripts/
│   └── generate_video.py        # Script principal CLI
├── prompts/
│   ├── viral_hooks.txt          # Plantillas de ganchos
│   ├── script_structure.txt     # Estructura de guiones
│   └── image_prompts.txt        # Prompts para imágenes
├── assets/
│   ├── fonts/                   # Fuentes para subtítulos
│   ├── music/                   # Música de fondo
│   └── templates/               # Plantillas de edición
├── output/                      # Videos generados
├── temp/                        # Archivos temporales
├── requirements.txt
├── .env.example
└── README.md
```

## 🔧 Configuración (.env)

```ini
# IA de Texto (Guiones)
# Selección de proveedor (openrouter | deepseek | openai | offline)
LLM_PROVIDER=openrouter
LLM_MODEL=deepseek/deepseek-chat
LLM_FALLBACK_MODELS=

# OpenRouter (recomendado para múltiples modelos)
OPENROUTER_API_KEY=sk-xxx
OPENROUTER_HTTP_REFERER=https://tusitio.com  # opcional
OPENROUTER_APP_TITLE=video-generator        # opcional

# DeepSeek / OpenAI (alternativas)
DEEPSEEK_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx

# Voz Humana (TTS)
# Selección de proveedor (elevenlabs | minimax | piper | mock)
TTS_PROVIDER=elevenlabs

# ElevenLabs
ELEVENLABS_API_KEY=xi-xxx
ELEVENLABS_VOICE_ID=rachel

# MiniMax (configura tu endpoint exacto)
MINIMAX_API_KEY=
MINIMAX_TTS_URL=
MINIMAX_VOICE=female-1

# Piper (open source local TTS)
PIPER_BIN=piper
PIPER_MODEL=/ruta/al/model.onnx

# Generación de Imágenes/Video
REPLICATE_API_TOKEN=r8-xxx
STABLE_DIFFUSION_MODEL=stability-ai/sdxl

# YouTube
YOUTUBE_API_KEY=AIzaSyD-xxx

# Stock Footage (Opcional)
PEXELS_API_KEY=xxx

# Configuración
OUTPUT_FORMAT=mp4
RESOLUTION=1920x1080
FPS=30
AUDIO_BITRATE=192k
```

## 🎬 Uso Básico

```bash
# Generar video desde texto
python scripts/generate_video.py \
  --text "La psicología del éxito: 3 hábitos que cambiarán tu vida" \
  --duration 60 \
  --style motivational \
  --voice rachel \
  --output mi_video.mp4

# Analizar tendencias virales
python scripts/generate_video.py \
  --analyze-trends "motivación" \
  --top 10

# Generar con plantilla viral detectada
python scripts/generate_video.py \
  --trend-id "abc123" \
  --custom-text "Mi versión del concepto"
```

## ⚡ Características Clave

### 1. Generación de Guiones Virales
- Detección de patrones en videos virales
- Estructura: Gancho (0-3s) → Problema → Solución → CTA
- Adaptación al nicho específico
- Longitud optimizada para retención

### 2. Voz Ultra-Realista
- 29+ voces humanas disponibles
- Control de emoción, tono y velocidad
- Eliminación de artefactos robóticos
- Sincronización labial (futuro)

### 3. Generación de Escenas
- Imágenes coherentes con el guión
- Transiciones suaves entre escenas
- Estilo visual consistente
- Integración de stock footage cuando aplica

### 4. Edición Automática
- Subtítulos dinámicos
- Música de fondo ajustada
- Efectos de sonido estratégicos
- Branding personalizado (logo, colores)

### 5. Optimización YouTube
- Título SEO-friendly
- Descripción optimizada
- Tags relevantes
- Miniatura generada por IA
- Análisis de probabilidad de viralidad

## 📊 Métricas de Calidad

- **Retención esperada:** >60% en primeros 30s
- **CTR estimado:** >8% con miniatura IA
- **Calidad de voz:** MOS >4.0/5.0
- **Tiempo de generación:** 2-5 minutos por video de 60s

## ⚠️ Consideraciones Legales

- Usar solo música libre de derechos o licenciada
- Respetar derechos de autor de imágenes generadas
- Cumplir políticas de contenido de YouTube
- No generar contenido engañoso o desinformación

## 🔄 Flujo de Trabajo

1. **Input:** Texto o idea del usuario
2. **Análisis Viral:** Búsqueda de tendencias similares
3. **Guión:** Generación con estructura probada
4. **Voz:** Síntesis TTS con voz seleccionada
5. **Imágenes:** Generación escena por escena
6. **Ensamblaje:** Edición automática con MoviePy
7. **Optimización:** Metadatos para YouTube
8. **Output:** Video listo para subir

## 🧪 Pruebas

```bash
pytest tests/ -v
```

## 📈 Roadmap

- [ ] Sincronización labial automática
- [ ] Generación de video completo (no solo imágenes)
- [ ] Multi-idioma automático
- [ ] Integración directa con YouTube upload
- [ ] A/B testing de versiones
- [ ] Analytics post-publicación
