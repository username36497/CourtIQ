import os
import tempfile
os.environ['DATABASE_URL']='sqlite:///'+tempfile.mktemp(suffix='.db')
os.environ.pop('OPENAI_API_KEY',None)
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.db import Session, Chunk
from app.pipeline import ingest, DEFAULT_GUIDES

@pytest.fixture
def client():
    with TestClient(app) as c:
        from app.auth import _attempts
        _attempts.clear()
        creds={'username':'testplayer','password':'test-password-123'}
        c.post('/api/auth/register',json=creds)
        assert c.post('/api/auth/login',json=creds).status_code==200
        yield c

def build_data():
    return {'name':'Gael PG','position':'PG','height':'6 foot 3','style':'Passing and shooting', 'attributes':{k:80 for k in ['Three-point','Mid-range','Pass accuracy','Ball handle','Driving dunk','Perimeter defense','Speed','Stamina']}}

def test_build_lifecycle_and_invalid_rating(client):
    body=build_data()
    made=client.post('/api/builds',json=body)
    assert made.status_code==201
    identifier=made.json()['id']
    body['name']='Updated PG'
    assert client.put(f'/api/builds/{identifier}',json=body).json()['name']=='Updated PG'
    assert any(b['id']==identifier for b in client.get('/api/builds').json())
    body['attributes']['Speed']=100
    assert client.post('/api/builds',json=body).status_code==422
    assert client.delete(f'/api/builds/{identifier}').status_code==204
    assert client.put(f'/api/builds/{identifier}',json=body).status_code==422

def test_source_backed_answer_and_history(client):
    result=client.post('/api/chat',json={'question':'How do badge tokens and progression work?'}).json()
    assert result['mode']=='demo'
    assert any(c['source']=='official-badge-progression' for c in result['citations'])
    assert not result['sample_sources'] and all(c['url'].startswith('https://newsroom.2k.com/') for c in result['citations'])
    assert len(client.get('/api/history').json())>=1
    assert client.delete('/api/history').status_code==204
    assert client.get('/api/history').json()==[]

def test_unknown_and_patch_filter_abstain(client):
    for body in [{'question':'Explain quantum entanglement'},{'question':'badge tokens and progression','patch':'nonexistent'}]:
        result=client.post('/api/chat',json=body).json()
        assert result['abstained'] and not result['citations']
    assert client.post('/api/chat',json={'question':'   '}).status_code==422
    assert client.post('/api/chat',json={'question':'badge tokens','build_id':999999}).status_code==404

def test_ingestion_idempotent_and_atomic(client,tmp_path):
    first=ingest()
    with Session() as db: ids=list(db.scalars(select(Chunk.id)))
    assert ingest()==first
    with Session() as db: assert list(db.scalars(select(Chunk.id)))==ids
    good=json.loads(next(DEFAULT_GUIDES.glob('*.json')).read_text())
    (tmp_path/'a.json').write_text(json.dumps(good))
    (tmp_path/'b.json').write_text('{broken')
    with pytest.raises(ValueError): ingest(tmp_path)
    with Session() as db: assert db.scalar(select(func.count()).select_from(Chunk))==first['chunks']

def test_provider_failure_is_explicit(client,monkeypatch):
    import httpx
    monkeypatch.setenv('OPENAI_API_KEY','test-not-real')
    monkeypatch.setenv('OPENAI_MODEL','configured-model')
    def fail(*args,**kwargs): raise httpx.ConnectError('offline')
    monkeypatch.setattr('app.rag.httpx.post',fail)
    result=client.post('/api/chat',json={'question':'badge tokens progression'}).json()
    assert result['mode']=='unavailable' and result['abstained']

