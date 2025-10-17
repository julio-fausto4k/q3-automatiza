"""
Validador Pré-Homologação iFood
Verifica se o catálogo está pronto para a nova estrutura de pedidos
"""

from typing import Dict, List
from datetime import datetime


class PreHomologValidator:
    """Valida catálogo antes da homologação."""
    
    def __init__(self):
        self.issues = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": []
        }
    
    def validate_catalog(self, items: List[Dict]) -> Dict:
        """
        Executa todas as validações no catálogo.
        
        Returns:
            Relatório completo com issues e estatísticas
        """
        for item in items:
            self._validate_item_structure(item)
            self._validate_item_prices(item)
            self._validate_item_options(item)
            self._validate_item_metadata(item)
        
        return self._generate_report()
    
    def _validate_item_structure(self, item: Dict):
        """Valida estrutura básica do item."""
        item_id = item.get("id") or item.get("itemId") or "unknown"
        item_name = item.get("name") or "sem nome"
        
        if not item.get("id") and not item.get("itemId"):
            self._add_issue("CRITICAL", {
                "check": "MISSING_ID",
                "item": item_name,
                "message": "Item sem ID - obrigatório para pedidos"
            })
        
        if not item.get("name"):
            self._add_issue("CRITICAL", {
                "check": "MISSING_NAME",
                "itemId": item_id,
                "message": "Item sem nome - obrigatório"
            })
        
        if not item.get("externalCode"):
            self._add_issue("LOW", {
                "check": "MISSING_EXTERNAL_CODE",
                "itemId": item_id,
                "item": item_name,
                "message": "ExternalCode ausente - recomendado para integração"
            })
    
    def _validate_item_prices(self, item: Dict):
        """Valida estrutura de preços."""
        item_id = item.get("id") or item.get("itemId")
        item_name = item.get("name")
        
        price = None
        if "price" in item:
            p = item["price"]
            if isinstance(p, dict):
                price = p.get("value")
            else:
                price = p
        
        if price is None:
            products = item.get("products", [])
            if products:
                p = products[0].get("price", {})
                if isinstance(p, dict):
                    price = p.get("value")
                else:
                    price = p
        
        if price is None:
            self._add_issue("HIGH", {
                "check": "MISSING_PRICE",
                "itemId": item_id,
                "item": item_name,
                "message": "Preço não encontrado - pode causar erro em pedidos"
            })
        elif price <= 0:
            self._add_issue("HIGH", {
                "check": "ZERO_PRICE",
                "itemId": item_id,
                "item": item_name,
                "price": price,
                "message": "Preço zero ou negativo"
            })
        elif price > 10000:
            self._add_issue("MEDIUM", {
                "check": "HIGH_PRICE",
                "itemId": item_id,
                "item": item_name,
                "price": price,
                "message": f"Preço muito alto: R$ {price:.2f} - verificar"
            })
    
    def _validate_item_options(self, item: Dict):
        """Valida opções/complementos."""
        item_id = item.get("id") or item.get("itemId")
        item_name = item.get("name")
        
        option_groups = item.get("optionGroups", [])
        
        for group in option_groups:
            group_name = group.get("name", "grupo sem nome")
            options = group.get("options", [])
            
            if not options:
                self._add_issue("MEDIUM", {
                    "check": "EMPTY_OPTION_GROUP",
                    "itemId": item_id,
                    "item": item_name,
                    "group": group_name,
                    "message": f"Grupo '{group_name}' sem opções"
                })
                continue
            
            for opt in options:
                opt_id = opt.get("id")
                opt_name = opt.get("name")
                
                if not opt_id:
                    self._add_issue("HIGH", {
                        "check": "OPTION_MISSING_ID",
                        "itemId": item_id,
                        "item": item_name,
                        "option": opt_name or "sem nome",
                        "message": "Opção sem ID"
                    })
                
                if not opt_name:
                    self._add_issue("HIGH", {
                        "check": "OPTION_MISSING_NAME",
                        "itemId": item_id,
                        "item": item_name,
                        "optionId": opt_id,
                        "message": "Opção sem nome"
                    })
    
    def _validate_item_metadata(self, item: Dict):
        """Valida metadados recomendados."""
        item_id = item.get("id") or item.get("itemId")
        item_name = item.get("name")
        
        if not item.get("description"):
            self._add_issue("LOW", {
                "check": "MISSING_DESCRIPTION",
                "itemId": item_id,
                "item": item_name,
                "message": "Descrição ausente - ajuda na conversão"
            })
        
        has_image = False
        for key in ["image", "imagePath", "images"]:
            if item.get(key):
                has_image = True
                break
        
        if not has_image:
            products = item.get("products", [])
            if products:
                for p in products:
                    if p.get("images") or p.get("imagePath"):
                        has_image = True
                        break
        
        if not has_image:
            self._add_issue("MEDIUM", {
                "check": "MISSING_IMAGE",
                "itemId": item_id,
                "item": item_name,
                "message": "Imagem ausente - impacta conversão"
            })
    
    def _add_issue(self, severity: str, data: Dict):
        """Adiciona issue ao relatório."""
        data["severity"] = severity
        self.issues[severity].append(data)
    
    def _generate_report(self) -> Dict:
        """Gera relatório final."""
        total_issues = sum(len(v) for v in self.issues.values())
        
        if self.issues["CRITICAL"]:
            status = "❌ REPROVADO"
            can_homolog = False
        elif self.issues["HIGH"]:
            status = "⚠️ ATENÇÃO"
            can_homolog = True
        else:
            status = "✅ APROVADO"
            can_homolog = True
        
        return {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "can_homolog": can_homolog,
            "total_issues": total_issues,
            "by_severity": {
                k: len(v) for k, v in self.issues.items()
            },
            "issues": self.issues,
            "recommendations": self._get_recommendations()
        }
    
    def _get_recommendations(self) -> List[str]:
        """Gera recomendações baseadas nos issues."""
        recs = []
        
        if self.issues["CRITICAL"]:
            recs.append("🚨 Corrija TODOS os itens críticos antes de homologar")
        
        if self.issues["HIGH"]:
            recs.append("⚠️ Recomenda-se corrigir itens de alta prioridade")
        
        if self.issues["MEDIUM"]:
            recs.append("💡 Considere corrigir itens de média prioridade")
        
        if not self.issues["CRITICAL"] and not self.issues["HIGH"]:
            recs.append("✨ Catálogo está pronto para homologação!")
        
        return recs


def streamlit_validation_ui(items: List[Dict]):
    """Interface Streamlit para validação (placeholder)."""
    pass
