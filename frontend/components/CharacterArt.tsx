import {getCharacter} from '@/lib/characters';
export default function CharacterArt({id,pose='idle',className=''}:{id:string;pose?:'idle'|'guide';className?:string}){
 const c=getCharacter(id);const active=pose==='guide';
 const cols=c.atlas==='main'?3:2,rows=c.atlas==='senior'?1:2;
 const cell=c.cell+(active?(c.atlas==='main'?3:c.atlas==='extra'?2:1):0);
 return <div className={`character-art ${className}`} role="img" aria-label={`${c.age} ${c.gender} 여행 친구 ${c.name}, ${active?'안내하는':'여행을 준비하는'} 모습`} style={{backgroundImage:`url('${c.file}')`,backgroundSize:`${cols*100}% ${rows*100}%`,backgroundPosition:`${cell%cols/(cols-1)*100}% ${rows===1?0:Math.floor(cell/cols)*100}%`}}/>;
}
