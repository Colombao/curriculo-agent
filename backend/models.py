from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class ExperienceItem(BaseModel):
    role: str = Field(description="Cargo ou função exercida")
    company: str = Field(description="Nome da empresa ou cliente")
    period: str = Field(description="Período (ex: Jan 2023 - Atual)")
    location: str = Field(default="Remoto / Brasil", description="Localidade")
    highlights: List[str] = Field(
        default_factory=list,
        description="Lista de realizações, entregas e resultados com verbos de ação e métricas"
    )


class EducationItem(BaseModel):
    degree: str = Field(description="Curso ou grau acadêmico")
    institution: str = Field(description="Instituição de ensino")
    period: str = Field(description="Período ou ano de conclusão")


class ProjectItem(BaseModel):
    name: str = Field(description="Nome do projeto ou serviço entregue")
    description: str = Field(description="Descrição concisa do impacto e solução")
    technologies: List[str] = Field(default_factory=list, description="Tecnologias usadas")
    link: Optional[str] = Field(default="", description="Link do projeto/repositório")


class ResumeProfile(BaseModel):
    full_name: str = Field(default="", description="Nome completo do candidato")
    headline: str = Field(default="", description="Título profissional principal")
    email: str = Field(default="", description="E-mail de contato")
    phone: str = Field(default="", description="Telefone / WhatsApp")
    location: str = Field(default="", description="Cidade / Estado / País")
    linkedin_url: str = Field(default="", description="URL do LinkedIn")
    github_or_portfolio_url: str = Field(default="", description="URL do GitHub ou Portfólio")
    summary: str = Field(default="", description="Resumo profissional base")
    hard_skills: List[str] = Field(default_factory=list, description="Habilidades técnicas e ferramentas")
    soft_skills: List[str] = Field(default_factory=list, description="Competências comportamentais")
    languages: List[str] = Field(default_factory=list, description="Idiomas e nível de proficiência")
    certifications: List[str] = Field(default_factory=list, description="Certificações e cursos relevantes")
    experiences: List[ExperienceItem] = Field(default_factory=list, description="Experiências profissionais")
    education: List[EducationItem] = Field(default_factory=list, description="Formação acadêmica")
    projects: List[ProjectItem] = Field(default_factory=list, description="Projetos de destaque")
    hourly_rate_brl: Optional[str] = Field(default="R$ 80/h", description="Valor hora médio para serviços freelance")
    preferred_roles: List[str] = Field(default_factory=list, description="Cargos ou tipos de serviços desejados")


class TailoredResumeResult(BaseModel):
    match_score: int = Field(description="Pontuação de aderência à vaga/serviço de 0 a 100")
    match_summary: str = Field(description="Explicação clara do porquê o perfil combina e o que foi destacado")
    matched_keywords: List[str] = Field(default_factory=list, description="Palavras-chave da vaga presentes no perfil")
    missing_keywords: List[str] = Field(default_factory=list, description="Requisitos ou palavras-chave da vaga que faltam ou precisam de atenção")
    improvement_tips: List[str] = Field(default_factory=list, description="Recomendações práticas para entrevista ou proposta")
    tailored_headline: str = Field(description="Título profissional adaptado exatamente para a vaga")
    tailored_summary: str = Field(description="Resumo profissional reescrito com foco nos requisitos e palavras-chave da vaga (padrão ATS)")
    prioritized_skills: List[str] = Field(default_factory=list, description="Skills ordenadas por relevância para a vaga")
    tailored_experiences: List[ExperienceItem] = Field(
        default_factory=list,
        description="Experiências reais do candidato com os bullet points reescritos para destacar aderência à vaga sem inventar fatos"
    )
    tailored_projects: List[ProjectItem] = Field(default_factory=list, description="Projetos mais relevantes para a vaga")
    cover_letter_or_proposal: str = Field(
        description="Carta de apresentação (para vaga CLT/PJ) ou proposta comercial persuasiva (para projeto freelance)"
    )
    email_subject: str = Field(description="Assunto ideal para envio de e-mail ou título da candidatura")


class JobOpportunity(BaseModel):
    id: Optional[int] = None
    title: str = Field(description="Título da vaga ou projeto freelance")
    company_or_client: str = Field(description="Nome da empresa ou cliente contratante")
    channel: Literal["Emprego", "Freelance", "Email Direto"] = Field(description="Tipo do canal da oportunidade")
    platform: str = Field(description="Plataforma de origem (ex: LinkedIn, Gupy, Indeed, Workana, 99Freelas, Upwork, E-mail)")
    location_or_modality: str = Field(default="Remoto", description="Remoto, Híbrido ou Presencial")
    compensation: str = Field(default="A combinar", description="Faixa salarial ou orçamento do projeto")
    description: str = Field(description="Descrição detalhada dos requisitos, atividades ou escopo do serviço")
    apply_url: str = Field(default="", description="URL da vaga ou projeto para candidatura")
    recruiter_email: str = Field(default="", description="E-mail direto de candidatura, se disponível")
    estimated_match: int = Field(default=85, description="Estimativa percentual de aderência ao currículo do usuário (0-100)")
    tags: List[str] = Field(default_factory=list, description="Principais tecnologias/skills pedidas")


class JobSearchResponse(BaseModel):
    opportunities: List[JobOpportunity] = Field(default_factory=list, description="Lista de vagas e serviços encontrados")
    search_insights: str = Field(default="", description="Resumo estratégico do mercado para o perfil do candidato")


class TailorRequest(BaseModel):
    job_title: str
    company_or_client: str = "Empresa / Cliente"
    channel: Literal["Emprego", "Freelance", "Email Direto"] = "Emprego"
    platform: str = "Manual"
    job_description: str
    job_url: str = ""
    recruiter_email: str = ""
    job_id: Optional[int] = None


class SearchRequest(BaseModel):
    custom_query: str = ""
    channels: List[str] = Field(default_factory=lambda: ["Emprego", "Freelance", "Email Direto"])
    modality: str = "Remoto"
    max_results: int = 8


class ApplicationApprovalUpdate(BaseModel):
    recipient_email: str = ""
    apply_url: str = ""
    email_subject: str
    cover_letter_or_proposal: str
    delivery_method: Literal["email", "browser_assist", "manual_mark"] = "browser_assist"


class AppSettings(BaseModel):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