def test_llm_rejects_invented_citation(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-not-real')
    monkeypatch.setenv('OPENAI_MODEL','configured-model')
    class Fake:
        def raise_for_status(self): pass
        def json(self): return {'output':[{'content':[{'type':'output_text','text':'Invented threshold [99]'}]}]}
    monkeypatch.setattr('app.rag.httpx.post',lambda *a,**k:Fake())
    result=client.post('/api/chat',json={'question':'badge tokens progression'}).json()
    assert result['abstained'] and result['mode']=='llm'

def test_llm_valid_response_parses_and_passes_build(client,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-not-real');monkeypatch.setenv('OPENAI_MODEL','configured-model')
    b=client.post('/api/builds',json=build_data()).json()
    class Fake:
        def raise_for_status(self): pass
        def json(self): return {'output':[{'content':[{'type':'output_text','text':'Demonstration notes suggest tracking passing opportunities [1].'}]}],'usage':{'input_tokens':100,'output_tokens':15}}
    def fake(*a,**kw):
        assert 'Gael PG' in kw['json']['input']
        assert kw['json']['store'] is False
        return Fake()
    monkeypatch.setattr('app.rag.httpx.post',fake)
    result=client.post('/api/chat',json={'question':'badge tokens progression','build_id':b['id']}).json()
    assert result['mode']=='llm' and len(result['citations'])==1
    assert result['usage']['output_tokens']==15


def test_unsupported_requirements_refuse_even_with_keyword_overlap(client):
    r=client.post('/api/chat',json={'question':'What three-point rating is required to unlock a gold shooting badge?'}).json()
    assert r['abstained'] and not r['citations']
    assert 'thresholds' in r['answer']

def test_followup_uses_history_and_patch_separation(client,monkeypatch):
    client.delete('/api/history')
    client.post('/api/chat',json={'question':'How do badge loadouts and Synergy work?'})
    r=client.post('/api/chat',json={'question':'Explain that more'}).json()
    assert any(c['source']=='official-badge-loadouts' for c in r['citations'])
    r=client.post('/api/chat',json={'question':'Explain that more','patch':'unrelated'}).json()
    assert r['abstained']

def test_startup_refreshes_sources(client):
    docs=client.get('/api/sources').json()['documents']
    assert len(docs)==7 and not any(d['sample'] for d in docs)
    assert all(d['url'] for d in docs)

def test_build_context_does_not_leak_between_builds(client):
    client.delete('/api/history')
    first=client.post('/api/builds',json=build_data()).json()['id']
    second=client.post('/api/builds',json=build_data()).json()['id']
    client.post('/api/chat',json={'question':'How do badge loadouts and Synergy work?','build_id':first})
    r=client.post('/api/chat',json={'question':'Explain that more','build_id':second}).json()
    assert r['abstained']


@pytest.mark.parametrize('question',[
 'What three-point rating unlocks a gold shooting badge?',
 'What rating do I need for a gold shooting badge?',
 'What are the requirements for a legal build?',
 'How much VC does an upgrade cost?'
])
def test_numerical_requirement_phrasings(client,question):
    assert client.post('/api/chat',json={'question':question}).json()['abstained']


def test_accounts_authorization_and_logout(client):
    from app.auth import _attempts
    _attempts.clear()
    first=client.post('/api/builds',json=build_data()).json()['id']
    client.post('/api/chat',json={'question':'How do badge tokens work?'})
    with TestClient(app) as other:
        creds={'username':'anotherplayer','password':'another-password-123'}
        other.post('/api/auth/register',json=creds)
        assert other.post('/api/auth/login',json=creds).status_code==200
        assert other.get('/api/builds').json()==[]
        assert other.get('/api/history').json()==[]
        assert other.put(f'/api/builds/{first}',json=build_data()).status_code==404
        assert other.delete(f'/api/builds/{first}').status_code==404
        assert other.post('/api/chat',json={'question':'badge tokens','build_id':first}).status_code==404
        assert other.post('/api/auth/logout').status_code==204
        assert other.get('/api/builds').status_code==401
    assert client.get('/api/builds').status_code==200

def test_cross_origin_and_bad_password(client):
    assert client.post('/api/builds',json=build_data(),headers={'Origin':'https://untrusted.example'}).status_code==403
    assert client.post('/api/auth/login',json={'username':'testplayer','password':'wrong-password-123'}).status_code==401

def test_session_revocation_and_password_storage(client):
    from app.auth import COOKIE
    from app.db import User, LoginSession
    token=client.cookies.get(COOKIE)
    with Session() as db:
        user=db.scalar(select(User).where(User.username=='testplayer'))
        assert 'test-password-123' not in user.password_hash
        assert db.get(LoginSession,token) is None
    assert client.post('/api/auth/logout').status_code==204
    client.cookies.set(COOKIE,token)
    assert client.get('/api/auth/me').status_code==401
