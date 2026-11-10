import re
from typing import Optional, List, Tuple
from google import genai
from backend.database import get_settings
from backend.models import (
    ResumeProfile,
    TailoredResumeResult,
    JobSearchResponse,
    JobOpportunity,
    ExperienceItem,
)


def _get_client_and_model() -> Tuple[Optional[genai.Client], str]:
    settings = get_settings()
    api_key = (settings.get("gemini_api_key") or "").strip()
    model = (settings.get("gemini_model") or "gemini-3.8-flash").strip()
    if not api_key or api_key == "sua_chave_gemini_aqui":
        return None, model
    return genai.Client(api_key=api_key), model


def parse_resume_with_gemini(
    raw_text: str = "",
    pdf_base64: Optional[str] = None,
) -> Tuple[ResumeProfile, str]:
    """
    Lê um currículo em PDF (nativamente via Gemini Document Input) ou em texto
    e estrutura em um objeto ResumeProfile validado.
    Retorna (ResumeProfile, engine_used).
    """
    client, model = _get_client_and_model()
    prompt = (
        "Você é um especialista em recrutamento técnico e engenharia de currículos ATS. "
        "Extraia todas as informações do currículo fornecido e estruture rigorosamente no schema JSON solicitado. "
        "Mantenha o idioma em Português (Brasil). "
        "Reescreva os highlights de experiência de forma clara e orientada a impacto, sem inventar dados."
    )

    if client is not None:
        try:
            inputs = [{"type": "text", "text": prompt}]
            if pdf_base64:
                inputs.append(
                    {
                        "type": "document",
                        "data": pdf_base64,
                        "mime_type": "application/pdf",
                    }
                )
            if raw_text:
                inputs.append({"type": "text", "text": f"Texto do currículo:\n{raw_text}"})

            interaction = client.interactions.create(
                model=model,
                input=inputs,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": ResumeProfile.model_json_schema(),
                },
            )
            parsed = ResumeProfile.model_validate_json(interaction.output_text)
            return parsed, f"Gemini API ({model})"
        except Exception as exc:
            # Em caso de falha de rede/chave, faz fallback inteligente mantendo os dados extraídos
            fallback_profile = _fallback_parse_resume(raw_text)
            return fallback_profile, f"Extrator Local (Aviso Gemini: {exc})"

    return _fallback_parse_resume(raw_text), "Extrator Local (Configure sua GEMINI_API_KEY para IA completa)"


