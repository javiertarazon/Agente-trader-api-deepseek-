import asyncio
import aiohttp
from datetime import datetime, timedelta
from config import CRYPTOPANIC_API_KEY, WHALE_ALERT_API_KEY, WHALE_MIN_VALUE

class ImpactMonitor:
    def __init__(self, symbols):
        self.symbols = symbols
        self.news_cache = {}
        self.whale_alerts = []
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession()
        asyncio.create_task(self.monitor_news())
        asyncio.create_task(self.monitor_whales())

    async def monitor_news(self):
        if not CRYPTOPANIC_API_KEY:
            return
        while True:
            try:
                async with self.session.get(
                    f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&public=true"
                ) as resp:
                    data = await resp.json()
                    for post in data.get('results', [])[:20]:
                        self._process_news(post)
            except Exception as e:
                print(f"Error monitoring news: {e}")
            await asyncio.sleep(60)

    async def monitor_whales(self):
        if not WHALE_ALERT_API_KEY:
            return
        while True:
            try:
                async with self.session.get(
                    f"https://api.whale-alert.io/v1/transactions?api_key={WHALE_ALERT_API_KEY}&min_value={WHALE_MIN_VALUE}"
                ) as resp:
                    data = await resp.json()
                    for tx in data.get('transactions', [])[:10]:
                        self._process_whale(tx)
            except Exception as e:
                print(f"Error monitoring whales: {e}")
            await asyncio.sleep(30)

    def _process_news(self, post):
        title = post.get('title', '').lower()
        created = post.get('created_at', '')
        for symbol in self.symbols:
            base = symbol.split('/')[0].lower()
            if base in title:
                sentiment = self._analyze_sentiment(title)
                self.news_cache[symbol] = {
                    'headline': post.get('title'),
                    'sentiment': sentiment,
                    'timestamp': created,
                    'source': post.get('source', {}).get('title', 'unknown')
                }

    def _process_whale(self, tx):
        symbol = tx.get('currency_symbol', '').upper()
        value = tx.get('usd_value', 0)
        for s in self.symbols:
            if symbol in s or (symbol == 'ETH' and 'ETH' in s):
                self.whale_alerts.append({
                    'symbol': s,
                    'value_usd': value,
                    'type': tx.get('transaction_type'),
                    'timestamp': tx.get('timestamp')
                })
        self.whale_alerts = self.whale_alerts[-50:]

    def _analyze_sentiment(self, text):
        positive_words = ['surge', 'moon', 'bullish', 'breakout', 'rally', 'gain']
        negative_words = ['crash', 'dump', 'bearish', 'drop', 'loss', 'sell']
        score = 5
        for word in positive_words:
            if word in text:
                score += 1
        for word in negative_words:
            if word in text:
                score -= 1
        return max(1, min(10, score))

    async def get_impact(self, symbol):
        news = self.news_cache.get(symbol)
        whale = None
        for w in reversed(self.whale_alerts):
            if w['symbol'] == symbol:
                whale = w
                break
        
        impact_score = 5
        reasons = []
        
        if news:
            age = datetime.now() - datetime.fromisoformat(news['timestamp'].replace('Z', '+00:00'))
            if age < timedelta(hours=1):
                impact_score = news['sentiment']
                reasons.append(f"News: {news['headline'][:50]}")
        
        if whale:
            if whale['value_usd'] > 1000000:
                impact_score += 2
                reasons.append(f"Whale alert: ${whale['value_usd']:,.0f}")
        
        return {
            'score': impact_score,
            'reasons': reasons,
            'news': news,
            'whale': whale
        }

    async def close(self):
        if self.session:
            await self.session.close()
