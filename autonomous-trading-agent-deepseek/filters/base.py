from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple

class BasePreFilter(ABC):
    @abstractmethod
    def should_analyze(self, symbol: str, market_data: Dict[str, Any],
                       features_1m: Dict, features_5m: Dict,
                       volume_profile: Dict, order_book: Dict) -> Tuple[bool, str]:
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]):
        pass
