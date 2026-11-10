# Feira Leads AI 2.0

GitHub Pages + Google OAuth + Google Drive API + FastAPI/Render + OpenAI + XLSX.

## 1. Google Cloud
1. Crie um projeto em https://console.cloud.google.com/ e habilite **Google Drive API**.
2. Configure a **OAuth consent screen** (External, modo Testing; adicione seu Gmail como usuário de teste). Solicite os escopos `openid`, `email`, `profile` e `https://www.googleapis.com/auth/drive.readonly`.
3. Crie credencial OAuth Client ID do tipo **Web application**. Adicione em **Authorized JavaScript origins** `https://inovaldo.github.io` (sem caminho). Em desenvolvimento local, adicione `http://localhost:8000`.
4. Copie o Client ID para `docs/config.js`. **O Client ID não é segredo**. Não coloque client secret no frontend.
5. ATENÇÃO: `drive.readonly` é escopo restrito do Google. Em modo Testing, só usuários de teste autorizados conseguem usar; para publicação geral, o Google pode exigir verificação e avaliação de segurança. O token de acesso é temporário e será mantido apenas na memória da aba.

## 2. Backend no Render
1. Crie um repositório GitHub com os arquivos deste ZIP.
2. Em https://dashboard.render.com crie **Web Service** a partir do repositório. Escolha runtime **Docker** e `backend` como Root Directory.
3. Configure as variáveis de ambiente:
   - `OPENAI_API_KEY` = sua chave OpenAI (segredo, apenas no Render)
   - `ALLOWED_EMAILS` = seu email Google (ou lista separada por vírgula)
   - `FRONTEND_ORIGIN` = `https://inovaldo.github.io`
4. Faça deploy e teste `https://SEU-BACKEND.onrender.com/health`.
5. Configure `API_URL` em `docs/config.js` com a URL do Render, **sem barra final**.

## 3. GitHub Pages
1. No repositório, abra Settings > Pages > Deploy from a branch.
2. Escolha `main` e pasta `/docs`.
3. Abra `https://inovaldo.github.io/NOME-DO-REPOSITORIO/`.
4. Clique **Conectar Google Drive**, navegue até a pasta, selecione os MP3, clique **Processar**, revise e baixe o Excel.

## Notas importantes
- O app **não está implantado**: o ZIP contém o código pronto para configurar e publicar.
- A listagem navega por pastas, selecionando MP3 da pasta atual. Não inclui subpastas automaticamente. Até 30 MP3 por lote, máximo 24 MB cada. O backend processa sequencialmente e o Render pode encerrar requisições longas; para lotes grandes, evoluir para fila assíncrona com progresso e autenticação persistente.
- Cada áudio pode gerar múltiplas linhas; dados ausentes ou incertos devem ser revisados. E-mails e números ditados por voz podem ser reconhecidos incorretamente.
- A API OpenAI é cobrada separadamente do ChatGPT. O serviço Render também pode ter custos.
- Segurança: o backend valida a identidade Google por chamada ao endpoint userinfo e exige allowlist `ALLOWED_EMAILS`; o token OAuth é enviado apenas ao backend configurado, via HTTPS. Use somente domínios sob seu controle. Para produção corporativa, acrescente limitação de requisições, auditoria, proteção contra abuso e avaliação de retenção de dados.
- Privacidade/LGPD: informe ao entrevistado que a conversa será gravada e processada para contato comercial; obtenha base legal adequada e defina retenção/eliminação dos dados. O áudio é enviado do Drive para o backend e para a API de transcrição; o backend não o grava permanentemente.
- Se não houver necessidade de ler a pasta inteira, uma futura versão com Google Picker + escopo `drive.file` pode reduzir permissões, mas **não** garante acesso automático a todos os arquivos já existentes em uma pasta.
