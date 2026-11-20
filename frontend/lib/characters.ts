import type {Character} from './types';
export const characters:Character[]=[
{id:'hana',name:'하나',gender:'여성',age:'청년',mood:'호기심 많은 여행가',file:'/characters/travel-buddies-v2.png',atlas:'main',cell:0},
{id:'leo',name:'이안',gender:'남성',age:'청년',mood:'설렘을 찾는 탐험가',file:'/characters/extra-buddies.png',atlas:'extra',cell:0},
{id:'yuna',name:'유나',gender:'여성',age:'중년',mood:'일상의 쉼표를 찾는 친구',file:'/characters/extra-buddies.png',atlas:'extra',cell:1},
{id:'jun',name:'준',gender:'남성',age:'중년',mood:'여유로운 길잡이',file:'/characters/travel-buddies-v2.png',atlas:'main',cell:1},
{id:'sora',name:'소라',gender:'여성',age:'시니어',mood:'다정한 탐험가',file:'/characters/travel-buddies-v2.png',atlas:'main',cell:2},
{id:'minho',name:'민호',gender:'남성',age:'시니어',mood:'든든한 여행 친구',file:'/characters/senior-male-v1.png',atlas:'senior',cell:0},
];
export function getCharacter(id:string){return characters.find(c=>c.id===id)||characters[0]}
