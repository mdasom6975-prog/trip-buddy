'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { CalendarDays, CloudSun, Download, ExternalLink, Info, Map, MapPin, RefreshCw } from 'lucide-react';
import type { Result, Slot } from '@/lib/types';
import CharacterArt from './CharacterArt';
import FestivalGallery from './FestivalGallery';

const RouteMap = dynamic(() => import('./RouteMap'), {
  ssr: false,
  loading: () => <div className="map-loading">지도를 준비하고 있어요…</div>,
});
const dayNames = ['첫째 날', '둘째 날', '셋째 날'];

type CourseActions = {
  onEdit?: (text: string) => void;
  onDownload: () => void;
  busy: boolean;
};

function PlaceCard({ slot, index, result, onEdit, busy }: {
  slot: Slot;
  index: number;
  result: Result;
  onEdit?: () => void;
  busy: boolean;
}) {
  const place = result.places[slot.id];
  const isLive = result.source === 'live';
  const image = place?.image;
  const visitInfo = [
    ['이용시간', place?.hours],
    ['휴무', place?.closure],
    ['입장료', place?.fee],
    ['주차', place?.parking],
    ['대표 메뉴', place?.main_menu],
  ].filter(([, value]) => value?.trim());
  const isSourceFact = (fact: string) =>
    fact === '정보 방금 확인' || /^정보 .+ 기준\(저장분\)$/.test(fact);
  const facts = (slot.facts ?? []).filter(fact => !isSourceFact(fact));
  const sourceFacts = (slot.facts ?? []).filter(isSourceFact);

  return (
    <article className="place-card">
      <span className="timeline-number">{index + 1}</span>
      <div className="place-top">
        <span className="slot-tag">{slot.slot}</span>
        <small>{slot.type}</small>
      </div>
      <h3>{slot.title}</h3>
      {slot.addr && <p className="place-address"><MapPin size={14} aria-hidden="true" />{slot.addr}</p>}
      {isLive && image && /^https?:\/\//.test(image) && (
        <img className="place-photo" src={image} alt={slot.title} loading="lazy" />
      )}
      {place?.overview && (
        <p className="place-intro">
          <span>{isLive ? '장소 소개 · 한국관광공사 원문 발췌' : '장소 소개 · 체험 예시'}</span>
          {place.overview}
        </p>
      )}
      {visitInfo.length > 0 && (
        <dl className="place-visit-info" aria-label="수집한 방문 정보">
          {visitInfo.map(([label, value]) => (
            <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
          ))}
        </dl>
      )}
      {facts.map((fact, index) => <p key={index} className="place-fact">{fact}</p>)}
      {slot.reason && <p className="place-reason"><strong>추천 이유</strong> {slot.reason}</p>}
      <div className="place-actions">
        {isLive && (
          <a
            href={place?.map_url || `https://map.kakao.com/link/search/${encodeURIComponent([slot.title, slot.addr].filter(Boolean).join(' '))}`}
            target="_blank"
            rel="noreferrer"
          >
            지도에서 보기 <ExternalLink size={13} aria-hidden="true" />
          </a>
        )}
        {onEdit && <button disabled={busy} onClick={onEdit}>
          <RefreshCw size={13} aria-hidden="true" /> 이 장소 바꾸기
        </button>}
      </div>
      <details className="place-details">
        <summary>장소 정보 더 보기</summary>
        {slot.access?.map(([label, values]) => (
          <p className="place-fact" key={label}>{label} · {values.join(' · ')}</p>
        ))}
        {sourceFacts.map((fact, index) => <p className="place-fact" key={index}>일정 검증 · {fact}</p>)}
        <small className="place-source">
          {isLive ? '출처 ⓒ한국관광공사' : '체험용 합성 데이터'}
          {' · 수집 정보 기준일 '}{place?.fetched || place?.modified || '확인 필요'}
        </small>
      </details>
    </article>
  );
}

