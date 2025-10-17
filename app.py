# Q3 Automatiza – App com Interface (Streamlit)
# Você terá:
# - Login automático (lendo .env)
# - Selecionar loja
# - Modo Itens / Complementos / Ambos
# - Listar, filtrar e PAUSAR/ATIVAR selecionados

import os, json, time
import requests
import streamlit as st
from dotenv import load_dotenv

# --- HTTP session global (usada por todas as chamadas) ---
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://merchant-api.ifood.com.br"  # mantenha uma única definição
AUTH_URL = f"{BASE}/authentication/v1.0/oauth/token"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Q3-Automatiza/1.0"})

# Re-tentativas automáticas para erros transitórios
_retries = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST", "PATCH", "PUT"]
)
SESSION.mount("https://", HTTPAdapter(max_retries=_retries))
SESSION.mount("http://", HTTPAdapter(max_retries=_retries))

# ----------------- Núcleo (mesmas funções do seu script) -----------------
def load_env():
    load_dotenv()
    return os.getenv("CLIENT_ID"), os.getenv("CLIENT_SECRET")

from urllib.parse import urlencode

def auth(cid, csc):
    headers = {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": cid,
        "client_secret": csc,
    }
    r = requests.post(AUTH_URL, headers=headers, data=urlencode(data), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Auth {r.status_code}: {r.text}")
    return r.json().get("accessToken")

def get_merchants(token):
    url = f"{BASE}/merchant/v1.0/merchants"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"merchants {r.status_code}: {r.text}")
    return r.json()

def get_catalogs(token, merchant_id):
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/catalogs"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"catalogs {r.status_code}: {r.text}")
    return r.json()

def get_categories(token, merchant_id, catalog_id):
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/catalogs/{catalog_id}/categories"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"categories {r.status_code}: {r.text}")
    return r.json()

def get_category_items(token, merchant_id, category_id):
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/categories/{category_id}/items"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("items", [])

def get_item_detail(token, merchant_id, item_id):
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/items/{item_id}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code != 200:
        return None
    return r.json()

def extract_options_from_item_detail(item_detail):
    """
    Pega complementos (options) de dentro de optionGroups (e também options diretas).
    Retorna lista [{id, name, group}]
    """
    if not item_detail:
        return []
    results = []
    og = item_detail.get("optionGroups") or []
    for g in og:
        gname = g.get("name") or ""
        opts = g.get("options") or []
        for op in opts:
            oid = op.get("id") or op.get("optionId")
            oname = op.get("name") or op.get("label") or "(sem nome)"
            if oid:
                results.append({"id": oid, "name": oname, "group": gname})
    # options diretas (se houver)
    if isinstance(item_detail.get("options"), list):
        for op in item_detail["options"]:
            oid = op.get("id") or op.get("optionId")
            oname = op.get("name") or op.get("label") or "(sem nome)"
            if oid:
                results.append({"id": oid, "name": oname, "group": ""})
    return results

def patch_item_status(token, merchant_id, item_id, new_status, catalog_context="DEFAULT"):
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/items/status"
    body = {
        "itemId": item_id,
        "status": new_status,  # AVAILABLE / UNAVAILABLE
        "statusByCatalog": [{"status": new_status, "catalogContext": catalog_context}],
    }
    r = requests.patch(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                       data=json.dumps(body), timeout=30)
    return r.status_code, r.text

# --- ITEM: alterar status (global ou por contexto) - NOVA FUNÇÃO ----------------
def patch_item_status_ctx(token: str, merchant_id: str, item_id: str, new_status: str, catalog_context: str | None = None):
    """
    PATCH /merchants/{merchantId}/items/status

    - Se catalog_context for None: altera globalmente (payload com 'status').
    - Se catalog_context vier (ex.: 'DEFAULT', 'INDOOR', 'WHITELABEL'): altera somente naquele contexto (payload com 'statusByCatalog').
    """
    if new_status not in ("AVAILABLE", "UNAVAILABLE"):
        raise ValueError("new_status deve ser 'AVAILABLE' ou 'UNAVAILABLE'.")

    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/items/status"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if catalog_context:
        payload = {
            "itemId": item_id,
            "statusByCatalog": [
                {"status": new_status, "catalogContext": catalog_context}
            ],
        }
    else:
        payload = {
            "itemId": item_id,
            "status": new_status,
        }

    r = SESSION.patch(url, headers=headers, json=payload, timeout=60)
    try:
        body = r.json()
    except Exception:
        body = r.text
    return r.status_code, body