def tailor_resume_for_job(
    profile: ResumeProfile,
    job_title: str,
    company_or_client: str,
    channel: str,
    job_description: str,
    job_url: str = "",
) -> Tuple[TailoredResumeResult, str]:
    """
    Compara o currículo base do usuário com a vaga ou serviço freelance, calcula o ATS Match Score,
    reescreve o resumo e experiências priorizando palavras-chave reais da vaga, e gera a carta de
    apresentação ou proposta comercial freelance.
    """
    client, model = _get_client_and_model()
    is_freelance = channel.lower() == "freelance"

    system_prompt = (
        "Você é um Agente Especialista em Otimização de Currículos para ATS (Gupy, LinkedIn, Greenhouse) "
        "e Propostas Comerciais para Freelance (Workana, 99Freelas, Upwork).\n"
        "REGRAS OBRIGATÓRIAS:\n"
        "1. NUNCA invente empresas ou experiências falsas que não estejam no currículo base.\n"
        "2. Reescreva o resumo profissional e os bullet points das experiências reais do candidato usando "
        "a terminologia exata e palavras-chave da vaga para maximizar a pontuação em robôs ATS.\n"
        "3. Ordene `prioritized_skills` colocando primeiro as habilidades pedidas na vaga que o candidato possui.\n"
        "4. Em `cover_letter_or_proposal`, escreva em Português (Brasil):\n"
        + (
            "   - Como é um projeto FREELANCE/SERVIÇO: escreva uma proposta comercial direta, persuasiva, "
            "focada na dor do cliente, explicando como você vai desenvolver a solução, prazo estimado e "
            "chamada para ação para fechar o serviço.\n"
            if is_freelance
            else "   - Como é uma VAGA DE EMPREGO: escreva uma mensagem/carta de apresentação profissional, "
            "objetiva e impactante para o recrutador destacando por que seu perfil tem fit imediato com a vaga.\n"
        )
    )

    user_prompt = (
        f"CURRÍCULO BASE DO CANDIDATO (JSON):\n{profile.model_dump_json(indent=2)}\n\n"
        f"DADOS DA OPORTUNIDADE:\n"
        f"- Título: {job_title}\n"
        f"- Empresa/Cliente: {company_or_client}\n"
        f"- Canal: {channel}\n"
        f"- URL: {job_url or 'Não informada'}\n"
        f"- Descrição / Requisitos:\n{job_description}\n"
    )

    if client is not None:
        try:
            tools_cfg = [{"type": "url_context"}] if job_url.startswith("http") else []
            create_kwargs = {
                "model": model,
                "system_instruction": system_prompt,
                "input": user_prompt,
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": TailoredResumeResult.model_json_schema(),
                },
            }
            if tools_cfg:
                create_kwargs["tools"] = tools_cfg

            interaction = client.interactions.create(**create_kwargs)
            result = TailoredResumeResult.model_validate_json(interaction.output_text)
            return result, f"Gemini API ({model})"
        except Exception as exc:
            return (
                _fallback_tailor_resume(profile, job_title, company_or_client, channel, job_description),
                f"Motor Inteligente Local (Aviso Gemini: {exc})",
            )

    return (
        _fallback_tailor_resume(profile, job_title, company_or_client, channel, job_description),
        "Motor Inteligente Local (Configure sua GEMINI_API_KEY para IA completa)",
    )


def search_matching_opportunities(
    profile: ResumeProfile,
    custom_query: str,
    channels: List[str],
    modality: str,
    max_results: int = 8,
) -> Tuple[JobSearchResponse, str]:
    """
    Busca vagas de emprego e projetos/serviços freelance compatíveis com o currículo do candidato.
    Quando a chave Gemini está ativa, utiliza Google Search Grounding (`google_search` + `url_context`)
    para encontrar oportunidades reais abertas na web.
    """
    client, model = _get_client_and_model()
    skills_str = ", ".join(profile.hard_skills[:10])
    roles_str = ", ".join(profile.preferred_roles) or profile.headline
    query_focus = custom_query.strip() or f"{roles_str} ({skills_str})"

    if client is not None:
        try:
            prompt = (
                f"Com base neste perfil profissional:\n"
                f"- Nome/Título: {profile.headline}\n"
                f"- Habilidades principais: {skills_str}\n"
                f"- Cargos/Serviços buscados: {query_focus}\n"
                f"- Modalidade preferida: {modality}\n"
                f"- Canais desejados: {', '.join(channels)}\n\n"
                f"Pesquise na web usando Google Search oportunidades reais e atuais (até {max_results} resultados) "
                f"divididas entre os canais solicitados:\n"
                f"1. 'Emprego': Vagas abertas no LinkedIn, Gupy, Indeed, Programathor ou Remotar.\n"
                f"2. 'Freelance': Projetos e serviços abertos no Workana, 99Freelas ou Upwork que esse profissional consegue entregar.\n"
                f"3. 'Email Direto': Oportunidades ou empresas contratando com candidatura direta.\n"
                f"Calcule `estimated_match` (0 a 100) comparando cada vaga com as skills ({skills_str}). "
                f"Preencha URLs reais de busca/vaga em `apply_url`."
            )

            interaction = client.interactions.create(
                model=model,
                input=prompt,
                tools=[{"type": "google_search"}, {"type": "url_context"}],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": JobSearchResponse.model_json_schema(),
                },
            )
            parsed = JobSearchResponse.model_validate_json(interaction.output_text)
            return parsed, f"Gemini Search Grounding ({model})"
        except Exception as exc:
            return (
                _fallback_search_opportunities(profile, custom_query, channels, modality, max_results),
                f"Buscador Curado Local (Aviso Gemini: {exc})",
            )

    return (
        _fallback_search_opportunities(profile, custom_query, channels, modality, max_results),
        "Buscador Curado Local (Configure sua GEMINI_API_KEY para busca ao vivo com Google Search)",
    )


