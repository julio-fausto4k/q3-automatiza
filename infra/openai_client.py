# infra/openai_client.py
"""OpenAI API client for AI-powered features."""
import os
from typing import Optional, Dict, Any, List
from infra.http_client import http_client

class OpenAIClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.base_url = "https://api.openai.com/v1"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for OpenAI API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> Optional[Dict[str, Any]]:
        """Create chat completion."""
        if not self.api_key:
            print("⚠️ OPENAI_API_KEY not configured")
            return None
        
        data = {
            "model": self.model,
            "messages": messages,
            **kwargs
        }
        
        try:
            response = http_client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=data
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"OpenAI API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return None
    
    def generate_review_reply(self, review_text: str, rating: float, context: str = "") -> Optional[str]:
        """Generate a reply to a customer review using AI."""
        system_prompt = """Você é um assistente que ajuda restaurantes a responder avaliações de clientes.
        Gere respostas profissionais, empáticas e personalizadas baseadas no contexto da avaliação.
        Mantenha um tom cordial e agradeça sempre o feedback."""
        
        user_prompt = f"""
        Avaliação: {review_text}
        Nota: {rating}/5
        Contexto adicional: {context}
        
        Gere uma resposta profissional para esta avaliação.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.chat_completion(messages, max_tokens=200, temperature=0.7)
        if response and "choices" in response:
            return response["choices"][0]["message"]["content"].strip()
        
        return None

# Global OpenAI client instance
openai_client = OpenAIClient()