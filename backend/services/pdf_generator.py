import re
import unicodedata
from datetime import datetime
from pathlib import Path
from fpdf import FPDF
from backend.config import RESUMES_DIR
from backend.models import ResumeProfile, TailoredResumeResult


def _clean_latin1(text: str) -> str:
    """Normaliza caracteres especiais para compatibilidade com fontes core do PDF (Helvetica ATS)."""
    if not text:
        return ""
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class ATSResumePDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 8, _clean_latin1(f"Currículo otimizado para sistemas ATS | Página {self.page_no()}"), align="C")


def generate_ats_pdf(
    profile: ResumeProfile,
    tailored: TailoredResumeResult,
    target_job_title: str,
    target_company: str,
) -> str:
    """
    Gera um arquivo PDF limpo, estruturado em coluna única (100% compatível com Gupy,
    Greenhouse, Lever e LinkedIn Easy Apply) e retorna o nome do arquivo salvo em RESUMES_DIR.
    """
    pdf = ATSResumePDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()

    # Nome Completo
    full_name = profile.full_name or "Candidato"
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 28, 45)
    pdf.cell(0, 9, _clean_latin1(full_name.upper()), new_x="LMARGIN", new_y="NEXT")

    # Título Adaptado para a Vaga
    headline = tailored.tailored_headline or profile.headline or target_job_title
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 98, 254)
    pdf.cell(0, 6, _clean_latin1(headline), new_x="LMARGIN", new_y="NEXT")

    # Linha de Contato
    contact_parts = [
        p
        for p in [
            profile.location,
            profile.email,
            profile.phone,
            profile.linkedin_url,
            profile.github_or_portfolio_url,
        ]
        if p and p.strip()
    ]
    if contact_parts:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(70, 75, 85)
        pdf.multi_cell(0, 5, _clean_latin1("  |  ".join(contact_parts)), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_draw_color(200, 208, 220)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)

    def add_section_title(title: str):
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(20, 28, 45)
        pdf.cell(0, 6, _clean_latin1(title.upper()), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(220, 225, 232)
        pdf.set_line_width(0.2)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(2)

    # 1. Resumo Profissional Adaptado
    add_section_title("Resumo Profissional")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(35, 40, 48)
    pdf.multi_cell(0, 5.2, _clean_latin1(tailored.tailored_summary or profile.summary), new_x="LMARGIN", new_y="NEXT")

    # 2. Competências e Palavras-Chave Técnicas (Priorizadas para o ATS)
    skills = tailored.prioritized_skills or profile.hard_skills
    if skills:
        add_section_title("Competências Técnicas & Ferramentas")
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(35, 40, 48)
        pdf.multi_cell(0, 5, _clean_latin1(" - ".join(skills)), new_x="LMARGIN", new_y="NEXT")

    # 3. Experiência Profissional Adaptada
    experiences = tailored.tailored_experiences or profile.experiences
    if experiences:
        add_section_title("Experiência Profissional")
        for exp in experiences:
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(20, 28, 45)
            header_left = f"{exp.role} - {exp.company}"
            pdf.cell(125, 5.5, _clean_latin1(header_left))
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(90, 95, 105)
            pdf.cell(0, 5.5, _clean_latin1(f"{exp.period} ({exp.location})"), align="R", new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(35, 40, 48)
            for bullet in exp.highlights:
                pdf.multi_cell(0, 5, _clean_latin1(f"  - {bullet}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)

    # 4. Projetos Relevantes
    projects = tailored.tailored_projects or profile.projects
    if projects:
        add_section_title("Projetos de Destaque")
        for proj in projects:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(20, 28, 45)
            tech_str = f" ({', '.join(proj.technologies)})" if proj.technologies else ""
            pdf.multi_cell(0, 5, _clean_latin1(f"{proj.name}{tech_str}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(45, 50, 58)
            pdf.multi_cell(0, 5, _clean_latin1(f"  {proj.description}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

    # 5. Formação Acadêmica
    if profile.education:
        add_section_title("Formação Acadêmica")
        for edu in profile.education:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(20, 28, 45)
            pdf.cell(135, 5, _clean_latin1(f"{edu.degree} - {edu.institution}"))
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(90, 95, 105)
            pdf.cell(0, 5, _clean_latin1(edu.period), align="R", new_x="LMARGIN", new_y="NEXT")

    # 6. Idiomas e Certificações
    extras = []
    if profile.languages:
        extras.append(f"Idiomas: {', '.join(profile.languages)}")
    if profile.certifications:
        extras.append(f"Certificações: {', '.join(profile.certifications)}")
    if extras:
        add_section_title("Idiomas & Certificações")
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(35, 40, 48)
        for line in extras:
            pdf.multi_cell(0, 5, _clean_latin1(line), new_x="LMARGIN", new_y="NEXT")

    # Salvar com nome amigável
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{full_name}_{target_company}_{target_job_title}")[:55].strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"CV_{safe_slug}_{timestamp}.pdf"
    output_path: Path = RESUMES_DIR / filename
    pdf.output(str(output_path))
    return filename
