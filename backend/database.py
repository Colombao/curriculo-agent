import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.config import Config
from backend.models import ResumeProfile, JobOpportunity


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data_json TEXT NOT NULL,
            raw_text TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company_or_client TEXT NOT NULL,
            channel TEXT NOT NULL,
            platform TEXT NOT NULL,
            location_or_modality TEXT NOT NULL,
            compensation TEXT NOT NULL,
            description TEXT NOT NULL,
            apply_url TEXT DEFAULT '',
            recruiter_email TEXT DEFAULT '',
            estimated_match INTEGER DEFAULT 80,
            tags_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            job_title TEXT NOT NULL,
            company_or_client TEXT NOT NULL,
            channel TEXT NOT NULL,
            platform TEXT NOT NULL,
            apply_url TEXT DEFAULT '',
            recipient_email TEXT DEFAULT '',
            email_subject TEXT NOT NULL,
            cover_letter_or_proposal TEXT NOT NULL,
            match_score INTEGER NOT NULL,
            tailored_json TEXT NOT NULL,
            pdf_filename TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_approval',
            delivery_log TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    # Seed initial profile if empty so the dashboard works out-of-the-box
    cur.execute("SELECT COUNT(*) as cnt FROM profile")
    if cur.fetchone()["cnt"] == 0:
        default_profile = ResumeProfile(
            full_name="João Vitor",
            headline="Desenvolvedor Full-Stack & Especialista em Automação / IA",
            email="joao.vitor@exemplo.com",
            phone="(11) 99999-0000",
            location="Brasil (Disponível para Remoto / Híbrido)",
            linkedin_url="https://linkedin.com/in/joao-vitor",
            github_or_portfolio_url="https://github.com/joaovitor",
            summary=(
                "Profissional de tecnologia focado em desenvolvimento de aplicações web modernas, "
                "APIs em Python/Node.js, automação de processos (RPA/Playwright) e integração de "
                "agentes de Inteligência Artificial (LLMs). Experiência na entrega de sistemas "
                "escaláveis, redução de tarefas manuais e criação de soluções sob medida."
            ),
            hard_skills=[
                "Python",
                "FastAPI",
                "JavaScript / TypeScript",
                "React",
                "HTML5 / CSS3",
                "SQL / PostgreSQL / SQLite",
                "Automação Web (Playwright / Selenium)",
                "APIs REST & Webhooks",
                "Integração de IA / Gemini API",
                "Git & Docker",
            ],
            soft_skills=[
                "Resolução de Problemas",
                "Comunicação Clara com Clientes",
                "Autonomia em Trabalho Remoto",
                "Foco em Resultados e Prazos",
            ],
            languages=["Português (Nativo)", "Inglês (Intermediário/Avançado para leitura técnica)"],
            certifications=[
                "Desenvolvimento Web Moderno & APIs REST",
                "Engenharia de Prompts e Agentes com IA Generativa",
            ],
            experiences=[
                ExperienceItem_dict := {
                    "role": "Desenvolvedor Full-Stack & Automação (Autônomo / Projetos)",
                    "company": "Projetos & Consultoria em Tecnologia",
                    "period": "2024 - Atual",
                    "location": "Remoto",
                    "highlights": [
                        "Desenvolveu sistemas web completos e dashboards interativos utilizando Python (FastAPI) e JavaScript moderno.",
                        "Criou robôs de automação e integrações via APIs que reduziram em até 70% o tempo gasto em processos operacionais repetitivos.",
                        "Implementou agentes inteligentes com LLMs para leitura de documentos PDF, triagem de dados e geração automatizada de relatórios.",
                    ],
                },
                {
                    "role": "Desenvolvedor Back-End / Suporte Técnico de Sistemas",
                    "company": "Tech Solutions Brasil",
                    "period": "2022 - 2024",
                    "location": "Brasil",
                    "highlights": [
                        "Atuou na manutenção evolutiva de microsserviços e bancos de dados relacionais (PostgreSQL e SQLite).",
                        "Desenvolveu scripts de extração, transformação e validação de dados para relatórios gerenciais.",
                        "Colaborou com equipes multidisciplinares aplicando metodologias ágeis (Scrum/Kanban).",
                    ],
                },
            ],
            education=[
                {
                    "degree": "Graduação em Análise e Desenvolvimento de Sistemas / Ciência da Computação",
                    "institution": "Instituição de Ensino Superior",
                    "period": "Em andamento / Concluído",
                }
            ],
            projects=[
                {
                    "name": "Agente Inteligente de Currículos e Automação de Vagas",
                    "description": "Plataforma web que analisa currículos em PDF com IA, adapta para sistemas ATS e automatiza candidaturas e propostas freelance.",
                    "technologies": ["Python", "FastAPI", "Gemini API", "Playwright", "HTML5/CSS3"],
                    "link": "https://github.com/joaovitor/curriculo-agent",
                }
            ],
            hourly_rate_brl="R$ 85/h",
            preferred_roles=[
                "Desenvolvedor Python",
                "Desenvolvedor Full-Stack",
                "Especialista em Automação e IA",
                "Freelancer Web & Bots",
            ],
        )
        cur.execute(
            "INSERT INTO profile (id, data_json, raw_text, updated_at) VALUES (1, ?, ?, ?)",
            (
                default_profile.model_dump_json(),
                default_profile.summary,
                datetime.now().isoformat(),
            ),
        )

    conn.commit()
    conn.close()


