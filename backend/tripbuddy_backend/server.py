"""Local-only authenticated job API. Defaults to the network-blocked demo engine."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator

from .engine import Engine


class Message(BaseModel):
    message: str = Field(min_length=1,max_length=3000)
    request_id: str = Field(pattern=r'^[a-zA-Z0-9-]{8,80}$')

    @field_validator('message')
    @classmethod
    def not_blank(cls,value):
        value=value.strip()
        if not value:
            raise ValueError('blank_message')
        return value


@dataclass
class Session:
    token_hash: str
    created: float = field(default_factory=time.time)
    active: str | None = None
    requests: dict = field(default_factory=dict)
    result: dict | None = None
    messages: list = field(default_factory=list)


@dataclass
class Job:
    id: str
    session_id: str
    message: str
    status: str = 'queued'
    events: list = field(default_factory=list)
    result: dict | None = None
    error: str | None = None

    def event(self,kind,**data):
        self.events.append({'id':len(self.events)+1,'type':kind,**data})


def create_app(engine=None):
    sessions, jobs = {}, {}
    queue = asyncio.Queue(maxsize=4)
    project = Path(__file__).resolve().parents[2]
    root = Path(os.environ.get('TRIPBUDDY_ENGINE_ROOT',str(project.parent/'tour-planner'))).resolve()
    mode = os.environ.get('TRIPBUDDY_MODE','demo')
    if mode not in ('demo','live'):
        raise RuntimeError('invalid_mode')
    engine = engine or Engine(root,Path(os.environ.get('TRIPBUDDY_ENGINE_PYTHON',str(root/'.venv/bin/python'))),project/'data',mode)
    startup_error = None

    async def consume():
        while True:
            job = await queue.get()
            try:
                job.status='running'
                async for event in engine.run(job.session_id,job.message):
                    kind=event['type']
                    if kind=='completed':
                        job.result=event['result']
                        sessions[job.session_id].result=job.result
                        answer=job.result['answer']
                        text=answer.get('text','') if answer['kind']!='course' else ('말씀하신 일정을 수정했어요.' if job.result.get('mode')=='edit' else '날짜별 여행 일정이 준비됐어요.')
                        sessions[job.session_id].messages.append({'role':'assistant','text':text})
                        job.status='completed'
                        job.event('completed',result=job.result)
                    elif kind=='failed':
                        code=event.get('code')
                        if code not in {'provider_rate_limited','provider_quota_exceeded','provider_auth_failed','provider_unavailable','provider_request_rejected'}:
                            raise RuntimeError('engine_request_failed')
                        job.status='failed'
                        job.error=code
                        job.event('failed',code=code)
                        break
                    else:
                        job.event(kind,**{k:v for k,v in event.items() if k!='type'})
                if job.status not in ('completed','failed'):
                    raise RuntimeError('engine_incomplete')
            except asyncio.CancelledError:
                job.status='failed'
                job.error='server_stopped'
                job.event('failed',code=job.error)
                raise
            except Exception:
                job.status='failed'
                job.error='engine_unavailable'
                job.event('failed',code=job.error)
                # Kill and restart to avoid reading the previous request's output.
                await engine.close()
                try:
                    await engine.start()
                except Exception:
                    pass
            finally:
                if job.session_id in sessions:
                    sessions[job.session_id].active=None
                queue.task_done()

    @asynccontextmanager
    async def lifespan(app):
        nonlocal startup_error
        try:
            await engine.start()
        except Exception:
            startup_error='engine_startup_failed'
        worker=asyncio.create_task(consume())
        yield
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        await engine.close()

    app=FastAPI(title='TripBuddy API',version='0.2.0',lifespan=lifespan)
    app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5174','http://localhost:5174'],
        allow_credentials=False,allow_methods=['GET','POST','DELETE'],allow_headers=['Authorization','Content-Type','Last-Event-ID'])
    app.state.sessions=sessions
    app.state.jobs=jobs

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return PlainTextResponse('invalid_request',status_code=422)

    def own(session_id,authorization):
        session=sessions.get(session_id)
        supplied=authorization.removeprefix('Bearer ') if authorization else ''
        if not session or not secrets.compare_digest(session.token_hash,hashlib.sha256(supplied.encode()).hexdigest()):
            raise HTTPException(404,'session_not_found')
        return session

    def owned_job(job_id,authorization):
        job=jobs.get(job_id)
        if not job:
            raise HTTPException(404,'job_not_found')
        own(job.session_id,authorization)
        return job

    @app.get('/health')
    async def health():
        return {'alive':True,'ready':engine.ready,'mode':mode,'error':startup_error if not engine.ready else None}

    @app.post('/sessions',status_code=201)
    async def new_session():
        if len(sessions)>=100:
            raise HTTPException(429,'session_capacity_reached')
        sid,token=uuid4().hex,secrets.token_urlsafe(32)
        sessions[sid]=Session(hashlib.sha256(token.encode()).hexdigest())
        return {'id':sid,'token':token,'mode':mode}

    @app.get('/sessions/{session_id}')
    async def session_state(session_id:str,authorization:str|None=Header(None)):
        s=own(session_id,authorization)
        return {'id':session_id,'active_job':s.active,'result':s.result,'messages':s.messages,'mode':mode}

    @app.post('/sessions/{session_id}/messages',status_code=202)
    async def send(session_id:str,body:Message,authorization:str|None=Header(None)):
        s=own(session_id,authorization)
        if body.request_id in s.requests:
            jid,original=s.requests[body.request_id]
            if original!=body.message:
                raise HTTPException(409,'request_id_conflict')
            return {'job_id':jid,'duplicate':True}
        if not engine.ready:
            raise HTTPException(503,'engine_not_ready')
        if s.active:
            raise HTTPException(409,'session_busy')
        if len(jobs)>=300:
            raise HTTPException(429,'job_capacity_reached')
        if queue.full():
            raise HTTPException(429,'queue_full')
        job=Job(uuid4().hex,session_id,body.message)
        jobs[job.id]=job
        s.active=job.id
        s.requests[body.request_id]=(job.id,body.message)
        s.messages.append({'role':'user','text':body.message})
        job.event('queued')
        queue.put_nowait(job)
        return {'job_id':job.id,'duplicate':False}

    @app.get('/jobs/{job_id}')
    async def job_state(job_id:str,authorization:str|None=Header(None)):
        j=owned_job(job_id,authorization)
        return {'id':j.id,'status':j.status,'result':j.result,'error':j.error,'events':j.events}

    @app.get('/jobs/{job_id}/events')
    async def events(job_id:str,request:Request,after:int=0,authorization:str|None=Header(None),
                     last_event_id:str|None=Header(None)):
        j=owned_job(job_id,authorization)
        try:
            previous_id=int(last_event_id or 0)
            cursor=max(after,previous_id)
            if after<0 or previous_id<0 or cursor>len(j.events):
                raise ValueError
        except ValueError:
            raise HTTPException(400,'invalid_cursor')
        async def stream():
            nonlocal cursor
            while True:
                if await request.is_disconnected():
                    break
                while cursor<len(j.events):
                    event=j.events[cursor]
                    yield f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event,ensure_ascii=False)}\n\n"
                    cursor+=1
                if j.status in ('completed','failed'):
                    break
                yield ': heartbeat\n\n'
                await asyncio.sleep(.2)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

    @app.get('/sessions/{session_id}/export')
    async def export(session_id:str,authorization:str|None=Header(None)):
        s=own(session_id,authorization)
        if not s.result or s.result['answer']['kind']!='course':
            raise HTTPException(409,'course_not_ready')
        return PlainTextResponse(s.result['markdown'],headers={'Content-Disposition':'attachment; filename="tripbuddy-course.md"'})

    return app


app=create_app()
