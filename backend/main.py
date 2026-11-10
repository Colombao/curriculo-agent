from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import BASE_DIR, RESUMES_DIR, UPLOADS_DIR
from backend.database import (
    init_db,
    get_profile,
    save_profile,
    save_jobs,
    list_jobs,
    get_job,
    create_application,
    list_applications,
    get_application,
    update_application_status,
    get_settings,
    save_settings,
)
from backend.models import (
    ResumeProfile,
    TailorRequest,
    SearchRequest,
    ApplicationApprovalUpdate,
    AppSettings,
)
from backend.services.pdf_parser import extract_pdf_data
from backend.services.pdf_generator import generate_ats_pdf
from backend.services.ai_agent import (
    parse_resume_with_gemini,
    tailor_resume_for_job,
    search_matching_opportunities,
)
from backend.services.automation import (
    send_application_email,
    launch_browser_assisted_apply,
)

init_db()

app = FastAPI(
    title="Agente Inteligente de Currículos & Automação de Vagas",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
def api_status():
    profile = get_profile()
    jobs = list_jobs()
    apps = list_applications()
    settings = get_settings()
    api_key = (settings.get("gemini_api_key") or "").strip()
    has_key = bool(api_key and api_key != "sua_chave_gemini_aqui")
    pending = sum(1 for a in apps if a["status"] == "pending_approval")
    sent = sum(1 for a in apps if a["status"] == "sent")
    return {
        "candidate_name": profile.full_name,
        "headline": profile.headline,
        "skills_count": len(profile.hard_skills),
        "jobs_count": len(jobs),
        "pending_approvals": pending,
        "sent_applications": sent,
        "gemini_configured": has_key,
        "gemini_model": settings.get("gemini_model", "gemini-3.8-flash"),
    }


@app.get("/api/profile")
def api_get_profile():
    return get_profile()


@app.put("/api/profile")
def api_update_profile(profile: ResumeProfile):
    saved = save_profile(profile)
    return {"status": "ok", "profile": saved}


@app.post("/api/profile/upload")
async def api_upload_resume(
    file: Optional[UploadFile] = File(default=None),
    raw_text: Optional[str] = Form(default=""),
):
    pdf_b64: Optional[str] = None
    extracted_text: str = (raw_text or "").strip()

    if file and file.filename:
        content = await file.read()
        save_path = UPLOADS_DIR / file.filename
        save_path.write_bytes(content)

        if file.filename.lower().endswith(".pdf"):
            pdf_b64, pdf_text = extract_pdf_data(content)
            if pdf_text:
                extracted_text = f"{extracted_text}\n{pdf_text}".strip()
        else:
            decoded = content.decode("utf-8", errors="ignore")
            extracted_text = f"{extracted_text}\n{decoded}".strip()

    if not pdf_b64 and not extracted_text:
        raise HTTPException(status_code=400, detail="Envie um arquivo PDF/TXT ou cole o texto do seu currículo.")

    parsed_profile, engine = parse_resume_with_gemini(raw_text=extracted_text, pdf_base64=pdf_b64)
    save_profile(parsed_profile, raw_text=extracted_text)
    return {
        "status": "ok",
        "engine": engine,
        "profile": parsed_profile,
    }


@app.post("/api/tailor")
def api_tailor_resume(req: TailorRequest):
    profile = get_profile()
    tailored, engine = tailor_resume_for_job(
        profile=profile,
        job_title=req.job_title,
        company_or_client=req.company_or_client,
        channel=req.channel,
        job_description=req.job_description,
        job_url=req.job_url,
    )
    pdf_filename = generate_ats_pdf(
        profile=profile,
        tailored=tailored,
        target_job_title=req.job_title,
        target_company=req.company_or_client,
    )
    app_record = create_application(
        job_id=req.job_id,
        job_title=req.job_title,
        company_or_client=req.company_or_client,
        channel=req.channel,
        platform=req.platform,
        apply_url=req.job_url,
        recipient_email=req.recruiter_email,
        email_subject=tailored.email_subject,
        cover_letter_or_proposal=tailored.cover_letter_or_proposal,
        match_score=tailored.match_score,
        tailored_data=tailored.model_dump(),
        pdf_filename=pdf_filename,
    )
    return {
        "status": "ok",
        "engine": engine,
        "tailored": tailored,
        "pdf_filename": pdf_filename,
        "pdf_url": f"/api/resumes/{pdf_filename}",
        "application": app_record,
    }


@app.get("/api/jobs")
def api_list_jobs():
    jobs = list_jobs()
    if not jobs:
        # Popula oportunidades iniciais com base no currículo caso ainda esteja vazio
        profile = get_profile()
        search_res, _ = search_matching_opportunities(
            profile=profile,
            custom_query="",
            channels=["Emprego", "Freelance", "Email Direto"],
            modality="Remoto",
            max_results=6,
        )
        jobs = save_jobs(search_res.opportunities, clear_previous=True)
    return {"jobs": jobs}


@app.post("/api/jobs/search")
def api_search_jobs(req: SearchRequest):
    profile = get_profile()
    search_res, engine = search_matching_opportunities(
        profile=profile,
        custom_query=req.custom_query,
        channels=req.channels,
        modality=req.modality,
        max_results=req.max_results,
    )
    saved_jobs = save_jobs(search_res.opportunities, clear_previous=True)
    return {
        "status": "ok",
        "engine": engine,
        "insights": search_res.search_insights,
        "jobs": saved_jobs,
    }


@app.post("/api/jobs/{job_id}/prepare")
def api_prepare_job_application(job_id: int):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada.")

    profile = get_profile()
    tailored, engine = tailor_resume_for_job(
        profile=profile,
        job_title=job["title"],
        company_or_client=job["company_or_client"],
        channel=job["channel"],
        job_description=job["description"],
        job_url=job.get("apply_url", ""),
    )
    pdf_filename = generate_ats_pdf(
        profile=profile,
        tailored=tailored,
        target_job_title=job["title"],
        target_company=job["company_or_client"],
    )
    app_record = create_application(
        job_id=job["id"],
        job_title=job["title"],
        company_or_client=job["company_or_client"],
        channel=job["channel"],
        platform=job["platform"],
        apply_url=job.get("apply_url", ""),
        recipient_email=job.get("recruiter_email", ""),
        email_subject=tailored.email_subject,
        cover_letter_or_proposal=tailored.cover_letter_or_proposal,
        match_score=tailored.match_score,
        tailored_data=tailored.model_dump(),
        pdf_filename=pdf_filename,
    )
    return {
        "status": "ok",
        "engine": engine,
        "application": app_record,
        "pdf_url": f"/api/resumes/{pdf_filename}",
    }


@app.post("/api/jobs/batch-prepare")
def api_batch_prepare_top_jobs():
    jobs = list_jobs()[:4]
    if not jobs:
        raise HTTPException(status_code=400, detail="Busque vagas/serviços primeiro para preparar o lote.")

    profile = get_profile()
    created = []
    for job in jobs:
        tailored, _ = tailor_resume_for_job(
            profile=profile,
            job_title=job["title"],
            company_or_client=job["company_or_client"],
            channel=job["channel"],
            job_description=job["description"],
            job_url=job.get("apply_url", ""),
        )
        pdf_filename = generate_ats_pdf(
            profile=profile,
            tailored=tailored,
            target_job_title=job["title"],
            target_company=job["company_or_client"],
        )
        app_record = create_application(
            job_id=job["id"],
            job_title=job["title"],
            company_or_client=job["company_or_client"],
            channel=job["channel"],
            platform=job["platform"],
            apply_url=job.get("apply_url", ""),
            recipient_email=job.get("recruiter_email", ""),
            email_subject=tailored.email_subject,
            cover_letter_or_proposal=tailored.cover_letter_or_proposal,
            match_score=tailored.match_score,
            tailored_data=tailored.model_dump(),
            pdf_filename=pdf_filename,
        )
        created.append(app_record)

    return {"status": "ok", "count": len(created), "applications": created}


@app.get("/api/applications")
def api_list_applications():
    return {"applications": list_applications()}


@app.post("/api/applications/{app_id}/approve")
def api_approve_and_send(app_id: int, req: ApplicationApprovalUpdate):
    app_record = get_application(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada.")

    pdf_filename = app_record["pdf_filename"]

    if req.delivery_method == "email":
        ok, msg = send_application_email(
            recipient_email=req.recipient_email,
            subject=req.email_subject,
            body=req.cover_letter_or_proposal,
            pdf_filename=pdf_filename,
        )
    elif req.delivery_method == "browser_assist":
        ok, msg = launch_browser_assisted_apply(
            apply_url=req.apply_url,
            cover_letter_or_proposal=req.cover_letter_or_proposal,
            pdf_filename=pdf_filename,
        )
    else:
        ok, msg = True, "Marcado como enviado manualmente pelo usuário."

    new_status = "sent" if ok else "failed"
    updated = update_application_status(
        app_id=app_id,
        status=new_status,
        delivery_log=msg,
        recipient_email=req.recipient_email,
        apply_url=req.apply_url,
        email_subject=req.email_subject,
        cover_letter_or_proposal=req.cover_letter_or_proposal,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"status": "ok", "message": msg, "application": updated}


@app.get("/api/resumes/{filename}")
def api_download_resume(filename: str):
    safe_name = Path(filename).name
    file_path = RESUMES_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo PDF não encontrado.")
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=safe_name,
    )


@app.get("/api/settings")
def api_get_settings():
    s = get_settings()
    masked_key = ""
    raw_key = s.get("gemini_api_key", "")
    if raw_key and raw_key != "sua_chave_gemini_aqui":
        masked_key = raw_key[:6] + "..." + raw_key[-4:] if len(raw_key) > 10 else "***"
    return {
        "gemini_api_key_masked": masked_key,
        "has_gemini_key": bool(raw_key and raw_key != "sua_chave_gemini_aqui"),
        "gemini_model": s.get("gemini_model", "gemini-3.8-flash"),
        "smtp_host": s.get("smtp_host", "smtp.gmail.com"),
        "smtp_port": s.get("smtp_port", 587),
        "smtp_user": s.get("smtp_user", ""),
        "has_smtp_password": bool(s.get("smtp_password")),
    }


@app.put("/api/settings")
def api_save_settings(req: AppSettings):
    current = get_settings()
    update_dict = {
        "gemini_model": req.gemini_model,
        "smtp_host": req.smtp_host,
        "smtp_port": req.smtp_port,
        "smtp_user": req.smtp_user,
    }
    if req.gemini_api_key.strip():
        update_dict["gemini_api_key"] = req.gemini_api_key.strip()
    else:
        update_dict["gemini_api_key"] = current.get("gemini_api_key", "")

    if req.smtp_password.strip():
        update_dict["smtp_password"] = req.smtp_password.strip()
    else:
        update_dict["smtp_password"] = current.get("smtp_password", "")

    save_settings(update_dict)
    return {"status": "ok", "message": "Configurações salvas com sucesso!"}


# Servir o Frontend estático
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
