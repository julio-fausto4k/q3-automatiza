"""
Otimizador de Coleta de Catálogo
Substitui o loop N+1 lento por requisições paralelas

USO NO SEU MAIN.PY:
    from catalog_optimizer import collect_catalog_parallel
    
    # Substitua _q3_collect_catalog_slow() por:
    items, opts, err = collect_catalog_parallel(token, merchant_id, catalog_id)
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional


def collect_catalog_parallel(
    token: str,
    merchant_id: str,
    catalog_id: str,
    cached_categories_func,      # sua função cached_categories
    cached_items_by_category_func, # sua função cached_items_by_category
    cached_item_detail_func,      # sua função cached_item_detail
    extract_options_func,         # sua função extract_options_from_item_detail
    max_workers: int = 10
) -> Tuple[List[Dict], List[Dict], Optional[str]]:
    """
    Coleta catálogo completo usando threads paralelas.
    
    Args:
        token: Token de autenticação
        merchant_id: ID do merchant
        catalog_id: ID do catálogo
        *_func: Suas funções existentes (passar como argumento)
        max_workers: Número de threads simultâneas (default: 10)
    
    Returns:
        (lista_itens, lista_opcoes, erro_se_houver)
    """
    rows_items = []
    rows_opts = []
    
    try:
        # 1. Busca categorias (rápido, não precisa paralelizar)
        categories = cached_categories_func(token, merchant_id, catalog_id)
        
        if not categories:
            return [], [], "Nenhuma categoria encontrada"
        
        # 2. Coleta IDs de todos os itens (ainda rápido)
        item_tasks = []  # (cat_id, cat_name, item_id)
        
        for cat in categories:
            cat_id = cat.get("id")
            cat_name = cat.get("name")
            
            try:
                items = cached_items_by_category_func(token, merchant_id, cat_id)
                for it in items or []:
                    item_id = it.get("id")
                    if item_id:
                        item_tasks.append((cat_id, cat_name, item_id))
            except Exception as e:
                print(f"⚠️ Erro ao listar itens da categoria {cat_name}: {e}")
                continue
        
        print(f"📦 Total de itens para processar: {len(item_tasks)}")
        
        # 3. Função que será executada em paralelo
        def fetch_item_details(task):
            cat_id, cat_name, item_id = task
            
            try:
                # Busca detalhes do item (AQUI estava o gargalo!)
                det = cached_item_detail_func(token, merchant_id, item_id)
                
                if not det:
                    return None, []
                
                # Monta dados do item
                item_name = det.get("name") or item_id or "(sem nome)"
                status = (det.get("status") or "UNKNOWN").upper()
                
                item_data = {
                    "itemId": item_id,
                    "name": item_name,
                    "status": status,
                    "category": cat_name or ""
                }
                
                # Extrai opções/complementos
                options = extract_options_func(det or {})
                options_data = []
                
                for op in options:
                    options_data.append({
                        "optionId": op.get("id") or op.get("optionId"),
                        "name": op.get("name"),
                        "group": op.get("group") or "",
                        "category": cat_name or "",
                        "parent": det.get("name") or "",
                        "parentId": item_id,
                        "status": (op.get("status") or "").upper()
                    })
                
                return item_data, options_data
                
            except Exception as e:
                print(f"⚠️ Erro ao processar item {item_id}: {e}")
                return None, []
        
        # 4. Executa em paralelo com ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submete todas as tarefas
            futures = {
                executor.submit(fetch_item_details, task): task
                for task in item_tasks
            }
            
            # Coleta resultados conforme vão finalizando
            completed = 0
            total = len(futures)
            
            for future in as_completed(futures):
                completed += 1
                
                # Mostra progresso
                if completed % 10 == 0 or completed == total:
                    print(f"⏳ Progresso: {completed}/{total} itens processados")
                
                try:
                    item_data, options_data = future.result()
                    
                    if item_data:
                        rows_items.append(item_data)
                    
                    if options_data:
                        rows_opts.extend(options_data)
                        
                except Exception as e:
                    print(f"⚠️ Erro ao coletar resultado: {e}")
        
        print(f"✅ Coleta finalizada: {len(rows_items)} itens, {len(rows_opts)} opções")
        return rows_items, rows_opts, None
        
    except Exception as e:
        error_msg = f"Erro geral na coleta: {e}"
        print(f"❌ {error_msg}")
        return [], [], error_msg


# ============= EXEMPLO DE INTEGRAÇÃO =============
"""
NO SEU main.py, SUBSTITUA:

    def _q3_collect_catalog_slow():
        # código antigo com loop...
        
POR:

    from catalog_optimizer import collect_catalog_parallel
    
    def _q3_collect_catalog_fast():
        return collect_catalog_parallel(
            token=st.session_state.token,
            merchant_id=st.session_state.merchant_id,
            catalog_id=catalog_id,
            cached_categories_func=cached_categories,
            cached_items_by_category_func=cached_items_by_category,
            cached_item_detail_func=cached_item_detail,
            extract_options_func=extract_options_from_item_detail,
            max_workers=10  # ajuste conforme necessário
        )

E ONDE USA:

    it, op, err = _q3_collect_catalog_slow()
    
TROQUE POR:

    it, op, err = _q3_collect_catalog_fast()
"""