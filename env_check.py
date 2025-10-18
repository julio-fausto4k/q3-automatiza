import os
from pathlib import Path

# Carrega .env só em dev, se existir
try:
    from dotenv import load_dotenv
    if Path(".").joinpath(".env").exists():
        load_dotenv(".env")
except Exception:
    pass

vars_to_check = [
    "OPENAI_API_KEY",
    "Q3_USERS_JSON",
    "PUBLIC_APP_URL",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM",
]

print("=== Verificando variáveis de ambiente (sem mostrar valores) ===")
missing = []
for k in vars_to_check:
    print(f"{k}: {'OK' if os.getenv(k) else 'FALTA'}")
    if not os.getenv(k):
        missing.append(k)

print("\nResultado:")
if missing:
    print("Faltam variáveis:", ", ".join(missing))
    raise SystemExit(1)
else:
    print("Tudo certo! .env carregado localmente.")