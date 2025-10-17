"""
Rate Limiter para APIs do iFood
Previne bloqueios 429 (Too Many Requests)

USO:
    from rate_limiter import limiter
    
    @limiter.limit("catalog")
    def minha_funcao():
        # faz requisição à API
"""

import time
from threading import Lock
from functools import wraps
from typing import Callable, Tuple, Dict, List


class GlobalRateLimiter:
    """
    Controla taxa de requisições por categoria de endpoint.
    
    Baseado nos limites oficiais do iFood:
    https://developer.ifood.com.br/en-US/docs/rate-limit/
    """
    
    # Limites: (max_requisicoes, periodo_em_segundos)
    LIMITS: Dict[str, Tuple[int, int]] = {
        "catalog": (3000, 60),     # 3.000 req/min (GET/PATCH itens)
        "reviews": (2000, 60),     # 2.000 req/min (GET/POST reviews)
        "auth": (20, 60),          # 20 req/min (POST /oauth/token)
        "merchant": (300, 60),     # 300 req/min (GET merchant info)
        "image": (15000, 60),      # 15.000 req/min (upload imagens)
    }
    
    def __init__(self):
        self.calls: Dict[str, List[float]] = {k: [] for k in self.LIMITS}
        self.locks: Dict[str, Lock] = {k: Lock() for k in self.LIMITS}
    
    def wait_if_needed(self, category: str) -> None:
        """
        Aguarda se o limite de requisições foi atingido.
        
        Args:
            category: Categoria do endpoint ("catalog", "reviews", etc)
        """
        if category not in self.LIMITS:
            return  # categoria desconhecida, não limita
        
        max_calls, period = self.LIMITS[category]
        
        with self.locks[category]:
            now = time.time()
            
            # Remove chamadas antigas (fora da janela de tempo)
            self.calls[category] = [
                call_time for call_time in self.calls[category]
                if call_time > now - period
            ]
            
            # Se atingiu o limite, aguarda
            if len(self.calls[category]) >= max_calls:
                oldest_call = self.calls[category][0]
                sleep_time = period - (now - oldest_call) + 0.1  # +0.1s margem
                
                if sleep_time > 0:
                    print(f"⏳ Rate limit: aguardando {sleep_time:.1f}s ({category})")
                    time.sleep(sleep_time)
            
            # Registra esta chamada
            self.calls[category].append(time.time())
    
    def limit(self, category: str) -> Callable:
        """
        Decorator para aplicar rate limiting em funções.
        
        Uso:
            @limiter.limit("catalog")
            def get_items():
                ...
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                self.wait_if_needed(category)
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def reset(self, category: str = None) -> None:
        """Reseta contadores (útil para testes)."""
        if category:
            self.calls[category] = []
        else:
            for cat in self.calls:
                self.calls[cat] = []


# Instância global (importar em outros módulos)
limiter = GlobalRateLimiter()


# ============= EXEMPLO DE USO =============
if __name__ == "__main__":
    import requests
    
    @limiter.limit("catalog")
    def buscar_item(item_id: str):
        """Exemplo: função que faz requisição à API."""
        print(f"📦 Buscando item {item_id}...")
        # requests.get(f"https://api.ifood.com.br/items/{item_id}")
        return f"Item {item_id}"
    
    # Testa com múltiplas chamadas
    print("🧪 Testando rate limiter...")
    for i in range(5):
        resultado = buscar_item(f"item_{i}")
        print(f"✅ {resultado}")
    
    print("\n✨ Sucesso! Todas as requisições respeitaram o limite.")