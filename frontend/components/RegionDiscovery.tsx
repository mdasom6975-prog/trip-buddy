'use client';

import { Image, LoaderCircle } from 'lucide-react';
import CardCarousel from './CardCarousel';
import discovery from '@/lib/region-discovery.json';

export const regions = Object.keys(discovery) as (keyof typeof discovery)[];

function RegionCarousel({ region }: { region: keyof typeof discovery }) {
  const places = discovery[region];
  const location = region === '전남광주' ? '전남·광주' : region;

  return (
    <>
      <CardCarousel
        title={`기다리는 동안 ${location} 둘러보기`}
        caption="지역 둘러보기용 추천"
        cards={places.map(place => (
          <li key={place.id} className="discovery-card">
            <div className="discovery-photo">
              <Image size={24} aria-hidden="true" />
              <img
                src={place.image}
                alt=""
                loading="lazy"
                decoding="async"
                referrerPolicy="no-referrer"
                onError={event => { event.currentTarget.hidden = true; }}
              />
            </div>
            <div className="discovery-copy">
              <span>{place.category}</span>
              <h4>{place.title}</h4>
              <p>{place.description}</p>
            </div>
          </li>
        ))}
      />
      <p className="credit">사진 출처 ⓒ한국관광공사</p>
    </>
  );
}

export default function RegionDiscovery({ region, step }: { region: string | null; step: string }) {
  const selected = regions.find(name => name === region);
  const location = selected === '전남광주' ? '전남·광주' : selected;
  return (
    <section className="course-result course-discovery" aria-label="여행 일정 생성 중">
      <h2>{location ? `${location} 일정을 만들고 있어요` : '여행 일정을 만들고 있어요'}</h2>
      <p className="discovery-progress" role="status"><LoaderCircle className="spin" size={17} />{step || '여행 조건을 살피고 있어요'}</p>
      {selected && <RegionCarousel key={selected} region={selected} />}
    </section>
  );
}
