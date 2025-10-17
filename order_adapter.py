"""
Adaptador para nova estrutura de Items da API iFood
Compatível com as mudanças obrigatórias de 2025
"""

from typing import Dict, List, Tuple, Optional, Any


def normalize_order_items(order_data: Dict) -> List[Dict]:
    """
    Normaliza a estrutura de itens de um pedido para o novo formato.
    
    Args:
        order_data: Dados completos do pedido
    
    Returns:
        Lista de itens normalizados
    """
    items = order_data.get("items", [])
    normalized = []
    
    for item in items:
        item_type = item.get("itemType", "ITEM")
        
        base_item = {
            "id": item.get("id"),
            "externalCode": item.get("externalCode"),
            "ean": item.get("ean"),
            "itemType": item_type,
            "name": item.get("name"),
            "quantity": item.get("quantity", 1),
            "price": _extract_price(item),
            "totalPrice": item.get("totalPrice") or (
                item.get("price", 0) * item.get("quantity", 1)
            ),
            "observations": item.get("observations", ""),
            "subItems": _normalize_subitems(item.get("subItems", [])),
            "options": _normalize_options(item.get("options", [])),
            "index": item.get("index", 0),
            "unitPrice": item.get("unitPrice") or item.get("price", 0),
        }
        
        normalized.append(base_item)
    
    return normalized


def _extract_price(item: Dict) -> float:
    """Extrai preço de forma robusta."""
    for field in ["price", "unitPrice", "totalPrice"]:
        if field in item:
            try:
                return float(item[field])
            except (ValueError, TypeError):
                continue
    return 0.0


def _normalize_subitems(subitems: List[Dict]) -> List[Dict]:
    """Normaliza sub-itens de kits/combos."""
    normalized = []
    
    for sub in subitems:
        normalized.append({
            "id": sub.get("id"),
            "name": sub.get("name"),
            "quantity": sub.get("quantity", 1),
            "price": _extract_price(sub),
            "externalCode": sub.get("externalCode"),
            "options": _normalize_options(sub.get("options", [])),
        })
    
    return normalized


def _normalize_options(options: List[Dict]) -> List[Dict]:
    """Normaliza opções/complementos."""
    normalized = []
    
    for opt in options:
        normalized.append({
            "id": opt.get("id"),
            "name": opt.get("name"),
            "quantity": opt.get("quantity", 1),
            "price": _extract_price(opt),
            "externalCode": opt.get("externalCode"),
            "addition": opt.get("addition", 0),
        })
    
    return normalized


def validate_item_structure(item: Dict) -> Tuple[bool, List[str]]:
    """
    Valida se um item está no formato correto da nova API.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Campos obrigatórios
    required = ["id", "name", "quantity", "price"]
    for field in required:
        if field not in item or item[field] is None:
            errors.append(f"Campo obrigatório ausente: {field}")
    
    # Valida tipo
    item_type = item.get("itemType", "ITEM")
    if item_type not in ["ITEM", "KIT", "COMBO"]:
        errors.append(f"itemType inválido: {item_type}")
    
    # Se for KIT, deve ter subItems
    if item_type == "KIT" and not item.get("subItems"):
        errors.append("Items do tipo KIT devem ter subItems")
    
    # Valida quantidade
    qty = item.get("quantity", 0)
    if not isinstance(qty, (int, float)) or qty <= 0:
        errors.append(f"Quantidade inválida: {qty}")
    
    # Valida preço
    price = item.get("price")
    if price is not None:
        try:
            float(price)
        except (ValueError, TypeError):
            errors.append(f"Preço inválido: {price}")
    
    return (len(errors) == 0, errors)


def convert_catalog_to_order_format(catalog_item: Dict) -> Dict:
    """
    Converte um item do catálogo para o formato de pedido.
    """
    return {
        "id": catalog_item.get("id") or catalog_item.get("itemId"),
        "externalCode": catalog_item.get("externalCode"),
        "name": catalog_item.get("name"),
        "quantity": 1,
        "price": _extract_catalog_price(catalog_item),
        "itemType": "ITEM",
        "observations": "",
        "options": _convert_catalog_options(catalog_item),
    }


def _extract_catalog_price(item: Dict) -> float:
    """Extrai preço de item do catálogo."""
    if "price" in item:
        p = item["price"]
        if isinstance(p, dict):
            return float(p.get("value", 0))
        return float(p)
    
    products = item.get("products", [])
    if products:
        p = products[0].get("price", {})
        if isinstance(p, dict):
            return float(p.get("value", 0))
        return float(p)
    
    return 0.0


def _convert_catalog_options(item: Dict) -> List[Dict]:
    """Converte opções do catálogo para formato de pedido."""
    options = []
    option_groups = item.get("optionGroups", [])
    
    for group in option_groups:
        for opt in group.get("options", []):
            options.append({
                "id": opt.get("id"),
                "name": opt.get("name"),
                "quantity": opt.get("quantity", 0),
                "price": _extract_catalog_price(opt),
                "addition": opt.get("price", {}).get("value", 0),
            })
    
    return options


def detect_catalog_inconsistencies(
    catalog_items: List[Dict],
    order_items: List[Dict]
) -> List[Dict]:
    """
    Detecta inconsistências entre catálogo e pedidos.
    
    Returns:
        Lista de inconsistências encontradas
    """
    inconsistencies = []
    
    catalog_map = {
        item.get("id") or item.get("itemId"): item
        for item in catalog_items
    }
    
    for order_item in order_items:
        item_id = order_item.get("id")
        
        if item_id not in catalog_map:
            inconsistencies.append({
                "type": "MISSING_IN_CATALOG",
                "itemId": item_id,
                "itemName": order_item.get("name"),
                "severity": "HIGH",
                "message": f"Item {item_id} presente em pedido mas ausente no catálogo"
            })
            continue
        
        catalog_item = catalog_map[item_id]
        
        catalog_status = catalog_item.get("status", "").upper()
        if catalog_status == "UNAVAILABLE":
            inconsistencies.append({
                "type": "UNAVAILABLE_ITEM",
                "itemId": item_id,
                "itemName": order_item.get("name"),
                "severity": "MEDIUM",
                "message": f"Item {item_id} está pausado mas foi pedido"
            })
        
        catalog_price = _extract_catalog_price(catalog_item)
        order_price = order_item.get("price", 0)
        
        if catalog_price > 0 and order_price > 0:
            diff = abs(catalog_price - order_price)
            if diff > 0.01:
                inconsistencies.append({
                    "type": "PRICE_MISMATCH",
                    "itemId": item_id,
                    "itemName": order_item.get("name"),
                    "severity": "MEDIUM",
                    "catalogPrice": catalog_price,
                    "orderPrice": order_price,
                    "difference": diff,
                    "message": f"Preço divergente: catálogo R$ {catalog_price:.2f}, pedido R$ {order_price:.2f}"
                })
    
    return inconsistencies