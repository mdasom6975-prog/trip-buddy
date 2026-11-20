import type { Metadata } from 'next';
import './globals.css';
import 'leaflet/dist/leaflet.css';
export const metadata: Metadata={title:'TripBuddy — 나다운 여행의 시작',description:'나만의 여행 친구와 함께 만드는 국내 여행 코스'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="ko"><body>{children}</body></html>}
