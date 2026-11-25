'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { CalendarDays, X } from 'lucide-react';
import type { Festival } from '@/lib/types';
import CardCarousel from './CardCarousel';

export default function FestivalGallery({ festivals, demo }: {
  festivals: Festival[];
  demo: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [selected, setSelected] = useState<Festival | null>(null);

  useEffect(() => {
    if (selected && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [selected]);

  const details = selected ? [
    ['기간', selected.period],
    ['여행 중 겹치는 날', selected.days_in_trip?.join(', ')],
    ['장소', selected.place],
    ['주소', selected.addr],
    ['요금', selected.fee],
    ['주최', selected.host],
  ].filter(([, value]) => value) : [];

  return (
    <section className="festival-gallery" aria-label="축제 정보">
      <CardCarousel
        title="축제 정보"
        caption={demo ? '체험용 축제와 장기 행사' : '여행 날짜와 겹치는 축제 및 상설·장기 행사'}
        cards={festivals.map(event => (
          <li key={event.id} className="discovery-card">
            <button type="button" className="festival-card" aria-haspopup="dialog" onClick={() => setSelected(event)}>
              <span className="festival-photo">
                <CalendarDays size={26} aria-hidden="true" />
                {/^https?:\/\//i.test(event.image) && (
                  <img src={event.image} alt="" loading="lazy" onError={e => { e.currentTarget.hidden = true; }} />
                )}
              </span>
              <span className="discovery-copy festival-card-copy">
                <span>{event.label}</span>
                <strong>{event.title}</strong>
                <span>{event.period}</span>
                <span className="festival-details-link">상세 보기</span>
              </span>
            </button>
          </li>
        ))}
      />

      <dialog ref={dialog} className="festival-dialog" aria-labelledby={titleId} onClose={() => setSelected(null)}>
        {selected && (
          <>
            <header>
              <div>
                <span className="slot-tag">{selected.label}</span>
                <h3 id={titleId}>{selected.title}</h3>
              </div>
              <form method="dialog">
                <button type="submit" className="icon-button" aria-label="축제 상세 닫기" autoFocus>
                  <X size={18} aria-hidden="true" />
                </button>
              </form>
            </header>
            <dl className="place-visit-info">
              {details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
            </dl>
            {selected.overview && <p className="place-intro"><span>{demo ? '행사 소개 · 체험 예시' : '행사 소개 · 한국관광공사 원문 발췌'}</span>{selected.overview}</p>}
            {selected.program && <p className="place-intro"><span>프로그램</span>{selected.program}</p>}
            {!demo && (
              <>
                <div className="place-actions">
                  {/^https?:\/\//i.test(selected.map) && <a href={selected.map} target="_blank" rel="noreferrer">지도에서 보기 ↗</a>}
                  {/^https?:\/\//i.test(selected.homepage) && <a href={selected.homepage} target="_blank" rel="noreferrer">공식 홈페이지 ↗</a>}
                </div>
                <p className="credit">출처 ⓒ한국관광공사{selected.modified && ` · 정보 기준일 ${selected.modified}`}</p>
              </>
            )}
          </>
        )}
      </dialog>
    </section>
  );
}