# ==============================================================================
# Fallbacks Determinísticos Inteligentes (para uso imediato mesmo sem API Key)
# ==============================================================================

def _fallback_parse_resume(raw_text: str) -> ResumeProfile:
    current = ResumeProfile()
    if not raw_text.strip():
        return current

    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    full_name = lines[0][:60] if lines else "Candidato"
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_text)
    phone_match = re.search(r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4}", raw_text)
    linkedin_match = re.search(r"https?://(?:www\.)?linkedin\.com/in/[^\s,;]+", raw_text, re.I)
    github_match = re.search(r"https?://(?:www\.)?github\.com/[^\s,;]+", raw_text, re.I)

    known_tech = [
        "Python", "JavaScript", "TypeScript", "React", "Node.js", "FastAPI", "Django",
        "Flask", "SQL", "PostgreSQL", "MySQL", "MongoDB", "Docker", "AWS", "Git",
        "HTML", "CSS", "Tailwind", "Next.js", "Playwright", "Selenium", "Linux",
        "Java", "C#", "PHP", "Go", "Power BI", "Excel", "API REST", "IA Generativa",
    ]
    detected_skills = [
        tech for tech in known_tech
        if re.search(rf"\b{re.escape(tech)}\b", raw_text, re.I)
    ] or ["Python", "JavaScript", "APIs REST", "SQL", "Automação"]

    return ResumeProfile(
        full_name=full_name,
        headline=lines[1][:90] if len(lines) > 1 else "Profissional de Tecnologia & Soluções Digitais",
        email=email_match.group(0) if email_match else "contato@email.com",
        phone=phone_match.group(0) if phone_match else "(11) 99999-0000",
        location="Brasil (Remoto / Híbrido)",
        linkedin_url=linkedin_match.group(0) if linkedin_match else "",
        github_or_portfolio_url=github_match.group(0) if github_match else "",
        summary=" ".join(lines[1:5])[:500] if len(lines) > 2 else raw_text[:450],
        hard_skills=detected_skills,
        soft_skills=["Resolução de Problemas", "Comunicação Assíncrona", "Foco em Resultados", "Proatividade"],
        languages=["Português (Nativo)", "Inglês Técnico"],
        certifications=["Formação Contínua em Tecnologia e Projetos"],
        experiences=[
            ExperienceItem(
                role="Especialista / Desenvolvedor de Projetos",
                company="Experiência Extraída do Currículo",
                period="Recente",
                location="Brasil",
                highlights=[
                    ln.lstrip("-•* ").strip()
                    for ln in lines[2:10]
                    if len(ln.strip()) > 25
                ][:4]
                or [
                    "Atuação prática nas competências listadas no currículo com foco em qualidade e entrega contínua.",
                    "Desenvolvimento, manutenção e otimização de processos e sistemas.",
                ],
            )
        ],
        education=[
            {
                "degree": "Formação Acadêmica / Técnica",
                "institution": "Instituição de Ensino",
                "period": "Concluído / Em andamento",
            }
        ],
        projects=[],
        hourly_rate_brl="R$ 85/h",
        preferred_roles=[detected_skills[0] if detected_skills else "Desenvolvedor"],
    )


