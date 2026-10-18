"""Password hashing and opaque, revocable cookie sessions. No secrets in React."""
import hashlib
import hmac
import os
import re
import secrets
import time
import threading
from collections import defaultdict, deque
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .db import User, LoginSession, Session
router=APIRouter(prefix='/api/auth',tags=['accounts'])
COOKIE='courtiq_session'
TTL=7*24*3600
_attempts=defaultdict(deque)
_lock=threading.Lock()

def rate_limit(request):
    address=request.client.host if request.client else 'unknown'
    now=time.monotonic()
    with _lock:
        queue=_attempts[address]
        while queue and queue[0]<now-60: queue.popleft()
        if len(queue)>=20: raise HTTPException(429,'Too many authentication attempts. Try again in a minute.')
        queue.append(now)

def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return salt+':'+digest

def current_user(request:Request):
    raw=request.cookies.get(COOKIE,'')
    if not raw: raise HTTPException(401,'Please sign in')
    with Session() as db:
        session=db.get(LoginSession,hashlib.sha256(raw.encode()).hexdigest())
        if not session or session.expires<time.time(): raise HTTPException(401,'Please sign in')
        user=db.get(User,session.owner_id)
        if not user: raise HTTPException(401,'Please sign in')
        return user

class Credentials(BaseModel):
    username:str=Field(min_length=3,max_length=40)
    password:str=Field(min_length=10,max_length=128)
    @field_validator('username')
    @classmethod
    def valid_name(cls,value):
        value=value.lower().strip()
        if not re.fullmatch(r'[a-z0-9_]{3,40}',value): raise ValueError('Use 3–40 letters, numbers or underscores')
        return value

def issue_session(db,user,response):
    token=secrets.token_urlsafe(32)
    db.execute(delete(LoginSession).where(LoginSession.expires<time.time()))
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),owner_id=user.id,expires=time.time()+TTL))
    response.set_cookie(COOKIE,token,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE','false').lower()=='true',max_age=TTL,path='/')
    return {'id':user.id,'username':user.username}

@router.post('/register',status_code=201)
def register(body:Credentials,request:Request,response:Response):
    rate_limit(request)
    if os.getenv('ALLOW_REGISTRATION','true').lower()!='true': raise HTTPException(403,'Registration is disabled')
    try:
        with Session.begin() as db:
            user=User(username=body.username,password_hash=hash_password(body.password));db.add(user);db.flush()
            return issue_session(db,user,response)
    except IntegrityError: raise HTTPException(409,'Username is unavailable')

@router.post('/login')
def login(body:Credentials,request:Request,response:Response):
    rate_limit(request)
    with Session.begin() as db:
        user=db.scalar(select(User).where(User.username==body.username))
        # Perform equivalent password work for unknown names.
        stored=user.password_hash if user else '0'*32+':'+'0'*128
        candidate=hash_password(body.password,stored.split(':')[0])
        if not user or not hmac.compare_digest(candidate,stored): raise HTTPException(401,'Invalid username or password')
        return issue_session(db,user,response)

@router.get('/me')
def me(request:Request):
    user=current_user(request)
    return {'id':user.id,'username':user.username}

@router.post('/logout',status_code=204)
def logout(request:Request,response:Response):
    raw=request.cookies.get(COOKIE,'')
    with Session.begin() as db: db.execute(delete(LoginSession).where(LoginSession.token_hash==hashlib.sha256(raw.encode()).hexdigest()))
    response.delete_cookie(COOKIE,path='/')
