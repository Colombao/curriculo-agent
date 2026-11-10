document.addEventListener("DOMContentLoaded", () => {
  let cachedProfile = null;
  let cachedApplications = [];

  // 1. Fallback obrigatório para light-dismiss em navegadores sem suporte nativo a <dialog closedby="any">
  if (!("closedBy" in HTMLDialogElement.prototype)) {
    const isOutside = (e, dialog) => {
      const r = dialog.getBoundingClientRect();
      return (
        e.clientX < r.left ||
        e.clientX > r.right ||
        e.clientY < r.top ||
        e.clientY > r.bottom
      );
    };
    for (const dialog of document.querySelectorAll('dialog[closedby="any"]')) {
      let pressedOutside = false;
      dialog.addEventListener("pointerdown", (e) => {
        if (e.target === dialog) {
          pressedOutside = isOutside(e, dialog);
        } else {
          pressedOutside = false;
        }
      });
      dialog.addEventListener("pointerup", (e) => {
        if (pressedOutside && e.target === dialog && isOutside(e, dialog)) {
          dialog.close();
        }
      });
    }
  }

  // Limpa returnValue no fechamento de cada dialog
  for (const dialog of document.querySelectorAll("dialog")) {
    dialog.addEventListener("close", () => {
      dialog.returnValue = "";
    });
  }

  // Utilitário de escape para evitar XSS ao injetar textos no DOM
  const escapeHTML = (str) => {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  };

  // Utilitário de Toast acessível (role="status" aria-live="polite")
  const toastEl = document.getElementById("toast-status");
  let toastTimer = null;
  const showToast = (msg) => {
    toastEl.textContent = msg;
    toastEl.hidden = false;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.hidden = true;
    }, 6500);
  };

  // Navegação por Abas
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");

  const switchTab = (targetId) => {
    tabButtons.forEach((btn) => {
      const isMatch = btn.dataset.tab === targetId;
      btn.classList.toggle("active", isMatch);
      if (isMatch) {
        btn.setAttribute("aria-current", "page");
      } else {
        btn.removeAttribute("aria-current");
      }
    });
    tabPanels.forEach((panel) => {
      panel.hidden = panel.id !== targetId;
    });
  };

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Carregar Status e Métricas
  const refreshStatus = async () => {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      document.getElementById("metric-candidate").textContent =
        data.candidate_name || "Candidato";
      document.getElementById("metric-skills").textContent =
        `${data.skills_count} competências mapeadas`;
      document.getElementById("metric-jobs").textContent = String(
        data.jobs_count
      );
      document.getElementById("metric-pending").textContent = String(
        data.pending_approvals
      );
      document.getElementById("metric-sent").textContent = String(
        data.sent_applications
      );
      document.getElementById("queue-badge").textContent = String(
        data.pending_approvals
      );

      const pill = document.getElementById("ai-engine-pill");
      if (data.gemini_configured) {
        pill.textContent = `IA Ativa: ${data.gemini_model}`;
        pill.classList.add("is-live");
      } else {
        pill.textContent = "Modo Local (Clique em Configurar Gemini)";
        pill.classList.remove("is-live");
      }
    } catch (err) {
      console.error("Erro ao carregar status:", err);
    }
  };

  // Renderizar Cards de Vagas e Serviços Freelance
  const renderJobs = (jobs) => {
    const grid = document.getElementById("jobs-grid");
    grid.innerHTML = "";
    if (!jobs || jobs.length === 0) {
      grid.innerHTML = `<p class="empty-hint">Nenhuma oportunidade listada ainda. Clique em Buscar acima.</p>`;
      return;
    }

    jobs.forEach((job) => {
      const card = document.createElement("article");
      card.className = "job-card";
      const hue = job.estimated_match >= 85 ? 145 : job.estimated_match >= 70 ? 200 : 40;
      const tagsHtml = (job.tags || [])
        .map((t) => `<span class="tag-badge">${escapeHTML(t)}</span>`)
        .join("");

      card.innerHTML = `
        <div>
          <div class="job-card-top">
            <span class="tag-badge">${escapeHTML(job.channel)} • ${escapeHTML(job.platform)}</span>
            <span class="match-pill" style="--match-hue: ${hue};">${Number(job.estimated_match) || 85}% Fit</span>
          </div>
          <h3>${escapeHTML(job.title)}</h3>
          <p class="job-company">${escapeHTML(job.company_or_client)} — ${escapeHTML(job.location_or_modality)} • <strong>${escapeHTML(job.compensation)}</strong></p>
          <div class="tags-row">${tagsHtml}</div>
          <p class="job-desc">${escapeHTML(job.description)}</p>
        </div>
        <div class="job-actions">
          <button type="button" class="btn btn-primary btn-prepare-job" data-job-id="${job.id}">
            Preparar Currículo PDF &amp; Envio 1-Clique
          </button>
          <button type="button" class="btn btn-secondary btn-customize-job" data-job-id="${job.id}">
            Editar no Adaptador
          </button>
        </div>
      `;

      card
        .querySelector(".btn-prepare-job")
        .addEventListener("click", async (e) => {
          const btn = e.currentTarget;
          btn.disabled = true;
          btn.textContent = "Gerando PDF ATS & Proposta...";
          try {
            const resp = await fetch(`/api/jobs/${job.id}/prepare`, {
              method: "POST",
            });
            const resData = await resp.json();
            if (!resp.ok) throw new Error(resData.detail || "Falha ao preparar");
            await loadApplications();
            await refreshStatus();
            showToast(
              `Currículo adaptado (${resData.application.pdf_filename}) pronto! Abrindo janela de aprovação 1-clique...`
            );
            openApprovalDialog(resData.application);
          } catch (err) {
            showToast(`Erro: ${err.message}`);
          } finally {
            btn.disabled = false;
            btn.textContent = "Preparar Currículo PDF & Envio 1-Clique";
          }
        });

      card.querySelector(".btn-customize-job").addEventListener("click", () => {
        document.getElementById("tailor-title").value = job.title;
        document.getElementById("tailor-company").value = job.company_or_client;
        document.getElementById("tailor-platform").value = job.platform;
        document.getElementById("tailor-url").value = job.apply_url || "";
        document.getElementById("tailor-email").value =
          job.recruiter_email || "";
        document.getElementById("tailor-desc").value = job.description;
        const radio = document.querySelector(
          `input[name="channel"][value="${job.channel}"]`
        );
        if (radio) radio.checked = true;
        switchTab("tab-tailor");
        document.getElementById("tailor-title").focus();
      });

      grid.appendChild(card);
    });
  };

  const loadJobs = async () => {
    try {
      const res = await fetch("/api/jobs");
      const data = await res.json();
      renderJobs(data.jobs || []);
    } catch (err) {
      console.error("Erro ao listar vagas:", err);
    }
  };

  // Busca de Vagas e Serviços
  const formSearch = document.getElementById("form-job-search");
  formSearch.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("btn-run-search");
    btn.disabled = true;
    btn.textContent = "Varrendo Vagas & Projetos Freelance...";

    const checkedChannels = Array.from(
      formSearch.querySelectorAll('input[name="channels"]:checked')
    ).map((el) => el.value);

    const payload = {
      custom_query: document.getElementById("search-query").value,
      modality: document.getElementById("search-modality").value || "Remoto",
      channels: checkedChannels.length
        ? checkedChannels
        : ["Emprego", "Freelance", "Email Direto"],
      max_results: 8,
    };

    try {
      const res = await fetch("/api/jobs/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      renderJobs(data.jobs || []);
      const insightsEl = document.getElementById("search-insights-banner");
      if (data.insights) {
        insightsEl.textContent = `${data.insights} (Motor: ${data.engine})`;
        insightsEl.hidden = false;
      }
      await refreshStatus();
      showToast(
        `Encontradas ${data.jobs?.length || 0} oportunidades alinhadas ao seu currículo!`
      );
    } catch (err) {
      showToast(`Erro na busca: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent = "Buscar Vagas & Serviços para Meu Currículo";
    }
  });

  // Botão Auto-Preparar Top 4 Vagas em Lote
  document
    .getElementById("btn-batch-prepare")
    .addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      btn.textContent = "Adaptando Top 4 Currículos PDF...";
      try {
        const res = await fetch("/api/jobs/batch-prepare", { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Falha no lote");
        await loadApplications();
        await refreshStatus();
        switchTab("tab-queue");
        showToast(
          `${data.count} currículos PDF adaptados e propostas adicionados à Fila de Aprovação 1-Clique!`
        );
      } catch (err) {
        showToast(`Erro: ${err.message}`);
      } finally {
        btn.disabled = false;
        btn.textContent = "Auto-Preparar Pacote para Top 4 Vagas";
      }
    });

  // Aba 2: Adaptar Currículo para Vaga Específica
  const formTailor = document.getElementById("form-tailor");
  formTailor.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("btn-submit-tailor");
    btn.disabled = true;
    btn.textContent = "Analisando Vaga & Gerando Currículo PDF ATS...";

    const selectedChannel =
      formTailor.querySelector('input[name="channel"]:checked')?.value ||
      "Emprego";

    const payload = {
      job_title: document.getElementById("tailor-title").value,
      company_or_client: document.getElementById("tailor-company").value,
      platform: document.getElementById("tailor-platform").value,
      channel: selectedChannel,
      job_url: document.getElementById("tailor-url").value,
      recruiter_email: document.getElementById("tailor-email").value,
      job_description: document.getElementById("tailor-desc").value,
    };

    try {
      const res = await fetch("/api/tailor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erro ao adaptar currículo");

      const t = data.tailored;
      const resultPanel = document.getElementById("tailor-result-panel");
      const matchedHtml = (t.matched_keywords || [])
        .map((k) => `<li class="kw-matched">✓ ${escapeHTML(k)}</li>`)
        .join("");
      const missingHtml = (t.missing_keywords || [])
        .map((k) => `<li class="kw-missing">! ${escapeHTML(k)}</li>`)
        .join("");

      resultPanel.innerHTML = `
        <h3>Diagnóstico ATS Concluído (${escapeHTML(data.engine)})</h3>
        <div class="score-banner">
          <div class="score-circle">${Number(t.match_score)}%</div>
          <div>
            <strong>Compatibilidade ATS Calculada</strong>
            <p class="metric-sub">${escapeHTML(t.match_summary)}</p>
          </div>
        </div>

        <h4>Palavras-Chave Destacadas no PDF</h4>
        <ul class="kw-list">${matchedHtml || '<li class="kw-matched">Competências principais alinhadas</li>'}</ul>

        ${
          missingHtml
            ? `<h4>Pontos de Atenção / Requisitos Extras da Vaga</h4><ul class="kw-list">${missingHtml}</ul>`
            : ""
        }

        <h4>Resumo Profissional Adaptado para a Vaga</h4>
        <p class="job-desc">${escapeHTML(t.tailored_summary)}</p>

        <div class="job-actions" style="margin-block-start: 1.25rem;">
          <a href="${escapeHTML(data.pdf_url)}" target="_blank" rel="noopener" class="btn btn-accent">
            Baixar / Visualizar PDF Adaptado (${escapeHTML(data.pdf_filename)})
          </a>
          <button type="button" id="btn-open-created-approval" class="btn btn-primary">
            Revisar e Enviar com 1 Clique
          </button>
        </div>
      `;

      document
        .getElementById("btn-open-created-approval")
        .addEventListener("click", () => {
          openApprovalDialog(data.application);
        });

      await loadApplications();
      await refreshStatus();
      showToast(
        "Currículo PDF padrão ATS gerado e adicionado à Fila de Aprovação!"
      );
    } catch (err) {
      showToast(`Erro ao adaptar: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent =
        "Analisar Vaga, Gerar Currículo PDF Adaptado & Colocar na Fila";
    }
  });

  // Aba 3: Fila de Aprovação 1-Clique
  const renderApplications = (apps) => {
    const listEl = document.getElementById("applications-list");
    listEl.innerHTML = "";
    if (!apps || apps.length === 0) {
      listEl.innerHTML = `<p class="empty-hint">Nenhum pacote na fila ainda. Prepare uma vaga na Aba 1 ou Aba 2.</p>`;
      return;
    }

    apps.forEach((appItem) => {
      const card = document.createElement("article");
      const isSent = appItem.status === "sent";
      card.className = `queue-card ${isSent ? "status-sent" : ""}`;

      card.innerHTML = `
        <div>
          <span class="tag-badge">${escapeHTML(appItem.channel)} • ${escapeHTML(appItem.platform)}</span>
          <span class="tag-badge">${Number(appItem.match_score)}% Fit ATS</span>
          <h3>${escapeHTML(appItem.job_title)} — ${escapeHTML(appItem.company_or_client)}</h3>
          <p class="metric-sub">
            Status: <strong>${isSent ? "Enviado / Executado ✓" : "Aguardando sua aprovação de 1 clique"}</strong>
            • Log: ${escapeHTML(appItem.delivery_log)}
          </p>
        </div>
        <div class="job-actions">
          <a href="/api/resumes/${encodeURIComponent(appItem.pdf_filename)}" target="_blank" rel="noopener" class="btn btn-secondary">
            Ver PDF Adaptado
          </a>
          <button type="button" class="btn ${isSent ? "btn-secondary" : "btn-primary"} btn-review-app">
            ${isSent ? "Reenviar / Ver Proposta" : "Aprovar & Enviar (1-Clique)"}
          </button>
        </div>
      `;

      card.querySelector(".btn-review-app").addEventListener("click", () => {
        openApprovalDialog(appItem);
      });

      listEl.appendChild(card);
    });
  };

  const loadApplications = async () => {
    try {
      const res = await fetch("/api/applications");
      const data = await res.json();
      cachedApplications = data.applications || [];
      renderApplications(cachedApplications);
    } catch (err) {
      console.error("Erro ao carregar candidaturas:", err);
    }
  };

  // Modal de Aprovação 1-Clique
  const dialogApprove = document.getElementById("dialog-approve");
  const openApprovalDialog = (appItem) => {
    document.getElementById("approve-app-id").value = appItem.id;
    document.getElementById("approve-job-badge").textContent =
      `${appItem.channel}: ${appItem.job_title} (${appItem.company_or_client})`;
    const pdfLink = document.getElementById("approve-pdf-link");
    pdfLink.href = `/api/resumes/${encodeURIComponent(appItem.pdf_filename)}`;
    pdfLink.textContent = `Abrir PDF Adaptado (${appItem.pdf_filename})`;

    document.getElementById("approve-url").value = appItem.apply_url || "";
    document.getElementById("approve-email").value =
      appItem.recipient_email || "";
    document.getElementById("approve-subject").value =
      appItem.email_subject || "";
    document.getElementById("approve-body").value =
      appItem.cover_letter_or_proposal || "";

    if (appItem.channel === "Email Direto" && appItem.recipient_email) {
      document.getElementById("method-email").checked = true;
    } else {
      document.getElementById("method-browser").checked = true;
    }

    dialogApprove.showModal();
  };

  document
    .getElementById("btn-cancel-approve")
    .addEventListener("click", () => {
      dialogApprove.close("cancel");
    });

  document
    .getElementById("form-approve-send")
    .addEventListener("submit", async (e) => {
      e.preventDefault();
      const appId = document.getElementById("approve-app-id").value;
      const btn = document.getElementById("btn-confirm-approve");
      btn.disabled = true;
      btn.textContent = "Executando Envio...";

      const selectedMethod =
        document.querySelector('input[name="delivery_method"]:checked')?.value ||
        "browser_assist";

      const payload = {
        delivery_method: selectedMethod,
        apply_url: document.getElementById("approve-url").value,
        recipient_email: document.getElementById("approve-email").value,
        email_subject: document.getElementById("approve-subject").value,
        cover_letter_or_proposal: document.getElementById("approve-body").value,
      };

      try {
        // Copia também a proposta/carta para a área de transferência por conveniência
        navigator.clipboard
          ?.writeText(payload.cover_letter_or_proposal)
          .catch(() => {});

        const res = await fetch(`/api/applications/${appId}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Falha no envio");

        dialogApprove.close("confirm");
        await loadApplications();
        await refreshStatus();
        showToast(data.message);
      } catch (err) {
        showToast(`Erro no disparo: ${err.message}`);
      } finally {
        btn.disabled = false;
        btn.textContent = "Aprovar e Executar Envio Agora";
      }
    });

  // Aba 4: Carregar e Salvar Perfil Base
  const populateProfileForm = (prof) => {
    cachedProfile = prof;
    document.getElementById("prof-name").value = prof.full_name || "";
    document.getElementById("prof-headline").value = prof.headline || "";
    document.getElementById("prof-email").value = prof.email || "";
    document.getElementById("prof-phone").value = prof.phone || "";
    document.getElementById("prof-linkedin").value = prof.linkedin_url || "";
    document.getElementById("prof-github").value =
      prof.github_or_portfolio_url || "";
    document.getElementById("prof-summary").value = prof.summary || "";
    document.getElementById("prof-skills").value = (
      prof.hard_skills || []
    ).join(", ");
    document.getElementById("prof-roles").value = (
      prof.preferred_roles || []
    ).join(", ");
  };

  const loadProfile = async () => {
    try {
      const res = await fetch("/api/profile");
      const prof = await res.json();
      populateProfileForm(prof);
    } catch (err) {
      console.error("Erro ao carregar perfil:", err);
    }
  };

  document
    .getElementById("form-upload-resume")
    .addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = document.getElementById("btn-upload-parse");
      btn.disabled = true;
      btn.textContent = "Lendo Currículo e Extraindo Dados...";

      const formData = new FormData(e.currentTarget);
      try {
        const res = await fetch("/api/profile/upload", {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Falha ao processar arquivo");
        populateProfileForm(data.profile);
        await refreshStatus();
        showToast(`Currículo lido e estruturado com sucesso via ${data.engine}!`);
      } catch (err) {
        showToast(`Erro: ${err.message}`);
      } finally {
        btn.disabled = false;
        btn.textContent = "Extrair e Atualizar Meu Perfil com IA";
      }
    });

  document
    .getElementById("form-edit-profile")
    .addEventListener("submit", async (e) => {
      e.preventDefault();
      const updated = {
        ...(cachedProfile || {}),
        full_name: document.getElementById("prof-name").value,
        headline: document.getElementById("prof-headline").value,
        email: document.getElementById("prof-email").value,
        phone: document.getElementById("prof-phone").value,
        linkedin_url: document.getElementById("prof-linkedin").value,
        github_or_portfolio_url: document.getElementById("prof-github").value,
        summary: document.getElementById("prof-summary").value,
        hard_skills: document
          .getElementById("prof-skills")
          .value.split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        preferred_roles: document
          .getElementById("prof-roles")
          .value.split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };

      try {
        const res = await fetch("/api/profile", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updated),
        });
        const data = await res.json();
        populateProfileForm(data.profile);
        await refreshStatus();
        showToast("Currículo base atualizado com sucesso!");
      } catch (err) {
        showToast(`Erro ao salvar: ${err.message}`);
      }
    });

  // Modal de Configurações (Gemini API Key & SMTP)
  const dialogSettings = document.getElementById("dialog-settings");
  document
    .getElementById("btn-open-settings")
    .addEventListener("click", async () => {
      try {
        const res = await fetch("/api/settings");
        const s = await res.json();
        document.getElementById("set-key-hint").textContent = s.has_gemini_key
          ? `Chave configurada (${s.gemini_api_key_masked}). Preencha apenas se quiser substituir.`
          : "Nenhuma chave configurada ainda. Obtenha gratuitamente no Google AI Studio.";
        document.getElementById("set-smtp-host").value =
          s.smtp_host || "smtp.gmail.com";
        document.getElementById("set-smtp-port").value = String(
          s.smtp_port || 587
        );
        document.getElementById("set-smtp-user").value = s.smtp_user || "";
        const modelRadio = document.querySelector(
          `input[name="gemini_model"][value="${s.gemini_model}"]`
        );
        if (modelRadio) modelRadio.checked = true;
      } catch (err) {
        console.error(err);
      }
      dialogSettings.showModal();
    });

  document
    .getElementById("btn-cancel-settings")
    .addEventListener("click", () => {
      dialogSettings.close("cancel");
    });

  document
    .getElementById("form-settings")
    .addEventListener("submit", async (e) => {
      e.preventDefault();
      const selectedModel =
        document.querySelector('input[name="gemini_model"]:checked')?.value ||
        "gemini-3.8-flash";
      const payload = {
        gemini_api_key: document.getElementById("set-gemini-key").value,
        gemini_model: selectedModel,
        smtp_host: document.getElementById("set-smtp-host").value,
        smtp_port:
          parseInt(document.getElementById("set-smtp-port").value, 10) || 587,
        smtp_user: document.getElementById("set-smtp-user").value,
        smtp_password: document.getElementById("set-smtp-pass").value,
      };
      try {
        const res = await fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        document.getElementById("set-gemini-key").value = "";
        document.getElementById("set-smtp-pass").value = "";
        dialogSettings.close("save");
        await refreshStatus();
        showToast(data.message || "Configurações salvas!");
      } catch (err) {
        showToast(`Erro ao salvar configurações: ${err.message}`);
      }
    });

  // Inicialização
  refreshStatus();
  loadProfile();
  loadJobs();
  loadApplications();
});
