import asyncio
import os
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from tripbuddy_backend.server import create_app
from tripbuddy_backend.engine import Engine


class FakeEngine:
    ready=False
    runs=0
    async def start(self):self.ready=True
    async def close(self):self.ready=False
    async def run(self,sid,message):
        self.runs+=1
        yield {'type':'started'}
        await asyncio.sleep(.05)
        if message=='fail':
            yield {'type':'failed','code':'private-secret'}
            return
        yield {'type':'progress','node':'retrieve'}
        result={'answer':{'kind':'course','text':'sample','days':[]},'markdown':'# sample','source':'demo'}
        yield {'type':'completed','result':result}


def auth(session):return {'Authorization':'Bearer '+session['token']}

def finish(client,jid,headers):
    for _ in range(100):
        result=client.get('/jobs/'+jid,headers=headers).json()
        if result['status'] in ('completed','failed'):return result
        time.sleep(.01)
    raise AssertionError('job_timeout')


def test_ownership_idempotency_events_export():
    engine=FakeEngine()
    with TestClient(create_app(engine)) as c:
        assert c.get('/health').json()['ready']
        a,b=c.post('/sessions').json(),c.post('/sessions').json()
        data={'message':'course','request_id':'request-12345'}
        job=c.post(f"/sessions/{a['id']}/messages",json=data,headers=auth(a)).json()['job_id']
        assert c.post(f"/sessions/{a['id']}/messages",json=data,headers=auth(a)).json()=={'job_id':job,'duplicate':True}
        assert c.post(f"/sessions/{a['id']}/messages",json={**data,'message':'different'},headers=auth(a)).status_code==409
        assert c.get('/jobs/'+job,headers=auth(b)).status_code==404
        assert c.get('/jobs/'+job).status_code==404
        result=finish(c,job,auth(a))
        assert result['status']=='completed' and engine.runs==1
        stream=c.get(f'/jobs/{job}/events?after=1',headers=auth(a)).text
        assert 'id: 1\n' not in stream and 'event: completed' in stream
        assert 'event: queued' not in stream
        cursor=len(result['events'])
        assert c.get(f'/jobs/{job}/events',headers={**auth(a),'Last-Event-ID':str(cursor)}).text==''
        assert c.get(f'/jobs/{job}/events?after=-1',headers=auth(a)).status_code==400
        assert c.get(f"/sessions/{a['id']}/export",headers=auth(a)).text=='# sample'
        assert c.get(f"/sessions/{a['id']}/export",headers=auth(b)).status_code==404


def test_busy_validation_and_failure_recovery():
    engine=FakeEngine()
    with TestClient(create_app(engine)) as c:
        s=c.post('/sessions').json();h=auth(s);path=f"/sessions/{s['id']}/messages"
        assert c.post(path,json={'message':'   ','request_id':'valid-123'},headers=h).status_code==422
        assert c.post(path,json={'message':'x'*3001,'request_id':'valid-123'},headers=h).status_code==422
        j=c.post(path,json={'message':'fail','request_id':'failed-123'},headers=h).json()['job_id']
        assert c.post(path,json={'message':'another','request_id':'other-123'},headers=h).status_code==409
        result=finish(c,j,h)
        assert result['status']=='failed' and 'private-secret' not in str(result)
        assert c.get(f"/sessions/{s['id']}",headers=h).json()['active_job'] is None
        next_job=c.post(path,json={'message':'course','request_id':'recover-123'},headers=h).json()['job_id']
        assert finish(c,next_job,h)['status']=='completed'


def test_cors_is_limited_to_local_frontend():
    with TestClient(create_app(FakeEngine())) as c:
        allowed=c.options('/sessions',headers={'Origin':'http://127.0.0.1:5174','Access-Control-Request-Method':'POST'})
        denied=c.options('/sessions',headers={'Origin':'https://untrusted.example','Access-Control-Request-Method':'POST'})
        assert allowed.status_code==200
        assert denied.status_code==400
        assert 'access-control-allow-origin' not in denied.headers


