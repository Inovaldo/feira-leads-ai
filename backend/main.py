import os, io, json, tempfile
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI
import xlsxwriter

app = FastAPI(title='Feira Leads AI')
origin = os.environ.get('FRONTEND_ORIGIN', 'http://localhost:8000').rstrip('/')
app.add_middleware(CORSMiddleware, allow_origins=[origin], allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['Authorization','Content-Type'])
client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
allowed = {x.strip().lower() for x in os.environ.get('ALLOWED_EMAILS','').split(',') if x.strip()}

async def google_request(token, url, params=None):
    async with httpx.AsyncClient(timeout=90) as h:
        r = await h.get(url, params=params, headers={'Authorization':f'Bearer {token}'})
    if r.status_code >= 400: raise HTTPException(400, f'Google API: {r.status_code}: {r.text[:180]}')
    return r

async def verify(auth):
    if not auth or not auth.startswith('Bearer '): raise HTTPException(401, 'Login Google necessário')
    token = auth[7:]
    r = await google_request(token, 'https://www.googleapis.com/oauth2/v3/userinfo')
    info = r.json()
    if not info.get('email_verified'): raise HTTPException(403, 'E-mail não verificado')
    if not allowed: raise HTTPException(503, 'Configure ALLOWED_EMAILS no servidor')
    if info.get('email','').lower() not in allowed: raise HTTPException(403, 'Conta não autorizada')
    return token

class FolderRequest(BaseModel):
    folder_id: str = 'root'
    page_token: Optional[str] = None

class ProcessRequest(BaseModel):
    file_ids: list[str]

class Lead(BaseModel):
    nome: str = ''
    empresa: str = ''
    equipamento: str = ''
    email: str = ''
    telefone: str = ''
    observacoes: str = ''
    revisao: str = ''
    arquivo: str = ''

class ExportRequest(BaseModel):
    leads: list[Lead]

@app.get('/health')
async def health(): return {'ok': True}

@app.post('/drive/list')
async def drive_list(req: FolderRequest, authorization: Optional[str] = Header(None)):
    token = await verify(authorization)
    folder = req.folder_id.replace("'", "\\'")
    q = f"'{folder}' in parents and trashed = false and (mimeType = 'application/vnd.google-apps.folder' or mimeType = 'audio/mpeg' or mimeType = 'audio/mp3' or name contains '.MP3' or name contains '.mp4' or name contains '.MP4' or name contains '.m4a' or name contains '.M4A' or name contains '.MP3')"
    params = {'q':q,'fields':'nextPageToken,files(id,name,mimeType,size)','pageSize':1000,'orderBy':'folder,name'}
    if req.page_token: params['pageToken']=req.page_token
    r = await google_request(token, 'https://www.googleapis.com/drive/v3/files', params)
    return r.json()

PROMPT = '''Extraia os visitantes do texto transcrito de uma gravação de feira comercial. Responda APENAS JSON válido no formato {"visitantes":[{"nome":"","empresa":"","equipamento":"","email":"","telefone":"","observacoes":"","revisao":""}]}. Cada pessoa citada como visitante é uma linha, inclusive quando houver várias no mesmo áudio. Compartilhe empresa/equipamento entre pessoas somente quando isso for explicitamente indicado. Nunca invente dados. Quando houver incerteza em nome, e-mail, telefone ou associação de dados, deixe o valor mais seguro possível e explique em revisao. Se não houver visitantes, retorne lista vazia. Preserve a grafia de e-mails falados quando inequívoca.'''

@app.post('/process')
async def process(req: ProcessRequest, authorization: Optional[str] = Header(None)):
    token = await verify(authorization)
    if not 1 <= len(req.file_ids) <= 30: raise HTTPException(400, 'Selecione de 1 a 30 MP3 por lote')
    leads, errors = [], []
    for file_id in req.file_ids:
        try:
            meta = (await google_request(token, f'https://www.googleapis.com/drive/v3/files/{file_id}', {'fields':'id,name,mimeType,size'})).json()
            name = meta.get('name','')
            if not name.lower().endswith(('.mp3', '.mp4')): raise ValueError('Somente arquivos MP3 ou MP4')
            if int(meta.get('size',0)) > 24 * 1024 * 1024: raise ValueError('MP3 acima de 24 MB; divida o áudio')
            audio = (await google_request(token, f'https://www.googleapis.com/drive/v3/files/{file_id}', {'alt':'media'})).content
            if len(audio) > 24 * 1024 * 1024: raise ValueError('Arquivo muito grande')
            mime_type = 'video/mp4' if name.lower().endswith('.mp4') else 'audio/mpeg'
            transcription = await client.audio.transcriptions.create(model='gpt-4o-mini-transcribe', file=(name, audio, mime_type), language='pt')
            response = await client.chat.completions.create(model='gpt-4o-mini', temperature=0, response_format={'type':'json_object'}, messages=[{'role':'system','content':PROMPT},{'role':'user','content':transcription.text}])
            data = json.loads(response.choices[0].message.content)
            for item in data.get('visitantes',[]):
                item['arquivo'] = name
                leads.append(Lead(**item).model_dump())
        except Exception as exc:
            errors.append({'arquivo':file_id,'erro':str(exc)[:250]})
    return {'leads':leads,'errors':errors}

@app.post('/export')
async def export(req: ExportRequest, authorization: Optional[str] = Header(None)):
    await verify(authorization)
    from fastapi.responses import Response
    buf = io.BytesIO()
    workbook = xlsxwriter.Workbook(buf, {'in_memory':True})
    ws = workbook.add_worksheet('Visitantes')
    headers = ['Nome','Empresa','Equipamento de interesse','E-mail','Telefone','Observações','Revisão necessária','Arquivo de origem']
    header_fmt = workbook.add_format({'bold':True,'font_color':'white','bg_color':'#17324D','border':0})
    text_fmt = workbook.add_format({'text_wrap':True,'valign':'top'})
    for c,h in enumerate(headers): ws.write(0,c,h,header_fmt)
    fields = ['nome','empresa','equipamento','email','telefone','observacoes','revisao','arquivo']
    for row,lead in enumerate(req.leads,1):
        for c,key in enumerate(fields): ws.write_string(row,c,str(getattr(lead,key) or ''),text_fmt)
    for i,w in enumerate([26,26,34,34,22,45,45,32]): ws.set_column(i,i,w)
    ws.freeze_panes(1,0)
    if req.leads: ws.autofilter(0,0,len(req.leads),len(headers)-1)
    workbook.close()
    return Response(buf.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="feira-leads.xlsx"'})
