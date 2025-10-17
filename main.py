from __future__ import annotations

# ============== Q3 Automatiza — main.py ==============
# - 🛒 Catálogo — Pausar/Ativar Itens e Complementos
# - 📋 Botão "Gerar lista de pausados"
# - 📝 Avaliações (IA)
# - Q3 Catálogo
# - 📊 Relatórios de Avaliações
# - 🏪 Merchant - Gestão da Loja

def force_logout_and_clear_all():
    """Limpa TODOS os dados de sessão e cache"""
    # Limpa session_state
    keys_to_clear = [
        "token", "refresh_token", "token_expires_at", "api_connected",
        "logged_in", "logged_user", "merchant_id", "store_id",
        "client_id", "client_secret", "_access_token",
        "catalog_id", "catalog_context", "catalog_loaded",
        "_product_img_index", "_options_index", "_groups_to_draw",
        "favorites", "merchants_cache"
    ]
    
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # Limpa cache de dados
    try:
        st.cache_data.clear()
    except:
        pass
    
    # Limpa cache de recursos
    try:
        st.cache_resource.clear()
    except:
        pass

import os
from urllib.parse import urljoin
from typing import List, Dict, Any  # coloque no topo do arquivo (se ainda não existir)

# === Catalog v2 base e builder de URLs ===
from urllib.parse import urljoin

def _c(path: str) -> str:
    """Monta URL segura para o Catalog v2 (evita repetir domínio e barras)."""
    base = CATALOG_BASE if CATALOG_BASE.endswith("/") else CATALOG_BASE + "/"
    return urljoin(base, path.lstrip("/"))

# ============================ IMPORTS ============================
import uuid
import os, json, time, base64, math, html, uuid, re as _re
from contextlib import contextmanager
from datetime import datetime, timedelta, date, time as dtime
from typing import Optional
from rate_limiter import limiter
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from werkzeug.security import check_password_hash
from catalog_optimizer import collect_catalog_parallel

load_dotenv(override=True)

# ============================ FUNÇÕES DE AUTENTICAÇÃO (CRÍTICAS) ============================
# ✅ Estas funções DEVEM estar no início do arquivo, logo após os imports

def _token_ok() -> bool:
    """Verifica se existe um token JWT válido na sessão"""
    t = st.session_state.get("token") or ""
    return isinstance(t, str) and len(t.strip()) > 20

def _is_logged() -> bool:
    """
    Verifica se o usuário está autenticado:
    - Tem logged_user definido
    - Tem token válido
    """
    has_user = bool(st.session_state.get("logged_user"))
    # ✅ MUDANÇA: Se tem usuário, já considera logado (token virá depois)
    if has_user:
        return True
    
    # Fallback: verifica token (caso logged_user não esteja definido mas token sim)
    return _token_ok()

def force_logout_and_clear_all():
    """Limpa TODOS os dados de sessão e cache"""
    keys_to_clear = [
        "token", "refresh_token", "token_expires_at", "api_connected",
        "logged_in", "logged_user", "merchant_id", "store_id",
        "client_id", "client_secret", "_access_token",
        "catalog_id", "catalog_context", "catalog_loaded",
        "_product_img_index", "_options_index", "_groups_to_draw",
        "favorites", "merchants_cache"
    ]
    
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # ✅ CRÍTICO: Limpar cache do Streamlit
    try:
        st.cache_data.clear()
        st.cache_resource.clear()
    except:
        pass
    
    # ✅ NOVO: Forçar re-fetch de merchants na próxima vez
    if "merchants_cache" in st.session_state:
        del st.session_state["merchants_cache"]

def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val).strip())
        return True
    except Exception:
        return False

def _img_url_from_path(path: str | None) -> str | None:
    if not path:
        return None
    s = str(path)
    # já é URL completa
    if s.startswith("http"):
        return s
    # caminho do CDN público clássico do iFood
    if s.startswith("image/upload") or s.startswith("/image/upload"):
        return f"https://static-images.ifood.com.br/{s.lstrip('/')}"
    # fallback: base do catálogo estático (pode ajustar via env)
    base = os.getenv("CATALOG_STATIC_BASE") or "https://merchant-api.ifood.com.br/catalog/static"
    return f"{base.rstrip('/')}/{s.lstrip('/')}"

# === BASES E HELPERS DE URL (depois dos imports e load_dotenv) ===
CATALOG_BASE = os.getenv(
    "IF_CATALOG_BASE",
    "https://merchant-api.ifood.com.br/catalog/v2.0/",
).rstrip("/")

IF_BASE = os.getenv(
    "IF_BASE",
    "https://merchant-api.ifood.com.br/",
).rstrip("/")

def build_url(path: str) -> str:
    """Monta URL absoluta respeitando barras sem duplicar."""
    base = IF_BASE + "/"
    return urljoin(base, path.lstrip("/"))

try:
    from streamlit_autorefresh import st_autorefresh  # opcional
except Exception:
    st_autorefresh = None

from PIL import Image
from io import BytesIO

def optimize_image(file_bytes, max_size=(800, 600), quality=85):
    """Redimensiona e comprime imagem antes do upload."""
    try:
        img = Image.open(BytesIO(file_bytes))
        
        # Redimensiona mantendo proporção
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Converte RGBA para RGB se necessário
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Comprime
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        print(f"⚠️ Erro ao otimizar imagem: {e}")
        return file_bytes  # retorna original se falhar

# ============================ CONSTANTES =========================
BASE = "https://merchant-api.ifood.com.br"
AUTH_URL = f"{BASE}/authentication/v1.0/oauth/token"

st.set_page_config(page_title="Q3 Automatiza", page_icon="🍽️", layout="wide")

# ============================ SESSION DEFAULTS ===================
DEFAULTS = {
    "api_connected": False,
    "logged_in": False,
    "logged_user": "",
    "token": "",
    "refresh_token": "",
    "token_expires_at": 0.0,
    "client_id": os.getenv("CLIENT_ID") or "",
    "client_secret": os.getenv("CLIENT_SECRET") or "",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

# Estado adicional usado no app
_init_defaults = {
    "_access_token": None,
    "merchant_id": None,
    "store_id": None,
    "_reply_open": False,
    "_selected_review": None,
    "_reply_text": "",
    "_reviews_last_refresh": 0.0,
}
for _k, _v in _init_defaults.items():
    st.session_state.setdefault(_k, _v)

st.session_state.setdefault("_status_override", {})  # id -> status
st.session_state.setdefault("_image_override", {})
st.session_state.setdefault("_meta_override", {})   # id -> name/description

# ============================ FEATURE FLAGS ======================
def _flag(env_name: str, default: bool = False) -> bool:
    v = str(os.getenv(env_name, "1" if default else "0")).strip().lower()
    return v in ("1","true","t","yes","y","sim","on")

Q3_SHOW_ANALYTICS = _flag("Q3_SHOW_ANALYTICS", False)  # mantido off
Q3_SHOW_REVIEWS  = True                                # (Aba IA)
Q3_SHOW_MONITOR  = _flag("Q3_SHOW_MONITOR",  False)
Q3_SHOW_CANCEL   = _flag("Q3_SHOW_CANCEL",   False)
Q3_SHOW_EXEC     = _flag("Q3_SHOW_EXEC",     False)

# ============================ HELPERS BÁSICOS ====================
def _reset_all_caches():
    try:
        st.cache_data.clear()
    except Exception:
        pass
    # limpa tudo que guarda dados antigos na sessão
    for k in ["_options_index", "_product_img_index", "_groups_to_draw"]:
        if k in st.session_state:
            st.session_state.pop(k, None)
    # bump de versão para invalidação por argumento
    st.session_state["_cache_bump"] = (st.session_state.get("_cache_bump", 0) + 1)

def _env_set(name: str, default_csv: str) -> set[str]:
    try:
        raw = os.getenv(name, default_csv)
        return {x.strip().upper() for x in str(raw).split(",") if x.strip()}
    except Exception:
        return set()

def _env_int(name: str, default: int) -> int:
    try:
        v = int(str(os.getenv(name, "")).strip())
        return v if v > 0 else default
    except Exception:
        return default

def _env_float(name: str, default: float) -> float:
    try:
        v = float(str(os.getenv(name, "")).strip().replace(",", "."))
        return v if v > 0 else default
    except Exception:
        return default

def safe_json(obj):
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj) if obj is not None else "<unserializable>"

def cache_bust(url: str | None) -> str | None:
    if not url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}cb={int(time.time())}"

# =================== REVIEWS: Persistência e Relatórios ===================
import sqlite3
from pathlib import Path

DB_PATH = Path("reviews.db")