def test_real_persistent_graph_demo_roundtrip(tmp_path):
    root=Path(os.environ.get('TRIPBUDDY_ENGINE_ROOT',str(Path(__file__).resolve().parents[3]/'tour-planner')))
    engine=Engine(root,root/'.venv/bin/python',tmp_path,'demo')
    with TestClient(create_app(engine)) as c:
        assert c.get('/health').json()['ready']
        s=c.post('/sessions').json();h=auth(s);path=f"/sessions/{s['id']}/messages"
        def send(message,rid):
            response=c.post(path,json={'message':message,'request_id':rid},headers=h)
            assert response.status_code==202,response.text
            return finish(c,response.json()['job_id'],h)
        first=send('강릉 2일 여행','first-123')
        assert first['result']['answer']['kind']=='ask_back'
        next_turn=send('내일 출발','next-12345')
        assert next_turn['status']=='completed',next_turn
        answer=next_turn['result']['answer']
        assert answer['kind']=='course' and len(answer['days'])==2
        assert any(e.get('node') == 'route' and e.get('operation') == 'new' for e in next_turn['events'])
        assert any(e.get('node') == 'parse_request' and e.get('region') == '강릉' for e in next_turn['events'])
        assert [cafe['id'] for cafe in answer['cafes']] == ['demo-c0', 'demo-c1']
        festivals = next_turn['result']['festivals']
        assert [event['label'] for event in festivals] == ['축제', '상설 · 장기 행사']
        assert all(event['days_in_trip'] == [day['date'] for day in answer['days']] for event in festivals)
        assert next_turn['result']['violations']==[]
        for day in answer['days']:
            for slot in day['slots']:
                place = next_turn['result']['places'][slot['id']]
                assert '합성 장소' in place['overview']
                assert '체험 예시' in place['hours']
        edit=send('첫째 날 점심만 바꿔 줘','edit-12345')
        assert edit['status']=='completed'
        assert any(e.get('node') == 'route' and e.get('operation') == 'edit' for e in edit['events'])
        after=edit['result']['answer']
        old=[s['id'] for d in answer['days'] for s in d['slots']]
        new=[s['id'] for d in after['days'] for s in d['slots']]
        assert [i for i,(a,b) in enumerate(zip(old,new)) if a!=b]==[1]
        assert '합성 장소' in edit['result']['places'][new[1]]['overview']
        assert '합성 데이터' in c.get(f"/sessions/{s['id']}/export",headers=h).text


def test_queue_capacity_and_sessions_are_isolated():
    class SlowEngine(FakeEngine):
        async def run(self,sid,message):
            yield {'type':'started'}
            await asyncio.sleep(10)
    with TestClient(create_app(SlowEngine())) as c:
        accepted=0;rejected=0
        for i in range(7):
            s=c.post('/sessions').json()
            response=c.post(f"/sessions/{s['id']}/messages",json={'message':'sample','request_id':f'capacity-{i}'},headers=auth(s))
            accepted+=response.status_code==202
            rejected+=response.status_code==429
        assert accepted<=5 and rejected>=2


def test_startup_failure_does_not_accept_generation():
    class BrokenEngine(FakeEngine):
        async def start(self):raise RuntimeError('secret_startup_detail')
    with TestClient(create_app(BrokenEngine())) as c:
        h=c.get('/health').json()
        assert not h['ready'] and h['error']=='engine_startup_failed'
        s=c.post('/sessions').json()
        response=c.post(f"/sessions/{s['id']}/messages",json={'message':'sample','request_id':'startup-123'},headers=auth(s))
        assert response.status_code==503
        assert 'secret_startup_detail' not in str(h)


def test_live_mode_requires_explicit_opt_in(tmp_path,monkeypatch):
    monkeypatch.setenv('TRIPBUDDY_ALLOW_PAID','0')
    root=Path(os.environ.get('TRIPBUDDY_ENGINE_ROOT',str(Path(__file__).resolve().parents[3]/'tour-planner')))
    engine=Engine(root,root/'.venv/bin/python',tmp_path,'live')
    with TestClient(create_app(engine)) as c:
        assert not c.get('/health').json()['ready']


def test_no_export_without_course_and_validation_does_not_echo_input():
    with TestClient(create_app(FakeEngine())) as c:
        s=c.post('/sessions').json();h=auth(s)
        assert c.get(f"/sessions/{s['id']}/export",headers=h).status_code==409
        bad=c.post(f"/sessions/{s['id']}/messages",headers=h,json={'message':'do-not-echo-this','request_id':'!invalid!'})
        assert bad.status_code==422 and 'do-not-echo-this' not in bad.text


def test_provider_failure_is_not_ask_back_and_does_not_restart_engine():
    class LimitedEngine(FakeEngine):
        starts=0
        async def start(self):
            self.starts+=1
            self.ready=True
        async def run(self,sid,message):
            yield {'type':'failed','code':'provider_rate_limited'}
    engine=LimitedEngine()
    with TestClient(create_app(engine)) as c:
        session=c.post('/sessions').json();headers=auth(session)
        response=c.post(f"/sessions/{session['id']}/messages",headers=headers,json={'message':'강릉 여행','request_id':'limited-123'})
        state=finish(c,response.json()['job_id'],headers)
        assert state['status']=='failed' and state['error']=='provider_rate_limited'
        assert state['result'] is None
        assert state['events'][-1]['type']=='failed'
        assert engine.starts==1
        assert c.get('/health').json()['ready']