def patch_option_status(token, merchant_id, option_id, new_status, catalog_context="DEFAULT"):
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/options/status"
    body = {
        "optionId": option_id,
        "status": new_status,  # AVAILABLE / UNAVAILABLE
        "statusByCatalog": [{"status": new_status, "catalogContext": catalog_context}],
    }
    r = requests.patch(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                       data=json.dumps(body), timeout=30)
    return r.status_code, r.text

# ----------------- Cache leve pra navegação rápida -----------------
@st.cache_data(show_spinner=False, ttl=120)
def cached_merchants(token):
    return get_merchants(token)

@st.cache_data(show_spinner=False, ttl=120)
def cached_catalogs(token, merchant_id):
    return get_catalogs(token, merchant_id)

@st.cache_data(show_spinner=False, ttl=120)
def cached_categories(token, merchant_id, catalog_id):
    return get_categories(token, merchant_id, catalog_id)

@st.cache_data(show_spinner=False, ttl=120)
def cached_items_by_category(token, merchant_id, category_id):
    return get_category_items(token, merchant_id, category_id)

@st.cache_data(show_spinner=False, ttl=120)
def cached_item_detail(token, merchant_id, item_id):
    return get_item_detail(token, merchant_id, item_id)

if __name__ == "__main__":
    # --- Loja
    try:
        merchants = cached_merchants(st.session_state.token)
    except Exception as e:
        st.error(f"Erro listando lojas: {e}")
        st.stop()

    merchant_labels = [f"{m.get('name')} ({m.get('id')})" for m in merchants]
    merchant_ids = [m.get("id") for m in merchants]
    sel_idx = st.selectbox("Escolha a loja", options=list(range(len(merchant_labels))),
                        format_func=lambda i: merchant_labels[i])

    st.session_state.merchant_id = merchant_ids[sel_idx]
    merchant_name = merchants[sel_idx].get("name")

    # --- Catálogo e contexto
    try:
        catalogs = cached_catalogs(st.session_state.token, st.session_state.merchant_id)
        if not catalogs:
            st.warning("Nenhum catálogo encontrado.")
            st.stop()
        catalog_id = catalogs[0]["catalogId"]
        contexts = catalogs[0].get("context") or ["DEFAULT"]
        st.session_state.catalog_context = contexts[0]
    except Exception as e:
        st.error(f"Erro buscando catálogo: {e}")
        st.stop()

    st.markdown(f"**Loja:** {merchant_name}  \n**CatalogId:** `{catalog_id}`  \n**Contexto:** `{st.session_state.catalog_context}`")

    modo = st.radio("O que você quer mexer?", ["Itens", "Complementos", "Itens + Complementos"], horizontal=True)

    # Carregar categorias e itens
    try:
        categories = cached_categories(st.session_state.token, st.session_state.merchant_id, catalog_id)
    except Exception as e:
        st.error(f"Erro buscando categorias: {e}")
        st.stop()

    # --------- Construir listas (itens e/ ou complementos) ---------
    linhas_itens = []  # [{itemId, name, status, category}]
    linhas_opts = []   # [{optionId, name, group, category}]

    for cat in categories:
        cat_id = cat.get("id"); cat_name = cat.get("name")
        items = cached_items_by_category(st.session_state.token, st.session_state.merchant_id, cat_id)
        for it in items:
            # item 'resumo' pode não ter name; vamos pegar no detalhe para ter complements também
            det = cached_item_detail(st.session_state.token, st.session_state.merchant_id, it.get("id"))
            if det:
                item_name = det.get("name") or "(sem nome)"
                status = det.get("status") or "UNKNOWN"
            else:
                item_name = it.get("id")
                status = it.get("status") or "UNKNOWN"

            if modo in ("Itens", "Itens + Complementos"):
                linhas_itens.append({
                    "itemId": it.get("id"),
                    "name": item_name,
                    "status": status,
                    "category": cat_name or ""
                })

            if modo in ("Complementos", "Itens + Complementos"):
                options = extract_options_from_item_detail(det or {})
                for op in options:
                    linhas_opts.append({
                        "optionId": op["id"],
                        "name": op["name"],
                        "group": op.get("group") or "",
                        "category": cat_name or ""
                    })

    col1, col2 = st.columns(2)

    # ====================== BLOCO ITENS ======================
    if modo in ("Itens", "Itens + Complementos"):
        with col1:
            st.subheader("Itens")
            filtro_item = st.text_input("Filtrar itens por nome (ex: strog):", "")
            mostra_itens = [x for x in linhas_itens if filtro_item.lower() in (x["name"] or "").lower()]
            if not mostra_itens:
                st.info("Nenhum item para mostrar.")
            else:
                st.dataframe(mostra_itens, hide_index=True, use_container_width=True)
                ids_selecionados = st.multiselect(
                    "Selecione 1 ou mais itens para alterar:",
                    options=[x["itemId"] for x in mostra_itens],
                    format_func=lambda iid: next((x["name"] for x in mostra_itens if x["itemId"] == iid), iid)
                )
                colA, colB = st.columns(2)
                if colA.button("Pausar Itens Selecionados"):
                    if not ids_selecionados:
                        st.warning("Selecione ao menos 1 item.")
                    else:
                        ok, fails = 0, []
                        for iid in ids_selecionados:
                            st.write(f"Pausando: `{iid}` ...")
                            st.toast(f"Pausando item: {iid}", icon="⏸️")
                            st.status(f"Pausando {iid}")
                            st_code, st_body = patch_item_status(st.session_state.token, st.session_state.merchant_id, iid, "UNAVAILABLE", st.session_state.catalog_context)
                            if st_code == 200:
                                ok += 1
                            else:
                                fails.append((iid, st_code))
                            time.sleep(0.1)
                        if ok:
                            st.success(f"{ok} item(ns) atualizado(s).")
                        if fails:
                            st.error(f"Falhou: {fails}")
                        st.info("Atualize o app (R) para recarregar status.")
                if colB.button("Ativar Itens Selecionados"):
                    if not ids_selecionados:
                        st.warning("Selecione ao menos 1 item.")
                    else:
                        ok, fails = 0, []
                        for iid in ids_selecionados:
                            st.write(f"Ativando: `{iid}` ...")
                            st.toast(f"Ativando item: {iid}", icon="▶️")
                            st_code, st_body = patch_item_status(st.session_state.token, st.session_state.merchant_id, iid, "AVAILABLE", st.session_state.catalog_context)
                            if st_code == 200:
                                ok += 1
                            else:
                                fails.append((iid, st_code))
                            time.sleep(0.1)
                        if ok:
                            st.success(f"{ok} item(ns) atualizado(s).")
                        if fails:
                            st.error(f"Falhou: {fails}")
                        st.info("Atualize o app (R) para recarregar status.")

    # =================== BLOCO COMPLEMENTOS ===================
    if modo in ("Complementos", "Itens + Complementos"):
        with col2:
            st.subheader("Complementos")
            filtro_opt = st.text_input("Filtrar complementos por nome (ex: batata, bacon):", "")
            mostra_opts = [x for x in linhas_opts if filtro_opt.lower() in (x["name"] or "").lower()]
            if not mostra_opts:
                st.info("Nenhum complemento para mostrar.")
            else:
                st.dataframe(mostra_opts, hide_index=True, use_container_width=True)
                opts_sel = st.multiselect(
                    "Selecione 1 ou mais complementos para alterar:",
                    options=[x["optionId"] for x in mostra_opts],
                    format_func=lambda oid: next((x["name"] for x in mostra_opts if x["optionId"] == oid), oid)
                )
                colC, colD = st.columns(2)
                if colC.button("Pausar Complementos Selecionados"):
                    if not opts_sel:
                        st.warning("Selecione ao menos 1 complemento.")
                    else:
                        ok, fails = 0, []
                        for oid in opts_sel:
                            st.write(f"Pausando: `{oid}` ...")
                            st.toast(f"Pausando complemento: {oid}", icon="⏸️")
                            st_code, st_body = patch_option_status(st.session_state.token, st.session_state.merchant_id, oid, "UNAVAILABLE", st.session_state.catalog_context)
                            if st_code == 200:
                                ok += 1
                            else:
                                fails.append((oid, st_code))
                            time.sleep(0.1)
                        if ok:
                            st.success(f"{ok} complemento(s) atualizado(s).")
                        if fails:
                            st.error(f"Falhou: {fails}")
                if colD.button("Ativar Complementos Selecionados"):
                    if not opts_sel:
                        st.warning("Selecione ao menos 1 complemento.")
                    else:
                        ok, fails = 0, []
                        for oid in opts_sel:
                            st.write(f"Ativando: `{oid}` ...")
                            st.toast(f"Ativando complemento: {oid}", icon="▶️")
                            st_code, st_body = patch_option_status(st.session_state.token, st.session_state.merchant_id, oid, "AVAILABLE", st.session_state.catalog_context)
                            if st_code == 200:
                                ok += 1
                            else:
                                fails.append((oid, st_code))
                            time.sleep(0.1)
                        if ok:
                            st.success(f"{ok} complemento(s) atualizado(s).")
                        if fails:
                            st.error(f"Falhou: {fails}")
