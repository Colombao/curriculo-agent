# 🚀 AutoCV & Freelance Agent

Agente inteligente em Python + Web Dashboard para **leitura de currículo**, **adaptação automática para vagas (padrão ATS)**, **busca de vagas de emprego e projetos freelance** e **automação semi-automática de envio com aprovação de 1 clique**.

---

## ✨ Funcionalidades Principais

1. **📄 Leitura e Estruturação do Currículo Base**
   - Faça upload do seu currículo em **PDF** ou cole o texto do seu currículo/LinkedIn.
   - Utiliza a **Google Gemini API (`google-genai`)** com leitura nativa de documentos PDF (`gemini-3.8-flash` ou `gemini-4-argon`) e *Structured Outputs* (`Pydantic`) para extrair dados pessoais, resumo, hard skills, soft skills, experiências, projetos e formação.

2. **🎯 Adaptação de Currículo para Vagas (Padrão ATS) + Carta/Proposta**
   - Cole a descrição ou URL de qualquer vaga ou projeto freelance.
   - O agente calcula o **Score de Compatibilidade ATS (0 a 100%)**, mostra as **palavras-chave encontradas** e os **requisitos faltantes**.
   - Reescreve seu **Resumo Profissional** e os **bullet points das suas experiências reais** destacando os termos exatos buscados pelos robôs de recrutamento (Gupy, Greenhouse, Lever, LinkedIn), **sem inventar experiências falsas**.
   - Gera automaticamente:
     - **Currículo em PDF padrão ATS** (layout limpo em coluna única salvo em `data/resumes/`).
     - **Carta de Apresentação** (para vagas CLT/PJ) ou **Proposta Comercial persuasiva** (para serviços Freelance).

3. **🔍 Radar de Vagas de Emprego & Serviços Freelance**
   - Busca oportunidades compatíveis com as habilidades do seu currículo em 3 canais:
     - **Portais de Emprego:** LinkedIn, Gupy, Indeed, Programathor.
     - **Plataformas de Freelance / Serviços:** Workana, 99Freelas, Upwork.
     - **Candidatura por E-mail Direto.**
   - Quando a `GEMINI_API_KEY` está configurada, utiliza **Google Search Grounding (`google_search` + `url_context`)** para buscar vagas reais abertas na web.
   - Possui botão **"Auto-Preparar Pacote para Top 4 Vagas"** que gera os PDFs adaptados e propostas em lote.

4. **⚡ Fila de Aprovação e Automação de Envio (1-Clique)**
   - Nenhuma candidatura é enviada no escuro: tudo vai para a **Central de Aprovação 1-Clique**.
   - Você revisa o PDF adaptado e a proposta/carta e escolhe como disparar:
     - **Robô de Navegador (Playwright):** Abre a página da vaga/projeto, preenche automaticamente os campos detectados (nome, e-mail, telefone, carta/proposta), anexa o PDF adaptado e copia o texto para sua área de transferência, aguardando apenas sua confirmação final.
     - **Envio Direto por E-mail (SMTP):** Envia o e-mail para o recrutador/cliente já com o currículo PDF adaptado em anexo.

---

## 🛠️ Pré-requisitos