function CourseResult({ result, onEdit, onDownload, busy }: CourseActions & { result: Result }) {
  const days = result.answer.days ?? [];
  const [selectedDate, setSelectedDate] = useState(days[0]?.date);
  const [view, setView] = useState<'일정' | '지도'>('일정');
  const current = days.find(day => day.date === selectedDate) ?? days[0];
  const dayIndex = days.indexOf(current);
  const dayLabel = dayNames[dayIndex] ?? `${dayIndex + 1}일차`;
  const weather = result.weather.days?.find(day => day.date === current?.date);
  const demo = result.source === 'demo';
  const showcase = result.mode === 'showcase';
  const festivals = result.festivals ?? [];
  const notices = (result.answer.notices ?? []).filter(notice =>
    festivals.length === 0 || !(
      notice.startsWith('이 기간 축제:')
      || notice.startsWith('상설 · 장기 행사 ')
      || notice === '이 기간에 등록된 축제가 없습니다.'
    )
  );

  return (
    <section className="course-result" aria-label="여행 코스">
      <div className="section-title">
        <h2>{result.request.region ? `${result.request.region} ` : ''}{days.length > 0 ? `${days.length}일 여행` : '여행 일정'}</h2>
        <button className="course-download" onClick={onDownload}>
          <Download size={17} aria-hidden="true" /> 일정 저장
        </button>
      </div>
      {demo && <p className="source-label demo"><Info size={15} aria-hidden="true" /> 체험용 합성 일정</p>}
      {showcase && (
        <p className="source-label"><Info size={15} aria-hidden="true" /> 저장된 시연 일정{result.snapshot_date && ` · 데이터 기준일 ${result.snapshot_date}`}</p>
      )}
      <div className="course-navigation">
        <div className="day-tabs" role="group" aria-label="여행 날짜">
          {days.map((day, index) => (
            <button key={day.date} aria-pressed={day.date === current?.date} onClick={() => setSelectedDate(day.date)}>
              <b>{dayNames[index] ?? `${index + 1}일차`}</b>
              <span>{day.date.slice(5).replace('-', '.')}</span>
            </button>
          ))}
        </div>
        <div className="view-tabs" role="group" aria-label="코스 보기">
          <button aria-pressed={view === '일정'} onClick={() => setView('일정')}><CalendarDays size={15} aria-hidden="true" /> 일정</button>
          <button aria-pressed={view === '지도'} onClick={() => setView('지도')}><Map size={15} aria-hidden="true" /> 지도</button>
        </div>
      </div>
      {current && (
        <>
          <p className="weather-line">
            <CloudSun size={19} aria-hidden="true" />
            {weather?.available ? `${weather.temp_min}~${weather.temp_max}℃ · 강수확률 ${weather.rain_prob}%` : '예보 확인 필요'}
            {demo && <small>체험 날씨</small>}
            {showcase && <small>저장 당시 예보</small>}
          </p>
          {weather?.indoor && result.answer.rain_reason && <p className="notice">{result.answer.rain_reason}</p>}
          {view === '지도' ? (
            <>
              <RouteMap days={[current]} />
              <p className="muted small">장소 사이의 선과 거리는 직선 기준입니다.{demo && ' 체험 좌표를 표시하고 있어요.'}</p>
              <ol className="route-stops">
                {current.slots.map(slot => (
                  <li key={slot.slot + slot.id}>
                    {slot.title}
                    {slot.leg_km != null && <small>직전 장소에서 약 {slot.leg_km}km</small>}
                  </li>
                ))}
              </ol>
            </>
          ) : (
            <div className="timeline">
              {current.slots.map((slot, index) => (
                <PlaceCard
                  key={slot.slot + slot.id}
                  slot={slot}
                  index={index}
                  result={result}
                  busy={busy}
                  onEdit={onEdit && (() => onEdit(`${dayLabel} ${slot.slot}만 다른 곳으로 바꿔 줘`))}
                />
              ))}
            </div>
          )}
        </>
      )}
      {festivals.length > 0 && <FestivalGallery key={festivals.map(event => event.id).join(',')} festivals={festivals} demo={demo} />}
      {(notices.length || result.violations.length) > 0 && (
        <details className="notices" open>
          <summary><Info size={16} aria-hidden="true" /> 여행 전 확인해 주세요</summary>
          {notices.length
            ? notices.map((notice, index) => <p key={index}>{notice}</p>)
            : <p>일부 일정은 방문 전에 장소 정보를 다시 확인해 주세요.</p>}
        </details>
      )}
      {(result.answer.cafes?.length ?? 0) > 0 && (
        <details className="backup">
          <summary>근처 카페 추천</summary>
          {result.answer.cafes?.map((place, index) => {
            const image = place.id ? result.places[place.id]?.image : undefined;
            return (
              <p key={place.id ?? index}>
                <strong>{place.title}</strong>
                {!demo && image && /^https?:\/\//i.test(image) && (
                  <img className="recommended-cafe-photo" src={image} alt={place.title || ''} loading="lazy" onError={e => { e.currentTarget.hidden = true; }} />
                )}
                {place.reason && <><br />{place.reason}</>}
                {place.addr && <><br />{place.addr}</>}
                {place.facts?.map((fact, index) => <span key={index}><br />{fact}</span>)}
                {!demo && place.title && (
                  <><br /><a
                    href={`https://map.kakao.com/link/search/${encodeURIComponent([place.title, place.addr].filter(Boolean).join(' '))}`}
                    target="_blank"
                    rel="noreferrer"
                  >지도에서 보기 ↗</a></>
                )}
              </p>
            );
          })}
        </details>
      )}
      {(result.answer.backup?.length ?? 0) > 0 && (
        <details className="backup">
          <summary>비가 오면 갈 만한 곳</summary>
          {result.answer.backup?.map((place, index) => <p key={place.id ?? index}><strong>{place.title}</strong><br />{place.reason}{showcase && place.addr && <><br />{place.addr}</>}</p>)}
        </details>
      )}
      <p className="credit">
        {result.credit}
        {!demo && <> · <a href="https://api.visitkorea.or.kr/#/useServiceGuide/2" target="_blank" rel="noreferrer">저작권 정책</a></>}
      </p>
    </section>
  );
}

export default function CourseView({ result, character, ...actions }: CourseActions & {
  result: Result | null;
  character: string;
}) {
  if (!result || result.answer.kind !== 'course') {
    return (
      <section className="course-empty">
        <CharacterArt id={character} pose="guide" />
        <h2>여행 일정</h2>
        <p>지역과 날짜를 선택하면 여기에 일정이 표시돼요.</p>
      </section>
    );
  }

  // Keep the selected day when the same itinerary receives a partial edit.
  const itinerary = JSON.stringify([result.mode === 'showcase', result.request.region, result.answer.days?.map(day => day.date)]);
  return <CourseResult key={itinerary} result={result} {...actions} />;
}
