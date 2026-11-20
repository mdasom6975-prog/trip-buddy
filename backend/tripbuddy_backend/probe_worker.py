"""Real graph/runtime with fake retrieval, LLM, weather and detail services.

Executed from the engine root in its Python environment. All socket connects
blocked; no source data, model, live service or production checkpoint is used.
"""
import contextlib
import io
import json
import socket
import sys

network_attempts = 0
sequence = 0
protocol = sys.stdout


def block_network(*args, **kwargs):
    global network_attempts
    network_attempts += 1
    raise RuntimeError("network_disabled_in_probe")


socket.socket.connect = block_network
socket.socket.connect_ex = block_network
socket.create_connection = block_network


def emit(kind, **data):
    global sequence
    sequence += 1
    protocol.write(json.dumps({"id": sequence, "type": kind, **data}, ensure_ascii=False) + "\n")
    protocol.flush()


def main():
    scenario = json.load(sys.stdin)["scenario"]
    with contextlib.redirect_stdout(io.StringIO()):
        import config
        from graph.runtime import make_graph
        from graph.schemas import Course, EditedCourse, Grade, NewQuery, Route, TripRequest
        from harness.trace import Trace
        from langgraph.checkpoint.memory import InMemorySaver

        today, travel_date = "2026-11-19", "2026-11-21"
        places = [{"id": f"fixture-{prefix}{n}", "title": f"테스트 전용 {prefix}{n}",
            "region": "강릉", "type": type_, "addr": "강원특별자치도 강릉시 테스트로",
            "lat": 37.75, "lon": 128.89 + n * 0.001, "overview": "연결 시험용 합성 장소입니다.",
            "rest_status": "always_open", "rest_weekdays": [], "rest_nth": [], "rest_note": False,
            "fetched": today, "modified": today, "is_cafe": False, "access": {}, "pet": {}}
            for prefix, type_, count in (("s", "관광지", 4), ("f", "음식점", 3)) for n in range(count)]

        class FixtureRetriever:
            def __init__(self):
                self.places = places

            def search(self, query, *, types=None, **kwargs):
                if scenario == "failure":
                    raise RuntimeError("fixture_search_failure")
                picked = [] if scenario == "abstain" else [p for p in places if p["type"] in (types or [])]
                return {"ok": True, "results": [{"id": p["id"], "score": 1.0} for p in picked], "took_ms": 0}

        turn = 0

        def llm(system, user, schema):
            if schema is TripRequest:
                if scenario == "clarification":
                    return TripRequest(start_date=travel_date) if turn else TripRequest(region="강릉", days=1)
                return TripRequest(region="강릉", days=1, start_date=travel_date)
            if schema is Grade:
                return Grade(relevant_ids=[p["id"] for p in places])
            if schema is NewQuery:
                return NewQuery(query="강릉")
            if schema is Route:
                return Route(mode="edit")
            if schema in (Course, EditedCourse):
                ids = ["fixture-s0", "fixture-f2" if turn else "fixture-f0", "fixture-s1", "fixture-s2", "fixture-f1"]
                return schema.model_validate({"days": [{"date": travel_date, "slots": [
                    {"slot": name, "content_id": cid, "reason": "합성 데이터 기반 연결 시험입니다."}
                    for name, cid in zip(config.COURSE_SLOTS, ids)]}]})
            raise AssertionError("unexpected_schema")

        def weather(lat, lon, start, end):
            return {"daily": {"time": [travel_date], "temperature_2m_max": [15], "temperature_2m_min": [8],
                "precipitation_probability_max": [10], "snowfall_sum": [0]}}

        def detail(operation, params):
            return {"ok": False, "reason": "offline_fixture"}

        emit("started", source="fixture", scenario=scenario)
        graph = make_graph(FixtureRetriever(), Trace(save=False), llm=llm, checkpointer=InMemorySaver(),
                           today=today, weather_fetch=weather, detail_fetch=detail)
        cfg = {"configurable": {"thread_id": "offline-probe"}}
        messages = ["강릉 하루 여행"]
        if scenario == "clarification":
            messages.append("11월 21일 출발")
        if scenario == "edit":
            messages.append("점심만 다른 식당으로 바꿔 주세요")
        answers, states = [], []
        for turn, message in enumerate(messages):
            final = {}
            for mode, chunk in graph.stream({"message": message}, cfg, stream_mode=["updates", "values"]):
                if mode == "values":
                    final = chunk
                else:
                    for node in chunk:
                        emit("progress", turn=turn + 1, node=node)
            answer = final.get("answer", {})
            if answer.get("kind") not in {"ask_back", "abstain", "course", "error"}:
                raise RuntimeError("missing_answer")
            answers.append(answer)
            states.append({"mode": final.get("mode"), "request": final.get("request"),
                "violations": final.get("violations", []), "retries": final.get("retries", {})})
            emit("turn_completed", turn=turn + 1, answer=answer)
        emit("completed", source="fixture", scenario=scenario, answers=answers, states=states,
             network_attempts=network_attempts, streamlit_imported="streamlit" in sys.modules, persistent_storage=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit("failed", code="probe_failed", network_attempts=network_attempts)