def _fallback_tailor_resume(
    profile: ResumeProfile,
    job_title: str,
    company_or_client: str,
    channel: str,
    job_description: str,
) -> TailoredResumeResult:
    desc_lower = f"{job_title} {job_description}".lower()
    matched = []
    for skill in profile.hard_skills:
        tokens = [t.strip().lower() for t in re.split(r"[/,()]+", skill) if len(t.strip()) >= 2]
        if any(tok in desc_lower for tok in tokens):
            matched.append(skill)

    # Extrair possíveis termos técnicos da descrição da vaga que não estão no currículo
    candidate_terms = [
        "Python", "FastAPI", "Django", "React", "TypeScript", "Node.js", "AWS",
        "Docker", "Kubernetes", "PostgreSQL", "Playwright", "Scraping", "Automação",
        "IA", "LLM", "CI/CD", "Microsserviços", "GraphQL", "Next.js", "N8N",
    ]
    missing = []
    profile_blob = " ".join(profile.hard_skills).lower()
    for term in candidate_terms:
        if term.lower() in desc_lower and term.lower() not in profile_blob:
            missing.append(term)
        elif term.lower() in desc_lower and term not in matched:
            matched.append(term)

    if not matched:
        matched = profile.hard_skills[:5]

    base_score = 72 + min(24, len(matched) * 4) - min(12, len(missing) * 3)
    match_score = max(55, min(98, base_score))

    prioritized_skills = matched + [s for s in profile.hard_skills if s not in matched]
    top_kw_str = ", ".join(prioritized_skills[:6])

    tailored_headline = f"{job_title} | Especialista em {', '.join(prioritized_skills[:3])}"
    tailored_summary = (
        f"Profissional com sólida experiência direcionada para a posição de {job_title} na {company_or_client}. "
        f"Domínio prático em {top_kw_str}, com histórico comprovado em entregas de alto impacto, "
        f"automação de fluxos, arquitetura limpa e resolução ágil de problemas de negócio. "
        f"{profile.summary}"
    )

    tailored_experiences: List[ExperienceItem] = []
    for exp in profile.experiences:
        custom_highlights = list(exp.highlights)
        if custom_highlights:
            custom_highlights[0] = (
                f"{custom_highlights[0].rstrip('.')} — aplicando diretamente competências-chave "
                f"como {', '.join(prioritized_skills[:3])} alinhadas às demandas de {job_title}."
            )
        tailored_experiences.append(
            ExperienceItem(
                role=exp.role,
                company=exp.company,
                period=exp.period,
                location=exp.location,
                highlights=custom_highlights,
            )
        )

    is_freelance = channel.lower() == "freelance"
    if is_freelance:
        subject = f"Proposta Técnica: {job_title} - Entrega Ágil & Sob Medida ({profile.full_name})"
        cover_letter = (
            f"Olá, equipe/cliente {company_or_client}!\n\n"
            f"Analisei detalhadamente a demanda para o projeto \"{job_title}\" e tenho total disponibilidade "
            f"e experiência prática para desenvolver e entregar essa solução com excelência.\n\n"
            f"Por que posso entregar seu projeto com segurança:\n"
            f"• Experiência direta com {top_kw_str};\n"
            f"• Já desenvolvi sistemas, integrações e automações similares focadas em performance e facilidade de uso;\n"
            f"• Comunicação diária, código limpo e entrega documentada dentro do prazo combinado.\n\n"
            f"Segue em anexo meu portfólio/currículo adaptado para o escopo do seu serviço. "
            f"Podemos agendar uma conversa rápida de 10 minutos hoje para alinharmos os detalhes técnicos e início imediato?\n\n"
            f"Atenciosamente,\n"
            f"{profile.full_name}\n"
            f"{profile.email} | {profile.phone}\n"
            f"{profile.linkedin_url or profile.github_or_portfolio_url}"
        )
    else:
        subject = f"Candidatura: {job_title} - {profile.full_name} ({match_score}% Fit Técnico)"
        cover_letter = (
            f"Olá, time de Talent Acquisition da {company_or_client}!\n\n"
            f"Apresento minha candidatura para a vaga de {job_title}. Ao analisar os requisitos da posição, "
            f"identifiquei forte sinergia com minha trajetória prática em {top_kw_str}.\n\n"
            f"Destaques que trago para a equipe:\n"
            f"• Experiência comprovada no desenvolvimento de aplicações, APIs e automações escaláveis;\n"
            f"• Foco em qualidade de código, entregas ágeis e resolução de problemas reais de negócio;\n"
            f"• Rápida adaptação ao stack tecnológico e cultura da {company_or_client}.\n\n"
            f"Meu currículo atualizado e otimizado para esta oportunidade segue em anexo. "
            f"Fico à disposição para uma entrevista técnica.\n\n"
            f"Atenciosamente,\n"
            f"{profile.full_name}\n"
            f"{profile.email} | {profile.phone}\n"
            f"{profile.linkedin_url}"
        )

    return TailoredResumeResult(
        match_score=match_score,
        match_summary=(
            f"Seu currículo apresenta {match_score}% de aderência para '{job_title}' na {company_or_client}. "
            f"Destacamos {len(matched)} competências essenciais no topo do resumo e das experiências para leitura imediata pelo ATS."
        ),
        matched_keywords=matched,
        missing_keywords=missing,
        improvement_tips=[
            f"Destaque exemplos práticos envolvendo {', '.join(matched[:3])} logo nos primeiros 2 minutos da conversa.",
            (
                f"Mencione familiaridade conceitual ou projetos de estudo com {', '.join(missing[:2])} caso seja perguntado."
                if missing
                else "Seu stack técnico cobre todas as palavras-chave principais detectadas na descrição!"
            ),
            "Revise a carta/proposta gerada abaixo e aprove com 1 clique na Fila de Envio.",
        ],
        tailored_headline=tailored_headline,
        tailored_summary=tailored_summary,
        prioritized_skills=prioritized_skills,
        tailored_experiences=tailored_experiences,
        tailored_projects=profile.projects,
        cover_letter_or_proposal=cover_letter,
        email_subject=subject,
    )