- **Python 3.11+** instalado no sistema.
- **Chave de API do Google Gemini** (gratuita no [Google AI Studio](https://aistudio.google.com/apikey)).
  - *Nota:* O sistema também conta com um **Motor Local de Fallback**, permitindo testar toda a interface, geração de PDF ATS e fila de envio mesmo antes de configurar a chave da API.

---

## 🚀 Como Instalar e Executar

### Opção 1: Execução Rápida no Windows (PowerShell)

Abra o PowerShell na pasta do projeto e execute:

```powershell
.\run.ps1
```

O script criará automaticamente o ambiente virtual `.venv`, instalará as dependências e iniciará o servidor em **http://127.0.0.1:8000**.

### Opção 2: Passo a Passo Manual (Windows / Linux / macOS)

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/Colombao/curriculo-agent.git
   cd curriculo-agent
   ```

2. **Crie e ative o ambiente virtual:**
   ```powershell
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **(Opcional) Instale o navegador do Playwright para a automação de preenchimento web:**
   ```bash
   playwright install chromium
   ```

5. **Inicie o servidor:**
   ```bash
   uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```

6. **Acesse no navegador:**
   Abra [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 📖 Guia de Uso Passo a Passo (Como Usar no Dia a Dia)

### Passo 1: Configurar sua Chave do Gemini e E-mail
1. No canto superior direito do painel web, clique em **"Configurar Gemini & E-mail"**.
2. Cole sua **Google Gemini API Key** (`AIzaSy...`) e escolha o modelo (`gemini-3.8-flash` para rapidez ou `gemini-4-argon` para raciocínio profundo).
3. *(Opcional)* Preencha os dados de **SMTP** (ex: `smtp.gmail.com`, porta `587`, seu e-mail e uma [Senha de App do Google](https://myaccount.google.com/apppasswords)) caso queira disparar candidaturas por e-mail diretamente pelo painel.
4. Clique em **Salvar Configurações**.

### Passo 2: Cadastrar seu Currículo Base (Aba "4. Meu Currículo Base")
1. Vá até a aba **4. Meu Currículo Base**.
2. Faça o upload do seu currículo atual em `.pdf` (ou `.txt`) ou cole o texto completo do seu currículo e clique em **"Extrair e Atualizar Meu Perfil com IA"**.
3. Revise os campos ao lado (Nome, Título, E-mail, Telefone, LinkedIn, GitHub, Resumo, Hard Skills e Cargos Alvo) e clique em **"Salvar Alterações no Currículo Base"**.

### Passo 3: Buscar Vagas e Serviços Freelance (Aba "1. Buscar Vagas & Serviços")
1. Na aba **1. Buscar Vagas & Serviços**, escolha os canais desejados:
   - *Portais de Emprego (LinkedIn, Gupy, Indeed)*
   - *Projetos & Serviços Freelance (Workana, 99Freelas, Upwork)*
   - *Vagas com E-mail Direto*
2. Clique em **"Buscar Vagas & Serviços para Meu Currículo"**.
3. Em qualquer oportunidade encontrada, clique em **"Preparar Currículo PDF & Envio 1-Clique"** (ou use o botão **"Auto-Preparar Pacote para Top 4 Vagas"** no topo para gerar vários de uma vez).

### Passo 4: Adaptar para uma Vaga Específica (Aba "2. Adaptar Currículo para Vaga")
1. Viu uma vaga interessante no LinkedIn, Gupy ou um projeto no Workana/99Freelas? Vá na aba **2. Adaptar Currículo para Vaga**.
2. Preencha o Título, Empresa/Cliente, selecione se é **Vaga de Emprego**, **Serviço Freelance** ou **E-mail Direto**, e cole a descrição dos requisitos.
3. Clique em **"Analisar Vaga, Gerar Currículo PDF Adaptado & Colocar na Fila"**.
4. Veja imediatamente seu **Score ATS (%)**, palavras-chave destacadas, pontos de atenção e baixe o **PDF padrão ATS** gerado sob medida.

### Passo 5: Aprovar e Enviar com 1 Clique (Aba "3. Fila de Envio 1-Clique")
1. Acesse a aba **3. Fila de Envio 1-Clique**.
2. Clique em **"Aprovar & Enviar (1-Clique)"** no pacote desejado.
3. Na janela de revisão final:
   - Confira o PDF adaptado clicando no link de visualização.
   - Edite (se desejar) o assunto e a Carta de Apresentação / Proposta Comercial.
   - Escolha o método de envio (**Robô de Navegador Playwright**, **E-mail Direto SMTP com Anexo** ou **Apenas copiar proposta**) e clique em **"Aprovar e Executar Envio Agora"**.

---

## 📁 Estrutura de Pastas

```text
curriculo-agent/
├── backend/
│   ├── main.py               # API FastAPI + Servidor de arquivos estáticos
│   ├── config.py             # Caminhos e variáveis de ambiente
│   ├── database.py           # Persistência SQLite (Perfil, Vagas, Fila, Configs)
│   ├── models.py             # Schemas Pydantic (Currículo, Adaptação ATS, Vagas)
│   └── services/
│       ├── ai_agent.py       # Integração Google Gemini API + Google Search Grounding
│       ├── pdf_parser.py     # Leitura e codificação de PDF para o Gemini
│       ├── pdf_generator.py  # Gerador de Currículo PDF padrão ATS (fpdf2)
│       └── automation.py     # Envio SMTP com anexo + Robô Playwright semi-automático
├── frontend/
│   ├── index.html            # Interface Web semântica e acessível
│   ├── styles.css            # Estilização moderna (Dark Mode, Dialogs nativos)
│   └── app.js                # Lógica de interface e integração REST
├── data/
│   ├── resumes/              # Currículos PDF adaptados gerados automaticamente
│   └── uploads/              # Currículos originais enviados pelo usuário
├── .env.example              # Exemplo de configuração de variáveis de ambiente
├── requirements.txt          # Dependências Python do projeto
└── run.ps1                   # Script de inicialização rápida no Windows
```
