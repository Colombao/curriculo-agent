import smtplib
import threading
import webbrowser
from email.message import EmailMessage
from pathlib import Path
from typing import Tuple
from backend.config import RESUMES_DIR
from backend.database import get_settings, get_profile


def send_application_email(
    recipient_email: str,
    subject: str,
    body: str,
    pdf_filename: str,
) -> Tuple[bool, str]:
    """
    Envia o currículo PDF adaptado em anexo junto com a carta de apresentação / proposta
    para o e-mail do recrutador/cliente via SMTP.
    """
    settings = get_settings()
    smtp_host = (settings.get("smtp_host") or "smtp.gmail.com").strip()
    smtp_port = int(settings.get("smtp_port") or 587)
    smtp_user = (settings.get("smtp_user") or "").strip()
    smtp_password = (settings.get("smtp_password") or "").strip()

    pdf_path: Path = RESUMES_DIR / pdf_filename
    if not pdf_path.exists():
        return False, f"Arquivo PDF adaptado não encontrado em {pdf_path.name}."

    if not recipient_email or "@" not in recipient_email:
        return False, "Informe um e-mail de destinatário válido para envio via SMTP."

    if not smtp_user or not smtp_password or smtp_password == "sua_senha_de_app_aqui":
        return (
            True,
            f"Simulação concluída com sucesso para {recipient_email} (Anexo: {pdf_filename}). "
            f"Configure seu SMTP em 'Configurações' para disparo real via servidor de e-mail.",
        )

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = recipient_email
        msg.set_content(body)

        pdf_bytes = pdf_path.read_bytes()
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=pdf_filename,
        )

        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        return True, f"E-mail enviado com sucesso para {recipient_email} com o anexo {pdf_filename}!"
    except Exception as exc:
        return False, f"Erro ao enviar e-mail via SMTP: {exc}"


def launch_browser_assisted_apply(
    apply_url: str,
    cover_letter_or_proposal: str,
    pdf_filename: str,
) -> Tuple[bool, str]:
    """
    Inicia a automação semi-automática via Playwright (em thread separada para não bloquear a API):
    Abre o navegador na vaga/projeto, preenche automaticamente campos detectados (nome, e-mail,
    telefone, proposta/carta e input de arquivo PDF) e aguarda o clique final do usuário.
    Caso o binário do Chromium Playwright não esteja instalado, abre no navegador padrão do sistema.
    """
    if not apply_url or not apply_url.startswith("http"):
        return False, "Esta oportunidade não possui uma URL externa cadastrada."

    profile = get_profile()
    pdf_path = str((RESUMES_DIR / pdf_filename).resolve())

    def _playwright_worker():
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)

                # Tenta preencher campos comuns de candidatura/proposta automaticamente
                selectors_map = [
                    ('input[name*="name" i], input[id*="name" i], input[autocomplete="name"]', profile.full_name),
                    ('input[type="email"], input[name*="email" i]', profile.email),
                    ('input[type="tel"], input[name*="phone" i], input[name*="telefone" i]', profile.phone),
                    ('textarea', cover_letter_or_proposal),
                ]
                for selector, val in selectors_map:
                    if not val:
                        continue
                    try:
                        loc = page.locator(selector).first
                        if loc.count() > 0 and loc.is_visible():
                            loc.fill(val)
                    except Exception:
                        pass

                # Tenta anexar o PDF adaptado em inputs file
                try:
                    file_input = page.locator('input[type="file"]').first
                    if file_input.count() > 0 and Path(pdf_path).exists():
                        file_input.set_input_files(pdf_path)
                except Exception:
                    pass

                # Injeta um banner informativo no topo da página para o usuário
                try:
                    page.evaluate(
                        """(info) => {
                            const banner = document.createElement('div');
                            banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:999999;background:#0f62fe;color:#fff;padding:10px 16px;font-family:sans-serif;font-size:14px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 10px rgba(0,0,0,0.3);';
                            banner.innerHTML = '<span><strong>Agente de Currículo:</strong> Dados e proposta preparados! O texto da proposta foi copiado e o PDF está em: ' + info.pdf + '</span>';
                            document.body.prepend(banner);
                            navigator.clipboard?.writeText(info.proposal).catch(() => {});
                        }""",
                        {"pdf": pdf_filename, "proposal": cover_letter_or_proposal},
                    )
                except Exception:
                    pass

                # Mantém a janela aberta até o usuário fechá-la
                page.wait_for_event("close", timeout=600000)
                browser.close()
        except Exception:
            # Fallback para o navegador padrão do Windows caso o Chromium Playwright não esteja baixado
            webbrowser.open(apply_url)

    threading.Thread(target=_playwright_worker, daemon=True).start()
    return (
        True,
        f"Automação de navegador iniciada para {apply_url}! "
        f"O agente abriu a vaga, preparou os campos e disponibilizou o currículo {pdf_filename}.",
    )
