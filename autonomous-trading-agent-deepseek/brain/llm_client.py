import asyncio
import aiohttp
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL
import logging

logger = logging.getLogger("LLMClient")

async def query_deepseek(prompt, max_retries=3):
    """Consultar API de DeepSeek con manejo robusto de errores"""
    if not DEEPSEEK_API_KEY:
        logger.warning("API key no configurada")
        return '{"direction": "wait", "confidence": 0, "reasoning": "API key no configurada"}'
    
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': DEEPSEEK_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.3,
        'max_tokens': 500
    }
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(
                    'https://api.deepseek.com/v1/chat/completions',
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status == 429:  # Rate limit
                        retry_after = int(resp.headers.get('Retry-After', 5))
                        logger.warning(f"Rate limit, esperando {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Error HTTP {resp.status}: {error_text}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Backoff exponencial
                            continue
                        return '{"direction": "wait", "confidence": 0, "reasoning": "Error en API LLM"}'
                    
                    data = await resp.json()
                    
                    if 'choices' not in data or not data['choices']:
                        logger.error("Respuesta inválida de la API")
                        return '{"direction": "wait", "confidence": 0, "reasoning": "Respuesta inválida"}'
                    
                    content = data['choices'][0]['message']['content']
                    logger.debug(f"Respuesta LLM: {content[:100]}...")
                    return content
                    
        except aiohttp.ClientError as e:
            logger.error(f"Error de conexión (intento {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                return '{"direction": "wait", "confidence": 0, "reasoning": "Error de conexión"}'
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout en intento {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                return '{"direction": "wait", "confidence": 0, "reasoning": "Timeout"}'
        
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return '{"direction": "wait", "confidence": 0, "reasoning": "Error interno"}'
    
    return '{"direction": "wait", "confidence": 0, "reasoning": "Max retries exceeded"}'
