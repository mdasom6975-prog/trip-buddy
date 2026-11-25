"""Persistent engine process: owns retrieval models, checkpoints and graph execution."""
import contextlib
import copy
from datetime import datetime, timedelta
import io
import json
import os
from pathlib import Path
import re
import runpy
import socket
import sys
from zoneinfo import ZoneInfo

OUT = sys.stdout
MODE = os.environ.get('TRIPBUDDY_MODE', 'demo')
DATA = Path(os.environ['TRIPBUDDY_DATA_DIR'])


def emit(kind, **payload):
    OUT.write(json.dumps({'type': kind, **payload}, ensure_ascii=False) + '\n')
    OUT.flush()


if MODE == 'demo':
    def offline(*args, **kwargs):
        raise RuntimeError('demo_network_disabled')
    socket.socket.connect = offline
    socket.socket.connect_ex = offline
    socket.create_connection = offline


def main():
    with contextlib.redirect_stdout(io.StringIO()):
        import config
        from graph.runtime import make_graph, open_checkpointer
        from graph.schemas import TripRequest, Grade, NewQuery, Route, Course, EditedCourse
        from graph.present import excerpt, export_markdown, festival_cards
        from harness.trace import Trace
        from langgraph.checkpoint.memory import InMemorySaver

        DATA.mkdir(parents=True, exist_ok=True)
        provider = os.environ.get('TRIPBUDDY_PROVIDER') or config.LLM_PROVIDER
        if provider not in config.MODELS:
            raise RuntimeError('unsupported_provider')
        if MODE == 'live':
            if os.environ.get('TRIPBUDDY_ALLOW_PAID') != '1':
                raise RuntimeError('paid_mode_not_enabled')
            from rag.retriever import Retriever
            retriever = Retriever.from_file(index_dir=DATA / 'index')
            saver = open_checkpointer(str(DATA / 'chat.sqlite'))
        else:
            saver = InMemorySaver()
        previous = {}
        emit('ready', mode=MODE)
        for line in sys.stdin:
            try:
                payload = json.loads(line)
                session, message = payload['session_id'], payload['message']
                if payload.get('command') == 'forget':
                    previous.pop(session, None)
                    saver.delete_thread(session)
                    emit('forgotten')
                    continue
                today = datetime.now(ZoneInfo('Asia/Seoul')).date()
                old = previous.get(session, {})
                parsed = {'region': next((r for r in config.REGIONS if r in message), None),
                          'days': None, 'start_date': None}
                for city, region in [('전주','전북'),('군산','전북'),('여수','전남광주'),('광주','전남광주')]:
                    if city in message:
                        parsed.update(region=region, place=city)
                if match := re.search(r'(\d+)박\s*(\d+)일', message):
                    parsed['days'] = int(match[2])
                elif match := re.search(r'(\d+)일\s*(?:여행|일정|동안)', message):
                    parsed['days'] = int(match[1])
                elif '당일' in message:
                    parsed['days'] = 1
                if match := re.search(r'\d{4}-\d{2}-\d{2}', message):
                    parsed['start_date'] = match[0]
                elif match := re.search(r'(\d+)월\s*(\d+)일', message):
                    parsed['start_date'] = f'{today.year}-{int(match[1]):02}-{int(match[2]):02}'
                elif '내일' in message:
                    parsed['start_date'] = (today + timedelta(days=1)).isoformat()
                raw = {k:v for k,v in parsed.items() if v is not None}
                effective = {**(old.get('request') or {}), **raw}
                region = effective.get('region') or '강릉'
                coords = {'강릉': (37.75,128.89),'서울': (37.57,126.98),'부산': (35.16,129.06),
                          '제주': (33.45,126.53),'전북': (35.82,127.14),'전남광주': (35.15,126.85)}
                lat, lon = coords[region]
                places = [{
                    'id': f'demo-{prefix}{n}', 'title': f'체험용 {label} {n+1}',
                    'region': region, 'type': type_, 'addr': f'{region} 체험 구역 (실제 장소 아님)',
                    'lat': lat + (n % 3) * .002, 'lon': lon + (n // 3) * .002,
                    'overview': 'API 연결을 확인하기 위한 합성 장소입니다. 실제 방문 장소가 아닙니다.',
                    'hours_text': '09:00~18:00 (체험 예시)', 'parking': '주차 가능 (체험 예시)',
                    'modified': today.isoformat(), 'fetched': today.isoformat(),
                    'rest_status': 'always_open','rest_weekdays': [],'rest_nth': [],'rest_note': False,
                    'is_cafe': prefix == 'c', 'access': {}, 'pet': {},
                } for prefix,label,type_,count in [('s','산책 공간','관광지',10),('f','식당','음식점',8),
                                                   ('i','실내 공간','문화시설',3),('c','카페','음식점',4)] for n in range(count)]

                for kind, duration in (('축제', 7), ('장기 행사', 90)):
                    places.append({
                        'id': f'demo-event-{duration}', 'title': f'체험용 {kind}',
                        'region': region, 'type': config.DETAIL_TYPES['15'],
                        'addr': f'{region} 체험 구역 (실제 장소 아님)', 'lat': lat, 'lon': lon,
                        'overview': '축제 정보 화면을 보여주기 위한 합성 행사입니다.',
                        'extra': {
                            'event_start': today.strftime('%Y%m%d'),
                            'event_end': (today + timedelta(days=duration - 1)).strftime('%Y%m%d'),
                            'event_place': '체험용 행사장',
                            'program': '체험용 전시와 공연',
                        },
                    })

                class FakeRetriever:
                    def __init__(self):
                        self.places = places
                    def search(self, query, *, types=None, **kwargs):
                        return {'ok': True, 'results': [{'id':p['id'],'score':1.0} for p in places if p['type'] in (types or [])], 'took_ms':0}

                def fake_llm(system, user, schema):
                    if schema is TripRequest:
                        return TripRequest(**raw)
                    if schema is Grade:
                        return Grade(relevant_ids=[p['id'] for p in places])
                    if schema is NewQuery:
                        return NewQuery(query=region)
                    if schema is Route:
                        return Route(mode='edit' if any(t in message for t in ['바꿔','교체','수정','빼 줘']) else 'new')
                    if schema is EditedCourse:
                        course = copy.deepcopy(old['course'])
                        day_index = 1 if '둘째' in message and len(course['days']) > 1 else 0
                        slot_name = next((s for s in config.COURSE_SLOTS if s in message), '점심')
                        target = next(s for s in course['days'][day_index]['slots'] if s['slot'] == slot_name)
                        used = {s['content_id'] for d in course['days'] for s in d['slots']}
                        kind = 'f' if slot_name in ['점심','저녁'] else 's'
                        target['content_id'] = next(p['id'] for p in places if p['id'].startswith(f'demo-{kind}') and p['id'] not in used)
                        target['reason'] = '수정 요청을 처리한 합성 장소입니다.'
                        return EditedCourse.model_validate(course)
                    if schema is Course:
                        start = datetime.strptime(effective['start_date'], '%Y-%m-%d').date()
                        days = []
                        for i in range(effective['days']):
                            ids = [f'demo-s{i*3}',f'demo-f{i*2}',f'demo-s{i*3+1}',f'demo-s{i*3+2}',f'demo-f{i*2+1}']
                            days.append({'date': (start+timedelta(days=i)).isoformat(), 'slots': [
                                {'slot':s,'content_id':cid,'reason':'여행 흐름을 확인하는 체험용 일정입니다.'}
                                for s,cid in zip(config.COURSE_SLOTS,ids)]})
                        return Course.model_validate({
                            'days': days,
                            'backup': [{'content_id': 'demo-i0', 'reason': '실내 대안 UI 확인용입니다.'}],
                            'cafes': [
                                {'content_id': 'demo-c0', 'reason': '일정 중 쉬어 가는 체험용 카페입니다.'},
                                {'content_id': 'demo-c1', 'reason': '주변 카페 추천을 확인하는 체험용 장소입니다.'},
                            ],
                        })
                    raise RuntimeError('unknown_schema')

                def fake_weather(lat, lon, start, end):
                    begin, finish = datetime.fromisoformat(start).date(), datetime.fromisoformat(end).date()
                    dates = [(begin+timedelta(days=i)).isoformat() for i in range((finish-begin).days+1)]
                    return {'daily':{'time':dates,'temperature_2m_max':[18]*len(dates),'temperature_2m_min':[10]*len(dates),
                                      'precipitation_probability_max':[20]*len(dates),'snowfall_sum':[0]*len(dates)}}

                usage = []
                guarded_llm = None
                if MODE == 'live':
                    from graph.llm import make_llm
                if MODE == 'live':
                    guard_type = runpy.run_path(str(Path(__file__).with_name('provider_errors.py')))['ProviderGuard']
                    guarded_llm = guard_type(make_llm(provider,on_usage=usage.append))
                kwargs = {'provider':provider,'llm':guarded_llm} if MODE == 'live' else {'llm':fake_llm,'weather_fetch':fake_weather,
                    'detail_fetch':lambda *a,**k:{'ok':False,'reason':'demo_fixture'}}
                active_retriever = retriever if MODE == 'live' else FakeRetriever()
                trace = Trace(base_dir=DATA / 'runs', save=MODE == 'live')
                graph = make_graph(active_retriever, trace, checkpointer=saver, today=today.isoformat(), **kwargs)
                final = {}
                emit('started')
                for mode, chunk in graph.stream({'message':message}, {'configurable':{'thread_id':session}}, stream_mode=['updates','values']):
                    if mode == 'values':
                        final = chunk
                    else:
                        for node, update in chunk.items():
                            progress = {'node': node}
                            if node == 'route' and update:
                                progress['operation'] = update.get('mode')
                            elif node == 'parse_request' and update:
                                progress['region'] = (update.get('request') or {}).get('region')
                            emit('progress', **progress)
                if guarded_llm and guarded_llm.failure:
                    emit('failed', code=guarded_llm.failure)
                    continue
                previous[session] = final
                answer = final.get('answer') or {'kind':'error','text':'코스를 만들지 못했습니다.'}
                place_lookup = {p['id']:p for p in active_retriever.places}
                selected_ids = {s['id'] for d in answer.get('days',[]) for s in d['slots']}
                selected_ids.update(p['id'] for p in answer.get('backup',[])+answer.get('cafes',[]))
                metadata = {}
                rechecked = final.get('rechecked') or {}
                for cid in selected_ids:
                    stored = place_lookup.get(cid)
                    checked = rechecked.get(cid) or {}
                    if stored is None or checked.get('withdrawn'):
                        continue
                    extra = stored.get('extra') or {}
                    metadata[cid] = {
                        **{key: stored.get(key) for key in ('title', 'image', 'modified', 'fetched', 'lat', 'lon')},
                        'id': cid,
                        'overview': excerpt(stored.get('overview'), 220),
                        'hours': stored.get('hours_text'),
                        'closure': stored.get('rest_text'),
                        'parking': stored.get('parking'),
                        'fee': extra.get('fee'),
                        'main_menu': extra.get('menu_main'),
                    }
                festival_data = final.get('festivals') or {}
                # The original gallery caps a single batch. Keep both groups and all matching events.
                events = []
                if answer['kind'] == 'course':
                    for group in ('items', 'long_running'):
                        records = festival_data.get(group) or []
                        for start in range(0, len(records), config.GALLERY_MAX):
                            events.extend(festival_cards({group: records[start:start + config.GALLERY_MAX]}, place_lookup))
                result = {'answer':answer, 'request':final.get('request',{}),'weather':final.get('weather',{}),
                    'festivals':events,
                    'violations':final.get('violations',[]),'mode':final.get('mode'),'source':MODE,
                    'places':metadata, 'usage':usage, 'provider':provider if MODE=='live' else 'fixture',
                    'model':config.MODELS[provider] if MODE=='live' else 'fixture', 'credit':'출처 : ⓒ한국관광공사' if MODE=='live' else '합성 데이터 · 실제 여행 정보 아님',
                    'markdown': export_markdown(final,place_lookup,today.isoformat()) if answer['kind']=='course' and MODE=='live' else
                        ('# TripBuddy 체험 일정\n\n합성 데이터 · 실제 여행 정보가 아닙니다.\n\n'+answer.get('text',''))}
                emit('completed', result=result)
            except Exception:
                emit('failed', code='engine_request_failed')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        emit('failed', code='engine_startup_failed')
