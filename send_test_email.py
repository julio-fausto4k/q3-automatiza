import os, ssl, smtplib
from email.message import EmailMessage
from pathlib import Path

# Carrega .env em dev/local
try:
    from dotenv import load_dotenv
    if Path(".").joinpath(".env").exists():
        load_dotenv(".env")
except Exception:
    pass

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM") or SMTP_USER

# Enviar para você mesmo (pode trocar)
to = os.getenv("SMTP_USER")

msg = EmailMessage()
msg["Subject"] = "Teste Titan SMTP (Q3 Automatiza)"
msg["From"] = SMTP_FROM
msg["To"] = to
msg.set_content("Funcionou! Este é um e-mail de teste enviado via SMTP Titan (SSL/StartTLS).")

print("Conectando ao servidor SMTP...")

try:
    if SMTP_PORT == 465:
        # SSL direto (recomendado pela Titan para porta 465)
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=30) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
    else:
        # Ex.: 587 com STARTTLS
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

    print("✅ E-mail de teste enviado para:", to)

except smtplib.SMTPAuthenticationError as e:
    print("❌ Falha de autenticação SMTP. Verifique usuário/senha no .env.")
    print("Detalhe:", e)
except smtplib.SMTPConnectError as e:
    print("❌ Falha de conexão com o servidor SMTP.")
    print("Detalhe:", e)
except Exception as e:
    print("❌ Erro inesperado ao enviar e-mail:")
    print(type(e).__name__, e)