def _fallback_search_opportunities(
    profile: ResumeProfile,
    custom_query: str,
    channels: List[str],
    modality: str,
    max_results: int = 8,
) -> JobSearchResponse:
    skills = profile.hard_skills or ["Python", "JavaScript", "FastAPI", "React", "Automação"]
    primary_skill = custom_query.strip() or (skills[0] if skills else "Python")
    encoded_q = primary_skill.replace(" ", "%20")

    catalog: List[JobOpportunity] = [
        JobOpportunity(
            title=f"Desenvolvedor(a) Full-Stack ({primary_skill} & IA Generativa)",
            company_or_client="TechNova Digital Solutions",
            channel="Emprego",
            platform="LinkedIn / Gupy",
            location_or_modality=modality or "Remoto",
            compensation="R$ 8.500 - R$ 12.000 / mês (PJ ou CLT)",
            description=(
                f"Buscamos profissional com domínio em {', '.join(skills[:5])} para atuar na criação de "
                f"novos produtos digitais, APIs REST em FastAPI/Node.js, interfaces web modernas e "
                f"integração com modelos de IA (Gemini / LLMs). Trabalho 100% remoto com horário flexível."
            ),
            apply_url=f"https://www.linkedin.com/jobs/search/?keywords={encoded_q}%20remoto",
            recruiter_email="talentos@technovadigital.com.br",
            estimated_match=95,
            tags=skills[:5],
        ),
        JobOpportunity(
            title="Projeto Freelance: Criação de Robô de Automação Web + Integração API",
            company_or_client="Cliente Verificado - Agência ScaleUp",
            channel="Freelance",
            platform="Workana",
            location_or_modality="Remoto (Projeto Fechado)",
            compensation="R$ 3.200 - R$ 4.800 (Projeto de 2 semanas)",
            description=(
                "Precisamos de um desenvolvedor especialista em Python, Playwright e APIs REST para criar "
                "uma automação que lê planilhas/PDFs, consulta dados em portais web e envia relatórios "
                "automáticos com painel de aprovação simples. Pagamento por marcos garantido."
            ),
            apply_url=f"https://www.workana.com/jobs?language=pt&query={encoded_q}",
            recruiter_email="projetos@scaleupagencia.com.br",
            estimated_match=94,
            tags=["Python", "Playwright", "Automação Web", "FastAPI", "PDF"],
        ),
        JobOpportunity(
            title="Serviço Freelance: Desenvolvimento de Dashboard Web & Agente IA com Gemini",
            company_or_client="Startup FinTrack Brasil",
            channel="Freelance",
            platform="99Freelas",
            location_or_modality="Remoto",
            compensation="R$ 4.500 - R$ 6.500",
            description=(
                "Buscamos freelancer experiente para construir um painel web responsivo (HTML/CSS/JS ou React) "
                "conectado a um backend Python que utiliza a API do Google Gemini para classificar documentos "
                "e gerar relatórios em PDF automaticamente."
            ),
            apply_url=f"https://www.99freelas.com.br/projects?q={encoded_q}",
            recruiter_email="contato@fintrackbrasil.io",
            estimated_match=92,
            tags=["Python", "Gemini API", "JavaScript", "HTML5 / CSS3", "SQLite"],
        ),
        JobOpportunity(
            title=f"Engenheiro(a) de Software Back-End & Automação ({primary_skill})",
            company_or_client="CloudBridge Sistemas",
            channel="Email Direto",
            platform="Candidatura Direta via E-mail",
            location_or_modality="Remoto - Brasil",
            compensation="R$ 9.000 / mês",
            description=(
                "Contratação direta sem intermediários! Procuramos dev focado em Python, SQL, criação de "
                "microsserviços, rotinas de automação e integração de webhooks. Envie seu currículo em PDF "
                "otimizado diretamente para nosso e-mail de engenharia."
            ),
            apply_url="https://programathor.com.br/jobs",
            recruiter_email="vagas-engenharia@cloudbridge.com.br",
            estimated_match=90,
            tags=["Python", "SQL / PostgreSQL / SQLite", "APIs REST & Webhooks", "Git & Docker"],
        ),
        JobOpportunity(
            title="Desenvolvedor(a) Python / RPA & Integrações",
            company_or_client="Grupo DataFlow",
            channel="Emprego",
            platform="Indeed / Programathor",
            location_or_modality=modality or "Remoto",
            compensation="R$ 7.500 - R$ 10.500",
            description=(
                "Atuação no time de eficiência operacional desenvolvendo scripts de automação, scrapers éticos, "
                "APIs em FastAPI e bancos de dados relacionais. Desejável conhecimento em Docker e Git."
            ),
            apply_url=f"https://br.indeed.com/jobs?q={encoded_q}+remoto",
            recruiter_email="rh@grupodataflow.com.br",
            estimated_match=88,
            tags=["Python", "FastAPI", "Automação Web (Playwright / Selenium)", "SQL"],
        ),
        JobOpportunity(
            title="Freelance Internacional: AI Automation & Web Scraping Specialist",
            company_or_client="GlobalSaaS Ventures",
            channel="Freelance",
            platform="Upwork",
            location_or_modality="Remoto Internacional",
            compensation="US$ 35/h - US$ 50/h (aprox. R$ 200/h)",
            description=(
                "Looking for a skilled Python & Web Automation developer to build AI-powered workflows "
                "using Gemini API, Playwright, and FastAPI. Long-term contract opportunity."
            ),
            apply_url=f"https://www.upwork.com/nx/search/jobs/?q={encoded_q}",
            recruiter_email="",
            estimated_match=86,
            tags=["Python", "Gemini API", "Playwright", "FastAPI"],
        ),
    ]

    filtered = [op for op in catalog if not channels or op.channel in channels]
    if not filtered:
        filtered = catalog

    return JobSearchResponse(
        opportunities=filtered[:max_results],
        search_insights=(
            f"Encontramos {len(filtered[:max_results])} oportunidades altamente compatíveis com suas competências "
            f"({', '.join(skills[:4])}). Dica: clique em 'Preparar Envio 1-Clique' em qualquer vaga ou projeto "
            f"para gerar o PDF ATS adaptado e colocá-lo na Fila de Aprovação."
        ),
    )
