import os
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from urllib.parse import urlparse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from .db import Session, Build, Chunk, Chat, Run, init_db
from .pipeline import ingest
from .rag import answer
from .auth import router as auth_router, current_user
from pathlib import Path

@asynccontextmanager
async def lifespan(app):
    init_db()
    # Refresh the validated snapshot so upgrades cannot retain the demo corpus.
    ingest()
    yield

app = FastAPI(title='CourtIQ', version='1.1.0', lifespan=lifespan)
app.include_router(auth_router)
@app.middleware('http')
async def same_origin(request:Request, call_next):
    origin=request.headers.get('origin')
    if origin and request.method not in ('GET','HEAD','OPTIONS'):
        allowed=set(os.getenv('ALLOWED_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(','))
        own_origin=str(request.base_url).rstrip('/')
        if origin != own_origin and origin not in allowed:
            return JSONResponse({'detail':'Cross-origin write rejected'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    return response
ATTRS = {'Three-point','Mid-range','Pass accuracy','Ball handle','Driving dunk','Perimeter defense','Speed','Stamina'}
class BuildIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    position: Literal['PG','SG','SF','PF','C']
    height: str = Field(min_length=1, max_length=20)
    style: str = Field(max_length=300)
    attributes: dict[str, int]
    @field_validator('attributes')
    @classmethod
    def valid_attributes(cls, values):
        if set(values) != ATTRS or any(not 25 <= x <= 99 for x in values.values()):
            raise ValueError('Provide all eight supported attributes, each 25–99. These are display ranges, not verified build caps.')
        return values
    @field_validator('name','height')
    @classmethod
    def not_blank(cls, value):
        if not value.strip(): raise ValueError('Must not be blank')
        return value.strip()
class Question(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    build_id: int | None = None
    patch: str | None = Field(default=None, max_length=60)
    @field_validator('question')
    @classmethod
    def not_blank(cls, value):
        if not value.strip(): raise ValueError('Question cannot be blank')
        return value.strip()

def serialize_build(b): return {'id':b.id,'name':b.name,'position':b.position,'height':b.height,'style':b.style,'attributes':b.attributes}
@app.get('/api/health')
def health():
    with Session() as db: db.execute(select(1))
    return {'status':'healthy','mode':'llm' if os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL') else 'demo'}
@app.get('/api/builds')
def builds(user=Depends(current_user)):
    with Session() as db: return [serialize_build(b) for b in db.scalars(select(Build).where(Build.owner_id==user.id).order_by(Build.id.desc()))]
@app.post('/api/builds', status_code=201)
def create_build(data: BuildIn,user=Depends(current_user)):
    with Session.begin() as db:
        b = Build(owner_id=user.id,**data.model_dump()); db.add(b); db.flush(); return serialize_build(b)
@app.put('/api/builds/{identifier}')
def update_build(identifier:int, data:BuildIn,user=Depends(current_user)):
    with Session.begin() as db:
        b=db.get(Build,identifier)
        if not b or b.owner_id!=user.id: raise HTTPException(404,'Build not found')
        for key,value in data.model_dump().items(): setattr(b,key,value)
        return serialize_build(b)
@app.delete('/api/builds/{identifier}',status_code=204)
def delete_build(identifier:int,user=Depends(current_user)):
    with Session.begin() as db:
        b=db.get(Build,identifier)
        if not b or b.owner_id!=user.id: raise HTTPException(404,'Build not found')
        db.delete(b)
@app.get('/api/sources')
def sources():
    with Session() as db:
        rows=list(db.scalars(select(Chunk).order_by(Chunk.title)))
        run=db.scalar(select(Run).order_by(Run.id.desc()).limit(1))
        documents={c.source:{'source':c.source,'title':c.title,'patch':c.patch,'url':c.url,'sample':c.sample} for c in rows}
        return {'documents':list(documents.values()),'chunks':len(rows),'last_run':run.summary if run else None}
@app.post('/api/chat')
def chat(data:Question,user=Depends(current_user)):
    with Session.begin() as db:
        b=db.get(Build,data.build_id) if data.build_id else None
        if data.build_id and (not b or b.owner_id!=user.id): raise HTTPException(404,'Build not found')
        recent=list(db.scalars(select(Chat).where(Chat.owner_id==user.id).order_by(Chat.id.desc()).limit(20)))
        context=[{'question':c.question} for c in reversed(recent)
                 if c.answer.get('context_build_id')==data.build_id and c.answer.get('context_patch')==data.patch][-4:]
        result=answer(db,data.question,serialize_build(b) if b else None,data.patch,context)
        result.update(context_build_id=data.build_id,context_patch=data.patch)
        db.add(Chat(owner_id=user.id,question=data.question,answer=result))
        return result
@app.get('/api/history')
def history(user=Depends(current_user)):
    with Session() as db:
        rows=list(db.scalars(select(Chat).where(Chat.owner_id==user.id).order_by(Chat.id.desc()).limit(20)))
        return [{'id':r.id,'question':r.question,**r.answer} for r in reversed(rows)]
@app.delete('/api/history',status_code=204)
def clear_history(user=Depends(current_user)):
    from sqlalchemy import delete
    with Session.begin() as db: db.execute(delete(Chat).where(Chat.owner_id==user.id))

# Serve the compiled React app in the Docker image (API routes remain first).
web=Path(os.getenv('WEB_DIST','../frontend/dist'))
if web.is_dir(): app.mount('/',StaticFiles(directory=web,html=True),name='web')
