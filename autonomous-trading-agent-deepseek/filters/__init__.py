from .base import BasePreFilter
from .technical import TechnicalFilter
from .quantitative import QuantitativeFilter
from .price_action import PriceActionFilter
from .probabilistic import ProbabilisticFilter
from .volume_sentiment import VolumeSentimentFilter
from .composite import CompositeFilter

FILTER_REGISTRY = {
    'technical': TechnicalFilter,
    'quantitative': QuantitativeFilter,
    'price_action': PriceActionFilter,
    'probabilistic': ProbabilisticFilter,
    'volume_sentiment': VolumeSentimentFilter,
    'composite': CompositeFilter,
}

def load_filter(name: str, **kwargs) -> BasePreFilter:
    cls = FILTER_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Filtro desconocido: {name}")
    return cls(**kwargs)

def list_filters():
    return list(FILTER_REGISTRY.keys())