def get_profile() -> ResumeProfile:
    conn = get_connection()
    row = conn.execute("SELECT data_json FROM profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return ResumeProfile()
    return ResumeProfile.model_validate_json(row["data_json"])


def save_profile(profile: ResumeProfile, raw_text: str = "") -> ResumeProfile:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO profile (id, data_json, raw_text, updated_at)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            data_json = excluded.data_json,
            raw_text = CASE WHEN excluded.raw_text != '' THEN excluded.raw_text ELSE profile.raw_text END,
            updated_at = excluded.updated_at
        """,
        (profile.model_dump_json(), raw_text, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return profile


def save_jobs(opportunities: List[JobOpportunity], clear_previous: bool = False) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    if clear_previous:
        cur.execute("DELETE FROM jobs")

    saved: List[Dict[str, Any]] = []
    now = datetime.now().isoformat()
    for job in opportunities:
        cur.execute(
            """
            INSERT INTO jobs (
                title, company_or_client, channel, platform,
                location_or_modality, compensation, description,
                apply_url, recruiter_email, estimated_match, tags_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.title,
                job.company_or_client,
                job.channel,
                job.platform,
                job.location_or_modality,
                job.compensation,
                job.description,
                job.apply_url,
                job.recruiter_email,
                job.estimated_match,
                json.dumps(job.tags, ensure_ascii=False),
                now,
            ),
        )
        job_id = cur.lastrowid
        job_dict = job.model_dump()
        job_dict["id"] = job_id
        saved.append(job_dict)

    conn.commit()
    conn.close()
    return saved


def list_jobs() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM jobs ORDER BY estimated_match DESC, id DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.pop("tags_json", "[]"))
        result.append(d)
    return result


def get_job(job_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["tags"] = json.loads(d.pop("tags_json", "[]"))
    return d


def create_application(
    job_id: Optional[int],
    job_title: str,
    company_or_client: str,
    channel: str,
    platform: str,
    apply_url: str,
    recipient_email: str,
    email_subject: str,
    cover_letter_or_proposal: str,
    match_score: int,
    tailored_data: Dict[str, Any],
    pdf_filename: str,
) -> Dict[str, Any]:
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute(
        """
        INSERT INTO applications (
            job_id, job_title, company_or_client, channel, platform,
            apply_url, recipient_email, email_subject, cover_letter_or_proposal,
            match_score, tailored_json, pdf_filename, status, delivery_log,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_approval', 'Aguardando aprovação de 1 clique', ?, ?)
        """,
        (
            job_id,
            job_title,
            company_or_client,
            channel,
            platform,
            apply_url,
            recipient_email,
            email_subject,
            cover_letter_or_proposal,
            match_score,
            json.dumps(tailored_data, ensure_ascii=False),
            pdf_filename,
            now,
            now,
        ),
    )
    app_id = cur.lastrowid
    conn.commit()
    conn.close()
    return get_application(app_id)


def get_application(app_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["tailored"] = json.loads(d.pop("tailored_json", "{}"))
    return d


def list_applications() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM applications ORDER BY id DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["tailored"] = json.loads(d.pop("tailored_json", "{}"))
        result.append(d)
    return result


def update_application_status(
    app_id: int,
    status: str,
    delivery_log: str,
    recipient_email: Optional[str] = None,
    apply_url: Optional[str] = None,
    email_subject: Optional[str] = None,
    cover_letter_or_proposal: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    current = get_application(app_id)
    if not current:
        conn.close()
        return None

    conn.execute(
        """
        UPDATE applications
        SET status = ?,
            delivery_log = ?,
            recipient_email = ?,
            apply_url = ?,
            email_subject = ?,
            cover_letter_or_proposal = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            delivery_log,
            recipient_email if recipient_email is not None else current["recipient_email"],
            apply_url if apply_url is not None else current["apply_url"],
            email_subject if email_subject is not None else current["email_subject"],
            cover_letter_or_proposal if cover_letter_or_proposal is not None else current["cover_letter_or_proposal"],
            datetime.now().isoformat(),
            app_id,
        ),
    )
    conn.commit()
    conn.close()
    return get_application(app_id)


def get_settings() -> Dict[str, Any]:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    db_map = {r["key"]: r["value"] for r in rows}
    return {
        "gemini_api_key": db_map.get("gemini_api_key", Config.GEMINI_API_KEY),
        "gemini_model": db_map.get("gemini_model", Config.DEFAULT_MODEL),
        "smtp_host": db_map.get("smtp_host", Config.SMTP_HOST),
        "smtp_port": int(db_map.get("smtp_port", str(Config.SMTP_PORT))),
        "smtp_user": db_map.get("smtp_user", Config.SMTP_USER),
        "smtp_password": db_map.get("smtp_password", Config.SMTP_PASSWORD),
    }


def save_settings(settings_data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    for k, v in settings_data.items():
        if v is not None:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, str(v)),
            )
    conn.commit()
    conn.close()
    return get_settings()
