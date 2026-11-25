'use client';

import { useRef, useState, type ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function CardCarousel({ title, caption, cards }: {
  title: string;
  caption?: string;
  cards: ReactNode[];
}) {
  const list = useRef<HTMLUListElement>(null);
  const [index, setIndex] = useState(0);

  function goTo(target: number) {
    const track = list.current;
    if (!track) return;
    const first = track.children[0] as HTMLElement;
    const item = track.children[target] as HTMLElement | undefined;
    if (item) track.scrollTo({ left: item.offsetLeft - first.offsetLeft });
  }

  function updateIndex() {
    const track = list.current;
    if (!track || track.children.length < 2) return;
    const first = track.children[0] as HTMLElement;
    const next = track.children[1] as HTMLElement;
    const width = next.offsetLeft - first.offsetLeft;
    if (width > 0) setIndex(Math.round(track.scrollLeft / width));
  }

  return (
    <div className="discovery-carousel" aria-label={title}>
      <div className="discovery-heading">
        <h3>{title}</h3>
        {cards.length > 1 && (
          <div className="discovery-controls">
            <button type="button" aria-label="이전 카드" disabled={index <= 0} onClick={() => goTo(index - 1)}><ChevronLeft size={18} /></button>
            <span aria-live="polite">{index + 1} / {cards.length}</span>
            <button type="button" aria-label="다음 카드" disabled={index >= cards.length - 1} onClick={() => goTo(index + 1)}><ChevronRight size={18} /></button>
          </div>
        )}
      </div>
      {caption && <p className="discovery-caption">{caption}</p>}
      <ul className="discovery-track" ref={list} onScroll={updateIndex}>{cards}</ul>
    </div>
  );
}