def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id TEXT PRIMARY KEY,
        merchant_id TEXT,
        created_at TEXT,
        rating REAL,
        comment TEXT,
        reply_text TEXT,
        replied_at TEXT
    )
    """)
    conn.commit()
    return conn

def upsert_reviews(merchant_id: str, rows: list[dict]):
    """Salva/atualiza avaliações cruas (sem resposta ainda)."""
    if not rows:
        return
    conn = _db()
    cur = conn.cursor()
    for r in rows:
        rid = _get_review_id(r)  # definido mais abaixo no arquivo
        if not rid:
            continue
        created = str(r.get("createdAt") or r.get("created") or r.get("date") or "")
        rating  = _review_rating(r)
        comment = _review_text(r)
        cur.execute("""
            INSERT INTO reviews (id, merchant_id, created_at, rating, comment)
            VALUES (?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              merchant_id=excluded.merchant_id,
              created_at=excluded.created_at,
              rating=excluded.rating,
              comment=excluded.comment
        """, (rid, merchant_id, created, rating, comment))
    conn.commit()
    conn.close()

def save_reply_to_db(review_id: str, reply_text: str):
    """Registra a resposta enviada pela IA (ou manual)."""
    if not review_id:
        return
    conn = _db()
    conn.execute("""
        UPDATE reviews
           SET reply_text = ?, replied_at = datetime('now','localtime')
         WHERE id = ?
    """, (reply_text, review_id))
    conn.commit()
    conn.close()

def query_reviews(merchant_id: str, start_date: str, end_date: str, stars: set[int] | None):
    """
    Retorna rows do período (inclusive) filtrando por estrelas (set de ints) se informado.
    Datas no formato 'YYYY-MM-DD'.
    """
    conn = _db()
    cur = conn.cursor()
    q = "SELECT id, created_at, rating, comment, reply_text, replied_at FROM reviews WHERE merchant_id=?"
    params = [merchant_id]
    if start_date:
        q += " AND date(created_at) >= date(?)"; params.append(start_date)
    if end_date:
        q += " AND date(created_at) <= date(?)"; params.append(end_date)
    if stars:
        placeholders = ",".join("?"*len(stars))
        q += f" AND CAST(round(rating) AS INT) IN ({placeholders})"
        params.extend([int(s) for s in stars])
    q += " ORDER BY created_at ASC"
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return rows

# ============================ USERS (SQLite) ============================
import sqlite3, secrets, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

USERS_DB_PATH = "q3_data.db"

def _users_conn():
    cx = sqlite3.connect(USERS_DB_PATH, check_same_thread=False)
    cx.row_factory = sqlite3.Row
    cx.execute("""
      CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT,
        email TEXT UNIQUE,
        pw_hash TEXT NOT NULL,
        created_at TEXT,
        updated_at TEXT,
        reset_token TEXT,
        reset_expires_at TEXT
      );
    """)
    return cx

def users_find_by_login(login:str):
    """Aceita email ou username."""
    cx = _users_conn()
    if "@" in (login or ""):
        return cx.execute("SELECT * FROM users WHERE lower(email)=lower(?)", (login,)).fetchone()
    return cx.execute("SELECT * FROM users WHERE lower(username)=lower(?)", (login,)).fetchone()

def users_verify_password(row, password:str)->bool:
    return (row is not None) and check_password_hash(row["pw_hash"], password or "")

def users_change_password(user_id:int, current_pw:str, new_pw:str):
    cx = _users_conn()
    row = cx.execute("SELECT pw_hash FROM users WHERE id=?", (user_id,)).fetchone()
    if not row or not check_password_hash(row["pw_hash"], current_pw or ""):
        return False, "Senha atual incorreta."
    cx.execute("UPDATE users SET pw_hash=?, updated_at=? WHERE id=?",
               (generate_password_hash(new_pw), datetime.utcnow().isoformat(), user_id))
    cx.commit()
    return True, "Senha alterada com sucesso."

def users_generate_reset(email:str):
    """Gera token de reset + envia email com link. Retorna (ok,msg,maybe_link)."""
    import os
    cx = _users_conn()
    row = cx.execute("SELECT id,email FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
    if not row:
        return False, "E-mail não encontrado.", None
    token = secrets.token_urlsafe(32)
    exp = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    cx.execute("UPDATE users SET reset_token=?, reset_expires_at=? WHERE id=?",
               (token, exp, row["id"]))
    cx.commit()

    base = os.getenv("PUBLIC_APP_URL", "http://localhost:8501").rstrip("/")
    reset_link = f"{base}?reset={token}"
    ok, err = _send_email(
        to=row["email"],
        subject="Redefinir senha — Q3 Automatiza",
        html=f"<p>Para redefinir sua senha, clique: <a href='{reset_link}'>redefinir senha</a></p><p>Link válido por 1 hora.</p>"
    )
    # se SMTP não configurado, devolvo o link pra você copiar no log
    if not ok:
        print("[EMAIL DEV - LINK DE RESET]", reset_link, "| motivo:", err)
    return True, "Se o e-mail existir, enviamos um link de redefinição. (Confira o spam)", reset_link if not ok else None

def users_validate_reset_token(token:str):
    """Retorna user_id válido para o token, ou None se inválido/expirado."""
    cx = _users_conn()
    row = cx.execute("SELECT id, reset_expires_at FROM users WHERE reset_token=?", (token,)).fetchone()
    if not row:
        return None
    try:
        if datetime.utcnow() > datetime.fromisoformat(row["reset_expires_at"]):
            return None
    except Exception:
        return None
    return row["id"]

def users_consume_reset(user_id:int, new_pw:str):
    cx = _users_conn()
    cx.execute("UPDATE users SET pw_hash=?, reset_token=NULL, reset_expires_at=NULL, updated_at=? WHERE id=?",
               (generate_password_hash(new_pw), datetime.utcnow().isoformat(), user_id))
    cx.commit()

def _send_email(to:str, subject:str, html:str):
    """SMTP opcional; se faltar config, imprime no console."""
    import os
    host = os.getenv("SMTP_HOST"); port = int(os.getenv("SMTP_PORT","587"))
    user = os.getenv("SMTP_USER");  pwd  = os.getenv("SMTP_PASS")
    sender = os.getenv("SMTP_FROM", user or "no-reply@q3.local")
    if not host or not user or not pwd:
        return False, "SMTP não configurado"
    try:
        msg = MIMEMultipart()
        msg["From"] = sender; msg["To"] = to; msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)

def users_create_if_missing(username:str, email:str, password:str):
    """Utilitário opcional pra criar 1 usuário (use no dev)."""
    cx = _users_conn()
    r = cx.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
    if r: return
    cx.execute("INSERT INTO users(username,email,pw_hash,created_at,updated_at) VALUES(?,?,?,?,?)",
               (username, email, generate_password_hash(password), datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
    cx.commit()

# ============================ HTTP SESSION (RETRY) ================
def _session():
    total   = _env_int("Q3_HTTP_RETRY_TOTAL", 1)
    backoff = _env_float("Q3_HTTP_BACKOFF", 0.1)
    statuses_csv = os.getenv("Q3_HTTP_RETRY_STATUSES", "429,500,502,503,504")
    status_forcelist = tuple(int(x) for x in statuses_csv.split(",") if x.strip().isdigit())
    allowed_methods = _env_set("Q3_HTTP_RETRY_METHODS", "GET,HEAD,OPTIONS")
    write_methods   = _env_set("Q3_HTTP_RETRY_METHODS_WRITE", "")
    allowed_methods = allowed_methods | write_methods

    r = Retry(
        total=total,
        backoff_factor=backoff,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,
        respect_retry_after_header=(os.getenv("Q3_HTTP_RESPECT_RETRY_AFTER","false").lower()=="true"),
    )
    adapter = HTTPAdapter(max_retries=r, pool_connections=20, pool_maxsize=20)

    s = requests.Session()
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

SESSION = _session()
if 'http' not in st.session_state or not isinstance(st.session_state.http, requests.Session):
    st.session_state.http = _session()
else:
    try:
        st.session_state.http.mount('https://', SESSION.adapters['https://'])
        st.session_state.http.mount('http://',  SESSION.adapters['http://'])
    except Exception:
        st.session_state.http = _session()

# ============================ FAVORITOS (por usuário) =============
def _user_scoped_name(base: str) -> str:
    u = st.session_state.get("logged_user") or "default"
    safe = "".join(ch for ch in u if ch.isalnum() or ch in ("-","_")).lower()
    return f"{base}.{safe}.json"

def _load_json_file(path: str) -> list:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []

def _save_json_file(path: str, rows: list):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _favorites_path(): return _user_scoped_name("q3_favorites")
def _load_favorites_file(): return _load_json_file(_favorites_path())
def _save_favorites_file(favs: list): _save_json_file(_favorites_path(), favs)

def _is_favorite(mid: str) -> bool:
    favs = st.session_state.get("favorites") or []
    return mid in favs

def _toggle_favorite(mid: str):
    if not mid: return
    favs = st.session_state.get("favorites") or []
    favs = [x for x in favs if x != mid] if mid in favs else favs + [mid]
    st.session_state.favorites = favs
    _save_favorites_file(favs)

st.session_state.setdefault("favorites", _load_favorites_file())

# ============================ ESTADO/INIT APP =====================
def init_state():
    defaults = {
        "_locally_answered": set(),
        "logged_in": False,
        "logged_user": None,
        "token": None,
        "merchant_id": None,
        "catalog_context": "DEFAULT",
        "confirm_ctx": None,
        "favorites": st.session_state.get("favorites"),
        "show_favorites_only": False,
        "reply_confirm": None,
        "cancel_confirm": None,
        "sel_items": set(),
        "sel_opts": set(),
        "reviews_refresh_token": 0,
        "_suspend_until": 0.0,
        "_events_winner": None,
        "_kpi_css_loaded": False,
        "reviews_tone": "descontraído",
        "reviews_signature": "",
        "reviews_use_emojis": True,
        "reviews_page": 1,
        "reviews_page_size": 10,
        "_review_suggestions": {},
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
init_state()
st.session_state.setdefault("_reviews_locally_closed", set())

# ============================ CSS/TEMA ============================
st.markdown("""
<style>
.main .block-container{padding-top:1.25rem!important}
.stButton>button,[data-testid="baseButton-primary"],[data-testid="baseButton-secondary"]{
  background:linear-gradient(90deg,#FF4BC6,#8B00FF)!important;color:#fff!important;border:0!important;border-radius:12px!important;
  font-weight:700!important;padding:10px 14px!important;box-shadow:0 2px 8px rgba(139,0,255,.25)!important}
.stButton>button:hover,[data-testid="baseButton-primary"]:hover,[data-testid="baseButton-secondary"]:hover{
  filter:brightness(1.05)!important;transform:translateY(-1px)!important}
.stButton>button:disabled,[data-testid="baseButton-primary"][disabled],[data-testid="baseButton-secondary"][disabled]{opacity:.6!important}
input, textarea, .stSelectbox div[data-baseweb="select"]{border-radius:12px!important;background:#1b1e26!important;color:#e8e8e8!important;border:1px solid #323542!important}
[data-testid="stMetric"]{border-radius:14px;padding:8px 12px;background:#151922}
.q3-banner{background:linear-gradient(90deg,#FF4BC6,#8B00FF);color:#fff;padding:12px 14px;border-radius:12px;border:1px solid rgba(255,255,255,.25);font-weight:700;text-align:center}
.q3-connected{display:block;width:100%;background:linear-gradient(90deg,#FF4BC6,#8B00FF);color:#fff;padding:10px 16px;border-radius:12px;border:1px solid rgba(255,255,255,.25);font-weight:700;white-space:nowrap;margin:0}
.q3-progress{background:#1b1e26;border:1px solid #2e3241;border-radius:12px;padding:8px 12px;position:relative;overflow:hidden}
.q3-progress-bar{height:10px;border-radius:8px;background:linear-gradient(90deg,#FF4BC6,#8B00FF);transition:width .15s ease}
.q3-progress-label{font-size:.85rem;margin-bottom:6px;color:#cfd3e0}
.q3-progress-perc{position:absolute;right:12px;top:8px;font-weight:700;color:#fff}
[data-testid="stExpander"]>details{border:1px solid #2e3241;border-radius:12px;overflow:hidden;background:#151922}
[data-testid="stExpander"]>details>summary{list-style:none;cursor:pointer;padding:10px 14px;background:linear-gradient(90deg,#FF4BC6,#8B00FF);color:#fff;font-weight:800;border-radius:12px;display:flex;align-items:center;gap:8px}
[data-testid="stExpander"]>details>summary::-webkit-details-marker{display:none}
[data-testid="stExpander"]>details[open]>summary{border-bottom:1px solid rgba(255,255,255,.08);border-bottom-left-radius:0;border-bottom-right-radius:0}
[data-testid="stExpander"] .streamlit-expanderContent{background:#151922;padding:12px 14px}
.q3-catbar{display:flex;align-items:center;gap:10px;margin:8px 0 12px;
  padding:10px 14px;border-radius:12px;background:#151922;border:1px solid #2e3241;font-weight:800}
.q3-chip{background:rgba(255,255,255,.09);padding:3px 8px;border-radius:999px;font-size:.8rem}
.q3-card-actions > div [data-testid="baseButton-secondary"],
.q3-card-actions > div [data-testid="baseButton-primary"]{width:100%}
</style>
""", unsafe_allow_html=True)

def q3_success(msg: str):
    st.markdown(f"""<div class="q3-banner">{msg}</div>""", unsafe_allow_html=True)

def q3_info(msg: str):
    st.markdown(
        f"""<div style="background: linear-gradient(90deg,#005BFF,#003EC7);
            color:#fff; padding:12px 14px; border-radius:12px;
            border:1px solid rgba(255,255,255,0.25); font-weight:700; text-align:center;">
            {msg}</div>""",
        unsafe_allow_html=True,
    )

@contextmanager
def q3_progress(label="Carregando..."):
    holder = st.empty()
    def _render(pct, text=label):
        pct_clamped = max(0, min(100, int(pct)))
        holder.markdown(f"""
        <div class="q3-progress">
          <div class="q3-progress-label">{text}</div>
          <div class="q3-progress-perc">{pct_clamped}%</div>
          <div style="width:100%;background:#0f1320;border-radius:8px;overflow:hidden">
            <div class="q3-progress-bar" style="width:{pct_clamped}%"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    _render(3)
    try:
        yield _render
    finally:
        holder.empty()

# ============================ KEYS/UTILS ==========================
st.session_state.setdefault("_keyseq", {})
def _ukey(prefix: str) -> str:
    n = st.session_state["_keyseq"].get(prefix, 0) + 1
    st.session_state["_keyseq"][prefix] = n
    return f"{prefix}__{n}"

def _looks_like_uuid(s: str) -> bool:
    if not s:
        return False
    return bool(_re.fullmatch(r"[0-9a-fA-F-]{36}", str(s).strip()))

def _safe_key(*parts):
    s = "_".join(str(p) for p in parts if p is not None)
    return _re.sub(r"[^0-9A-Za-z_.-]+", "_", s)

def _iid(x):  # id como string
    try: return str(x).strip()
    except Exception: return ""

def parse_price_input(v) -> float | None:
    if v in (None, ""): return None
    try:
        s = str(v).replace("R$","").replace(" ","").replace(",",".")
        return round(float(s), 2)
    except Exception:
        return None

def fmt_price_br(v) -> str:
    try: return f"{float(v):.2f}".replace(".", ",")
    except Exception: return ""

def _normalize_img_url(path: str | None) -> str:
    """Converte imagePath (ex.: 'image/upload/...') em URL completa.
    Se já for http/https, devolve como está."""
    if not path:
        return ""
    p = str(path).strip()
    if p.startswith("http://") or p.startswith("https://"):
        return p
    # iFood usa esse host para servir as imagens do imagePath:
    return f"https://static-images.ifood.com.br/image/upload/{p.lstrip('/')}"

# ======== iFood Catalog v2 — IMAGENS (HTTP) ========
import base64, requests, mimetypes

IFOOD_BASE_URL = "https://merchant-api.ifood.com.br"
STATIC_IMG_BASE = "https://static-images.ifood.com.br/image/upload/"

def img_url_from_path(path: str | None) -> str | None:
    if not path:
        return None
    path = str(path).lstrip("/")
    if path.startswith("http"):
        return path
    return f"{STATIC_IMG_BASE}{path}"

def build_product_img_index_v1(merchant_id: str, catalog_id: str) -> dict[str, str]:
    """
    Varre categorias v1 com includeItems=true e monta um índice:
    { productId -> URL completa da imagem }
    """
    url = f"{CATALOG_BASE}/merchants/{merchant_id}/catalogs/{catalog_id}/categories"
    params = {"includeItems": "true"}
    headers = auth_headers(st.session_state.token)

    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json() or []

    index: dict[str, str] = {}
    for cat in data:
        for it in (cat.get("items") or []):
            for p in (it.get("products") or []):
                pid = p.get("id")
                ipath = p.get("imagePath")
                if pid and ipath:
                    index[pid] = _normalize_img_url(ipath)
    return index

def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def _guess_mime_from_filename(name: str | None) -> str:
    if not name:
        return "image/jpeg"
    mt, _ = mimetypes.guess_type(name)
    return mt or "image/jpeg"

def upload_item_image(token: str, merchant_id: str, item_id: str, file_bytes: bytes, filename: str | None = None) -> dict:
    """
    Faz upload da IMAGEM (v2) e retorna um dict com imagePath.
    Endpoint: POST /catalog/v2.0/merchants/{merchantId}/image/upload
    O item_id aqui é irrelevante para o upload (só mantemos a assinatura compatível com sua UI).
    """
    mime = _guess_mime_from_filename(filename)
    b64 = base64.b64encode(file_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    url = f"{IFOOD_BASE_URL}/catalog/v2.0/merchants/{merchant_id}/image/upload"
    resp = requests.post(url, json={"image": data_url}, headers=_auth_headers(token), timeout=20)
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text}

    return {
        "status_code": resp.status_code,
        "ok": resp.ok,
        "imagePath": (payload.get("imagePath") if isinstance(payload, dict) else None),
        "response": payload,
    }

def get_item_flat_image(token: str, merchant_id: str, item_id: str) -> dict:
    """
    Lê o item no formato 'flat' para montar payload e/ou exibir no card.
    Endpoint: GET /catalog/v2.0/merchants/{merchantId}/items/{itemId}/flat
    """
    url = f"{IFOOD_BASE_URL}/catalog/v2.0/merchants/{merchant_id}/items/{item_id}/flat"
    resp = requests.get(url, headers=_auth_headers(token), timeout=20)
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text}
    return {"status_code": resp.status_code, "ok": resp.ok, "response": payload}

@st.cache_data(ttl=300, show_spinner=False)
def list_option_groups(merchant_id: str, include_options: bool = False):
    """
    GET /merchants/{merchantId}/optionGroups[?includeOptions=true]
    Quando include_options=True, alguns ambientes já retornam options embutidas.
    """
    url = f"{BASE_V1}/merchants/{merchant_id}/optionGroups"
    params = {"includeOptions": "true"} if include_options else None
    r = requests.get(url, headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def _ctx_mods(opt: dict) -> list[dict]:
    return (opt.get("contextOptionModifiers")
            or opt.get("contextModifiers")
            or [])

def fetch_options_for_group_from_categories(merchant_id: str, catalog_id: str, group_id: str):
    """
    Varre categories?includeItems=true e devolve as options do group_id,
    já com campos úteis para a UI (id, name, price, status, productId, groupId).
    """
    try:
        cats = list_categories_with_items(merchant_id, catalog_id) or []
    except Exception:
        cats = []

    out = []
    for cat in cats:
        for it in (cat.get("items") or []):
            product_id = it.get("productId")  # ID do 'item' (produto base)
            for og in (it.get("optionGroups") or []):
                if (og.get("id") or "") != group_id:
                    continue
                ctx = (st.session_state.get("catalog_context") or "DEFAULT").upper()
                
                products = {p.get("id"): p for p in (it.get("products") or []) if p.get("id")}

                for opt in (og.get("options") or []):

                    prod = products.get(opt.get("productId") or "", {})

                    # ----- cálculo de preço/status + imagem -----
                    price_val = (opt.get("price") or {}).get("value", 0.0)         # preço global
                    status_val = (opt.get("status") or "AVAILABLE").upper()        # status global
                    image_path = opt.get("imagePath") or ""                         # imagem da opção (se tiver)

                    ctx = (st.session_state.get("catalog_context") or "DEFAULT").upper()

                    # sobrescrever por contexto, se bater com o contexto atual
                    _ctx_mods = (opt.get("contextModifiers") 
                                or opt.get("contextOptionModifiers") 
                                or [])
                    for cm in _ctx_mods:
                        if (cm.get("catalogContext") or "").upper() == ctx:
                            if (cm.get("price") or {}).get("value") is not None:
                                price_val = cm["price"]["value"]
                            if cm.get("status"):
                                status_val = cm["status"].upper()
                            if cm.get("imagePath"):
                                image_path = cm["imagePath"]
                            break

                    # se a opção não tiver imagem, tenta a do produto base ligado à opção
                    if not image_path:
                        prod_img_idx = st.session_state.get("_product_img_index", {})
                        image_path = prod.get("imagePath") or prod_img_idx.get(opt.get("productId") or "", "")

                    # sobrescritas por contexto (quando existirem)
                    for cm in _ctx_mods(opt):
                        if (cm.get("catalogContext") or "").upper() == ctx:
                            if (cm.get("price") or {}).get("value") is not None:
                                price_val = cm["price"]["value"]
                            if cm.get("status"):
                                status_val = cm["status"].upper()
                            if cm.get("imagePath"):
                                image_path = cm["imagePath"]

                    out.append({
                        "id": opt.get("id"),
                        "name": opt.get("name") or opt.get("label") or "",
                        "description": opt.get("description") or "",
                        "price": float(price_val or 0.0),
                        "status": status_val,
                        "paused": status_val in ("UNAVAILABLE", "PAUSED"),
                        "groupId": group_id,
                        "productId": product_id,
                        "imagePath": image_path,
                        "img": _normalize_img_url(image_path),   # 👈 adicione a URL final
                    })

    return out

def upload_complement_image_v1(merchant_id: str, file: bytes, filename: str):
    """
    POST /merchants/{merchantId}/image/upload
    Retorna path que pode ser associado depois.
    """
    url = f"{BASE_V1}/merchants/{merchant_id}/image/upload"
    files = {"image": (filename, file)}
    r = requests.post(url, headers={"Authorization": _headers().get("Authorization")}, files=files, timeout=60)
    if r.status_code in (200, 201):
        return True, r.json()
    return False, f"Erro {r.status_code}: {r.text[:300]}"

def list_categories_with_items(merchant_id: str, catalog_id: str):
    """
    GET /merchants/{merchantId}/catalogs/{catalogId}/categories?includeItems=true
    -> items[] -> optionGroups[] -> options[] (onde de fato vemos os complementos)
    """
    url = f"{BASE_V1}/merchants/{merchant_id}/catalogs/{catalog_id}/categories"
    params = {"includeItems": "true"}
    r = requests.get(url, headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def patch_option_group_status(merchant_id: str, group_id: str, new_status: str) -> tuple[bool, str]:
    """
    PATCH /catalog/v2.0/merchants/{merchantId}/optionGroups/{optionGroupId}/status
    """
    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/optionGroups/{group_id}/status"
    payload = {"status": new_status}
    r = requests.patch(url, json=payload, headers=_headers(), timeout=30)
    if r.status_code in (200, 202):
        return True, "Status do grupo atualizado."
    return False, f"Erro {r.status_code}: {r.text[:300]}"

def patch_option_group(merchant_id: str, group_id: str, *, name: str | None = None, description: str | None = None) -> tuple[bool, str]:
    """
    PATCH /catalog/v2.0/merchants/{merchantId}/optionGroups/{optionGroupId}
    """
    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/optionGroups/{group_id}"
    payload = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if not payload:
        return True, "Nada para alterar."
    r = requests.patch(url, json=payload, headers=_headers(), timeout=30)
    if r.status_code in (200, 202):
        return True, "Grupo atualizado."
    return False, f"Erro {r.status_code}: {r.text[:300]}"

def update_item_image_path(token: str, merchant_id: str, item_id: str, image_path: str) -> dict:
    """
    Atualiza o(s) produto(s) do item para usar o imagePath informado.
    Endpoint: PUT /catalog/v2.0/merchants/{merchantId}/items
    Payload mínimo: itens -> products (id e imagePath).
    Estratégia: lemos o item flat para descobrir os productIds e montamos o PUT.
    """
    # 1) Descobre products atuais do item (ids)
    flat = get_item_flat(token, merchant_id, item_id)
    if not flat.get("ok"):
        return {"status_code": flat.get("status_code", 0), "ok": False, "response": flat.get("response"), "detail": "GET flat falhou"}

    body_flat = flat["response"] if isinstance(flat["response"], dict) else {}
    products = body_flat.get("products") or []  # a estrutura comum traz "products" no flat

    if not isinstance(products, list) or not products:
        return {"status_code": 400, "ok": False, "response": {"error": "Item sem products para atualizar imagePath"}}

    # 2) Monta PUT com lista de products contendo imagePath
    put_payload = {
        "items": [
            {
                "id": item_id,
                "products": [{"id": p.get("id") or p.get("productId"), "imagePath": image_path} for p in products],
            }
        ]
    }

    url = f"{IFOOD_BASE_URL}/catalog/v2.0/merchants/{merchant_id}/items"
    resp = requests.put(url, json=put_payload, headers=_auth_headers(token), timeout=20)
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text}

    return {"status_code": resp.status_code, "ok": resp.ok, "response": payload, "sent": put_payload}
# ======== /iFood Catalog v2 — IMAGENS (HTTP) ========

# ============================ API: AUTH ===========================
def load_users_from_env():
    if not os.getenv("OPENAI_API_KEY"):
        st.warning("OPENAI_API_KEY não encontrada no .env (fallback sem IA).")
    users_raw = os.getenv("Q3_USERS_JSON") or "[]"
    try:
        users = json.loads(users_raw)
        return users if isinstance(users, list) else []
    except Exception:
        return []

def find_user(username: str):
    for u in load_users_from_env():
        if (u.get("username") or "").strip().lower() == (username or "").strip().lower():
            return u
    return None

@limiter.limit("auth")
def auth_with_ifood(client_id: str, client_secret: str) -> dict:
    """
    Autentica no iFood e retorna o JSON (normaliza chaves para snake_case).
    """
    url = AUTH_URL
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    payloads = [
        {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        {"grantType": "client_credentials", "clientId": client_id, "clientSecret": client_secret},
    ]
    tried = []
    for data in payloads:
        try:
            from urllib.parse import urlencode
            body = urlencode(data)
            r = requests.post(url, headers=headers, data=body, timeout=30)
            ct = r.headers.get("Content-Type", "")
            tried.append((url, r.status_code, r.text[:200]))
            if r.status_code == 200 and "application/json" in ct.lower():
                js = r.json() or {}
                js.setdefault("access_token", js.get("accessToken"))
                js.setdefault("refresh_token", js.get("refreshToken"))
                js.setdefault("expires_in", js.get("expiresIn", 300))
                return js
        except Exception as e:
            tried.append((url, "exc", str(e)))
    raise RuntimeError(f"Login iFood falhou: {tried}")

st.session_state.setdefault("api_connected", False)
st.session_state.setdefault("token_expires_at", 0.0)

def ensure_api_connection():
    """
    Conecta no iFood usando credenciais.
    Retorna True se conectou, False se falhou.
    """
    # Debug temporário
    st.sidebar.write("🔍 ensure_api_connection() chamado")
    
    if not st.session_state.get("logged_user"):
        st.sidebar.error("❌ Sem logged_user")
        return False

    # Se já conectado e token ainda válido
    if st.session_state.get("api_connected"):
        now = time.time()
        exp = float(st.session_state.get("token_expires_at") or 0)
        if now < (exp - 30):
            st.sidebar.success("✅ Já conectado (token válido)")
            return True

    st.sidebar.info("🔄 Tentando autenticar...")
    
    # Força recarregamento do .env
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    # Pega credenciais
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    # Fallback: JSON de usuários
    if not client_id or not client_secret:
        users = load_users_from_env()
        u = find_user(st.session_state.get("logged_user")) if users else None
        if not u and isinstance(users, list) and len(users) == 1:
            u = users[0]
        if u:
            client_id = client_id or u.get("client_id", "")
            client_secret = client_secret or u.get("client_secret", "")

    if not client_id or not client_secret:
        st.sidebar.error("❌ Credenciais ausentes")
        return False
    
    # Tenta autenticar
    try:
        st.sidebar.info(f"🔑 Usando CLIENT_ID: {client_id[:20]}...")
        resp = auth_with_ifood(client_id, client_secret)
        
        st.session_state.client_id = client_id
        st.session_state.client_secret = client_secret
        st.session_state.token = resp["access_token"]
        st.session_state.refresh_token = resp.get("refresh_token")
        st.session_state.token_expires_at = time.time() + resp.get("expires_in", 300)
        st.session_state.api_connected = True
        
        # ✅ NOVO: Limpar merchant_id antigo e cache
        st.session_state.merchant_id = None
        if "merchants_cache" in st.session_state:
            del st.session_state["merchants_cache"]
        
        # ✅ NOVO: Forçar limpeza do cache do Streamlit
        try:
            st.cache_data.clear()
        except:
            pass
        
        st.sidebar.success("✅ Autenticado com sucesso!")
        return True
        
    except Exception as e:
        st.sidebar.error(f"❌ Erro ao autenticar: {e}")
        return False

# ===== FUNÇÕES DE AUTENTICAÇÃO (devem vir cedo) =====
def _token_ok() -> bool:
    t = st.session_state.get("token") or ""
    return isinstance(t, str) and len(t.strip()) > 20

def force_logout_and_clear_all():
    keys_to_clear = [
        "token", "refresh_token", "token_expires_at", "api_connected",
        "logged_in", "logged_user", "merchant_id", "store_id",
        "client_id", "client_secret", "_access_token",
        "catalog_id", "catalog_context", "catalog_loaded",
        "_product_img_index", "_options_index", "_groups_to_draw",
        "favorites", "merchants_cache"
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    try:
        st.cache_data.clear()
        st.cache_resource.clear()
    except:
        pass

# ===== Resto do código continua aqui =====
    
    # Pega credenciais
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    # Fallback: JSON de usuários
    if not client_id or not client_secret:
        users = load_users_from_env()
        u = find_user(st.session_state.get("logged_user")) if users else None
        if not u and isinstance(users, list) and len(users) == 1:
            u = users[0]
        if u:
            client_id = client_id or u.get("client_id", "")
            client_secret = client_secret or u.get("client_secret", "")

    if not client_id or not client_secret:
        return False
    
    # Tenta autenticar
    try:
        resp = auth_with_ifood(client_id, client_secret)
        
        st.session_state.client_id = client_id
        st.session_state.client_secret = client_secret
        st.session_state.token = resp["access_token"]
        st.session_state.refresh_token = resp.get("refresh_token")
        st.session_state.token_expires_at = time.time() + resp.get("expires_in", 300)
        st.session_state.api_connected = True
        
        return True
        
    except Exception as e:
        st.sidebar.error(f"Erro OAuth: {e}")
        return False

def get_valid_token() -> str:
    if not st.session_state.get("logged_user"):
        return ""  # NADA de auth aqui
    
    pad = 30
    now = time.time()
    exp = float(st.session_state.get("token_expires_at") or 0)

    if st.session_state.get("token") and (now < (exp - pad)):
        return st.session_state.token

    # se não tem token válido, apenas devolve vazio:
    return ""

def _token_ok() -> bool:
    t = st.session_state.get("token") or ""
    return isinstance(t, str) and len(t.strip()) > 20  # JWT bem grandinho

def _headers():
    """
    Cabeçalho da API. NÃO tenta mais autenticar sozinho.
    Só funciona quando já existe token válido.
    """
    if not _token_ok():
        # Evita acionar ensure_api_connection() nos carregamentos da tela de login
        # e evita toasts/erros toda vez que a página reroda.
        return {"Authorization": "", "Content-Type": "application/json"}

    # Se já tem token, aí sim podemos renovar quando estiver perto de expirar
    return {
        "Authorization": f"Bearer {get_valid_token()}",
        "Content-Type": "application/json",
    }

# ============================ API: GETs ===========================
@limiter.limit("merchant")
def get_merchants(token):
    """
    GET /merchant/v1.0/merchants
    Retorna lista de merchants autorizados.
    """
    if not token:
        raise RuntimeError("Token vazio ao chamar get_merchants()")
    
    url = f"{BASE}/merchant/v1.0/merchants"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        r = SESSION.get(url, headers=headers, timeout=20)
        
        # Debug temporário
        if r.status_code != 200:
            st.sidebar.error(f"❌ get_merchants falhou: {r.status_code}")
            st.sidebar.code(f"Response: {r.text[:300]}")
        
        r.raise_for_status()
        return r.json()
        
    except requests.HTTPError as e:
        raise RuntimeError(f"merchants {e.response.status_code}: {e.response.text[:300]}")
    except Exception as e:
        raise RuntimeError(f"Erro ao buscar merchants: {str(e)}")
    
@limiter.limit("catalog")
def get_catalogs(token, merchant_id):
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/catalogs"
    r = SESSION.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"catalogs {r.status_code}: {r.text[:300]}")
    return r.json()

# Onde quer que você chame get_categories(), adicione antes:
st.sidebar.write("🔍 **Debug - Parâmetros:**")
st.sidebar.code(f"""
Token exists: {bool(st.session_state.get('token'))}
Token (first 30): {str(st.session_state.get('token', ''))[:30]}...
Merchant ID: {st.session_state.get('merchant_id')}
Catalog ID: {st.session_state.get('catalog_id')}
""")

# Testa construção da URL
token = st.session_state.get('token')
merchant_id = st.session_state.get('merchant_id')
catalog_id = st.session_state.get('catalog_id')

if token and merchant_id and catalog_id:
    test_url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/catalogs/{catalog_id}/categories"
    st.sidebar.success(f"✅ URL será: {test_url}")
else:
    st.sidebar.error("❌ Parâmetros ausentes!")
    st.sidebar.write(f"Token: {bool(token)}")
    st.sidebar.write(f"Merchant: {merchant_id}")
    st.sidebar.write(f"Catalog: {catalog_id}")

@limiter.limit("catalog")
def get_categories(token, merchant_id, catalog_id):
    """
    GET /catalog/v2.0/merchants/{merchantId}/catalogs/{catalogId}/categories
    """
    if not token or not merchant_id or not catalog_id:
        raise RuntimeError(f"Parâmetros ausentes: token={bool(token)}, merchant={merchant_id}, catalog={catalog_id}")
    
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/catalogs/{catalog_id}/categories"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        r = SESSION.get(url, headers=headers, timeout=20)
        
        # Debug
        if r.status_code != 200:
            st.sidebar.error(f"❌ get_categories falhou: {r.status_code}")
            st.sidebar.code(f"URL: {url}")
            st.sidebar.code(f"Response: {r.text[:300]}")
        
        r.raise_for_status()
        return r.json()
        
    except requests.HTTPError as e:
        raise RuntimeError(f"categories {e.response.status_code}: {e.response.text[:300]}")
    except Exception as e:
        raise RuntimeError(f"Erro ao buscar categorias: {str(e)}")

@limiter.limit("catalog")
def get_category_items(token, merchant_id, category_id):
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/categories/{category_id}/items"
    r = SESSION.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("items", [])

@limiter.limit("catalog")
def get_item_detail(token, merchant_id, item_id, catalog_context="DEFAULT"):
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/items/{item_id}"
    r = SESSION.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params={"catalogContext": catalog_context},
        timeout=30,
    )
    if r.status_code != 200:
        return None
    return r.json()

def extract_options_from_item_detail(item_detail):
    if not item_detail: return []
    results = []
    og = item_detail.get("optionGroups") or []
    for g in og:
        gname = g.get("name") or ""
        for op in (g.get("options") or []):
            oid = op.get("id") or op.get("optionId")
            oname = op.get("name") or op.get("label") or "(sem nome)"
            ostatus = (op.get("status") or "").upper()
            if oid:
                results.append({"id": oid, "name": oname, "group": gname, "status": ostatus})
    if isinstance(item_detail.get("options"), list):
        for op in item_detail["options"]:
            oid = op.get("id") or op.get("optionId")
            oname = op.get("name") or op.get("label") or "(sem nome)"
            ostatus = (op.get("status") or "").upper()
            if oid:
                results.append({"id": oid, "name": oname, "group": "", "status": ostatus})
    return results

def get_item_flat(token: str, merchant_id: str, item_id: str) -> dict:
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/items/{item_id}/flat"
    r = SESSION.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"GET item flat falhou: {r.status_code} {r.text[:200]}")
    return r.json() or {}

# ============================ PATCH/UPLOAD ========================

@limiter.limit("catalog")
def patch_item_status(token: str, merchant_id: str, item_id: str, new_status: str, catalog_context: str | None = None):
    """
    PATCH /merchants/{merchantId}/items/status
    """
    if new_status not in ("AVAILABLE", "UNAVAILABLE"):
        raise ValueError("new_status deve ser 'AVAILABLE' ou 'UNAVAILABLE'.")
    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/items/status"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    if catalog_context:
        payload = {"itemId": item_id, "statusByCatalog": [{"status": new_status, "catalogContext": catalog_context}]}
    else:
        payload = {"itemId": item_id, "status": new_status}
    r = SESSION.patch(url, headers=headers, json=payload, timeout=60)
    try: body = r.json()
    except Exception: body = r.text
    return r.status_code, body

def _try_http(http, method, url, headers=None, timeout=20, **req_kwargs):
    headers = headers or {}
    if 'json' in req_kwargs:
        headers.setdefault('Content-Type', 'application/json')
    def _do():
        try:
            return http.request(method, url, headers=headers, timeout=timeout, **req_kwargs)
        except Exception as e:
            return e
    resp = _do()
    if isinstance(resp, Exception):
        return False, f"{type(resp).__name__}: {resp}"
    if resp.status_code == 401:
        try:
            get_valid_token()
            headers["Authorization"] = f"Bearer {st.session_state.get('token','')}"
            resp = _do()
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
    ok = 200 <= getattr(resp, "status_code", 0) < 300
    try: payload = resp.json()
    except Exception: payload = getattr(resp, "text", "")
    out = {"status": getattr(resp, "status_code", None), "body": payload}
    return (True, out) if ok else (False, out)

@limiter.limit("catalog")
def patch_option_status(token: str, merchant_id: str, option_id: str, new_status: str, catalog_context: str | None = None):
    """
    PATCH Catalog v2: /catalog/v2.0/merchants/{merchantId}/options/status
    Body esperado (singular):
    {
      "optionId": "uuid",
      "status": "AVAILABLE" | "UNAVAILABLE" | "PAUSED",
      "catalogContext": "WHITELABEL" | "DEFAULT" | ...
    }
    """
    if not _is_uuid(option_id):
        return False, f"ID inválido para optionId: {option_id!r}"

    base = os.getenv("CATALOG_BASE") or "https://merchant-api.ifood.com.br/catalog/v2.0"
    url = f"{base.rstrip('/')}/merchants/{merchant_id}/options/status"

    payload = {
        "optionId": option_id.strip(),
        "status": new_status.strip().upper(),
    }
    if catalog_context:
        payload["catalogContext"] = str(catalog_context).strip()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    r = requests.patch(url, json=payload, headers=headers, timeout=30)
    if r.status_code in (200, 202):
        return True, "Status atualizado"
    try:
        js = r.json()
    except Exception:
        js = {"text": r.text}
    return False, f"{r.status_code}: {js}"

def _detect_mime(name: str) -> str:
    ext = (name or "").lower().rsplit(".", 1)[-1]
    return _ALLOWED_EXT.get(ext, "image/jpeg")

@limiter.limit("image")
def upload_image_to_ifood(token: str, merchant_id: str, file_name: str, file_bytes) -> str:
    """
    Upload de imagem e retorno de imagePath (200/201/202).
    """
    file_bytes = optimize_image(file_bytes)
    if hasattr(file_bytes, "tobytes"): file_bytes = file_bytes.tobytes()
    elif hasattr(file_bytes, "read"):  file_bytes = file_bytes.read()
    elif isinstance(file_bytes, bytearray): file_bytes = bytes(file_bytes)

    size = len(file_bytes or b"")
    if size == 0: raise RuntimeError("Arquivo vazio.")
    if size > 5 * 1024 * 1024: raise RuntimeError("Arquivo excede 5MB.")

    mime = _detect_mime(file_name)
    b64 = base64.b64encode(file_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    url = f"{BASE}/catalog/v2.0/merchants/{merchant_id}/image/upload/"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    payload = {"image": data_url}
    r = SESSION.post(url, headers=headers, json=payload, timeout=60)

    try: js = r.json()
    except Exception: js = {}

    if r.status_code in (200, 201, 202):
        for k in ("imagePath", "path", "url"):
            v = js.get(k) if isinstance(js, dict) else None
            if isinstance(v, str) and v.strip():
                return v.strip()
        if isinstance(js, str) and js.strip():
            return js.strip()
        raise RuntimeError(f"Upload ok ({r.status_code}), mas sem imagePath: {str(js)[:200]}")
    if r.status_code == 413: raise RuntimeError("Imagem muito grande (413). Limite: 5MB.")
    if r.status_code in (400, 415): raise RuntimeError("Formato inválido. Envie PNG/JPG/JPEG.")
    raise RuntimeError(f"Falha no upload ({r.status_code}). {str(js)[:200]}")

# ============================ CACHES GETs ========================
@st.cache_data(show_spinner=False, ttl=600)
def cached_item_flat(token, merchant_id, item_id):
    return get_item_flat(token, merchant_id, item_id)

@st.cache_data(show_spinner=False, ttl=300)
def cached_merchants(token):
    """Cache de merchants com TTL de 5 minutos"""
    if not token:
        raise RuntimeError("Token vazio ao chamar cached_merchants()")
    return get_merchants(token)

@st.cache_data(show_spinner=False, ttl=300)
def cached_catalogs(token, merchant_id): return get_catalogs(token, merchant_id)

@st.cache_data(show_spinner=False, ttl=300)
def cached_categories(token, merchant_id, catalog_id):
    """Cache de categorias com TTL de 5 minutos"""
    if not token or not merchant_id or not catalog_id:
        raise RuntimeError(
            f"cached_categories: parâmetros ausentes - "
            f"token={bool(token)}, merchant={merchant_id}, catalog={catalog_id}"
        )
    return get_categories(token, merchant_id, catalog_id)

@st.cache_data(show_spinner=False, ttl=600)
def cached_items_by_category(token, merchant_id, category_id): return get_category_items(token, merchant_id, category_id)

@st.cache_data(show_spinner=False, ttl=600)
def cached_item_detail(token, merchant_id, item_id):
    ctx = st.session_state.get("catalog_context") or "DEFAULT"
    return get_item_detail(token, merchant_id, item_id, catalog_context=ctx)

# ============================ HELPERS DE AUTENTICAÇÃO ============================

def _token_ok() -> bool:
    """Verifica se existe um token válido na sessão"""
    t = st.session_state.get("token") or ""
    return isinstance(t, str) and len(t.strip()) > 20  # JWT tem dezenas de chars

def _get_current_user() -> str:
    """Retorna o nome do usuário logado ou 'Visitante'"""
    return st.session_state.get("logged_user") or "Visitante"

# ============================ LOGIN/UI INICIAL ===================
def load_users_from_env_for_login():
    # wrapper para não repetir warning
    users_raw = os.getenv("Q3_USERS_JSON") or "[]"
    try:
        users = json.loads(users_raw)
        return users if isinstance(users, list) else []
    except Exception:
        return []

def _token_ok() -> bool:
    t = st.session_state.get("token") or ""
    return isinstance(t, str) and len(t.strip()) > 20  # JWT tem dezenas de chars

# ===== Helpers de login (unifica DB e JSON antigo) =====
def q3_find_user_any(login: str):
    """
    1) Tenta no SQLite (email ou username)
    2) Se não achar, tenta no Q3_USERS_JSON (se você ainda usa em dev)
    Retorna dict compatível: {"id":..., "username":..., "email":..., "pw_hash":...}
    """
    row = users_find_by_login(login or "")
    if row:
        return {"id": row["id"], "username": row["username"], "email": row["email"], "pw_hash": row["pw_hash"]}
    # fallback antigo (Q3_USERS_JSON) — opcional
    u = find_user(login)  # sua função antiga que lia o JSON do .env
    if u:
        return {"id": -1, "username": u.get("username"), "email": u.get("email",""), "pw_hash": u.get("pw_hash")}
    return None

def q3_verify_user_password(user_obj: dict, plain: str) -> bool:
    if not user_obj:
        return False
    return check_password_hash(user_obj.get("pw_hash",""), plain or "")

# ===== Reset por token na URL (?reset=TOKEN) =====
try:
    _qp = st.query_params  # streamlit novo
except Exception:
    _qp = st.experimental_get_query_params()  # fallback antigo

_reset_token = None
if isinstance(_qp, dict):
    _reset_token = _qp.get("reset")
    if isinstance(_reset_token, list):
        _reset_token = _reset_token[0]

def render_reset_password_flow(token: str):
    """Tela de 'definir nova senha' ao abrir o link do e-mail."""
    # Se você colou os helpers do PASSO 1 (SQLite), usamos:
    if "users_validate_reset_token" not in globals() or "users_consume_reset" not in globals():
        st.error("Redefinição de senha não está habilitada (helpers de usuários ausentes).")
        return

    uid = users_validate_reset_token(token)
    st.title("🔑 Redefinir senha")
    if not uid:
        st.error("Link inválido ou expirado.")
        return

    with st.form("reset_pw_form"):
        new_pw = st.text_input("Nova senha", type="password")
        confirm = st.text_input("Confirmar nova senha", type="password")
        ok = st.form_submit_button("Salvar nova senha")

    if ok:
        if not new_pw or len(new_pw) < 8:
            st.warning("Use ao menos 8 caracteres.")
            return
        if new_pw != confirm:
            st.warning("As senhas não conferem.")
            return
        users_consume_reset(uid, new_pw)
        st.success("Senha redefinida. Faça login.")

def render_login():
    # ---- estilos do login ----
    st.markdown("""
    <style>
      .q3-login-wrap{display:flex;gap:28px;align-items:flex-start; margin: 12px 0 8px;}
      .q3-login-left{flex:1}
      .q3-login-right{flex:1; background:#151922; border:1px solid #2e3241; border-radius:14px; padding:18px;}
      .q3-hero { display:flex; align-items:center; gap:16px; margin: 4px 0 14px; }
      .q3-hero .q3-logo { height:88px; width:auto; display:block; }
      .q3-hero .q3-title { display:flex; flex-direction:column; justify-content:center; }
      .q3-hero .q3-h1 { margin:0; line-height:1.15; font-size:38px; font-weight:800; }
      .q3-hero .q3-sub { margin-top:6px; opacity:.8; }
      .q3-grad {
        background: linear-gradient(90deg,#FF4BC6,#8B00FF);
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent; color: transparent;
      }
      .q3-fortune {
        margin-top:8px; background:rgba(255,255,255,.08);
        border:1px solid rgba(255,255,255,.12); border-radius:12px;
        padding:14px; font-size:15px;
      }
      @media (max-width: 920px){
        .q3-login-wrap{flex-direction:column;}
      }
    </style>
    """, unsafe_allow_html=True)

    # ---- util: carregar logo como data URI ----
    def _img_data_uri_inline(path: str) -> str:
        import os, base64
        ext = os.path.splitext(path)[1].lower()
        if ext in {".png", ".apng"}: mime = "image/png"
        elif ext in {".jpg", ".jpeg"}: mime = "image/jpeg"
        elif ext == ".gif": mime = "image/gif"
        else: mime = "application/octet-stream"
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return f"data:{mime};base64,{b64}"
        except Exception:
            return ""

    # ---- frase do dia ----
    def _fortune_of_the_day() -> str:
        import random
        from datetime import date
        local = [
            "Hoje é um ótimo dia para encantar clientes 🍀",
            "Pequenas melhorias viram grandes resultados.",
            "Cada pedido é uma nova chance de brilhar ✨",
            "Ouvir o cliente é o atalho para evoluir.",
            "Consistência vence. Um passo de cada vez!",
            "Simplicidade e carinho: receita de sucesso.",
            "Quem mede, melhora. Bora crescer hoje?",
        ]
        seed = int(date.today().strftime("%Y%m%d"))
        random.seed(seed)
        msg = random.choice(local)

        _getter = globals().get("_get_openai_client")
        if callable(_getter):
            try:
                client, err = _getter()
                if client and not err:
                    resp = client.chat.completions.create(
                        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                        messages=[
                            {"role":"system","content":"Escreva uma frase curta, otimista e profissional para motivar a equipe de um restaurante. Sem clichês óbvios, 12–18 palavras, em PT-BR."},
                            {"role":"user","content":"Gerar 1 frase do dia."},
                        ],
                        temperature=0.9, max_tokens=60,
                    )
                    ai = (resp.choices[0].message.content or "").strip()
                    if ai:
                        msg = ai
            except Exception:
                pass
        return msg

    logo_src = _img_data_uri_inline("logo-q3.png")
    logo_html = (f'<img src="{logo_src}" alt="Q3" class="q3-logo" />'
                 if logo_src else
                 '<div style="width:88px;height:88px;border-radius:10px;background:linear-gradient(180deg,#FF4BC6,#8B00FF);"></div>')      

    # ---- layout login ----
    st.markdown('<div class="q3-login-wrap">', unsafe_allow_html=True)

    # Lado esquerdo: hero + frase
    st.markdown('<div class="q3-login-left">', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="q3-hero">
      {logo_html}
      <div class="q3-title">
        <div class="q3-h1"><span class="q3-grad">Bem-vindo(a)!</span></div>
        <div class="q3-sub">Acesse para gerenciar catálogos e avaliações.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f'<div class="q3-fortune">💡 <b>Frase do dia</b><br>{_fortune_of_the_day()}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)  # /left

    # Lado direito: formulário
    st.markdown('<div class="q3-login-right">', unsafe_allow_html=True)

    # ----- FORM DE LOGIN -----
    st.markdown("#### Acesse sua conta")

    # 1) aceita e-mail OU usuário
    login_input = st.text_input(
        "E-mail ou usuário", 
        key="login_user_input",  # ✅ key única
        placeholder="seu e-mail ou usuário"
    )
    senha = st.text_input(
        "Senha", 
        type="password", 
        key="login_pass_input",  # ✅ key única
        placeholder="********"
    )

    # helpers
    def _resolve_user(login: str):
        if "users_find_by_login" in globals():
            row = users_find_by_login(login or "")
            if row:
                return {"id": row["id"], "username": row["username"], "email": row["email"], "pw_hash": row["pw_hash"]}
        u = find_user(login)
        if u:
            return {"id": -1, "username": u.get("username"), "email": u.get("email",""), "pw_hash": u.get("pw_hash")}
        return None

    def _verify_pw(user_obj, plain: str) -> bool:
        return bool(user_obj) and check_password_hash(user_obj.get("pw_hash",""), plain or "")

    # 2) botões: Entrar + Esqueci a senha
    c_login, c_forgot = st.columns([3,1])

    with c_login:
        btn_enter = st.button(
            "Entrar", 
            type="primary", 
            use_container_width=True,
            key="btn_login_enter"  # ✅ key única
        )
        
        if btn_enter:
            u = _resolve_user(login_input)
            if not u or not _verify_pw(u, senha):
                st.error("Usuário/e-mail ou senha inválidos.")
                st.stop()

            # ✅ Marca como logado
            st.session_state.logged_user = (u.get("username") or u.get("email"))
            st.session_state["user_id"] = u.get("id")
            st.session_state.logged_in = True

            # ✅ DEBUG TEMPORÁRIO (remova depois)
            st.write(f"🔍 logged_user: {st.session_state.logged_user}")
            st.write(f"🔍 _token_ok(): {_token_ok()}")
            st.write(f"🔍 _is_logged(): {_is_logged()}")
            
            # PAUSE para ver o debug
            if st.button("Continuar após debug"):
                st.rerun()
            
            # ✅ IMPORTANTE: Reseta flag de conexão
            st.session_state.api_connected = False
            
            # ✅ CRÍTICO: Usar st.rerun() direto (sem mensagens antes)
            st.rerun()

    with c_forgot:
        with st.popover("Esqueci a senha", use_container_width=True):
            email = st.text_input(
                "Seu e-mail cadastrado", 
                key="forgot_email_input"  # ✅ key única
            )
            if st.button(
                "Enviar link", 
                key="btn_send_reset_link"  # ✅ key única
            ):
                if "users_generate_reset" not in globals():
                    st.info("Redefinição não habilitada (helpers de usuários ausentes).")
                else:
                    ok, msg, dev_link = users_generate_reset(email)
                    st.info(msg)
                    if dev_link:
                        st.caption(f"(Dev) Link de reset: {dev_link}")
                        
    st.markdown('</div>', unsafe_allow_html=True)  # /right
    st.markdown('</div>', unsafe_allow_html=True)  # /wrap

# ============================ PONTO DE ENTRADA PRINCIPAL ============================
# ✅ ESTA SEÇÃO DEVE ESTAR NO FINAL DO ARQUIVO, APÓS TODAS AS FUNÇÕES

# ========== 1. VERIFICAÇÃO DE LOGIN (OBRIGATÓRIO) ==========
# ✅ Debug temporário
st.sidebar.write("🔍 Verificando login...")
st.sidebar.write(f"logged_user: {st.session_state.get('logged_user')}")
st.sidebar.write(f"_is_logged(): {_is_logged()}")

if not _is_logged():
    st.sidebar.write("❌ Não logado → Renderizando tela de login")
    render_login()
    st.stop()
st.sidebar.success("✅ Login OK! Prosseguindo...")

# ========== 2. GARANTIR CONEXÃO COM API ==========
if not st.session_state.get("api_connected"):
    with st.spinner("🔐 Conectando na API do iFood..."):
        try:
            success = ensure_api_connection()
            if not success:
                st.error("❌ Falha ao conectar no iFood. Verifique `.env`")
                if st.button("🚪 Fazer Logout", key="logout_conn_fail"):
                    force_logout_and_clear_all()
                    st.rerun()
                st.stop()
        except Exception as e:
            st.error(f"❌ Erro ao conectar: {e}")
            if st.button("🚪 Fazer Logout", key="logout_conn_error"):
                force_logout_and_clear_all()
                st.rerun()
            st.stop()

# ============================ TOP BAR/AÇÕES ======================
col_connected, col_favs, col_reload, col_logout = st.columns([5, 2, 2, 1])

with col_connected:
    if _token_ok():
        # Mostra qual CLIENT_ID está sendo usado
        current_client = st.session_state.get("client_id", os.getenv("CLIENT_ID", ""))[:20] + "..."
        st.markdown(
            f'<div class="q3-connected">✅ Conectado! (App: {current_client})</div>', 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="q3-connected" style="background:#7a1c1c">❌ Desconectado</div>', 
            unsafe_allow_html=True
        )

with col_favs:
    fav_count = len(st.session_state.get("favorites") or [])
    st.caption(f"⭐ Favoritas: {fav_count}")

with col_reload:
    if st.button("🔄 Recarregar dados"):
        st.cache_data.clear()
        st.rerun()

with col_logout:
    if st.button("🚪 Sair"):
        force_logout_and_clear_all()
        st.success("Logout completo! Recarregue a página (F5)")
        st.stop()

st.session_state.setdefault("catalog_id", None)

# ✅ GARANTIR que temos token válido
token = st.session_state.get("token")

if not token:
    st.error("❌ Token não encontrado. Faça login novamente.")
    if st.button("🔄 Reconectar"):
        st.session_state.api_connected = False
        st.rerun()
    st.stop()

try:
    with q3_progress("Carregando lojas...") as prog:
        prog(10, "Buscando lojas...")

        # ✅ NOVO: Botão de debug para forçar reload
        if st.button("Forçar atualização de lojas", type="primary"):
            _reset_all_caches()
            st.rerun()

            st.cache_data.clear()
            if "merchants_cache" in st.session_state:
                del st.session_state["merchants_cache"]
            st.rerun()
        
        # ✅ Passa o token explicitamente
        token = st.session_state.get("token")
        merchants = cached_merchants(token)
        
        if not merchants:
            st.warning("Nenhuma loja autorizada encontrada.")
            st.info("Autorize o app no portal do iFood: https://portal.ifood.com.br")
            st.stop()

        # ✅ DEBUG: Mostrar quantas lojas foram retornadas
        st.sidebar.write(f"🏪 Lojas encontradas: {len(merchants)}")
        for m in merchants[:5]:  # Mostra até 5 lojas
            st.sidebar.code(f"{m.get('name')} - {m.get('id')}")
        
        prog(30, f"{len(merchants)} loja(s) encontrada(s)")
        
        # Filtra favoritos
        fav_ids = set(st.session_state.get("favorites") or [])
        filtered_merchants = [m for m in merchants if m.get('id') in fav_ids] if st.session_state.get("show_favorites_only") else merchants

        # Filtro por nome
        name_query = (st.session_state.get("loja_query") or "").strip().lower()
        if name_query:
            filtered_merchants = [m for m in filtered_merchants if name_query in (m.get("name") or "").lower()]

        if not filtered_merchants:
            st.info("Nenhuma loja encontrada para esse filtro. Mostrando todas.")
            filtered_merchants = merchants

        prog(60, "Preparando lista de lojas...")
        
        merchant_labels = [f"{m.get('name')} ({m.get('id')})" for m in filtered_merchants]
        merchant_ids = [m.get("id") for m in filtered_merchants]
        
        current_mid = st.session_state.get("merchant_id")
        default_idx = merchant_ids.index(current_mid) if (current_mid in merchant_ids) else 0
        
        prog(80, "Renderizando seletor...")
        
        sel_idx = st.selectbox(
            "Escolha a loja", 
            options=list(range(len(merchant_labels))),
            index=(default_idx if merchant_labels else 0),
            format_func=lambda i: merchant_labels[i] if merchant_labels else "",
            key="merchant_selector"
        )

        st.session_state.merchant_id = merchant_ids[sel_idx]
        merchant_name = filtered_merchants[sel_idx].get("name")

        # ✅ GARANTIR que catalog_id está definido
        if not st.session_state.get("catalog_id"):
            try:
                # Busca catálogos do merchant
                catalogs = cached_catalogs(token, st.session_state.merchant_id) or []
                
                if catalogs:
                    # Pega o primeiro catálogo disponível
                    first_catalog = catalogs[0]
                    catalog_id = first_catalog.get("id") or first_catalog.get("catalogId")
                    
                    if catalog_id:
                        st.session_state.catalog_id = catalog_id
                        st.sidebar.success(f"📋 Catálogo carregado: {catalog_id[:8]}...")
                    else:
                        st.error("❌ Catálogo sem ID")
                        st.stop()
                else:
                    st.warning("⚠️ Nenhum catálogo encontrado para esta loja")
                    st.stop()
                    
            except Exception as e:
                st.error(f"❌ Erro ao carregar catálogo: {e}")
                st.stop()
        
        prog(100, "Concluído!")

        # Botão de favoritos
        cur_mid = st.session_state.merchant_id
        is_fav = _is_favorite(cur_mid)
        fav_label = "★ Remover dos favoritos" if is_fav else "☆ Adicionar aos favoritos"
        
        if st.button(fav_label, key=f"btn_toggle_fav_{cur_mid}"):
            _toggle_favorite(cur_mid)
            st.toast(("Removida" if is_fav else "Adicionada") + " aos favoritos", icon="⭐")
            st.rerun()
        
        st.markdown("―")

        # ... resto do código de catálogos ...

except RuntimeError as e:
    st.error(f"❌ {e}")
    st.stop()
except Exception as e:
    st.error(f"❌ Erro inesperado: {e}")
    st.stop()

# ============================ HEADER/TOPO ========================
def _img_data_uri(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    mime = "image/png" if ext in {".png", ".apng"} else "image/jpeg" if ext in {".jpg",".jpeg"} else "image/gif" if ext==".gif" else "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"

def render_header_with_logo(logo_filename: str = "logo-q3.png", logo_height: int = 88):
    st.markdown(f"""
    <style>
      .q3-hero {{ display:flex; align-items:center; gap:16px; margin: 4px 0 20px; }}
      .q3-hero .q3-logo {{ height:{logo_height}px; width:auto; display:block; }}
      .q3-hero .q3-title {{ display:flex; flex-direction:column; justify-content:center; }}
      .q3-hero .q3-h1 {{ margin:0; line-height:1.15; font-size:38px; font-weight:800; }}
      .q3-hero .q3-sub {{ margin-top:6px; opacity:.8; }}
      .q3-grad {{
        background: linear-gradient(90deg,#FF4BC6,#8B00FF);
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent; color: transparent;
      }}
      @media (max-width: 720px) {{
        .q3-hero {{ flex-direction:column; align-items:flex-start; gap:8px; }}
      }}
    </style>
    """, unsafe_allow_html=True)

    if os.path.exists(logo_filename):
        src = _img_data_uri(logo_filename)
        logo_html = f'<img src="{src}" alt="Q3 logo" class="q3-logo" />'
    else:
        logo_html = (f'<div style="width:{logo_height}px;height:{logo_height}px;'
                     'border-radius:10px;background:linear-gradient(180deg,#FF4BC6,#8B00FF);"></div>')

    st.markdown(f"""
    <div class="q3-hero">
      {logo_html}
      <div class="q3-title">
        <div class="q3-h1"><span class="q3-grad">Automatiza</span></div>
        <div class="q3-sub">Automatizador de operações</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

render_header_with_logo("logo-q3.png")

# ====================== CONFIRMAÇÃO (Pausar/Ativar) ====================
def open_confirm(action: str, kind: str, entries: list, danger: bool = False):
    if not entries:
        st.warning("Selecione ao menos 1 registro.")
        return
    nice_action = "Pausar" if action == "pause" else "Ativar"
    st.session_state["confirm_ctx"] = {
        "action": action, "kind": kind, "entries": entries,
        "nice_action": nice_action, "danger": danger,
    }

def _clear_confirm(): st.session_state["confirm_ctx"] = None

def _run_confirmed_action():
    ctx = st.session_state.get("confirm_ctx")
    if not ctx:
        return
    new_status = "UNAVAILABLE" if ctx["action"] == "pause" else "AVAILABLE"
    ok, fails = 0, []
    for e in ctx["entries"]:
        _id = str(e.get("id") or e)
        if not _id:
            continue

        try:
            if ctx["kind"] == "item":
                if "patch_item_status" in globals():
                    code, _ = patch_item_status(
                        st.session_state.token,
                        st.session_state.merchant_id,
                        _id,
                        new_status,
                        catalog_context=(st.session_state.catalog_context or "DEFAULT"),
                    )
                    ok += 1 if code in (200, 201, 202) else 0
                    if code not in (200, 201, 202):
                        fails.append((_id, code))
                else:
                    code = _patch_item_status_one(_id, new_status)
                    ok += 1 if code in (200, 201, 202) else 0
                    if code not in (200, 201, 202):
                        fails.append((_id, code))

            elif ctx["kind"] == "option":
                if "patch_option_status" in globals():
                    code, _ = patch_option_status(
                        st.session_state.token,
                        st.session_state.merchant_id,
                        _id,
                        new_status,
                        catalog_context=(st.session_state.catalog_context or "DEFAULT"),
                    )
                    ok += 1 if code in (200, 201, 202) else 0
                    if code not in (200, 201, 202):
                        fails.append((_id, code))
                else:
                    code = _patch_option_status_one(_id, new_status)
                    ok += 1 if code in (200, 201, 202) else 0
                    if code not in (200, 201, 202):
                        fails.append((_id, code))
        except Exception as ex:
            fails.append((_id, str(ex)))

    try:
        st.cache_data.clear()
    except Exception:
        pass

    if ok:
        st.toast(f"{ok} registro(s) atualizados para {new_status}.", icon="✅")
    if fails:
        st.toast(f"{len(fails)} falha(s). Veja log/status.", icon="⚠️")
        st.warning("Falhas:\n" + "\n".join([f"- {i}: {c}" for i, c in fails[:10]]))

    _clear_confirm()
    st.rerun()

# ---------- Fallbacks de PATCH de status ----------
def _auth_headers_basic():
    return {
        "Authorization": f"Bearer {st.session_state.get('token')}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def _patch_item_status_one(item_id: str, status: str) -> int:
    """
    PATCH /catalog/v1.0/merchants/{merchantId}/items/status
    Body: {"items":[{"id": "...", "status": "AVAILABLE|UNAVAILABLE"}]}
    """
    import json as _json
    mid = st.session_state.get("merchant_id")
    ctx = st.session_state.get("catalog_context") or "DEFAULT"
    url = f"{BASE}/catalog/v1.0/merchants/{mid}/items/status"
    payload = {"items": [{"id": str(item_id), "status": status}]}
    r = (globals().get("SESSION") or requests.Session()).patch(
        url,
        headers=_auth_headers_basic(),
        params={"catalogContext": ctx},
        data=_json.dumps(payload),
        timeout=30,
    )
    return r.status_code

def _patch_option_status_one(option_id: str, status: str) -> int:
    """
    PATCH /catalog/v1.0/merchants/{merchantId}/options/status
    Body: {"options":[{"id": "...", "status": "AVAILABLE|UNAVAILABLE"}]}
    """
    import json as _json
    mid = st.session_state.get("merchant_id")
    ctx = st.session_state.get("catalog_context") or "DEFAULT"
    url = f"{BASE}/catalog/v1.0/merchants/{mid}/options/status"
    payload = {"options": [{"id": str(option_id), "status": status}]}
    r = (globals().get("SESSION") or requests.Session()).patch(
        url,
        headers=_auth_headers_basic(),
        params={"catalogContext": ctx},
        data=_json.dumps(payload),
        timeout=30,
    )
    return r.status_code

# ---------------------- UI do popup de confirmação ----------------------
def show_confirm_popup():
    ctx = st.session_state.get("confirm_ctx")
    if not ctx:
        return

    nice = ctx.get("nice_action") or ("Pausar" if ctx.get("action") == "pause" else "Ativar")
    kind = "itens" if ctx.get("kind") == "item" else "complementos"
    entries = ctx.get("entries") or []
    danger = bool(ctx.get("danger"))

    with st.container(border=True):
        st.markdown(f"### Confirmação — {nice} {kind}")
        st.caption(f"{len(entries)} selecionado(s).")
        for e in entries[:10]:
            _name = e.get("name") or e.get("id") or "-"
            _id   = e.get("id") or "-"
            st.write(f"- **{_name}** (`{_id}`)")
        if len(entries) > 10:
            st.caption(f"... e mais {len(entries) - 10}.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Cancelar", use_container_width=True):
                _clear_confirm()
                st.rerun()
        with c2:
            if st.button(("⚠️ " if danger else "") + "Confirmar", type="primary", use_container_width=True):
                _run_confirmed_action()

# ---------------------- Agrupamento de complementos ----------------------
def _group_options_by_id(rows):
    """
    Agrupa complementos pelo optionId (mostra 1 por opção).
    Agrega: groups, parents, categories, parentIds.
    Mantém price/price_str (pega o primeiro valor válido).
    """
    agg = {}
    for r in rows or []:
        oid = str(r.get("optionId") or "").strip()
        if not oid:
            continue
        gname  = r.get("group") or ""
        parent = r.get("parent") or ""
        cat    = r.get("category") or ""
        pid    = str(r.get("parentId") or "")

        if oid not in agg:
            agg[oid] = {
                "optionId": oid,
                "name": r.get("name") or oid,
                "status": (r.get("status") or "AVAILABLE").upper(),
                "groups": set(),
                "parents": [],
                "categories": set(),
                "parentIds": set(),
                "parentId": pid,
                "price": r.get("price"),
                "price_str": r.get("price_str") or "0,00",
                "imagePath": r.get("imagePath") or "",   # 👈 ADICIONE
                "productId": r.get("productId") or "",   # 👈 ADICIONE
            }

        a = agg[oid]
        if gname:  a["groups"].add(gname)
        if parent: a["parents"].append(parent)
        if cat:    a["categories"].add(cat)
        if pid:    a["parentIds"].add(pid)

        if a.get("price") in (None, "", {}, []):
            a["price"] = r.get("price")
            a["price_str"] = r.get("price_str") or a["price_str"]
        
        if not a.get("imagePath") and r.get("imagePath"):
            a["imagePath"] = r["imagePath"]
        if not a.get("productId") and r.get("productId"):
            a["productId"] = r["productId"]

        n_new, n_old = (r.get("name") or ""), (a.get("name") or "")
        if len(n_new) > len(n_old):
            a["name"] = n_new

    out = []
    for v in agg.values():
        out.append({
            "optionId": v["optionId"],
            "name": v["name"],
            "group": ", ".join(sorted(v["groups"])) or "-",
            "parent": ", ".join(sorted(set(v["parents"]))) or "-",
            "category": ", ".join(sorted(v["categories"])) or "-",
            "status": v["status"],
            "price": v.get("price"),
            "price_str": v.get("price_str") or "0,00",
            "parentId": v.get("parentId") or "",
            "img": _normalize_img_url(v.get("imagePath") or ""),   # 👈 ADICIONE
            "usos": len(v["parentIds"]) or 1,
        })

    return out

#============== Seção: 🛒 Catálogo — Pausar/Ativar Itens e Complementos ==============
with st.expander("🛒 Catálogo — Pausar/Ativar Itens e Complementos", expanded=True):

    def _q3_collect_catalog_fast():  # ← renomeie!
        return collect_catalog_parallel(
            token=st.session_state.token,
            merchant_id=st.session_state.merchant_id,
            catalog_id=st.session_state.get("catalog_id"),  # usa o valor persistido
            cached_categories_func=cached_categories,
            cached_items_by_category_func=cached_items_by_category,
            cached_item_detail_func=cached_item_detail,
            extract_options_func=extract_options_from_item_detail,
            max_workers=4
        )

    # Cache leve em globals
    try: _linhas_itens = linhas_itens
    except Exception: _linhas_itens = []
    try: _linhas_opts = linhas_opts
    except Exception: _linhas_opts = []

    st.session_state.setdefault("catalog_loaded", False)

    if st.button("🔄 Carregar catálogo") or st.session_state["catalog_loaded"]:
        with st.spinner("Carregando catálogo (pode levar alguns segundos)…"):
            it, op, err = _q3_collect_catalog_fast()
        if not err:
            _linhas_itens, _linhas_opts = it, op
            globals()["linhas_itens"] = it
            globals()["linhas_opts"]  = op
            st.session_state["catalog_loaded"] = True
    else:
        st.info("Clique em **Carregar catálogo** para trazer itens e complementos.")

    try: _linhas_itens = linhas_itens
    except Exception: _linhas_itens = []
    try: _linhas_opts = linhas_opts
    except Exception: _linhas_opts = []

    # ------------------------- TABS -------------------------
    tab_items, tab_opts = st.tabs(["🍔 Itens", "➕ Complementos"])

    # -------------------------- ITENS -----------------------
    with tab_items:
        filtro_item = st.text_input("Filtrar itens por nome", "")
        df_src = [x for x in _linhas_itens if filtro_item.lower() in (x.get("name") or "").lower()]
        df_src = sorted(df_src, key=lambda x: (x.get("name") or "").lower())
        st.caption(f"{len(df_src)} item(ns) carregado(s).")

        if df_src:
            df_it = pd.DataFrame(df_src, columns=["itemId", "name", "category", "status"])
            df_it.insert(
                0,
                "Status",
                df_it["status"].map(
                    lambda s: "🟢 ATIVO"
                    if (s or "").upper() == "AVAILABLE"
                    else ("🔴 PAUSADO" if (s or "").upper() == "UNAVAILABLE" else "⚪ DESCONHECIDO")
                ),
            )
            st.dataframe(df_it.drop(columns=["status"]), hide_index=True, use_container_width=True, height=320)
            st.divider()

            def _is_paused(rec: dict) -> bool:
                status = (rec.get("status") or "").upper()
                return status in ("UNAVAILABLE", "PAUSADO", "INACTIVE")

            if st.button("Reativar TODOS os itens", key="btn_react_all_open"):
                paused_ids = [x["itemId"] for x in _linhas_itens if _is_paused(x)]
                if not paused_ids:
                    st.toast("Não há itens pausados para reativar.", icon="⚠️")
                else:
                    local_names_map = {x.get("itemId"): (x.get("name") or x.get("itemId")) for x in _linhas_itens if x.get("itemId")}
                    entries = [{"id": iid, "name": local_names_map.get(iid, iid)} for iid in paused_ids]
                    open_confirm("activate", "item", entries, danger=True)
                    st.rerun()

            names_map = {x["itemId"]: x.get("name", x["itemId"]) for x in df_src}
            ids_disp = [x["itemId"] for x in df_src]
            sel = st.multiselect(
                "Selecione itens",
                options=ids_disp,
                format_func=lambda iid: names_map.get(iid, iid),
                key="quick_items_sel",
            )

            c1, c2 = st.columns(2)
            if c1.button("Pausar selecionados", key="btn_pause_items"):
                if not sel:
                    st.warning("Selecione ao menos 1 item.")
                else:
                    entries = [{"id": iid, "name": names_map.get(iid, iid)} for iid in sel]
                    open_confirm("pause", "item", entries)

            if c2.button("Ativar selecionados", key="btn_activate_items"):
                if not sel:
                    st.warning("Selecione ao menos 1 item.")
                else:
                    entries = [{"id": iid, "name": names_map.get(iid, iid)} for iid in sel]
                    open_confirm("activate", "item", entries)

    # ---------------------- COMPLEMENTOS --------------------
    with tab_opts:
        filtro_op = st.text_input("Filtrar complementos por nome", "")
        df_src = [x for x in _linhas_opts if filtro_op.lower() in (x.get("name") or "").lower()]
        df_src = sorted(df_src, key=lambda x: (x.get("name") or "").lower())
        df_src = _group_options_by_id(df_src)

        st.caption(f"{len(df_src)} complemento(s) exibido(s) (agrupados).")
        if df_src:
            df_op = pd.DataFrame(df_src, columns=["optionId", "name", "group", "usos", "parent", "category", "status"])
            df_op.insert(
                0,
                "Status",
                df_op["status"].map(
                    lambda s: "🟢 ATIVO"
                    if (s or "").upper() == "AVAILABLE"
                    else ("🔴 PAUSADO" if (s or "").upper() == "UNAVAILABLE" else "⚪ DESCONHECIDO")
                ),
            )
            st.dataframe(df_op.drop(columns=["status"]), hide_index=True, use_container_width=True, height=320)

            def _is_paused(rec: dict) -> bool:
                status = (rec.get("status") or "").upper()
                return status in ("UNAVAILABLE", "PAUSADO", "INACTIVE")

            def _opt_id(rec: dict):
                return rec.get("optionId") or rec.get("id") or rec.get("complementId") or rec.get("uuid")

            def _dedupe_by_id(rows, id_getter):
                seen = set(); out = []
                for r in rows:
                    k = id_getter(r)
                    if not k or k in seen: continue
                    seen.add(k); out.append(r)
                return out

            if st.button("Reativar TODOS os complementos", key="btn_react_all_opts_open"):
                rows_u = _dedupe_by_id(_linhas_opts, _opt_id)
                paused_ids = [_opt_id(x) for x in rows_u if _is_paused(x)]
                if not paused_ids:
                    st.toast("Não há complementos pausados para reativar.", icon="⚠️")
                else:
                    names_map_opt = {_opt_id(x): (x.get("name") or x.get("optionName") or _opt_id(x)) for x in rows_u if _opt_id(x)}
                    entries = [{"id": oid, "name": names_map_opt.get(oid, oid)} for oid in paused_ids]
                    open_confirm("activate", "option", entries, danger=True)
                    st.rerun()

            names_map = {x["optionId"]: x["name"] for x in df_src if x.get("optionId")}
            ids_disp  = [x["optionId"] for x in df_src if x.get("optionId")]
            sel_o = st.multiselect(
                "Selecione complementos",
                options=ids_disp,
                format_func=lambda oid: names_map.get(oid, oid),
                key="quick_opts_sel",
            )

            c1, c2 = st.columns(2)
            if c1.button("Pausar selecionados", key="quick_pause_opts"):
                if not sel_o:
                    st.warning("Selecione ao menos 1 complemento.")
                else:
                    entries = [{"id": oid, "name": names_map.get(oid, oid)} for oid in sel_o]
                    open_confirm("pause", "option", entries)
                    st.rerun()

            if c2.button("Ativar selecionados", key="quick_act_opts"):
                if not sel_o:
                    st.warning("Selecione ao menos 1 complemento.")
                else:
                    entries = [{"id": oid, "name": names_map.get(oid, oid)} for oid in sel_o]
                    open_confirm("activate", "option", entries)
                    st.rerun()

# Mostra modal/diálogo de confirmação (se houver)
show_confirm_popup()

# --- Estado da UI para o painel de pausados ---
st.session_state.setdefault("paused_panel_open", False)
st.session_state.setdefault("paused_text", "")

# --- Botão: gerar lista em texto (Itens e Complementos pausados) ---
if st.button("📋 Gerar lista de pausados"):

    paused_items = [
        f"- {x.get('name')} ({x.get('category')})"
        for x in _linhas_itens
        if str(x.get('status')).upper() in ("UNAVAILABLE", "PAUSADO", "INACTIVE")
    ]

    # ✅ Agrupar complementos pausados por optionId (sem repetições)
    seen_opts = set()
    paused_opts = []
    for x in _linhas_opts:
        if str(x.get('status')).upper() not in ("UNAVAILABLE", "PAUSADO", "INACTIVE"):
            continue
        oid = x.get("optionId") or x.get("id") or x.get("name")
        if not oid or oid in seen_opts:
            continue
        seen_opts.add(oid)
        paused_opts.append(f"- {x.get('name')}")

    today = datetime.now().strftime("%d/%m/%Y")
    text = f"📌 Itens pausados em {today}:\n" + "\n".join(paused_items or ["(nenhum)"])
    text += "\n\n➕ Complementos pausados:\n" + "\n".join(paused_opts or ["(nenhum)"])

    st.session_state.paused_text = text
    st.session_state.paused_panel_open = True
    st.toast("Lista gerada! Copie e cole no WhatsApp.", icon="📋")

    with st.expander("Copie o texto abaixo:", expanded=st.session_state.paused_panel_open):
        st.text_area(" ", st.session_state.paused_text, key="paused_text_area", height=300)
        # (segue igual: botões Recolher, Copiar e Limpar)

        col1, col2, col3 = st.columns([1,1,1])

        with col1:
            if st.button("Recolher"):
                st.session_state.paused_panel_open = False
                st.rerun()

        with col2:
            components.html(
                f"""
                <div style="display:flex;align-items:center;gap:.5rem">
                <button id="copy-btn"
                        style="padding:.5rem 1rem;border-radius:.5rem;border:0;cursor:pointer;
                                background:linear-gradient(90deg,#ff4bd1,#7a3cff);color:#fff;">
                    Copiar
                </button>
                <span id="copied" style="display:none;opacity:.9">Copiado ✅</span>
                </div>
                <script>
                (function(){{
                    const text = {json.dumps(st.session_state.paused_text)};
                    const btn = document.getElementById('copy-btn');
                    const ok = document.getElementById('copied');

                    function fallbackCopy(t) {{
                      const ta = document.createElement('textarea');
                      ta.value = t;
                      ta.style.position = 'fixed';
                      ta.style.top = '-1000px';
                      document.body.appendChild(ta);
                      ta.focus(); ta.select();
                      try {{ document.execCommand('copy'); }} catch(e) {{}}
                      document.body.removeChild(ta);
                    }}

                    btn.addEventListener('click', function() {{
                      if (navigator.clipboard && window.isSecureContext) {{
                        navigator.clipboard.writeText(text).then(() => {{
                          ok.style.display = 'inline';
                        }}).catch(() => {{
                          fallbackCopy(text);
                          ok.style.display = 'inline';
                        }});
                      }} else {{
                        fallbackCopy(text);
                        ok.style.display = 'inline';
                      }}
                    }});
                }})();
                </script>
                """,
                height=46,
            )

        with col3:
            if st.button("Limpar"):
                st.session_state.paused_text = ""
                st.session_state.paused_panel_open = False
                st.rerun()

# ============================================================
# Seção: 📝 Avaliações (IA) — respostas rápidas
# ============================================================

# ---------- Helpers de IDs ----------
def _extract_review_ids_any(obj):
    if isinstance(obj, str):
        s = (obj or "").strip()
        return (s or None, None)
    if not isinstance(obj, dict):
        return (None, None)

    def pick(d, keys):
        for k in keys:
            v = d.get(k)
            if v:
                return str(v).strip()
        return None

    review_id = pick(obj, ["id","reviewId","review_id","ratingId","ratingID","reviewUuid","reviewUUID","uuid"])
    survey_id = pick(obj, ["surveyId","survey_id","surveyID","surveyUuid","surveyUUID","feedbackId","feedbackID"])
    return review_id, survey_id

@limiter.limit("reviews")
def send_review_reply_any(token: str, merchant_id: str, review_or_id, message: str) -> tuple[int, str]:
    import json as _json

    if not token or len(str(token)) < 20:
        return 0, "Token ausente/curto."
    if not merchant_id:
        return 0, "merchant_id ausente."

    def _ok(code: int, text: str) -> bool:
        if code in (200, 201, 202):
            return True
        if code in (409, 422):
            s = (text or "").lower()
            return any(w in s for w in ("already", "respondida", "pending", "moderation"))
        return False

    headers = {"Authorization": f"Bearer {token}", "Content-Type":  "application/json", "Accept": "application/json"}
    rid, sid = _extract_review_ids_any(review_or_id)
    id_candidates = [x for x in (rid, sid) if x]
    tried = []

    route_templates = [
        f"{BASE}/review/v1.0/merchants/{{mid}}/reviews/{{rid}}/reply",
        f"{BASE}/review/v1.0/merchants/{{mid}}/reviews/{{rid}}/answers",
        f"{BASE}/review/v1.0/merchants/{{mid}}/reviews/{{rid}}/responses",
    ]

    payload_reply   = _json.dumps({"message": message})
    payload_answers = _json.dumps({"text": message})

    for _id in id_candidates or [""]:
        for tpl in route_templates:
            url = tpl.format(mid=merchant_id, rid=_id)
            payload = payload_answers if url.endswith("/answers") else payload_reply
            try:
                r = SESSION.post(url, headers=headers, data=payload, timeout=30)
                if _ok(r.status_code, r.text or ""):
                    return r.status_code, (r.text or "")
                tried.append((url, f"{r.status_code} {(r.text or '')[:160]}"))
                if r.status_code in (401, 403):
                    return r.status_code, (r.text or "Unauthorized")
            except Exception as e:
                tried.append((url, f"exc:{str(e)[:120]}"))
                continue

    return 0, f"Reply failed. Tried={tried}"

@limiter.limit("reviews")
def reviews_get_list(token: str, merchant_id: str, page: int = 1, size: int = 50) -> list:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    paths = [
        f"{BASE}/review/v1.0/merchants/{merchant_id}/reviews",
        f"{BASE}/review/v1.0/merchants/{merchant_id}/ratings",
    ]
    params = {"page": page, "size": size}
    for url in paths:
        try:
            r = SESSION.get(url, headers=headers, params=params, timeout=30)
            data = None
            try: data = r.json()
            except Exception: pass
            if r.status_code == 200 and data is not None:
                if isinstance(data, dict):
                    for k in ("content", "reviews", "ratings", "items"):
                        if isinstance(data.get(k), list):
                            return data[k]
                if isinstance(data, list):
                    return data
        except Exception:
            continue
    return []

def _get_review_id(r: dict) -> str:
    for k in ("id","reviewId","review_id","uuid","ratingId","ratingID","evaluationId","evaluation_id","surveyId"):
        v = r.get(k)
        if v: return str(v)
    return ""

def _review_has_reply(r: dict) -> bool:
    if r.get("answered") is True:
        return True
    reply = r.get("reply") or r.get("response") or r.get("answer")
    if isinstance(reply, dict) and any(reply.get(k) for k in ("message","text","createdAt","created_at")):
        return True
    for k in ("replyCreatedAt","answeredAt","response_at","answerCreatedAt"):
        if r.get(k): return True
    flags = [
        str(r.get("answerStatus") or "").lower(),
        str(r.get("replyStatus") or "").lower(),
        str(r.get("moderationStatus") or "").lower(),
        str(r.get("status") or "").lower(),
    ]
    joined = " ".join(flags)
    return ("answered" in joined) or ("approved" in joined)

def _review_text(r: dict) -> str:
    if not isinstance(r, dict): return ""
    for k in ("comment","comments","text","message","reviewText","content","observation"):
        v = r.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def _review_rating(r: dict) -> Optional[float]:
    if not isinstance(r, dict): return None
    for k in ("rating","rate","stars","score","nota","value"):
        v = r.get(k)
        if v is not None:
            try: return float(v)
            except Exception: pass
    return None

# ---------- IA: geração de resposta ----------
def _get_openai_client():
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None, "OPENAI_API_KEY ausente"
        client = OpenAI(api_key=api_key)
        return client, None
    except Exception as e:
        return None, f"OpenAI SDK não disponível: {e}"

def generate_reply_ia(texto: str, rating: Optional[float], tone: str, assinatura: str, use_emojis: bool) -> str:
    client, err = _get_openai_client()
    if err or client is None:
        base = "Obrigado pelo seu feedback!"
        if rating is not None and rating <= 2:
            base = "Sentimos muito pela experiência abaixo do esperado; vamos ajustar."
        elif rating is not None and rating >= 4:
            base = "Que bom que você gostou! Obrigado pela preferência."
        if use_emojis:
            base += " 🙂" if (rating and rating >= 4) else " 🙏"
        return f"Olá! {base}" + (f" — {assinatura}" if assinatura else "")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    tone_map = {
        "formal": "tom formal e profissional",
        "neutro": "tom neutro e educado",
        "descontraído": "tom descontraído, acolhedor e direto",
    }
    guia = (
        f"Você é atendente de restaurante e responde avaliações no iFood em {tone_map.get(tone,'tom neutro')}.\n"
        "Responda em português do Brasil, com 1–2 frases, objetivas e humanas. "
        "Elogios → agradeça. Críticas → peça desculpas e diga que vai ajustar. "
        "Não invente políticas internas."
    )
    guia += " Sem emojis." if not use_emojis else " Use no máximo 1 emoji apropriado."
    if rating is not None:
        guia += f" A avaliação foi {rating} estrela(s)."

    msgs = [
        {"role": "system", "content": guia},
        {"role": "user", "content": texto or "Sem comentário textual."},
    ]
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=msgs,
            temperature=0.5,
            max_tokens=140,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception:
        if rating is not None and rating <= 2:
            text = "Sinto muito pela experiência; vamos corrigir. Obrigado por avisar!"
        elif rating is not None and rating >= 4:
            text = "Obrigado pelo carinho! Esperamos vê-lo(a) em breve!"
        else:
            text = "Agradecemos o feedback — ele nos ajuda a melhorar!"
        if use_emojis:
            text += " 🙂"
    if assinatura:
        text = f"{text} — {assinatura}"
    return text

# =================== Tópicos/Sumário (IA com fallback) ===================
TOPIC_KEYWORDS = {
    "embalagem": ["embalagem", "vazou", "aberta", "rasgada", "mal embalada", "marmita", "lacre"],
    "atraso/entrega": ["atraso", "demorou", "demora", "entrega", "motoboy", "atrasada"],
    "temperatura": ["frio", "gelado", "morno", "esfriou", "quente demais"],
    "qualidade do prato": ["ruim", "horrível", "péssimo", "estranho", "cru", "sal", "sem sal", "molho"],
    "quantidade/porção": ["pouco", "porção", "quantidade", "menor que", "veio a menos"],
    "preço/custo-benefício": ["caro", "caríssima", "preço", "caríssimo", "custo benefício"],
    "erro no pedido": ["errado", "faltando", "não veio", "trocado"],
    "atendimento": ["atendimento", "educado", "mal atendimento", "suporte"],
}

def _keyword_topics(text: str) -> list[str]:
    txt = (text or "").lower()
    hits = []
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(k in txt for k in kws):
            hits.append(topic)
    return hits or ["outros"]

def extract_topics_auto(texts: list[str], use_ai: bool = True) -> dict[str, int]:
    """
    Retorna dict topic -> contagem. Usa OpenAI se disponível; senão, keywords.
    """
    if use_ai:
        client, err = _get_openai_client()  # já definido acima
        if client and not err:
            try:
                prompt = (
                    "Classifique cada linha em até 2 tópicos curtos (1-3 palavras), "
                    "ex.: embalagem, atraso/entrega, temperatura, qualidade do prato, "
                    "quantidade/porção, preço/custo-benefício, erro no pedido, atendimento, outros. "
                    "Responda como JSON: lista de objetos [{texto:'...', topicos:['t1','t2']}]."
                )
                sample = "\n".join(f"- {t[:240]}" for t in texts[:80])  # limite de amostra
                resp = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "system", "content": prompt},
                              {"role": "user", "content": sample}],
                    temperature=0.0,
                    max_tokens=800,
                )
                import json as _json
                js = _json.loads(resp.choices[0].message.content)
                counts = {}
                for row in js:
                    for t in row.get("topicos") or []:
                        t = (t or "").strip().lower()
                        if not t:
                            continue
                        counts[t] = counts.get(t, 0) + 1
                if counts:
                    return counts
            except Exception:
                pass

    # Fallback por palavras-chave
    counts = {}
    for t in texts:
        for label in _keyword_topics(t):
            counts[label] = counts.get(label, 0) + 1
    return counts

# ---------- Envio (1) e envio em massa ----------
def _send_one(review_obj: dict, text_key: str):
    tok = st.session_state.get("_access_token") or st.session_state.get("token")
    mid = st.session_state.get("merchant_id") or st.session_state.get("store_id")
    if not tok or not mid:
        st.error("Sem token ou loja selecionada.")
        return

    reply_text = (st.session_state.get(text_key) or "").strip()
    if not reply_text:
        st.warning("Escreva/aceite um texto antes de enviar.")
        return

    code, body = send_review_reply_any(tok, mid, review_obj, reply_text)

    ok = (code in (200, 201, 202, 409, 422))
    if ok:
        rid = _get_review_id(review_obj)
        st.session_state.setdefault("_recently_answered_ids", set()).add(rid)

        # ✅ salva a resposta no banco (NOVO)
        try:
            save_reply_to_db(rid, reply_text)
        except Exception as _e:
            print(f"warn: save_reply_to_db falhou: {_e}")

        st.toast("Resposta enviada! ✅", icon="✅")
        st.session_state["_reviews_last_refresh"] = time.time()
    else:
        st.error(f"Falhou ({code}). {str(body)[:300]}")

def _reply_all_current_page(rows):
    tok = st.session_state.get("_access_token") or st.session_state.get("token")
    mid = st.session_state.get("merchant_id") or st.session_state.get("store_id")
    if not tok or not mid:
        st.error("Sem token/merchant_id na sessão. Faça login e selecione a loja.")
        return

    enviados, falhas = 0, []
    recent = st.session_state.setdefault("_recently_answered_ids", set())

    for r in rows:
        time.sleep(0.1)
        rid = _get_review_id(r)

        key1 = f"resp_sug_{rid}"
        key2 = f"reply_text_{rid}"
        msg = (
            st.session_state.get(key1)
            or st.session_state.get(key2)
            or st.session_state.get("_reply_text")
            or ""
        ).strip()

        if not msg:
            txt = _review_text(r)
            rating = _review_rating(r)
            msg = generate_reply_ia(
                texto=txt,
                rating=rating,
                tone=st.session_state.get("reviews_tone", "neutro"),
                assinatura=st.session_state.get("reviews_signature", ""),
                use_emojis=bool(st.session_state.get("reviews_use_emojis", True)),
            ).strip()

        if not msg:
            falhas.append((rid, "sem_texto"))
            continue

        code, body = send_review_reply_any(tok, mid, r, msg)

        if code in (200, 201, 202, 409, 422):
            enviados += 1
            recent.add(rid)
        else:
            falhas.append((rid, code))

    st.session_state["_reviews_last_refresh"] = time.time()
    st.toast(f"Envios concluídos: {enviados} OK, {len(falhas)} erro(s).",
             icon="✅" if not falhas else "⚠️")

# --------------------------- UI: Avaliações IA --------------------------
if Q3_SHOW_REVIEWS:
    with st.expander("📝 Avaliações (IA)", expanded=True):
        colc1, colc2, colc3 = st.columns([1,1,2])
        with colc1:
            _tone_opts = ["descontraído", "formal", "neutro"]
            _cur = st.session_state.get("reviews_tone", "descontraído")
            _idx = _tone_opts.index(_cur) if _cur in _tone_opts else 0
            st.selectbox("Tom da resposta", _tone_opts, index=_idx, key="reviews_tone")
        with colc2:
            st.toggle("Usar 1 emoji", value=bool(st.session_state.get("reviews_use_emojis", True)),
                      key="reviews_use_emojis")
        with colc3:
            st.text_input("Assinatura opcional (ex.: Equipe Q3)", key="reviews_signature")

        colp1, colp2, colp3 = st.columns([1,1,2])
        with colp1:
            page = st.number_input("Página", min_value=1, step=1,
                                   value=int(st.session_state.get("reviews_page",1)))
            st.session_state["reviews_page"] = int(page)
        with colp2:
            st.selectbox("Por página", [10], index=0, key="reviews_page_size")
        with colp3:
            if st.button("🔄 Atualizar avaliações", key="btn_refresh_reviews"):
                st.session_state["_reviews_locally_closed"] = set()
                st.session_state["_reviews_last_refresh"] = time.time()
                st.session_state["_review_suggestions"] = {}
                st.session_state["reviews_page"] = 1
                st.rerun()

        token = st.session_state.get("_access_token") or st.session_state.get("token")
        mid   = st.session_state.get("merchant_id")  or st.session_state.get("store_id")
        if not token or not mid:
            st.info("Faça login e selecione a loja para ver as avaliações.")
        else:
            raw = []
            for p in range(1, 4):
                lst = reviews_get_list(token, mid, page=p, size=100)
                if not lst: break
                raw.extend(lst)

            # DEPOIS do loop de coleta (raw):
            try:
                upsert_reviews(mid, raw)
            except Exception as _e:
                # não quebra a UI caso banco falhe
                st.debug(f"warn: upsert_reviews falhou: {_e}")

            base = [r for r in raw if _review_text(r) and not _review_has_reply(r)]

            recent = st.session_state.setdefault("_recently_answered_ids", set())
            unanswered = [r for r in base if _get_review_id(r) not in recent]

            # ... depois de calcular `unanswered` ...
            total = len(unanswered)
            st.caption(f"Encontradas **{total}** avaliações sem resposta com comentário.")

            # ✅ 1) garanta que exista, mesmo quando não há avaliações
            page_rows = []

            # ✅ 2) NÃO pare o app; só pule o resto da seção
            if total == 0:
                st.info("Não há avaliações com comentário pendentes no momento.")
            else:
                # Paginação (10 por página)
                per = 10
                pg = max(1, int(st.session_state.get("reviews_page", 1)))
                total_pages = max(1, math.ceil(total / per))
                if pg > total_pages:
                    pg = total_pages
                    st.session_state["reviews_page"] = pg
                start = (pg - 1) * per
                end = start + per
                page_rows = unanswered[start:end]

                st.caption(f"Página {pg}/{total_pages}")

                # Gera/cached sugestões da página
                cache = st.session_state.get("_review_suggestions") or {}
                for r in page_rows:
                    rid = _get_review_id(r) or f"idx-{start}"
                    if rid not in cache:
                        cache[rid] = generate_reply_ia(
                            texto=_review_text(r),
                            rating=_review_rating(r),
                            tone=st.session_state.get("reviews_tone","descontraído"),
                            assinatura=st.session_state.get("reviews_signature",""),
                            use_emojis=bool(st.session_state.get("reviews_use_emojis", True)),
                        )
                st.session_state["_review_suggestions"] = cache

                # Botão em massa
                st.button(
                    f"🟣 Responder TODAS desta página ({len(page_rows)})",
                    key="btn_reply_all_page",
                    type="primary",
                    use_container_width=True,
                    on_click=_reply_all_current_page,
                    kwargs={"rows": page_rows}
                )

                # Render das avaliações da página
                for idx, r in enumerate(page_rows, start=start+1):
                    rid = _get_review_id(r) or str(idx)
                    comment = _review_text(r)
                    rating  = _review_rating(r)
                    created = (r.get("createdAt") or r.get("created") or r.get("date") or "")
                    author  = r.get("consumerName") or r.get("author") or "Cliente"

                    text_key = f"resp_sug_{rid}"
                    if text_key not in st.session_state:
                        st.session_state[text_key] = cache.get(rid, "")

                    with st.container(border=True):
                        st.markdown(f"**#{idx}** — ⭐ {rating if rating is not None else '—'} — {author}  \n*{created}*")
                        st.markdown(f"> {comment}")
                        st.text_area("Resposta sugerida", key=text_key, height=100, label_visibility="collapsed")

                        colb1, colb2 = st.columns([1,1])
                        with colb1:
                            if st.button("📋 Copiar", key=f"copy_{rid}"):
                                st.code(st.session_state[text_key])
                                st.toast("Texto mostrado acima. Selecione e copie (Ctrl+C).", icon="📋")
                        with colb2:
                            # botão que retorna True quando clicado — fazemos o envio inline
                            if st.button("Enviar", key=f"send_{rid}", use_container_width=True):
                                reply_text = st.session_state.get(text_key, "").strip()
                                review_obj = r

                                if not reply_text:
                                    st.warning("Resposta vazia — digite algo antes de enviar.")
                                else:
                                    try:
                                        # se você tem uma função que já envia, chame-a:
                                        # _send_one(review_obj=review_obj, text_key=text_key)
                                        # Caso contrário, implemente aqui a chamada à API / envio.
                                        _send_one(review_obj=review_obj, text_key=text_key)
                                    except Exception as exc:
                                        st.error(f"Falha ao enviar: {exc}")
                                    else:
                                        # marca como respondido localmente
                                        rid2 = _get_review_id(review_obj)
                                        st.session_state.setdefault("_recently_answered_ids", set()).add(rid2)

                                        # salva no banco (não quebra a UI em caso de erro)
                                        try:
                                            save_reply_to_db(rid2, reply_text)
                                        except Exception as _e:
                                            st.debug(f"warn: save_reply_to_db: {_e}")

                                        st.toast("Resposta enviada! ✅", icon="✅")
                                        st.session_state["_reviews_last_refresh"] = time.time()

            st.caption("Dica: ajuste tom/assinatura/emojis e clique em **Atualizar avaliações** para gerar novas sugestões.")

# ============================ 📊 Relatórios de Avaliações ============================
with st.expander("📊 Relatórios de Avaliações", expanded=False):
    if not st.session_state.get("merchant_id"):
        st.info("Selecione uma loja para gerar o relatório.")
    else:
        c1, c2, c3 = st.columns([2,2,2])
        with c1:
            dr = st.date_input("Período", value=(date.today().replace(day=1), date.today()))
            start_date = dr[0].strftime("%Y-%m-%d") if isinstance(dr, tuple) else date.today().strftime("%Y-%m-%d")
            end_date   = dr[1].strftime("%Y-%m-%d") if isinstance(dr, tuple) else date.today().strftime("%Y-%m-%d")
        with c2:
            star_opts = [1,2,3,4,5]
            sel_stars = st.multiselect("Filtrar por estrelas", star_opts, default=star_opts)
            sel_stars = set(sel_stars)
        with c3:
            use_ai_topics = st.toggle("Resumo de tópicos com IA", value=True)

        if st.button("Gerar relatório", type="primary"):
            rows = query_reviews(st.session_state.merchant_id, start_date, end_date, sel_stars)
            # monta DataFrame
            cols = ["id","created_at","rating","comment","reply_text","replied_at"]
            df = pd.DataFrame(rows, columns=cols)

            st.caption(f"Carregadas {len(df)} avaliações no período filtrado.")

            # ---- Métricas por estrela (robusto p/ df vazio) ----
            # garanta a coluna 'star' sempre
            if "rating" not in df.columns:
                df["rating"] = pd.Series(dtype="float")

            try:
                df["star"] = pd.to_numeric(df["rating"], errors="coerce").round().astype("Int64")
            except Exception:
                df["star"] = pd.Series([pd.NA] * len(df), dtype="Int64")

            counts = (
                df["star"].value_counts(dropna=True).sort_index()
                if not df.empty else pd.Series(dtype="int64")
            )
            total = int(counts.sum()) if not counts.empty else 0

            # cards rápidos
            st.write("### Métricas")
            met_cols = st.columns(6)
            with met_cols[0]: st.metric("Total", total)
            for i, star in enumerate([1,2,3,4,5], start=1):
                with met_cols[i]:
                    st.metric(f"{star} ⭐", int(counts.get(star, 0)))

            # ---- Tópicos (foca em 1–3 estrelas; seguro p/ df vazio) ----
            st.write("### Tópicos mais citados")
            if not df.empty and "comment" in df.columns:
                low_df = df[df["star"].isin([1,2,3])]
                comments_list = low_df["comment"].dropna().astype(str).tolist()
                topics_counts = extract_topics_auto(comments_list, use_ai=use_ai_topics) if comments_list else {}
            else:
                topics_counts = {}

            if topics_counts:
                topics_df = pd.DataFrame(
                    sorted(topics_counts.items(), key=lambda x: x[1], reverse=True),
                    columns=["tópico","ocorrências"]
                )
                st.dataframe(topics_df, use_container_width=True, hide_index=True, height=240)
            else:
                st.info("Sem comentários suficientes para agrupar tópicos.")

            # ---------- Exportações ----------
            from io import BytesIO
            csv = df.to_csv(index=False).encode("utf-8")
            xbuf = BytesIO()
            with pd.ExcelWriter(xbuf, engine="xlsxwriter") as w:
                df.to_excel(w, sheet_name="Avaliações", index=False)
                # aba de métricas
                met = pd.DataFrame({"estrela":[1,2,3,4,5], "quantidade":[int(counts.get(s,0)) for s in [1,2,3,4,5]]})
                met.to_excel(w, sheet_name="Métricas", index=False)
                if topics_counts:
                    pd.DataFrame(topics_counts.items(), columns=["tópico","ocorrências"]).to_excel(w, sheet_name="Tópicos", index=False)
            xbuf.seek(0)

            st.download_button("⬇️ Baixar CSV", data=csv, file_name=f"avaliacoes_{start_date}_a_{end_date}.csv", mime="text/csv")
            st.download_button("⬇️ Baixar Excel", data=xbuf.getvalue(), file_name=f"avaliacoes_{start_date}_a_{end_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # ---- PDF (ReportLab) ----
            from io import BytesIO

            def _build_pdf_bytes(df, counts, topics_counts, start_date, end_date):
                try:
                    from reportlab.lib.pagesizes import A4
                    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                    from reportlab.lib.units import cm
                    from reportlab.lib import colors
                    from reportlab.pdfbase import pdfmetrics
                    from reportlab.pdfbase.ttfonts import TTFont
                    import os
                except Exception:
                    return None

                # fonte com suporte a PT-BR (coloque DejaVuSans.ttf na raiz do projeto se quiser)
                base_font = "Helvetica"
                font_path = "DejaVuSans.ttf"
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
                        base_font = "DejaVuSans"
                    except Exception:
                        pass

                buf = BytesIO()
                doc = SimpleDocTemplate(
                    buf, pagesize=A4,
                    leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm
                )
                styles = getSampleStyleSheet()
                styles.add(ParagraphStyle(name="Body", fontName=base_font, fontSize=10, leading=14))
                styles["Title"].fontName = base_font
                styles["Heading2"].fontName = base_font
                styles["Normal"].fontName  = base_font

                story = []
                story.append(Paragraph(f"Relatório de Avaliações — {start_date} a {end_date}", styles["Title"]))
                story.append(Spacer(1, 12))

                # Métricas
                data = [["Estrela","Qtde"]] + [[str(s), str(int(counts.get(s,0)))] for s in [1,2,3,4,5]]
                tbl = Table(data, colWidths=[3*cm, 3*cm])
                tbl.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#8B00FF")),
                    ("TEXTCOLOR",(0,0),(-1,0),colors.white),
                    ("GRID",(0,0),(-1,-1),0.25,colors.grey),
                    ("FONTNAME",(0,0),(-1,-1),base_font),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 12))

                # Tópicos
                if topics_counts:
                    story.append(Paragraph("Tópicos mais citados (1–3 ⭐)", styles["Heading2"]))
                    tdata = [["Tópico","Ocorrências"]] + [[k, str(v)] for k,v in sorted(topics_counts.items(), key=lambda x:x[1], reverse=True)]
                    ttbl = Table(tdata, colWidths=[10*cm, 3*cm])
                    ttbl.setStyle(TableStyle([
                        ("GRID",(0,0),(-1,-1),0.25,colors.grey),
                        ("FONTNAME",(0,0),(-1,-1),base_font),
                    ]))
                    story.append(ttbl)
                    story.append(Spacer(1, 12))

                # Amostra de avaliações
                story.append(Paragraph("Amostra de avaliações (até 50)", styles["Heading2"]))
                sub = df[["created_at","rating","comment","reply_text"]].fillna("").head(50)
                for _, r in sub.iterrows():
                    story.append(Paragraph(f"<b>{r['created_at']}</b> — {r['rating']}⭐", styles["Body"]))
                    if r["comment"]:
                        story.append(Paragraph(f"Cliente: {r['comment'][:800]}", styles["Body"]))
                    if r["reply_text"]:
                        story.append(Paragraph(f"Resposta: {r['reply_text'][:800]}", styles["Body"]))
                    story.append(Spacer(1, 6))

                doc.build(story)
                buf.seek(0)
                return buf.getvalue()

            pdf_bytes = _build_pdf_bytes(df, counts, topics_counts, start_date, end_date)
            if pdf_bytes:
                st.download_button("⬇️ Baixar PDF", data=pdf_bytes, file_name=f"avaliacoes_{start_date}_a_{end_date}.pdf", mime="application/pdf")
            else:
                st.caption("PDF indisponível: instale 'reportlab' (e opcionalmente DejaVuSans.ttf) para habilitar o download.")

# ======================= Q3 Catálogo (Cards Modernos) =======================
import os, requests, streamlit as st

# ------------------------ Config ------------------------
def _get_from_any(*keys, default=None):
    for k in keys:
        if k in st.session_state and st.session_state.get(k):
            return st.session_state.get(k)
    try:
        for k in keys:
            if k in st.secrets and st.secrets[k]:
                return st.secrets[k]
    except Exception:
        pass
    for k in keys:
        v = os.environ.get(k)
        if v: return v
    return default

IFD_BASE   = "https://merchant-api.ifood.com.br/catalog/v2.0"
MERCHANT_ID = st.session_state.get("merchant_id")
CATALOG_ID = st.session_state.get("catalog_id")
TOKEN = st.session_state.get("token")

def _auth_headers():
    return {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json", "Content-Type": "application/json"}

def _get(path, params=None):
    r = requests.get(f"{IFD_BASE}{path}", headers=_auth_headers(), params=params, timeout=25)
    r.raise_for_status()
    return r.json() if r.content else None

def _post(path, json=None):
    r = requests.post(f"{IFD_BASE}{path}", headers=_auth_headers(), json=json, timeout=25)
    r.raise_for_status()
    return r.json() if r.content else None

def _patch(path, json=None):
    r = requests.patch(f"{IFD_BASE}{path}", headers=_auth_headers(), json=json, timeout=25)
    r.raise_for_status()
    return r.json() if r.content else None

def _delete(path):
    r = requests.delete(f"{IFD_BASE}{path}", headers=_auth_headers(), timeout=25)
    if r.status_code not in (200, 202, 204): r.raise_for_status()
    return None

# ============================ OPTION GROUP (Catalog v2) ============================
@limiter.limit("catalog")
def list_option_groups(merchant_id: str, include_options: bool = False, catalog_context: str | None = None) -> list[dict]:
    """
    GET /merchants/{merchantId}/optionGroups
      ?includeOptions=true|false
      ?catalogContext=<WHITELABEL|INDOOR|...>  (opcional)
    """
    url = _c(f"merchants/{merchant_id}/optionGroups")
    params = {}
    if include_options:
        # a doc nova usa `includeOptions`; a antiga aceitava `include_options` tbm (deprecated)
        params["includeOptions"] = "true"
    if catalog_context:
        params["catalogContext"] = str(catalog_context)

    r = requests.get(url, headers=_headers(), params=params, timeout=30)
    if r.status_code == 200:
        js = r.json() or []
        return js if isinstance(js, list) else []
    raise RuntimeError(f"list_option_groups falhou: {r.status_code} {r.text[:200]}")

def update_option_group(merchant_id: str, option_group_id: str, payload: dict) -> tuple[bool, str]:
    """
    PATCH /merchants/{merchantId}/optionGroups/{optionGroupId}
    body: { "name": "...", "description": "..." }
    """
    url = _c(f"merchants/{merchant_id}/optionGroups/{option_group_id}")
    r = requests.patch(url, headers=_headers(), json=(payload or {}), timeout=30)
    if 200 <= r.status_code < 300:
        return True, "Grupo atualizado"
    return False, f"{r.status_code}: {r.text[:200]}"

def delete_option_group(merchant_id: str, option_group_id: str):
    """
    DELETE /merchants/{merchantId}/optionGroups/{optionGroupId}
    """
    url = _c(f"merchants/{merchant_id}/optionGroups/{option_group_id}")
    try:
        resp = requests.delete(url, headers=_headers(), timeout=30)
        if resp.status_code in (200, 202, 204):
            return True, "Grupo excluído."
        return False, f"Erro {resp.status_code}: {resp.text[:300]}"
    except Exception as e:
        return False, f"Erro: {str(e)[:300]}"

def patch_option_group_status(token: str, merchant_id: str, option_group_id: str, new_status: str, catalog_context: str | None = None) -> tuple[bool, str]:
    """
    PATCH /merchants/{merchantId}/optionGroups/{optionGroupId}/status
    body: {"status":"AVAILABLE"|"UNAVAILABLE", "catalogContext":"..."}  (catalogContext opcional)
    """
    url = _c(f"merchants/{merchant_id}/optionGroups/{option_group_id}/status")
    body = {"status": str(new_status).upper()}
    if catalog_context:
        body["catalogContext"] = str(catalog_context)

    r = requests.patch(url, headers=_headers(), json=body, timeout=30)
    if 200 <= r.status_code < 300:
        return True, "Status do grupo atualizado"
    return False, f"{r.status_code}: {r.text[:200]}"

# ============================ OPTION lookups (fallback via Items v2) ==============
def build_options_index_from_items_v2(merchant_id: str, catalog_id: str | None = None) -> dict:
    """
    Fallback para montar um índice {groupId: [options...]} a partir dos itens (GET item flat).
    É usado quando list_option_groups(..., includeOptions=True) retorna vazio na sua conta.
    """
    from collections import defaultdict

    cat_id = catalog_id or (globals().get("CATALOG_ID") or st.session_state.get("catalog_id"))
    idx = defaultdict(list)

    try:
        cats = list_categories(merchant_id, cat_id) or []
    except Exception:
        cats = []

    for c in cats:
        category_id = c.get("id") or c.get("categoryId")
        if not category_id:
            continue

        try:
            items = list_items_by_category(merchant_id, category_id) or []
            if isinstance(items, dict) and "items" in items:
                items = items["items"]
        except Exception:
            items = []

        for it in items:
            item_id = it if isinstance(it, str) else (it.get("id") or it.get("itemId") or it.get("productId"))
            if not item_id:
                continue

            try:
                flat = get_item_flat(merchant_id, item_id) or {}
                products = flat.get("products") or []
                _prod_idx = {p.get("id"): p.get("imagePath") for p in products if p.get("id")}
                base_idx = st.session_state.get("_product_img_index", {})
                base_idx.update(_prod_idx)
                st.session_state["_product_img_index"] = base_idx
            except Exception:
                continue

            products = {p.get("id"): p for p in (flat.get("products") or []) if p.get("id")}
            options  = {o.get("id"): o for o in (flat.get("options") or [])  if o.get("id")}
            ctx      = (st.session_state.get("catalog_context") or "").upper()

            for og in (flat.get("optionGroups") or []):
                gid = og.get("id")
                if not gid:
                    continue

                for opt_ref in (og.get("options") or []):
                    oid = opt_ref.get("id") or opt_ref.get("optionId")
                    if not oid or oid not in options:
                        continue
                    opt = options[oid]
                    prod = products.get(opt.get("productId") or "" , {})

                    # nome
                    name = (
                        opt.get("name")
                        or prod.get("name")
                        or prod.get("externalCode")
                        or f"Complemento {oid[:6]}"
                    )

                    # preço / status globais
                    price_value = (opt.get("price") or {}).get("value", 0.0)
                    status_value = (opt.get("status") or "AVAILABLE").upper()

                    # imagem: começa pela imagem da própria opção (se houver)
                    image_path = opt.get("imagePath") or ""

                    # sobrescreve por contexto (respeita tanto 'contextModifiers' quanto 'contextOptionModifiers')
                    _ctx_mods = (
                        opt.get("contextModifiers")
                        or opt.get("contextOptionModifiers")
                        or []
                    )
                    for cm in _ctx_mods:
                        if (cm.get("catalogContext") or "").upper() == ctx:
                            if (cm.get("price") or {}).get("value") is not None:
                                price_value = cm["price"]["value"]
                            if cm.get("status"):
                                status_value = cm["status"].upper()
                            if cm.get("imagePath"):
                                image_path = cm["imagePath"]
                            break  # primeira coincidência no contexto já resolve

                    # se ainda não tem imagem, pega do produto ou do índice de produtos
                    if not image_path:
                        prod_img_idx = st.session_state.get("_product_img_index", {})
                        image_path = prod.get("imagePath") or prod_img_idx.get(opt.get("productId") or "", "")

                    idx[gid].append({
                        "id": oid,
                        "optionId": oid,
                        "name": name,
                        "description": opt.get("description") or "",
                        "status": status_value,
                        "price": float(price_value or 0.0),
                        "imagePath": image_path,
                        "img": _normalize_img_url(image_path),   # 👈 URL completa para a UI
                        "productId": opt.get("productId"),
                        "groupId": gid,
                    })

def fetch_options_for_group(merchant_id: str, catalog_id: str, option_group_id: str) -> List[Dict[str, Any]]:
    """
    Helper compatível com a sua aba.
    Tenta pegar do índice cacheado; se não houver, constrói via build_options_index_from_items_v2.
    """
    results: list[dict] = []

    # tenta usar o índice em sessão se existir
    idx = st.session_state.get("_options_index") or {}
    if not idx:
        try:
            st.session_state["_options_index"] = build_options_index_from_items_v2(merchant_id)
            idx = st.session_state["_options_index"]
        except Exception:
            idx = {}
    return idx.get(group_id) or []

# ------------------------ Endpoints ------------------------
def get_catalogs(merchant_id): return _get(f"/merchants/{merchant_id}/catalogs")
def list_categories(merchant_id, catalog_id): return _get(f"/merchants/{merchant_id}/catalogs/{catalog_id}/categories")
def list_items_by_category(merchant_id, category_id): return _get(f"/merchants/{merchant_id}/categories/{category_id}/items")
def get_item_flat(merchant_id: str, item_id: str, cache_bust: int = 0) -> dict:
    return _get(f"/merchants/{merchant_id}/items/{item_id}/flat")  # 👈 corpo da função

@st.cache_data(show_spinner=False, ttl=120)

# ==== NOVO: busca complementos (options) de um grupo, via Catalog v1 ====
@st.cache_data(show_spinner=False, ttl=120)
def fetch_options_for_group_by_catalog(
    merchant_id: str, catalog_id: str, option_group_id: str
) -> List[Dict[str, Any]]:
    """
    Retorna as OPTIONS (complementos) pertencentes a um Option Group.
    Como a API não tem GET direto de opções por grupo, buscamos os itens "flat"
    e filtramos por optionGroupId.
    """
    results: List[Dict[str, Any]] = []

    # 1) Listar categorias do catálogo
    try:
        cats = list_categories(merchant_id, catalog_id) or []
    except Exception:
        cats = []

    for cat in cats:
        cat_id = cat.get("id") or cat.get("categoryId")
        if not cat_id:
            continue

        # 2) Itens da categoria
        try:
            items = list_items_by_category(merchant_id, cat_id) or []
            if isinstance(items, dict) and "items" in items:
                items = items["items"]
        except Exception:
            items = []

        for it in items:
            # id do produto "pai" (o item do cardápio que contém o grupo)
            owner_product_id = it if isinstance(it, str) else (it.get("id") or it.get("itemId") or it.get("productId"))
            if not owner_product_id:
                continue

            # 3) Item flat traz optionGroups[].options[]
            try:
                flat = get_item_flat(merchant_id, owner_product_id) or {}
            except Exception:
                continue

            # imagem/nome do item pai (para exibir referência)
            products = flat.get("products") or []
            p0 = products[0] if products else {}
            owner_product_name = p0.get("name") or owner_product_id

            for og in (flat.get("optionGroups") or []):
                if (og.get("id") or og.get("optionGroupId")) != option_group_id:
                    continue

                for opt in (og.get("options") or []):
                    opt_id = opt.get("id")
                    if not opt_id:
                        continue

                    # imagem (normaliza caminho relativo do iFood CDN)
                    img = None
                    img_path = opt.get("imagePath")
                    if img_path:
                        img = _normalize_img_url(img_path)


                    # preço (aceita dict ou num)
                    price = 0.0
                    if isinstance(opt.get("price"), dict):
                        v = opt["price"].get("value")
                        price = float(v) if v is not None else 0.0
                    elif isinstance(opt.get("price"), (int, float)):
                        price = float(opt["price"])

                    status = (opt.get("status") or "AVAILABLE").upper()
                    paused = status in ("UNAVAILABLE", "PAUSED")

                    results.append({
                        "id": opt_id,                         # optionId
                        "name": opt.get("name") or opt.get("label") or "Complemento",
                        "description": opt.get("description") or "",
                        "price": price,
                        "status": status,
                        "paused": paused,
                        "img": img,
                        "groupId": option_group_id,          # grupo ao qual pertence
                        "ownerProductId": owner_product_id,  # produto "pai" (necessário para DELETE/duplicar)
                        "ownerProductName": owner_product_name,
                        "externalCode": opt.get("externalCode"),
                        "productId": opt.get("productId"),   # produto do PRÓPRIO complemento, quando existir
                    })

    return results

# ============================================================
# Helpers: opções (complementos) por grupo
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def _build_options_index(merchant_id: str, cache_bust: int = 0) -> dict:
    """
    Tenta 2 rotas:
    1) v1 optionGroups?includeOptions=true  -> grupos já vêm com as opções
    2) v2 items (products, optionGroups, options) -> monta índice {groupId: [options...]}
    Retorna: { groupId: [ {id, productId, groupId, name, description, price, status, paused, img} ] }
    """
    headers = _headers()

    # --- TENTATIVA 1: v1 com includeOptions=true (quando habilitado pelo tenant) ---
    try:
        url = f"https://merchant-api.ifood.com.br/catalog/v1.0/merchants/{merchant_id}/optionGroups?includeOptions=true"
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        js = r.json() or []
        idx = {}
        total = 0
        for g in js:
            gid = g.get("id")
            if not gid:
                continue
            opts = []
            for o in (g.get("options") or []):
                price_val = (o.get("price") or {}).get("value", 0.0)
                status = (o.get("status") or "AVAILABLE").upper()
                paused = status in ("UNAVAILABLE", "PAUSED")

                img = None
                img_path = o.get("imagePath")
                if img_path:
                    img = _normalize_img_url(img_path)

                opts.append({
                    "id": o.get("id"),
                    "productId": o.get("productId"),
                    "groupId": gid,
                    "name": o.get("name") or o.get("label") or "",
                    "description": o.get("description") or "",
                    "price": float(price_val or 0.0),
                    "status": status,
                    "paused": paused,
                    "img": img,
                })
            idx[gid] = opts
            total += len(opts)

        # se retornou opções, usamos esse índice
        if total > 0:
            return idx
    except Exception:
        pass

    # --- TENTATIVA 2 (fallback): v2 items -> correlaciona products, optionGroups e options ---
    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/items"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    js = r.json() or {}

    products = {p.get("id"): p for p in (js.get("products") or [])}
    groups = js.get("optionGroups") or []
    options = js.get("options") or []

    idx = {g.get("id"): [] for g in groups if g.get("id")}

    for o in options:
        gid = o.get("optionGroupId") or o.get("groupId")
        if not gid:
            continue
        prod = products.get(o.get("productId"), {})
        name = (
            o.get("name")
            or prod.get("name")
            or prod.get("externalCode")
            or f"Complemento {str(o.get('id'))[:6]}"
        )
        price_val = (o.get("price") or {}).get("value", 0.0)
        status = (o.get("status") or "AVAILABLE").upper()
        paused = status in ("UNAVAILABLE", "PAUSED")

        img = None
        img_path = o.get("imagePath") or prod.get("imagePath")
        if img_path:
            img = _normalize_img_url(img_path)

        idx.setdefault(gid, []).append({
            "id": o.get("id"),
            "productId": o.get("productId"),
            "groupId": gid,
            "name": name,
            "description": prod.get("description") or "",
            "price": float(price_val or 0.0),
            "status": status,
            "paused": paused,
            "img": img,
        })

    return idx


@st.cache_data(ttl=60, show_spinner=False)
def fetch_options_for_group_by_catalog(merchant_id: str, catalog_id: str, group_id: str) -> list:
    """
    Retorna as opções (complementos) de um group_id específico, já normalizadas.
    O catalog_id é recebido só para manter a assinatura consistente com seu código.
    """
    idx = _build_options_index(merchant_id)
    return idx.get(group_id, [])

# ===================== HELPERS: OPTIONS BY GROUP =====================
def _fetch_group_options_via_items_v2(merchant_id: str, catalog_id: str, group_id: str) -> list[dict]:
    """
    Tenta montar a lista de 'options' pertencentes a um optionGroup (group_id)
    percorrendo os itens do catálogo (Catalog v2 GET Items), pois a resposta de
    itens traz 'optionGroups' e suas 'options'. 
    """
    out = []

    # Cache simples na sessão para não re-varrer tudo em cada clique
    cache_key = f"_opts_by_group_{catalog_id}_{group_id}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    try:
        categories = list_categories(merchant_id, catalog_id) or []
    except Exception:
        categories = []

    headers = {
        "Authorization": f"Bearer {st.session_state.get('token','')}",
        "Content-Type": "application/json",
    }

    # Vamos varrer categoria por categoria buscando itens (v2 GET Items)
    for cat in categories:
        category_id = cat.get("id") or cat.get("categoryId")
        if not category_id:
            continue

        try:
            # Endpoint: GET Items (Catalog v2) por categoryId — a doc informa que
            # a resposta inclui 'optionGroups' e 'options' (com price/status) 
            # (ver guia Catalog v2 -> GET Items). :contentReference[oaicite:0]{index=0}
            url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/items?categoryId={category_id}"
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                continue
            js = resp.json() if hasattr(resp, "json") else resp

            # Na resposta de v2 GET Items, normalmente temos:
            #  - "products": [{id, name, ...}]
            #  - "items": [...]
            #  - "optionGroups": [{id, name, ...}]
            #  - "options": [{id, optionGroupId, productId, price{value}, status, ...}]
            products = {p["id"]: p for p in (js.get("products") or [])}
            all_options = js.get("options") or []

            for opt in all_options:
                if (opt.get("optionGroupId") or opt.get("groupId")) == group_id:
                    prod = products.get(opt.get("productId"), {})
                    nome = prod.get("name") or opt.get("name") or "Complemento"
                    price_value = (opt.get("price") or {}).get("value") or 0
                    status_value = (opt.get("status") or "AVAILABLE").upper()
                    paused = status_value in ("PAUSED", "UNAVAILABLE")

                    img = None
                    img_path = (opt.get("imagePath") or "").strip()
                    if img_path:
                        img = _normalize_img_url(img_path)

                    out.append({
                        "id": opt.get("id"),
                        "name": opt.get("name") or opt.get("label") or "",
                        "description": opt.get("description") or "",
                        "price": float(price_value or 0.0),            # <- usa a variável certa
                        "status": status_value,                        # <- usa a variável certa
                        "paused": paused,
                        "groupId": group_id,
                        "productId": opt.get("productId"),
                        "imagePath": img_path or None,
                    })


        except Exception:
            continue

    st.session_state[cache_key] = out
    return out


def fetch_options_for_group(merchant_id: str, item_id: str, group_id: str, cache_bust: int = 0) -> list:
    """
    Tenta buscar as opções de um group:
      1) GET /merchants/{merchantId}/optionGroups?includeOptions=true  (e filtra pelo groupId)
      2) (fallback) pegar o item flat e filtrar as options do grupo.
    """
    # 1) via includeOptions
    try:
        groups = list_option_groups(merchant_id, include_options=True) or []
        for g in groups:
            if (g.get("id") or "") == option_group_id:
                opts = []
                for o in (g.get("options") or []):
                    price_val = (o.get("price") or {}).get("value", 0.0)
                    status_val = (o.get("status") or "AVAILABLE").upper()
                    opts.append({
                        "id": o.get("id"),
                        "name": o.get("name") or o.get("label") or "",
                        "description": o.get("description") or "",
                        "price": float(price_val or 0.0),
                        "status": status_val,
                        "groupId": option_group_id,
                        "productId": o.get("productId"),
                        "img": _normalize_img_url(opt.get("imagePath") or product_img_index.get(opt.get("productId"))),
                    })

                if opts:
                    return opts
        # se não achou via includeOptions, cai pro fallback
    except Exception:
        pass

    # 2) fallback: item flat
    if product_id:
        try:
            flat = get_item_flat(merchant_id, item_id)
            products = {p["id"]: p for p in (flat.get("products") or []) if p.get("id")}
            options  = {o["id"]: o for o in (flat.get("options")  or []) if o.get("id")}
            out = []
            for og in (flat.get("optionGroups") or []):
                if (og.get("id") or "") != option_group_id:
                    continue
                for ref in (og.get("options") or []):
                    oid = ref.get("id") or ref.get("optionId")
                    if not oid or oid not in options:
                        continue
                    
                    ctx = (st.session_state.get("catalog_context") or "").upper()
                    prod_img_idx = st.session_state.get("_product_img_index", {})

                    o = options[oid]

                    # preço/status globais
                    price_val  = (opt.get("price")  or {}).get("value", 0.0)
                    status_val = (opt.get("status") or "AVAILABLE").upper()

                    # imagem inicial da option (se houver)
                    image_path = opt.get("imagePath") or ""

                    # sobrescrever por contexto (v2 usa 'contextModifiers' ou 'contextOptionModifiers')
                    _ctx_mods = (
                        opt.get("contextModifiers")
                        or opt.get("contextOptionModifiers")
                        or []
                    )
                    for cm in _ctx_mods:
                        if (cm.get("catalogContext") or "").upper() == ctx:
                            if (cm.get("price") or {}).get("value") is not None:
                                price_val = cm["price"]["value"]
                            if cm.get("status"):
                                status_val = cm["status"].upper()
                            if cm.get("imagePath"):
                                image_path = cm["imagePath"]
                            break

                    # fallback pra imagem do produto base, se a option não tiver
                    if not image_path:
                        image_path = prod_img_idx.get(opt.get("productId") or "", "")

                    out.append({
                        "id":        opt.get("id"),
                        "name":      opt.get("name") or opt.get("label") or "",
                        "description": opt.get("description") or "",
                        "price":     float(price_val or 0.0),
                        "status":    status_val,
                        "paused":    status_val in ("UNAVAILABLE", "PAUSED"),
                        "groupId":   option_group_id,
                        "productId": opt.get("productId"),
                        "imagePath": image_path,
                    })

            return out
        except Exception:
            return []
    return []

# ========== OPTIONS (Complementos) – helpers exatos dos endpoints ==========

def _auth_headers_json() -> dict:
    """Cabeçalho JSON com Bearer já válido (não renova token aqui)."""
    return {
        "Authorization": f"Bearer {st.session_state.get('token','')}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def patch_option_status(token: str, merchant_id: str, option_id: str, new_status: str, catalog_context: str | None = None) -> tuple[bool, str]:
    """
    PATCH /merchants/{merchantId}/options/status
    body: { "options": [{"id": "<optionId>", "status": "AVAILABLE|UNAVAILABLE", "catalogContext": "..."}] }
    """
    url = _c(f"merchants/{merchant_id}/options/status")
    payload = {
        "options": [{
            "id": option_id,
            "status": str(new_status).upper(),
        }]
    }
    if catalog_context:
        payload["options"][0]["catalogContext"] = str(catalog_context)

    r = requests.patch(url, headers=_headers(), json=payload, timeout=30)
    if 200 <= r.status_code < 300:
        return True, "Status do complemento atualizado"
    return False, f"{r.status_code}: {r.text[:200]}"

def update_complement_price(merchant_id: str, product_id: str, option_id: str, new_price: float) -> tuple[bool, str]:
    """
    PATCH /merchants/{merchantId}/options/price
    body: { "options": [{"id":"...", "price":{"value": <float>}}] }
    product_id é ignorado aqui (mantido para compatibilidade da sua assinatura).
    """
    url = _c(f"merchants/{merchant_id}/options/price")
    payload = {"options": [{"id": option_id, "price": {"value": float(new_price)}}]}
    r = requests.patch(url, headers=_headers(), json=payload, timeout=30)
    if 200 <= r.status_code < 300:
        return True, "Preço do complemento atualizado"
    return False, f"{r.status_code}: {r.text[:200]}"

@limiter.limit("opt_external")
def update_complement_external_code(merchant_id: str, option_id: str, external_code: str) -> tuple[bool, str]:
    """
    PATCH /merchants/{merchantId}/options/externalCode
    body:
    {
      "id": "<optionId>",
      "externalCode": "ABC-123"
    }
    """
    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/options/externalCode"
    body = {
        "id": option_id,
        "externalCode": external_code or ""
    }
    try:
        r = requests.patch(url, headers=_auth_headers_json(), json=body, timeout=30)
        if r.status_code in (200, 204):
            return True, "ExternalCode atualizado"
        return False, f"Erro {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return False, str(e)


@limiter.limit("opt_delete")
def delete_complement(merchant_id: str, owner_product_id: str, group_id: str, option_id: str) -> tuple[bool, str]:
    """
    DELETE /merchants/{merchantId}/optionGroups/{optionGroupId}/products/{productId}/option
    (remove a opção daquele produto/grupo)
    """
    url = (
        f"https://merchant-api.ifood.com.br/catalog/v2.0"
        f"/merchants/{merchant_id}/optionGroups/{group_id}/products/{owner_product_id}/option"
    )
    # Algumas impls aceitam body {"id": option_id}; em outras basta o path.
    # Enviaremos o body por segurança (não quebra quando ignorado).
    body = {"id": option_id}
    try:
        r = requests.delete(url, headers=_auth_headers_json(), json=body, timeout=30)
        if r.status_code in (200, 202, 204):
            return True, "Complemento removido do grupo"
        return False, f"Erro {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return False, str(e)


@limiter.limit("opt_create")
def create_complement(merchant_id: str, group_id: str, name: str, price_value: float, description: str = "", product_payload: dict | None = None) -> tuple[bool, str, dict]:
    """
    POST /merchants/{merchantId}/optionGroups/{optionGroupId}/options
    Min payload válido pela doc (simplificado):
    {
      "status": "AVAILABLE",
      "product": { "name": "...", "description": "...", ... },
      "price": { "value": 9.90 }
    }
    product_payload pode ser usado para enviar campos extras (ean, tags, imagePath etc.)
    """
    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/optionGroups/{group_id}/options"
    product = {"name": name.strip()}
    if description:
        product["description"] = description.strip()
    if isinstance(product_payload, dict):
        product.update(product_payload)

    body = {
        "status": "AVAILABLE",
        "product": product,
        "price": {"value": float(price_value)},
    }
    try:
        r = requests.post(url, headers=_auth_headers_json(), json=body, timeout=30)
        if r.status_code in (200, 201, 202):
            js = r.json() if "application/json" in (r.headers.get("Content-Type","").lower()) else {}
            return True, "Complemento criado", (js or {})
        return False, f"Erro {r.status_code}: {r.text[:300]}", {}
    except Exception as e:
        return False, str(e), {}

def list_option_groups_for_item(merchant_id: str, item_id: str) -> list:
    """
    Em Catalog v2, os grupos vêm junto do item (optionGroups).
    Então a forma mais estável é pegar o item “flat” e ler optionGroups.
    """
    js = get_item_flat(merchant_id, item_id) or {}
    return js.get("optionGroups") or []

def patch_option_price(merchant_id: str, option_id: str, value: float, original_value: float | None = None):
    """
    PATCH /merchants/{merchantId}/options/price
    body: [{ "optionId": "...", "price": {"value": 5, "originalValue": 0} }]
    """
    url = f"{BASE_V1}/merchants/{merchant_id}/options/price"
    body = [{
        "optionId": option_id,
        "price": {"value": value} | ({"originalValue": original_value} if original_value is not None else {})
    }]
    r = requests.patch(url, headers=_headers(), json=body, timeout=30)
    if r.status_code in (200, 202):
        return True, "Preço atualizado"
    return False, f"Erro {r.status_code}: {r.text[:300]}"

def update_option_group_name(token: str, merchant_id: str, group_id: str, new_name: str) -> tuple[bool, str]:
    """
    Endpoint de update de Option Group (rename).
    Está no portal como “updateOptionGroup”.
    """
    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/option-groups/{group_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.patch(url, headers=headers, json={"name": new_name}, timeout=30)
    ok = r.status_code in (200, 204)
    return ok, (r.text if not ok else "Grupo renomeado")

def delete_option_group(token: str, merchant_id: str, group_id: str) -> tuple[bool, str]:
    """
    Remove um grupo de complemento inteiro (se sua loja permitir).
    """
    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/option-groups/{group_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.delete(url, headers=headers, timeout=30)
    ok = r.status_code in (200, 204)
    return ok, (r.text if not ok else "Grupo excluído")

def list_all_groups_and_options(merchant_id: str, catalog_id: str) -> list[dict]:
    """
    Varrendo categorias -> itens -> optionGroups -> options
    Retorna uma lista de grupos, cada grupo com sua lista de options.
    """
    groups: dict[str, dict] = {}

    cats = list_categories(merchant_id, catalog_id) or []
    for cat in cats:
        cid = cat.get("id") or cat.get("categoryId")
        cat_name = cat.get("name") or "Categoria"

        items = list_items_by_category(merchant_id, cid) or []
        if isinstance(items, dict) and "items" in items:
            items = items["items"]

        for it in items:
            item_id = it if isinstance(it, str) else (it.get("id") or it.get("itemId") or it.get("productId"))
            if not item_id:
                continue

            flat = get_item_flat(merchant_id, item_id) or {}
            prod_name = ""
            prods = flat.get("products") or []
            if prods:
                prod_name = prods[0].get("name") or ""

            # --- Mapa para resolver optionIds -> options (formato v2) ---
            products_map = {p.get("id"): p for p in (flat.get("products") or [])}
            options_map  = {o.get("id"): o for o in (flat.get("options")  or [])}

            for og in (flat.get("optionGroups") or []):
                group_name = og.get("name") or "Grupo sem nome"
                group_id   = og.get("id")

                # v2: optionIds; v1 (legado): 'options' (lista de objetos)
                raw = og.get("optionIds")
                if raw and isinstance(raw, list):
                    opt_list = [options_map.get(oid) for oid in raw if options_map.get(oid)]
                else:
                    # fallback p/ legado se vier og.options como objetos
                    opt_list = og.get("options") or []

                for opt in (opt_list or []):
                    opt_id = opt.get("id")
                    if not opt_id:
                        continue

                    # nome do complemento vem do 'productId' em 'products'
                    prod   = products_map.get(opt.get("productId"), {})
                    opt_nm = prod.get("name") or opt.get("externalCode") or "Complemento"

                    # imagem (quando existir)
                    opt_img = None
                    img = (opt.get("imagePath") or "").strip()
                    if img:
                        opt_img = _normalize_img_url(img)

                    price_val = 0.0
                    if isinstance(opt.get("price"), dict):
                        price_val = float(opt["price"].get("value") or 0)

                    status_val = (opt.get("status") or "AVAILABLE").upper()
                    paused     = status_val in ("UNAVAILABLE", "PAUSED")

                    all_complements.append({
                        "id":         opt_id,
                        "name":       opt_nm,
                        "description": opt.get("description") or "",
                        "group":      group_name,
                        "groupId":    group_id,
                        "item":       first_product.get("name") or item_name,  # mantém info do item “pai”
                        "itemId":     item_id,
                        "category":   category_name,
                        "categoryId": category_id,
                        "price":      price_val,
                        "status":     status_val,
                        "paused":     paused,
                        "img":        opt_img,
                        "productId":  opt.get("productId"),
                    })

    # normaliza sets -> listas
    out = []
    for g in groups.values():
        g["ownerItemIds"] = list(g["ownerItemIds"])
        g["ownerItemNames"] = list(g["ownerItemNames"])
        g["categoryNames"] = list(g["categoryNames"])
        out.append(g)
    return out

def patch_item_price(merchant_id, item_id, new_value, context=None, original=None):
    body = {"itemId": item_id, "price": {"value": float(new_value)}}
    if original is not None: body["price"]["originalValue"] = float(original)
    if context: body["priceByCatalog"] = [{"catalogContext": context, "value": float(new_value)}]
    return _patch(f"/merchants/{merchant_id}/items/price", body)

def patch_item_status(merchant_id, item_id, status, context=None):
    body = {"itemId": item_id, "status": status}
    if context: body["statusByCatalog"] = [{"catalogContext": context, "status": status}]
    return _patch(f"/merchants/{merchant_id}/items/status", body)

def patch_category_name(merchant_id, catalog_id, category_id, new_name):
    return _patch(f"/merchants/{merchant_id}/catalogs/{catalog_id}/categories/{category_id}", {"name": new_name})

def duplicate_category(merchant_id, catalog_id, category_id, category_name):
    """Duplica categoria E seus itens com payload correto."""
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%H:%M")
    payload = {
        "name": f"{category_name} (cópia {timestamp})",
        "status": "AVAILABLE",
        "template": "DEFAULT"
    }
    
    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/catalogs/{catalog_id}/categories"
    headers = {
        "Authorization": f"Bearer {st.session_state.token}",
        "Content-Type": "application/json"
    }
    
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    
    if resp.status_code not in (200, 201, 202):
        return None
    
    new_category = resp.json()
    new_category_id = new_category.get("id") or new_category.get("categoryId")
    
    if not new_category_id:
        return None
    
    items_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/categories/{category_id}/items"
    items_resp = requests.get(items_url, headers=headers, timeout=30)
    
    if items_resp.status_code != 200:
        return new_category
    
    items_data = items_resp.json()
    items = items_data.get("items", []) if isinstance(items_data, dict) else items_data
    
    if not items:
        return new_category
    
    copied = 0
    for item in items[:20]:
        item_id = item.get("id") or item.get("itemId")
        if not item_id:
            continue
        
        success, msg = duplicate_item_to_category(merchant_id, item_id, new_category_id)
        if success:
            copied += 1
    
    return new_category

def duplicate_item_to_category(merchant_id, item_id, target_category_id):
    """Duplica item seguindo o fluxo oficial da documentação."""
    import uuid
    import json
    
    headers = {
        "Authorization": f"Bearer {st.session_state.token}",
        "Content-Type": "application/json"
    }
    
    flat_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/items/{item_id}/flat"
    flat_resp = requests.get(flat_url, headers=headers, timeout=30)
    
    if flat_resp.status_code != 200:
        return False, f"Erro ao buscar item: {flat_resp.status_code}"
    
    flat = flat_resp.json()
    
    item_data = flat.get("item", {})
    products = flat.get("products", [])
    
    if not item_data or not products:
        return False, "Item incompleto"
    
    new_item_id = str(uuid.uuid4())
    new_product_id = str(uuid.uuid4())
    
    new_item = {
        "id": new_item_id,
        "type": item_data.get("type", "DEFAULT"),
        "categoryId": target_category_id,
        "status": "AVAILABLE",
        "price": item_data.get("price"),
        "productId": new_product_id,
        "shifts": item_data.get("shifts")
    }
    
    if "contextModifiers" in item_data:
        new_ctx = []
        for ctx in item_data["contextModifiers"]:
            clean_ctx = dict(ctx)
            clean_ctx.pop("itemContextId", None)
            new_ctx.append(clean_ctx)
        new_item["contextModifiers"] = new_ctx
    
    new_product = dict(products[0])
    new_product["id"] = new_product_id
    
    new_payload = {
        "item": new_item,
        "products": [new_product]
    }
    
    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/items"
    resp = requests.put(url, json=new_payload, headers=headers, timeout=30)
    
    if resp.status_code in (200, 201, 202):
        return True, "Item duplicado!"
    else:
        return False, f"Erro {resp.status_code}: {resp.text[:300]}"

def delete_category(merchant_id, category_id):
    return _delete(f"/merchants/{merchant_id}/categories/{category_id}")

# ------------------------ CSS Moderno ------------------------
st.markdown("""
<style>
.q3-catalog-wrap { max-width: 1400px; margin: 0 auto; padding: 20px 16px; }

.q3-cat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    margin: 16px 0 12px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 10px;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
}

.q3-cat-title {
    font-size: 16px;
    font-weight: 700;
    color: #fff;
    letter-spacing: 0.2px;
    margin: 0;
}

.q3-cat-count {
    background: rgba(255,255,255,0.2);
    padding: 3px 10px;
    border-radius: 16px;
    font-size: 11px;
    color: #fff;
    font-weight: 600;
}

.q3-items-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 16px;
    margin: 0 0 24px;
}

.q3-item-card {
    background: linear-gradient(145deg, #1e1e2e 0%, #252535 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
}

.q3-item-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.25);
    border-color: rgba(138,0,255,0.3);
}

.q3-card-img {
    width: 100%;
    height: 140px;
    object-fit: cover;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    position: relative;
}

.q3-card-img img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.q3-status-badge {
    position: absolute;
    top: 12px;
    right: 12px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.q3-badge-active {
    background: rgba(34, 197, 94, 0.9);
    color: #fff;
}

.q3-badge-paused {
    background: rgba(239, 68, 68, 0.9);
    color: #fff;
}

.q3-card-body {
    padding: 12px;
}

.q3-card-name {
    font-size: 14px;
    font-weight: 700;
    color: #fff;
    margin: 0 0 6px;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 36px;
}

.q3-card-desc {
    font-size: 11px;
    color: #9ca3af;
    margin: 0 0 10px;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 50px;
}

.q3-card-price {
    font-size: 20px;
    font-weight: 800;
    background: linear-gradient(90deg, #8a00ff, #ff2bd2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 10px;
}

.q3-card-actions {
    display: flex;
    gap: 8px;
}

.q3-change-img-btn {
    position: absolute;
    bottom: 8px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(138, 0, 255, 0.95);
    color: #fff;
    border: none;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.2s;
    backdrop-filter: blur(4px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}

.q3-card-img:hover .q3-change-img-btn {
    opacity: 1;
}

.q3-change-img-btn:hover {
    background: rgba(255, 43, 210, 0.95);
}

.q3-img-placeholder {
    width: 100%;
    height: 140px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 36px;
}

@media (max-width: 768px) {
    .q3-items-grid {
        grid-template-columns: 1fr;
    }
    
    .q3-cat-header {
        padding: 12px 16px;
    }
    
    .q3-cat-title {
        font-size: 18px;
    }
}

.q3-card-actions .stButton button {
    width: 100%;
    padding: 10px 16px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 14px;
}

.q3-price-edit {
    margin-top: 12px;
    padding: 16px;
    background: rgba(0,0,0,0.2);
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.05);
}
</style>
""", unsafe_allow_html=True)

# ------------------------ Helpers imagem ------------------------
def upload_item_image_wrapper(merchant_id, item_id, uploaded_file):
    """Upload de imagem via endpoint de PRODUTO."""
    try:
        from PIL import Image
        from io import BytesIO
        import base64
        
        img = Image.open(uploaded_file)
        img.thumbnail((800, 600), Image.Resampling.LANCZOS)
        
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = bg
        
        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        file_bytes = output.getvalue()
        
        b64 = base64.b64encode(file_bytes).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"
        
        headers = {
            "Authorization": f"Bearer {st.session_state.token}", 
            "Content-Type": "application/json"
        }
        
        upload_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/image/upload"
        resp = requests.post(upload_url, json={"image": data_url}, headers=headers, timeout=60)
        
        if resp.status_code not in (200, 201, 202):
            return False, f"Erro no upload: {resp.status_code}"
        
        image_path = resp.json().get("imagePath")
        if not image_path:
            return False, "Upload OK mas sem imagePath"
        
        flat_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/items/{item_id}/flat"
        flat_resp = requests.get(flat_url, headers=headers, timeout=30)
        
        if flat_resp.status_code != 200:
            return False, f"Erro ao buscar item: {flat_resp.status_code}"
        
        flat = flat_resp.json()
        products = flat.get("products", [])
        
        if not products:
            return False, "Item sem produtos"
        
        success = []
        errors = []
        
        for p in products:
            product_id = p.get("id")
            if not product_id:
                continue
            
            product_payload = dict(p)
            product_payload["imagePath"] = image_path
            
            product_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/products/{product_id}"
            
            try:
                product_resp = requests.put(
                    product_url,
                    json=product_payload,
                    headers=headers,
                    timeout=30
                )
                
                if product_resp.status_code in (200, 201, 202):
                    success.append(product_id)
                else:
                    errors.append(f"{product_id}: {product_resp.status_code}")
            except Exception as e:
                errors.append(f"{product_id}: {str(e)[:50]}")
        
        if success:
            return True, f"Imagem atualizada em {len(success)} produto(s)!"
        else:
            return False, f"Falha: {errors}"
            
    except Exception as e:
        import traceback
        return False, f"Erro: {traceback.format_exc()[:300]}"
    
def _first_img_from(flat, meta=None):
    """Extrai a primeira imagem encontrada nos dados do item."""
    import base64
    
    def _pick(v):
        if isinstance(v, str): 
            return v
        if isinstance(v, dict): 
            return v.get("url") or v.get("path") or v.get("imagePath") or v.get("image")
        if isinstance(v, list) and v:
            x = v[0]
            if isinstance(x, str): 
                return x
            if isinstance(x, dict): 
                return x.get("url") or x.get("path") or x.get("imagePath") or x.get("image")
        return None

    it = flat.get("item") if isinstance(flat, dict) and isinstance(flat.get("item"), dict) else {}
    prods = flat.get("products") if isinstance(flat, dict) and isinstance(flat.get("products"), list) else []
    imgs = flat.get("images") if isinstance(flat, dict) and isinstance(flat.get("images"), list) else []

    raw = _pick(it.get("image")) or _pick(it.get("imagePath")) or _pick(imgs)
    if meta:
        raw = raw or _pick(meta.get("image")) or _pick(meta.get("imagePath"))
    
    if not raw and prods:
        for p in prods:
            raw = _pick(p.get("images")) or _pick(p.get("imagePath")) or _pick(p.get("image"))
            if raw: 
                break
    
    if not raw: 
        return None
    
    s = str(raw).lstrip("/")
    if s.startswith("http"): 
        return s
    if "image/upload/" in s:
        s = s.split("image/upload/", 1)[-1]
        return f"https://static-images.ifood.com.br/image/upload/{s}"
    
    return None

# ------------------------ Guardas ------------------------
if not TOKEN or not MERCHANT_ID:
    st.error("Defina TOKEN e MERCHANT_ID (session_state / secrets / env) para usar o Catálogo.")
    st.stop()

if not CATALOG_ID:
    try:
        cats = get_catalogs(MERCHANT_ID)
        if isinstance(cats, list) and cats:
            CATALOG_ID = cats[0].get("id") or cats[0].get("catalogId")
            st.session_state["catalog_id"] = CATALOG_ID
        else:
            st.warning("Nenhum catálogo encontrado para este merchant.")
    except Exception as e:
        st.error(f"Erro ao listar catálogos: {e}")
        st.stop()

# ------------------------ Funções para Complementos ------------------------

def upload_complement_image(merchant_id, option_id, uploaded_file):
    """Upload de imagem para complemento (option)."""
    try:
        from PIL import Image
        from io import BytesIO
        import base64
        
        # Otimiza imagem
        img = Image.open(uploaded_file)
        img.thumbnail((800, 600), Image.Resampling.LANCZOS)
        
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = bg
        
        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        file_bytes = output.getvalue()
        
        # Faz upload
        b64 = base64.b64encode(file_bytes).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"
        
        headers = {
            "Authorization": f"Bearer {st.session_state.token}",
            "Content-Type": "application/json"
        }
        
        # Endpoint oficial: POST /merchants/{merchantId}/image/upload
        upload_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/image/upload"
        resp = requests.post(upload_url, json={"image": data_url}, headers=headers, timeout=60)
        
        if resp.status_code not in (200, 201, 202):
            return False, f"Erro no upload: {resp.status_code}"
        
        image_path = resp.json().get("imagePath")
        if not image_path:
            return False, "Upload OK mas sem imagePath"
        
        # Atualiza o complemento com o novo imagePath
        # Endpoint: PUT /merchants/{merchantId}/options/{optionId}
        update_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/options/{option_id}"
        update_payload = {
            "imagePath": image_path
        }
        
        update_resp = requests.put(update_url, json=update_payload, headers=headers, timeout=30)
        
        if update_resp.status_code in (200, 201, 202):
            return True, "Imagem atualizada!"
        else:
            return False, f"Erro ao atualizar: {update_resp.status_code}"
            
    except Exception as e:
        return False, f"Erro: {str(e)[:200]}"

def update_complement_details(merchant_id, item_id, option_id, new_name, new_description):
    """Atualiza nome e descrição de um complemento."""
    try:
        headers = {
            "Authorization": f"Bearer {st.session_state.token}",
            "Content-Type": "application/json"
        }
        
        # Endpoint: PUT /merchants/{merchantId}/options/{optionId}
        url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/options/{option_id}"
        
        payload = {
            "name": new_name,
            "description": new_description
        }
        
        resp = requests.put(url, json=payload, headers=headers, timeout=30)
        
        if resp.status_code in (200, 201, 202):
            return True, "Complemento atualizado!"
        else:
            return False, f"Erro {resp.status_code}: {resp.text[:200]}"
            
    except Exception as e:
        return False, f"Erro: {str(e)[:200]}"

def update_complement_price(merchant_id, item_id, option_id, new_price):
    """Atualiza preço de um complemento."""
    try:
        headers = {
            "Authorization": f"Bearer {st.session_state.token}",
            "Content-Type": "application/json"
        }
        
        # Endpoint: PUT /merchants/{merchantId}/options/{optionId}
        url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/options/{option_id}"
        
        payload = {
            "price": {
                "value": float(new_price)
            }
        }
        
        resp = requests.put(url, json=payload, headers=headers, timeout=30)
        
        if resp.status_code in (200, 201, 202):
            return True, "Preço atualizado!"
        else:
            return False, f"Erro {resp.status_code}"
            
    except Exception as e:
        return False, f"Erro: {str(e)[:200]}"

def duplicate_complement(merchant_id, item_id, group_id, option_id):
    """Duplica um complemento dentro do mesmo grupo."""
    try:
        import uuid
        
        headers = {
            "Authorization": f"Bearer {st.session_state.token}",
            "Content-Type": "application/json"
        }
        
        # 1️⃣ Busca dados do complemento original
        get_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/options/{option_id}"
        get_resp = requests.get(get_url, headers=headers, timeout=30)
        
        if get_resp.status_code != 200:
            return False, "Erro ao buscar complemento original"
        
        original = get_resp.json()
        
        # 2️⃣ Cria novo complemento
        new_id = str(uuid.uuid4())
        new_name = f"{original.get('name', 'Complemento')} (cópia)"
        
        create_payload = {
            "id": new_id,
            "name": new_name,
            "description": original.get("description", ""),
            "price": original.get("price", {"value": 0}),
            "optionGroupId": group_id
        }
        
        if original.get("imagePath"):
            create_payload["imagePath"] = original["imagePath"]
        
        # Endpoint: POST /merchants/{merchantId}/options
        create_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/options"
        create_resp = requests.post(create_url, json=create_payload, headers=headers, timeout=30)
        
        if create_resp.status_code in (200, 201, 202):
            return True, "Complemento duplicado!"
        else:
            return False, f"Erro {create_resp.status_code}"
            
    except Exception as e:
        return False, f"Erro: {str(e)[:200]}"

def delete_complement(merchant_id, item_id, group_id, option_id):
    """Exclui um complemento."""
    try:
        headers = {
            "Authorization": f"Bearer {st.session_state.token}",
            "Content-Type": "application/json"
        }
        
        # Endpoint: DELETE /merchants/{merchantId}/options/{optionId}
        url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{merchant_id}/options/{option_id}"
        
        resp = requests.delete(url, headers=headers, timeout=30)
        
        if resp.status_code in (200, 202, 204):
            return True, "Complemento removido!"
        else:
            return False, f"Erro {resp.status_code}"
            
    except Exception as e:
        return False, f"Erro: {str(e)[:200]}"

# ------------------------ UI ------------------------

# Header customizado com botão de adicionar
col_header, col_btn = st.columns([6, 1])

with col_header:
    st.markdown("### 🛒 Catálogo - Gerenciar Itens e Categorias")

with col_btn:
    with st.popover("➕ Nova Categoria"):
        with st.form(key="create_category_form_global"):
            new_cat_name = st.text_input("Nome da categoria", placeholder="Ex: Sobremesas")
            
            if st.form_submit_button("Criar categoria", type="primary", use_container_width=True):
                if not new_cat_name.strip():
                    st.error("Nome não pode estar vazio")
                else:
                    try:
                        url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{MERCHANT_ID}/catalogs/{CATALOG_ID}/categories"
                        headers = {
                            "Authorization": f"Bearer {st.session_state.token}",
                            "Content-Type": "application/json"
                        }
                        payload = {
                            "name": new_cat_name.strip(),
                            "status": "AVAILABLE",
                            "template": "DEFAULT"
                        }
                        
                        resp = requests.post(url, json=payload, headers=headers, timeout=30)
                        
                        if resp.status_code in (200, 201, 202):
                            st.success("Categoria criada!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Erro: {resp.status_code}")
                    except Exception as e:
                        st.error(f"Erro: {str(e)}")

with st.expander("", expanded=True):
    
    st.markdown("<div class='q3-catalog-wrap'>", unsafe_allow_html=True)
    
    # 🆕 TABS GLOBAIS: Itens vs Complementos
    tab_view_items, tab_view_complements = st.tabs(["🍽️ Itens", "➕ Complementos"])
    
    # ==================== ABA GLOBAL: ITENS ====================
    with tab_view_items:
        try:
            categories = list_categories(MERCHANT_ID, CATALOG_ID) or []
        except Exception as e:
            st.error(f"Erro ao listar categorias: {e}")
            categories = []
        
        for cat in categories:
            category_id = (cat.get("id") if isinstance(cat, dict) else None) or (cat.get("categoryId") if isinstance(cat, dict) else None)
            category_name = (cat.get("name") if isinstance(cat, dict) else None) or "Categoria"

            # Header da categoria
            try:
                items = list_items_by_category(MERCHANT_ID, category_id) or []
                if isinstance(items, dict) and "items" in items: 
                    items = items["items"]
                item_count = len(items)
            except Exception:
                items = []
                item_count = 0

            col1, col2 = st.columns([0.85, 0.15])
            
            with col1:
                st.markdown(f"""
                <div class='q3-cat-header'>
                    <div class='q3-cat-title'>{category_name}</div>
                    <div class='q3-cat-count'>{item_count} itens</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                with st.popover("⚙️ Opções"):
                    st.caption("Gerenciar categoria")
                    
                    # ➕ CRIAR ITEM
                    with st.form(key=f"create_item_{category_id}"):
                        st.subheader("➕ Criar Item")
                        
                        item_name = st.text_input("Nome do item", placeholder="Ex: Pizza Margherita")
                        item_desc = st.text_area("Descrição", placeholder="Ingredientes e detalhes", height=80)
                        item_price = st.text_input("Preço", placeholder="25.90")
                        
                        if st.form_submit_button("Criar Item", type="primary", use_container_width=True):
                            if not item_name.strip():
                                st.error("Nome é obrigatório")
                            elif not item_price.strip():
                                st.error("Preço é obrigatório")
                            else:
                                try:
                                    import uuid
                                    
                                    price_val = float(item_price.replace(",", "."))
                                    item_id = str(uuid.uuid4())
                                    product_id = str(uuid.uuid4())
                                    
                                    payload = {
                                        "items": [{
                                            "id": item_id,
                                            "item": {
                                                "id": item_id,
                                                "type": "DEFAULT",
                                                "categoryId": category_id,
                                                "status": "AVAILABLE",
                                                "price": {"value": price_val},
                                                "productId": product_id,
                                                "shifts": [{
                                                    "startTime": "00:00",
                                                    "endTime": "23:59",
                                                    "monday": True,
                                                    "tuesday": True,
                                                    "wednesday": True,
                                                    "thursday": True,
                                                    "friday": True,
                                                    "saturday": True,
                                                    "sunday": True
                                                }]
                                            },
                                            "products": [{
                                                "id": product_id,
                                                "name": item_name.strip(),
                                                "description": item_desc.strip() if item_desc else "",
                                                "serving": "SERVES_1"
                                            }]
                                        }]
                                    }
                                    
                                    url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{MERCHANT_ID}/items"
                                    headers = {
                                        "Authorization": f"Bearer {st.session_state.token}",
                                        "Content-Type": "application/json"
                                    }
                                    
                                    resp = requests.put(url, json=payload, headers=headers, timeout=30)
                                    
                                    if resp.status_code in (200, 201, 202):
                                        st.success("Item criado!")
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(f"Erro {resp.status_code}: {resp.text[:300]}")
                                        
                                except ValueError:
                                    st.error("Preço inválido. Use formato: 25.90")
                                except Exception as e:
                                    st.error(f"Erro: {str(e)}")
                    
                    st.divider()
                    
                    # Renomear categoria
                    with st.form(key=f"edit_{category_id}"):
                        new_name = st.text_input("Renomear", value=category_name, key=f"nm_{category_id}")
                        if st.form_submit_button("Salvar", use_container_width=True):
                            patch_category_name(MERCHANT_ID, CATALOG_ID, category_id, new_name)
                            st.success("Atualizado")
                            st.rerun()
                    
                    # Duplicar categoria
                    if st.button("📋 Duplicar categoria", key=f"dup_{category_id}", use_container_width=True):
                        with st.spinner("Duplicando categoria e itens..."):
                            result = duplicate_category(MERCHANT_ID, CATALOG_ID, category_id, category_name)
                            if result:
                                st.success("Categoria duplicada!")
                            else:
                                st.error("Erro ao duplicar")
                        st.cache_data.clear()
                        st.rerun()
                    
                    # Remover categoria
                    with st.form(key=f"del_{category_id}"):
                        ok = st.checkbox("Confirmar remoção", key=f"chk_{category_id}")
                        if st.form_submit_button("Remover", use_container_width=True, type="primary") and ok:
                            delete_category(MERCHANT_ID, category_id)
                            st.success("Removida")
                            st.rerun()

            if not items:
                st.info("Nenhum item nesta categoria")
                continue

            # Processar itens
            items_data = []
            for it in items:
                if isinstance(it, str):
                    item_id, meta = it, {}
                else:
                    item_id = it.get("id") or it.get("itemId") or it.get("productId")
                    meta = it
                
                if not item_id: 
                    continue

                try:
                    flat = get_item_flat(MERCHANT_ID, item_id) or {}
                except Exception as e:
                    flat = {}

                item_data = flat.get("item") or {}
                products = flat.get("products") or []
                first_product = products[0] if products else {}

                name = (
                    first_product.get("name") or 
                    meta.get("name") or 
                    item_id
                )

                desc = (
                    first_product.get("description") or 
                    meta.get("description") or 
                    ""
                ).strip()

                price = 0.0
                price_obj = item_data.get("price") or {}
                if isinstance(price_obj, dict):
                    price = float(price_obj.get("value", 0))
                elif isinstance(price_obj, (int, float)):
                    price = float(price_obj)

                current_context = st.session_state.get("catalog_context", "DEFAULT")
                status_raw = None

                context_modifiers = item_data.get("contextModifiers") or []
                for ctx in context_modifiers:
                    if ctx.get("catalogContext") == current_context:
                        status_raw = ctx.get("status")
                        # ⬇️ pega preço do contexto, se existir
                        pmod = ctx.get("price") or {}
                        if isinstance(pmod, dict) and pmod.get("value") is not None:
                            price = float(pmod["value"])
                        break

                if not status_raw:
                    status_raw = item_data.get("status")

                status = (status_raw or "AVAILABLE").upper()
                paused = status in ("UNAVAILABLE", "PAUSED", "INACTIVE", "DISABLED")

                img = _normalize_img_url(_first_img_from(flat, meta))

                items_data.append({
                    "id": item_id,
                    "name": name,
                    "desc": desc,
                    "price": price, 
                    "paused": paused,
                    "img": img,
                })

            # Renderizar grid (4 itens por linha)
            cols_per_row = 4
            for row_idx in range(0, len(items_data), cols_per_row):
                cols = st.columns(cols_per_row)
                
                for col_idx, item in enumerate(items_data[row_idx:row_idx + cols_per_row]):
                    with cols[col_idx]:
                        with st.container():

                            # Imagem com botão de upload
                            if item["img"]:
                                st.markdown(f"""
                                <div class='q3-card-img' style='position:relative;'>
                                    <img src='{item["img"]}' alt='{item["name"]}'/>
                                    <div class='q3-status-badge {"q3-badge-paused" if item["paused"] else "q3-badge-active"}'>
                                        {"PAUSADO" if item["paused"] else "ATIVO"}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div class='q3-img-placeholder' style='position:relative;'>
                                    🍽️
                                    <div class='q3-status-badge {"q3-badge-paused" if item["paused"] else "q3-badge-active"}' 
                                        style='position:absolute;top:12px;right:12px;'>
                                        {"PAUSADO" if item["paused"] else "ATIVO"}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            upload_counter_key = f"_upload_counter_{item['id']}"
                            if upload_counter_key not in st.session_state:
                                st.session_state[upload_counter_key] = 0

                            upload_key = f"img_{item['id']}_{st.session_state[upload_counter_key]}"

                            with st.popover("📷 Trocar foto", use_container_width=True):
                                uploaded = st.file_uploader(
                                    "Enviar nova imagem",
                                    type=["jpg", "jpeg", "png"],
                                    key=upload_key
                                )
                                
                                if uploaded:
                                    if st.session_state.get(f"_uploading_{item['id']}", False):
                                        st.warning("Upload em andamento...")
                                        st.stop()
                                    
                                    st.session_state[f"_uploading_{item['id']}"] = True
                                    
                                    with st.spinner("Otimizando e enviando..."):
                                        success, msg = upload_item_image_wrapper(MERCHANT_ID, item['id'], uploaded)
                                        
                                        if success:
                                            st.success(msg)
                                            st.cache_data.clear()
                                            st.session_state[upload_counter_key] += 1
                                            st.session_state[f"_uploading_{item['id']}"] = False
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                            st.session_state[f"_uploading_{item['id']}"] = False
                            
                            st.markdown(f"<div class='q3-card-name'>{item['name']}</div>", unsafe_allow_html=True)
                            
                            if item['desc']:
                                st.markdown(f"<div class='q3-card-desc'>{item['desc']}</div>", unsafe_allow_html=True)
                            else:
                                st.markdown("<div class='q3-card-desc' style='opacity:0.5;'>Sem descrição</div>", unsafe_allow_html=True)
                            
                            desc_key = f"desc_edit_{item['id']}"
                            
                            if st.button("✏️ Editar descrição", key=f"btn_desc_{item['id']}", use_container_width=True):
                                st.session_state[f"editing_desc_{item['id']}"] = True
                            
                            if st.session_state.get(f"editing_desc_{item['id']}", False):
                                new_desc = st.text_area(
                                    "Nova descrição",
                                    value=item['desc'],
                                    height=120,
                                    max_chars=500,
                                    key=desc_key
                                )
                                
                                col_save, col_cancel = st.columns(2)
                                
                                with col_save:
                                    if st.button("💾 Salvar", key=f"save_desc_{item['id']}", use_container_width=True):
                                        if st.session_state.get(f"_saving_desc_{item['id']}", False):
                                            st.warning("Salvando...")
                                            st.stop()
                                        
                                        st.session_state[f"_saving_desc_{item['id']}"] = True
                                        
                                        try:
                                            headers = {
                                                "Authorization": f"Bearer {st.session_state.token}", 
                                                "Content-Type": "application/json"
                                            }
                                            
                                            flat_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{MERCHANT_ID}/items/{item['id']}/flat"
                                            flat_resp = requests.get(flat_url, headers=headers, timeout=30)
                                            
                                            if flat_resp.status_code != 200:
                                                st.error(f"Erro: {flat_resp.status_code}")
                                                st.session_state[f"_saving_desc_{item['id']}"] = False
                                            else:
                                                flat = flat_resp.json()
                                                products = flat.get("products", [])
                                                
                                                if not products:
                                                    st.error("Item sem produtos")
                                                    st.session_state[f"_saving_desc_{item['id']}"] = False
                                                else:
                                                    success_count = 0
                                                    for p in products:
                                                        product_id = p.get("id")
                                                        if not product_id:
                                                            continue
                                                        
                                                        product_payload = dict(p)
                                                        product_payload["description"] = new_desc
                                                        
                                                        product_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{MERCHANT_ID}/products/{product_id}"
                                                        
                                                        product_resp = requests.put(
                                                            product_url,
                                                            json=product_payload,
                                                            headers=headers,
                                                            timeout=30
                                                        )
                                                        
                                                        if product_resp.status_code in (200, 201, 202):
                                                            success_count += 1
                                                    
                                                    if success_count > 0:
                                                        st.success("Descrição atualizada!")
                                                        st.cache_data.clear()
                                                        st.session_state[f"editing_desc_{item['id']}"] = False
                                                        st.session_state[f"_saving_desc_{item['id']}"] = False
                                                        st.rerun()
                                                    else:
                                                        st.error("Nenhum produto atualizado")
                                                        st.session_state[f"_saving_desc_{item['id']}"] = False
                                                        
                                        except Exception as e:
                                            st.error(f"Erro: {str(e)}")
                                            st.session_state[f"_saving_desc_{item['id']}"] = False
                                
                                with col_cancel:
                                    if st.button("❌ Cancelar", key=f"cancel_desc_{item['id']}", use_container_width=True):
                                        st.session_state[f"editing_desc_{item['id']}"] = False
                            
                            st.markdown(f"<div class='q3-card-price'>R$ {item['price']:.2f}</div>", unsafe_allow_html=True)
                            
                            col_action1, col_action2, col_action3, col_action4 = st.columns(4)
                            
                            with col_action1:
                                btn_label = "✅ Ativar" if item["paused"] else "⏸️ Pausar"
                                if st.button(btn_label, key=f"toggle_{item['id']}", use_container_width=True):
                                    new_status = "AVAILABLE" if item["paused"] else "UNAVAILABLE"
                                    patch_item_status(MERCHANT_ID, item['id'], new_status, context=current_context)
                                    st.success("Atualizado")
                                    st.cache_data.clear()
                                    st.rerun()
                            
                            with col_action2:
                                with st.popover("💰", use_container_width=True):
                                    with st.form(key=f"price_{item['id']}"):
                                        price_str = st.text_input(
                                            "Novo preço (ex: 25.90)",
                                            value=f"{item['price']:.2f}",
                                            key=f"np_{item['id']}"
                                        )
                                        
                                        if st.form_submit_button("Salvar", use_container_width=True):
                                            try:
                                                new_price = float(price_str.replace(",", "."))
                                                
                                                if new_price < 0:
                                                    st.error("Preço não pode ser negativo")
                                                else:
                                                    patch_item_price(MERCHANT_ID, item['id'], new_price, context=current_context)
                                                    st.success("Preço atualizado")
                                                    st.cache_data.clear()
                                                    st.rerun()
                                            except ValueError:
                                                st.error("Preço inválido. Use formato: 25.90")
                            
                            with col_action3:
                                with st.popover("🗑️", use_container_width=True):
                                    st.warning("⚠️ Ação irreversível!")
                                    if st.button("Confirmar exclusão", key=f"del_{item['id']}", type="primary", use_container_width=True):
                                        try:
                                            flat_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{MERCHANT_ID}/items/{item['id']}/flat"
                                            headers = {"Authorization": f"Bearer {st.session_state.token}"}
                                            flat_resp = requests.get(flat_url, headers=headers, timeout=30)
                                            
                                            if flat_resp.status_code != 200:
                                                st.error("Erro ao buscar item")
                                            else:
                                                flat = flat_resp.json()
                                                item_data = flat.get("item", {})
                                                product_id = item_data.get("productId")
                                                
                                                if not product_id:
                                                    st.error("productId não encontrado")
                                                else:
                                                    delete_url = f"https://merchant-api.ifood.com.br/catalog/v2.0/merchants/{MERCHANT_ID}/categories/{category_id}/products/{product_id}"
                                                    
                                                    resp = requests.delete(delete_url, headers=headers, timeout=30)
                                                    
                                                    if resp.status_code in (200, 202, 204):
                                                        st.success("Item removido!")
                                                        st.cache_data.clear()
                                                        st.rerun()
                                                    else:
                                                        st.error(f"Erro: {resp.status_code}")
                                                        
                                        except Exception as e:
                                            st.error(f"Erro: {str(e)}")
                                
                            with col_action4:
                                with st.popover("📋", use_container_width=True):
                                    st.caption("Duplicar item")
                                    if st.button("Confirmar duplicação", key=f"dup_{item['id']}", type="primary", use_container_width=True):
                                        with st.spinner("Duplicando..."):
                                            success, msg = duplicate_item_to_category(
                                                MERCHANT_ID, 
                                                item['id'], 
                                                category_id
                                            )
                                            if success:
                                                st.success(msg)
                                                st.cache_data.clear()
                                                st.rerun()
                                            else:
                                                st.error(msg)

# ==================== ABA GLOBAL: COMPLEMENTOS ====================
with tab_view_complements:
    st.subheader("🧩 Grupos de Complementos")
    
    # ✅ GARANTIR que o índice de imagens está construído
    if "_product_img_index" not in st.session_state:
        with st.spinner("Carregando imagens dos produtos..."):
            try:
                product_img_index = {}
                categories = list_categories(MERCHANT_ID, CATALOG_ID) or []
                
                for cat in categories:
                    category_id = cat.get("id") or cat.get("categoryId")
                    if not category_id:
                        continue
                    
                    try:
                        items = list_items_by_category(MERCHANT_ID, category_id) or []
                        if isinstance(items, dict) and "items" in items:
                            items = items["items"]
                    except Exception:
                        items = []
                    
                    for it in items:
                        item_id = it if isinstance(it, str) else (it.get("id") or it.get("itemId"))
                        if not item_id:
                            continue
                        
                        try:
                            flat = get_item_flat(MERCHANT_ID, item_id) or {}
                        except Exception:
                            flat = {}
                        
                        # Captura imagens dos products
                        for p in (flat.get("products") or []):
                            pid = p.get("id")
                            if not pid:
                                continue
                            
                            # Prioridade: imagePath > assets.image
                            pid = str(pid)
                            img = (
                                p.get("imagePath")
                                or (p.get("assets") or {}).get("image")
                                or p.get("image")
                                or ""
                            )
                            if pid and img and pid not in product_img_index:
                                product_img_index[pid] = _normalize_img_url(img)
                
                st.session_state["_product_img_index"] = product_img_index
                
            except Exception as e:
                st.warning(f"Não foi possível carregar índice de imagens: {e}")
                st.session_state["_product_img_index"] = {}

    # 1) Carrega TODOS os grupos de complementos
    with st.spinner("Carregando grupos de complementos..."):
        try:
            _groups = list_option_groups(MERCHANT_ID) or []
        except Exception as e:
            _groups = []
            st.warning(f"Não foi possível listar grupos: {e}")

    # 2) Monta mapa de grupos
    groups_map: dict[str, dict] = {
        (g.get("id") or g.get("optionGroupId")): {
            "id": (g.get("id") or g.get("optionGroupId")),
            "name": g.get("name") or "Grupo sem nome",
            "status": (g.get("status") or "AVAILABLE").upper(),
            "options": [],
        }
        for g in (_groups or [])
        if (g.get("id") or g.get("optionGroupId"))
    }

    # 3) Percorre Catálogo → Categorias → Itens → Flat → OptionGroups/Options
    with st.spinner("Relacionando opções aos grupos..."):
        try:
            categories = list_categories(MERCHANT_ID, CATALOG_ID) or []
        except Exception:
            categories = []

        for cat in (categories or []):
            category_id = cat.get("id") or cat.get("categoryId")
            try:
                items = list_items_by_category(MERCHANT_ID, category_id) or []
                if isinstance(items, dict) and "items" in items:
                    items = items["items"]
            except Exception:
                items = []

            for it in items:
                item_id = it if isinstance(it, str) else (it.get("id") or it.get("itemId") or it.get("productId"))
                if not item_id:
                    continue

                try:
                    flat = get_item_flat(MERCHANT_ID, item_id) or {}
                    
                    # ✅ ATUALIZA o índice de imagens dos products
                    products = flat.get("products") or []
                    _prod_idx = {}
                    for p in products:
                        pid = p.get("id")
                        if not pid:
                            continue
                        img = p.get("imagePath") or (p.get("assets") or {}).get("image") or p.get("image") or ""
                        if img:
                            _prod_idx[pid] = _normalize_img_url(img)
                    
                    _base = st.session_state.get("_product_img_index", {})
                    _base.update(_prod_idx)
                    st.session_state["_product_img_index"] = _base
                    
                except Exception:
                    continue

                products = {p["id"]: p for p in (flat.get("products") or [])}
                options = {o.get("id"): o for o in (flat.get("options") or []) if o.get("id")}

                for og in (flat.get("optionGroups") or []):
                    gid = og.get("id")
                    if not gid or gid not in groups_map:
                        continue

                    for opt_ref in (og.get("options") or []):
                        oid = opt_ref.get("id") or opt_ref.get("optionId")
                        if not oid or oid not in options:
                            continue

                        opt = options[oid]
                        prod = products.get(opt.get("productId") or "", {})

                        # -------- cálculo de preço/status + imagem ----------
                        
                        # preço global (aceita dict/float/str)
                        _p = opt.get("price")
                        if isinstance(_p, dict):
                            price_val = _p.get("value", 0.0)
                        elif isinstance(_p, (int, float)):
                            price_val = float(_p)
                        elif isinstance(_p, str) and _p.strip():
                            try:
                                price_val = float(_p)
                            except Exception:
                                price_val = 0.0
                        else:
                            price_val = 0.0

                        # status global
                        status_val = (opt.get("status") or "AVAILABLE").upper()

                        # imagem (prioridade: context > option.imagePath > imagem do produto)
                        image_path = opt.get("imagePath") or ""

                        # contexto atual
                        ctx = (st.session_state.get("catalog_context") or "DEFAULT").upper()

                        # tenta sobreescrever por contexto
                        _ctx_mods = (
                            opt.get("contextModifiers")
                            or opt.get("contextOptionModifiers")
                            or []
                        )

                        for cm in _ctx_mods:
                            if (cm.get("catalogContext") or "").upper() == ctx:
                                # preço do contexto
                                _raw = cm.get("price")
                                if isinstance(_raw, dict):
                                    _cm_price = _raw.get("value")
                                elif isinstance(_raw, (int, float)):
                                    _cm_price = float(_raw)
                                elif isinstance(_raw, str) and _raw.strip():
                                    try:
                                        _cm_price = float(_raw)
                                    except Exception:
                                        _cm_price = None
                                else:
                                    _cm_price = None

                                if _cm_price is not None:
                                    price_val = float(_cm_price)

                                # status do contexto
                                if cm.get("status"):
                                    status_val = cm["status"].upper()
                                
                                # imagem do contexto
                                if cm.get("imagePath"):
                                    image_path = cm["imagePath"]
                                
                                break

                        # se ainda não temos imagem, busca do produto base
                        if not image_path:
                            prod_img_idx = st.session_state.get("_product_img_index", {})
                            image_path = (
                                prod.get("imagePath")
                                or (prod.get("assets") or {}).get("image")
                                or prod.get("image")
                                or prod_img_idx.get(opt.get("productId") or "", "")
                            )

                        # ----------------------------------------------------

                        name = opt.get("name") or prod.get("name") or prod.get("externalCode") or f"Complemento {oid[:6]}"

                        groups_map[gid]["options"].append({
                            "id": oid,
                            "name": name,
                            "description": opt.get("description") or "",
                            "status": status_val,
                            "price": float(price_val or 0),
                            "productId": opt.get("productId"),
                            "groupId": gid,
                            "img": _normalize_img_url(image_path),  # ✅ URL completa
                        })

    # 4) Filtros de grupos
    col_q, col_status = st.columns([3, 1])
    with col_q:
        qg = st.text_input("🔎 Buscar grupo", placeholder="Ex.: Bebidas, Adicionais…")
    with col_status:
        fstatus = st.selectbox("Status do grupo", ["Todos", "Ativos", "Pausados"])

    groups_list = list(groups_map.values())
    if qg:
        qgl = qg.strip().lower()
        groups_list = [g for g in groups_list if qgl in (g["name"] or "").lower()]
    if fstatus == "Ativos":
        groups_list = [g for g in groups_list if (g["status"] or "AVAILABLE").upper() == "AVAILABLE"]
    elif fstatus == "Pausados":
        groups_list = [g for g in groups_list if (g["status"] or "").upper() in ("UNAVAILABLE", "PAUSED")]

    if not groups_list:
        st.info("Nenhum grupo encontrado com os filtros informados.")
        st.stop()
    
    # Índice de imagens de produtos (para as Options)
    if "_product_img_index" not in st.session_state:
        try:
            st.session_state["_product_img_index"] = build_product_img_index_v1(MERCHANT_ID, CATALOG_ID)
        except Exception:
            st.session_state["_product_img_index"] = {}

    # 5) Render de grupos (cards) + ações (mesmo padrão dos Itens)
    # ───────────────────────────────────────────────────────────────────────────────
    # Constrói (uma vez) um índice de "grupos -> item (productId)" para
    # conseguirmos listar as opções de cada grupo corretamente.
    # Cache em sessão para não refazer a cada rerun.
    # ───────────────────────────────────────────────────────────────────────────────
    
    # ───────────────────────────────────────────────────────────────────────────────
    # Constrói (uma vez) um índice de "grupos -> item (productId)" para
    # conseguirmos listar as opções de cada grupo corretamente.
    # Cache em sessão para não refazer a cada rerun.
    # ───────────────────────────────────────────────────────────────────────────────

    if "_groups_to_draw" not in st.session_state:
        _groups_to_draw = []
        _seen = set()  # evita duplicar o mesmo grupo atrelado ao mesmo item
        # 👇 NOVO: índice productId -> imagePath (de onde pegaremos as fotos das opções)
        _product_img_index: dict[str, str] = {}

        try:
            _cats = list_categories(MERCHANT_ID, CATALOG_ID) or []
        except Exception:
            _cats = []

        for _cat in _cats:
            _category_id = _cat.get("id") or _cat.get("categoryId")
            try:
                _items = list_items_by_category(MERCHANT_ID, _category_id) or []
                if isinstance(_items, dict) and "items" in _items:
                    _items = _items["items"]
            except Exception:
                _items = []

            for _it in _items:
                if isinstance(_it, str):
                    _item_id = _it
                else:
                    _item_id = _it.get("id") or _it.get("itemId") or _it.get("productId")
                if not _item_id:
                    continue

                try:
                    _flat = get_item_flat(MERCHANT_ID, _item_id) or {}
                except Exception:
                    continue

                # 👇 CAPTURA imagens dos products do flat (onde o portal costuma salvar as fotos)
                for _p in (_flat.get("products") or []):
                    pid = _p.get("id")
                    if not pid:
                        continue
                    img = _p.get("imagePath") or (_p.get("assets") or {}).get("image")
                    if img and pid not in _product_img_index:
                        _product_img_index[pid] = str(img)

                _products = _flat.get("products") or []
                _first_product = _products[0] if _products else {}
                _item_name = _first_product.get("name") or _first_product.get("externalCode") or _item_id

                for _og in (_flat.get("optionGroups") or []):
                    _gid = _og.get("id")
                    if not _gid:
                        continue

                    _key = (_gid, _item_id)
                    if _key in _seen:
                        continue
                    _seen.add(_key)

                    img_from_prod = product_img_index.get(_item_id) if 'product_img_index' in locals() or 'product_img_index' in globals() else None
                    img_url = _normalize_img_url(img_from_prod)

                    _groups_to_draw.append({
                        "id": _gid,
                        "name": _og.get("name") or "Grupo",
                        "status": (_og.get("status") or "AVAILABLE").upper(),
                        "itemId": _item_id, # ESSENCIAL para buscar opções do grupo
                        "itemName": _item_name,     # só para UI
                        "optionsCount": len(_og.get("options") or []),
                        "img": img_url,

                    })

        st.session_state["_groups_to_draw"] = _groups_to_draw
        # 👇 salva o índice de imagens para uso na renderização das opções
        st.session_state["_product_img_index"] = _product_img_index

    groups_to_draw = st.session_state.get("_groups_to_draw") or []

    try:
        st.session_state["_product_img_index"] = build_product_img_index_v1(MERCHANT_ID, CATALOG_ID)
    except Exception:
        st.session_state["_product_img_index"] = {}

    # ───────────────────────────────────────────────────────────────────────────────
    # Também montamos (uma vez) um índice "grupo -> lista de opções"
    # Primeiro tentamos a rota v1 com include_options; se vier vazio caímos no fallback v2.
    # ───────────────────────────────────────────────────────────────────────────────
    if "_options_index" not in st.session_state:
        try:
            _groups_with_opts = list_option_groups(MERCHANT_ID, include_options=True)
            _idx = {}
            for _gg in _groups_with_opts:
                _gid = _gg.get("id")
                _lst = []
                for _opt in (_gg.get("options") or []):
                    _price_val = (_opt.get("price") or {}).get("value", 0.0)
                    _status_val = (_opt.get("status") or "AVAILABLE").upper()
                    _lst.append({
                        "id": _opt.get("id"),
                        "productId": _opt.get("productId"),
                        "groupId": _gid,
                        "name": _opt.get("name") or _opt.get("label") or "",
                        "description": _opt.get("description") or "",
                        "price": float(_price_val or 0.0),
                        "status": _status_val,
                        "img": _normalize_img_url(
                            (_opt.get("imagePath") or "") 
                            or st.session_state.get("_product_img_index", {}).get(_opt.get("productId") or "", "")
                        ),
                        })


                _idx[_gid] = _lst
            # se veio tudo vazio, forçamos fallback
            if not any(_idx.values()):
                raise RuntimeError("includeOptions vazio")
            st.session_state["_options_index"] = _idx
        except Exception:
            try:
                st.session_state["_options_index"] = build_options_index_from_items_v2(MERCHANT_ID)
            except Exception:
                st.session_state["_options_index"] = {}

    _options_index = st.session_state.get("_options_index") or {}

    # Índice de imagens de produtos (para as Options)
    if "_product_img_index" not in st.session_state:
        try:
            st.session_state["_product_img_index"] = build_product_img_index_v1(MERCHANT_ID, CATALOG_ID)
        except Exception:
            st.session_state["_product_img_index"] = {}

    # ───────────────────────────────────────────────────────────────────────────────
    # Agora renderizamos os cards dos grupos.
    # Importante:
    # - NÃO iteramos todos os grupos de novo dentro do card.
    # - Cada key usa um sufixo único (card_key) baseado em i e cidx.
    # - Chamadas aos helpers com a assinatura correta.
    # ───────────────────────────────────────────────────────────────────────────────
    cols_per_row = 2
    for i in range(0, len(groups_list), cols_per_row):
        row = groups_list[i:i+cols_per_row]
        cols = st.columns(len(row))

        for cidx, g_card in enumerate(row):
            with cols[cidx]:
                card_key = f"{g_card['id']}_{i}_{cidx}"
                paused_group = (g_card["status"] or "").upper() in ("UNAVAILABLE", "PAUSED")

                st.markdown(
                    f"<div class='q3-card-name'>{g_card['name']}</div>"
                    f"<div class='q3-card-desc' style='opacity:.8'>ID: {g_card['id']} • {'PAUSADO' if paused_group else 'ATIVO'}</div>",
                    unsafe_allow_html=True
                )

                ca1, ca2, ca3, ca4 = st.columns(4)

                # ── Pausar/Ativar grupo
                with ca1:
                    lbl = "✅" if paused_group else "⏸️"
                    if st.button(lbl, key=f"group_toggle_{card_key}", use_container_width=True):
                        new_status = "AVAILABLE" if paused_group else "UNAVAILABLE"
                        ok, msg = patch_option_group_status(
                            st.session_state.token,
                            MERCHANT_ID,
                            g_card["id"],
                            new_status,
                            st.session_state.get("catalog_context", "DEFAULT"),
                        )
                        if ok:
                            st.success("Status do grupo atualizado")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(msg)

                # ── Editar nome do grupo
                with ca2:
                    with st.popover("✏️", use_container_width=True):
                        new_name = st.text_input("Nome do grupo", value=g_card["name"], key=f"grp_name_{card_key}")
                        if st.button("Salvar", key=f"grp_save_{card_key}", use_container_width=True):
                            ok, msg = update_option_group(MERCHANT_ID, g_card["id"], {"name": new_name})
                            if ok:
                                st.success("Grupo atualizado")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(msg)

                # ── Outras ações (placeholder)
                with ca3:
                    with st.popover("📋", use_container_width=True):
                        st.caption("Ações do grupo (opcional)")

                # ── Excluir grupo (se você tiver helper específico)
                with ca4:
                    with st.popover("🗑️", use_container_width=True):
                        st.warning("Excluir grupo?")
                        if st.button("Confirmar", key=f"grp_del_conf_{card_key}", type="primary", use_container_width=True):
                            ok, msg = delete_option_group(MERCHANT_ID, g_card["id"])
                            if ok:
                                st.success("Grupo excluído")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(msg)

                st.divider()

                # ── Opções do grupo (expander)
                with st.expander("Ver complementos deste grupo", expanded=False):
                    group_id = g_card.get("id")
                    if not group_id:
                        st.info("Grupo sem ID.")
                    else:
                        # 1) Tenta índice cacheado (rápido)
                        opts = list(_options_index.get(group_id) or [])

                        # 2) Se não houver no índice, usa a fonte oficial v1
                        if not opts:
                            try:
                                # NOVO (usa a versão que já trata preço por contexto + imagePath)
                                opts = fetch_options_for_group(MERCHANT_ID, g_card["itemId"], group_id) or []
                            except Exception:
                                opts = []

                        # Enriquecer cada option com imagem
                        product_img_index = st.session_state.get("_product_img_index", {})
                        ctx = (st.session_state.get("catalog_context") or "DEFAULT").upper()

                        def _attach_img_and_price(o: dict) -> dict:
                            """
                            Enriquece uma option com:
                            - imagePath correta (com fallback para productId)
                            - price ajustado por contexto
                            - status ajustado por contexto
                            """
                            product_img_index = st.session_state.get("_product_img_index", {})
                            ctx = (st.session_state.get("catalog_context") or "DEFAULT").upper() if "st" in globals() else "DEFAULT"

                            # 1️⃣ IMAGEM: prioridade option.imagePath > productId no índice
                            img_path = o.get("imagePath") or ""
                            
                            # Se não tem imagePath na option, busca do produto
                            if not img_path:
                                product_id = o.get("productId")
                                if product_id and product_id in product_img_index:
                                    img_path = product_img_index[product_id]
                            
                            if img_path:
                                o["img"] = _normalize_img_url(img_path)
                            else:
                                o["img"] = None
                            
                            # 2️⃣ PREÇO: considera contextModifiers
                            p = o.get("price")
                            if isinstance(p, dict):
                                price_val = p.get("value")
                            elif isinstance(p, (int, float)):
                                price_val = float(p)
                            elif isinstance(p, str) and p.strip() != "":
                                try:
                                    price_val = float(p)
                                except Exception:
                                    price_val = None
                            else:
                                price_val = None

                            if isinstance(price_val, (int, float)):
                                price_val = float(price_val)
                            else:
                                price_val = 0.0
                            
                            # Sobrescreve por contexto se existir
                            for cm in (o.get("contextModifiers") or []):
                                if (str(cm.get("catalogContext") or "")).upper() == ctx:
                                    raw = cm.get("price")
                                    if isinstance(raw, dict):
                                        cm_price = raw.get("value")
                                    elif isinstance(raw, (int, float)):
                                        cm_price = float(raw)
                                    elif isinstance(raw, str) and raw.strip() != "":
                                        try:
                                            cm_price = float(raw)
                                        except Exception:
                                            cm_price = None
                                    else:
                                        cm_price = None

                                    if cm_price is not None:
                                        price_val = float(cm_price)

                                    stt = cm.get("status")
                                    if stt:
                                        o["status"] = (stt or o.get("status") or "AVAILABLE").upper()
                                    break
                            
                            o["price"] = float(price_val) if price_val is not None else 0.0
                            try:
                                o["price_str"] = f"R$ {o['price']:.2f}".replace(".", ",")
                            except Exception:
                                o["price_str"] = "R$ 0,00"
                            
                            # 3️⃣ STATUS: considera contextModifiers
                            status_val = (o.get("status") or "AVAILABLE").upper()
                            
                            for cm in (o.get("contextModifiers") or []):
                                if (cm.get("catalogContext") or "").upper() == ctx:
                                    cm_status = cm.get("status")
                                    if cm_status:
                                        status_val = cm_status.upper()
                                    break
                            
                            o["status"] = status_val
                            
                            return o

                        product_img_index = st.session_state.get("_product_img_index", {})

                        opts = [_attach_img_and_price(o) for o in (opts or [])]
 
                        if not opts:
                            st.caption("Grupo sem complementos.")
                        else:
                            col_f1, col_f2 = st.columns([2, 1])
                            with col_f1:
                                qopt = st.text_input("Filtrar complementos", key=f"qopt_{group_id}", placeholder="Nome…")
                            with col_f2:
                                fopt_status = st.selectbox("Status", ["Todos", "Ativos", "Pausados"], key=f"fopt_{group_id}")

                            fopts = opts
                            if qopt:
                                ql = qopt.strip().lower()
                                fopts = [o for o in fopts if ql in (o.get("name") or "").lower()]
                            if fopt_status == "Ativos":
                                fopts = [o for o in fopts if (o.get("status") or "AVAILABLE").upper() == "AVAILABLE"]
                            elif fopt_status == "Pausados":
                                fopts = [o for o in fopts if (o.get("status") or "").upper() in ("UNAVAILABLE", "PAUSED")]

                            st.caption(f"{len(fopts)} complemento(s)")
                            st.divider()

                            product_img_index = st.session_state.get("_product_img_index", {})

                            cols_per_row_opts = 4
                            for _i in range(0, len(fopts), cols_per_row_opts):
                                _cols = st.columns(cols_per_row_opts)
                                for _j, opt in enumerate(fopts[_i:_i+cols_per_row_opts]):
                                    with _cols[_j]:
                                        paused_opt = (opt.get("status") or "").upper() in ("UNAVAILABLE", "PAUSED")

                                        # 1) tentar a própria imagem da opção
                                        _img_path = opt.get("imagePath") or ""

                                        # 2) se não tiver, tentar a imagem do produto-base (preenchida no passo 2 da minha msg anterior)
                                        if not _img_path:
                                            _pid = opt.get("productId")
                                            if _pid:
                                                _prod_idx = st.session_state.get("_product_img_index", {})  # {productId -> imagePath}
                                                _img_path = _prod_idx.get(_pid, "")

                                        # 3) converter path -> URL pública
                                        _img_url = _normalize_img_url(_img_path)

                                        # --- 3.C: renderizar ---
                                        if _img_url:
                                            st.markdown(
                                                f"""
                                                <div class='q3-card-img' style='position:relative;'>
                                                <img src='{_img_url}' alt='{opt.get("name","Complemento")}'/>
                                                <div class='q3-status-badge {"q3-badge-paused" if paused_opt else "q3-badge-active"}'>
                                                    {"PAUSADO" if paused_opt else "ATIVO"}
                                                </div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True
                                            )
                                        else:
                                            # seu placeholder de sempre
                                            st.markdown(
                                                f"""
                                                <div class='q3-img-placeholder' style='position:relative;'>
                                                ➕
                                                <div class='q3-status-badge {"q3-badge-paused" if paused_opt else "q3-badge-active"}'
                                                    style='position:absolute;top:12px;right:12px;'>
                                                    {"PAUSADO" if paused_opt else "ATIVO"}
                                                </div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True
                                            )

                                        # Trocar foto
                                        upload_counter_key_opt = f"_upload_counter_opt_{opt['id']}"
                                        if upload_counter_key_opt not in st.session_state:
                                            st.session_state[upload_counter_key_opt] = 0
                                        upload_key_opt = f"img_opt_{opt['id']}_{st.session_state[upload_counter_key_opt]}"

                                        with st.popover("📷 Trocar foto", use_container_width=True):
                                            up = st.file_uploader("Enviar imagem", type=["jpg", "jpeg", "png"], key=upload_key_opt)
                                            if up:
                                                if st.session_state.get(f"_uploading_opt_{opt['id']}", False):
                                                    st.warning("Upload em andamento..."); st.stop()
                                                st.session_state[f"_uploading_opt_{opt['id']}"] = True
                                                with st.spinner("Enviando..."):
                                                    ok, res = upload_complement_image_v1(MERCHANT_ID, up.read(), up.name)
                                                st.session_state[f"_uploading_opt_{opt['id']}"] = False
                                                if ok:
                                                    st.success("Imagem enviada ao iFood. Se necessário, associe o imagePath no cadastro da opção.")
                                                    st.cache_data.clear()
                                                    st.session_state[upload_counter_key_opt] += 1
                                                    st.rerun()
                                                else:
                                                    st.error(res)

                                        # Título/descrição
                                        st.markdown(f"<div class='q3-card-name'>{opt.get('name','Complemento')}</div>", unsafe_allow_html=True)
                                        _desc = opt.get("description") or ""
                                        if _desc:
                                            st.markdown(f"<div class='q3-card-desc'>{_desc}</div>", unsafe_allow_html=True)
                                        else:
                                            st.markdown("<div class='q3-card-desc' style='opacity:0.5;'>Sem descrição</div>", unsafe_allow_html=True)

                                        # Preço
                                        st.markdown(f"...{float(opt.get('price') or 0):.2f}...", unsafe_allow_html=True)

                                        # Ações
                                        oc1, oc2, oc3, oc4 = st.columns(4)

                                        # Pausar/Ativar
                                        with oc1:
                                            _lbl = "✅" if paused_opt else "⏸️"
                                            if st.button(_lbl, key=f"opt_toggle_{opt['id']}", use_container_width=True):
                                                option_uuid = (opt.get("id") or opt.get("optionId") or "").strip()
                                                if not _is_uuid(option_uuid):
                                                    st.error(f"ID do complemento inválido para PATCH: {option_uuid!r}")
                                                else:
                                                    _new_status = "AVAILABLE" if paused_opt else "UNAVAILABLE"
                                                    ok, msg = patch_option_status(
                                                        st.session_state.token,
                                                        MERCHANT_ID,
                                                        option_uuid,
                                                        _new_status,
                                                        st.session_state.get("catalog_context", "DEFAULT"),
                                                    )
                                                    if ok:
                                                        st.success("Status atualizado"); st.cache_data.clear(); st.rerun()
                                                    else:
                                                        st.error(msg)

                                        # Alterar preço
                                        with oc2:
                                            with st.popover("💰", use_container_width=True):
                                                price_str = st.text_input("Novo preço", value=f"{float(opt.get('price') or 0):.2f}", key=f"p_{opt['id']}")
                                                if st.button("Salvar", key=f"save_price_{opt['id']}", use_container_width=True):
                                                    try:
                                                        new_price = float(price_str.replace(",", "."))
                                                        ok, msg = update_complement_price(MERCHANT_ID, opt.get("productId"), opt["id"], new_price)
                                                        if ok:
                                                            st.success(msg); st.cache_data.clear(); st.rerun()
                                                        else:
                                                            st.error(msg)
                                                    except ValueError:
                                                        st.error("Preço inválido")

                                        # Editar nome/descrição
                                        with oc3:
                                            with st.popover("✏️", use_container_width=True):
                                                nn = st.text_input("Nome", value=opt.get("name",""), key=f"nn_{opt['id']}")
                                                nd = st.text_area("Descrição", value=_desc, key=f"nd_{opt['id']}")
                                                if st.button("Salvar", key=f"save_desc_{opt['id']}", use_container_width=True):
                                                    ok, msg = update_complement_details(MERCHANT_ID, opt.get("productId"), opt["id"], nn, nd)
                                                    if ok:
                                                        st.success(msg); st.cache_data.clear(); st.rerun()
                                                    else:
                                                        st.error(msg)

                                        # Duplicar / Excluir
                                        with oc4:
                                            with st.popover("⋯", use_container_width=True):
                                                st.caption("Duplicar / Excluir")
                                                c1, c2 = st.columns(2)
                                                with c1:
                                                    if st.button("📋 Duplicar", key=f"dup_{opt['id']}", use_container_width=True):
                                                        ok, msg = duplicate_complement(MERCHANT_ID, opt.get("productId"), opt["groupId"], opt["id"])
                                                        if ok:
                                                            st.success(msg); st.cache_data.clear(); st.rerun()
                                                        else:
                                                            st.error(msg)
                                                with c2:
                                                    if st.button("🗑️ Excluir", key=f"del_{opt['id']}", use_container_width=True):
                                                        ok, msg = delete_complement(MERCHANT_ID, opt.get("productId"), opt["groupId"], opt["id"])
                                                        if ok:
                                                            st.success(msg); st.cache_data.clear(); st.rerun()
                                                        else:
                                                            st.error(msg)

# ============================ Q3 FOOTER (fix) ============================
# Textos das políticas — definidos ANTES da função (evita NameError em defaults)
PRIVACY_MD = """
## 🔒 Política de Privacidade – Q3 Automatiza

A **Q3 Consultoria** valoriza a segurança e privacidade de seus usuários.  
Esta política descreve como tratamos os dados no aplicativo **Q3 Automatiza**.

### Coleta de Dados
- São coletados apenas dados essenciais para autenticação e operação do app, como **credenciais de acesso (token OAuth iFood)**, **ID da loja (merchantId)** e informações do catálogo (itens, complementos, avaliações).
- Nenhum dado sensível de clientes finais do iFood é armazenado permanentemente pela Q3 Consultoria.

### Uso dos Dados
- Os dados coletados são utilizados exclusivamente para possibilitar as funções do app: gerenciamento de catálogo, homologação de preços e respostas de avaliações.
- A Q3 Consultoria não compartilha dados com terceiros, salvo quando necessário para o funcionamento das APIs do iFood.

### Armazenamento e Segurança
- Os dados são processados de forma temporária e segura durante a sessão de uso.
- Tokens e informações de login expiram automaticamente conforme regras do iFood.
- Não mantemos banco de dados com informações pessoais de clientes finais.

### Direitos do Usuário
- O usuário pode solicitar a exclusão imediata de seus dados de acesso (caso armazenados em cache temporário) entrando em contato diretamente com a Q3 Consultoria.

### Contato
- **Razão Social**: 35.457.551 Marcus Vinicius Silva da Costa  
- **CNPJ**: 35.457.551/0001-63  
- **Site**: q3consultoria.online  
- **E-mail**: contato@q3consultoria.online
"""

REVIEWS_MD = """
## 📝 Política de Avaliação – iFood

A avaliação é um recurso disponibilizado pelo iFood para coletar a opinião de usuários sobre os pedidos feitos nas lojas parceiras, garantindo transparência, justiça e confiabilidade.  
A nota exibida para usuários e parceiros reflete a média ponderada de todas as avaliações válidas publicadas nos últimos **90 dias corridos**.  
Os usuários também podem visualizar individualmente o conteúdo das avaliações publicadas no app iFood.

---

### Regras, papéis e responsabilidades
- O usuário terá até **7 dias corridos** após a compra para realizar uma avaliação.  
- O iFood analisa todas as avaliações e descarta aquelas que não atendem às diretrizes.  
- Somente comentários válidos são encaminhados para a loja parceira.  
- A loja tem até **5 dias corridos** para responder à avaliação do usuário.  
- O usuário tem até **5 dias corridos** para revisar sua nota (quando aplicável).  
- Avaliações com notas **1 ou 2** exigem comentários obrigatórios.  
- Notas **3, 4 e 5** aceitam comentários opcionais.  
- Avaliações com nota **5** e comentários válidos são publicadas imediatamente após resposta da loja.  
- Em notas **1 a 4**, caso a loja responda, o usuário será notificado e poderá rever sua avaliação.  
- Usuários podem definir avaliações como **públicas** (contam para a nota média) ou **privadas** (não exibidas e sem impacto na nota).  
- Somente o **primeiro nome** do usuário é exibido nas avaliações.

---

### Para usuários
- Prazo de **7 dias corridos** após o pedido para avaliar.  
- Comentários devem seguir esta política e os Termos de Uso da plataforma iFood.  

**Permitido nas avaliações:**  
- Opiniões pessoais autênticas baseadas em experiência real.  
- Comentários sobre qualidade, prazo, custo-benefício e entrega.  

**Não permitido nas avaliações:**  
- Avaliações falsas ou de pessoas com vínculo comercial/familiar com a loja.  
- Inserir conteúdo político, religioso, ético ou social alheio ao pedido.  
- Comentários ofensivos, ameaçadores ou desrespeitosos.  
- Linguagem vulgar ou intimidação contra loja, entregadores ou iFood.  

Avaliações fora dos padrões podem ser removidas sem aviso prévio, e o usuário pode sofrer **penalidades** (suspensão/exclusão da conta ou medidas judiciais).

---

### Para o iFood
- As avaliações refletem **opiniões dos usuários** e não a posição oficial da plataforma.  
- O iFood monitora, descarta avaliações inadequadas e não colabora com terceiros para manipular notas.  
- Ofertas para manipulação de avaliações devem ser reportadas via canais oficiais.

---

### Para lojas parceiras
- Avaliações são retorno dos clientes sobre sua experiência.  
- Avaliações negativas por **gosto pessoal** não são removidas.  
- A nota não altera a ordem de exibição das lojas no app, apenas a percepção da reputação.  
- A loja pode sempre responder avaliações, desde que respeite as regras do iFood.

**Não permitido nas respostas:**  
- Conteúdo comercial ou incentivo a pedidos fora do iFood.  
- Comentários políticos, religiosos, éticos ou sociais.  
- Ameaças, intimidação ou ofensas ao usuário.  
- Divulgação de dados pessoais do usuário.  
- Restrições às contribuições dos usuários.  
- Respostas direcionadas à equipe do iFood ou críticas às políticas da plataforma.  

Respostas que violarem regras podem sofrer moderação ou até resultar em **rescisão de contrato**.

---

📅 **Data da versão: 25/04/2025**
"""

RULES_MD = """
## 📜 Política de Uso – Q3 Automatiza

O aplicativo **Q3 Automatiza** é uma solução desenvolvida pela **Q3 Consultoria**  
(CNPJ: 35.457.551/0001-63 – Razão Social: Marcus Vinicius Silva da Costa)  
para auxiliar parceiros na gestão de catálogos, avaliações e métricas da plataforma iFood.

### Regras de Uso
1. O acesso ao sistema é exclusivo para empresas ou consultores autorizados, mediante login.
2. O usuário é responsável pelas informações inseridas e pelas ações executadas dentro do app (ex.: pausar/ativar itens, homologar preços, responder avaliações).
3. É proibido utilizar o aplicativo para fins ilícitos, fraudes ou qualquer atividade que prejudique terceiros ou a integridade da plataforma iFood.
4. A Q3 Consultoria poderá suspender ou bloquear o acesso em caso de mau uso, tentativa de invasão ou descumprimento destas regras.
5. O uso do app implica na aceitação integral desta Política de Uso e de nossa Política de Privacidade.
"""

def _md_to_html(md: str) -> str:
    # Conversão simples: preserva quebras de linha e **negrito** básicos
    text = html.escape(md).replace("\n", "<br>")
    if "**" in text:
        text = text.replace("**", "<b>", 1).replace("**", "</b>", 1)
        while "**" in text:
            text = text.replace("**", "<b>", 1).replace("**", "</b>", 1)
    return text

def render_q3_footer_at_page_end(app_version: str = "1.0.0",
                                 privacy_md: str | None = None,
                                 reviews_md: str | None = None,
                                 rules_md: str | None = None):
    """
    Rodapé ESTÁTICO (aparece só ao final da página) com três expanders.
    """
    now_str = datetime.now().strftime('%d/%m %H:%M')
    privacy_html = _md_to_html(privacy_md or PRIVACY_MD)
    reviews_html = _md_to_html(reviews_md or REVIEWS_MD)
    rules_html   = _md_to_html(rules_md   or RULES_MD)

    st.markdown("""
    <style>
      [data-testid="stApp"]{ height:100vh; }
      [data-testid="stAppViewContainer"] > .main{ min-height:100vh; display:flex; flex-direction:column; }
      .block-container{ flex:1 0 auto; display:flex; flex-direction:column; }

      .q3-footer-static{
        margin-top:auto;
        color:#fff;
        background:linear-gradient(90deg,#FF4BC6,#8B00FF);
        box-shadow:0 -6px 24px rgba(0,0,0,.25);
      }
      .q3-footer-static .inner{
        max-width:1200px; margin:0 auto;
        display:flex; align-items:center; justify-content:space-between;
        gap:12px; padding:10px 16px; font-size:14px;
      }
      .q3-policies{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
      .q3-policies details{
        background: rgba(255,255,255,.12);
        border-radius:10px; padding:6px 10px;
      }
      .q3-policies summary{ list-style:none; cursor:pointer; user-select:none; }
      .q3-policies summary::-webkit-details-marker{ display:none; }
      .q3-policies details[open] summary{ opacity:.95; }
      .q3-panel{
        margin-top:8px; padding:10px; border-radius:10px;
        background: rgba(0,0,0,.25);
        max-height:220px; overflow:auto;
      }
      .q3-panel b{ color:#fff; }
      @media (max-width:720px){
        .q3-footer-static .inner{ flex-direction:column; gap:6px; text-align:center; }
        .q3-policies{ justify-content:center; }
      }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="q3-footer-static">
      <div class="inner">
        <div class="left">
          <div class="q3-policies">
            <details>
              <summary>Políticas de Privacidade</summary>
              <div class="q3-panel">{privacy_html}</div>
            </details>
            <details>
              <summary>Política de Avaliações iFood</summary>
              <div class="q3-panel">{reviews_html}</div>
            </details>
            <details>
              <summary>Regras de uso do APP</summary>
              <div class="q3-panel">{rules_html}</div>
            </details>
          </div>
        </div>
        <div class="center">Q3 Automatiza • Operações</div>
        <div class="center">App Produzido pela 4K Enterprise</div>
        <div class="right" style="opacity:.9;">v{app_version} • {now_str}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ============================ PONTO DE ENTRADA PRINCIPAL ============================

# 1️⃣ Verificação de login
if not _is_logged():
    render_login()
    st.stop()

# 2️⃣ Se chegou aqui, está logado. Agora garante conexão com API.
if not st.session_state.get("api_connected"):
    with st.spinner("🔐 Conectando na API do iFood..."):
        try:
            success = ensure_api_connection()
            
            if not success:
                st.error("❌ Falha ao conectar no iFood. Verifique o arquivo `.env`")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔄 Tentar Novamente", key="retry_conn"):
                        st.rerun()
                with col2:
                    if st.button("🚪 Fazer Logout", key="logout_conn_fail"):
                        force_logout_and_clear_all()
                        st.rerun()
                
                st.stop()
                
        except Exception as e:
            st.error(f"❌ Erro inesperado: {e}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Tentar Novamente", key="retry_error"):
                    st.rerun()
            with col2:
                if st.button("🚪 Fazer Logout", key="logout_error"):
                    force_logout_and_clear_all()
                    st.rerun()
            
            st.stop()

# 3️⃣ Se chegou aqui, está autenticado E conectado na API
st.sidebar.success("✅ Sistema pronto!")

# 4️⃣ TOP BAR
col_connected, col_favs, col_reload, col_logout = st.columns([5, 2, 2, 1])

with col_connected:
    if _token_ok():
        client_id_short = st.session_state.get("client_id", "")[:20] + "..."
        st.markdown(
            f'<div class="q3-connected">✅ Conectado! (App: {client_id_short})</div>', 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="q3-connected" style="background:#7a1c1c">❌ Desconectado</div>', 
            unsafe_allow_html=True
        )

with col_favs:
    fav_count = len(st.session_state.get("favorites") or [])
    st.caption(f"⭐ Favoritas: {fav_count}")

with col_reload:
    if st.button("🔄 Recarregar dados", key="btn_reload_main"):
        st.cache_data.clear()
        st.rerun()

with col_logout:
    if st.button("🚪 Sair", key="btn_logout_main"):
        force_logout_and_clear_all()
        st.rerun()

# 5️⃣ Agora carrega lojas
st.session_state.setdefault("catalog_id", None)

# ===== CHAMADA (FINAL do arquivo) =====
render_q3_footer_at_page_end(
    app_version="1.0.0",
    privacy_md=PRIVACY_MD,
    reviews_md=REVIEWS_MD,
    rules_md=RULES_MD
)
