import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const python=resolve(root,'backend/.venv/bin/python');
if(!existsSync(python)||!existsSync(resolve(root,'frontend/node_modules/next'))){
 console.error('먼저 README의 백엔드 가상환경 설치와 frontend npm ci를 실행해 주세요.');process.exit(1);
}
const engineRoot=process.env.TRIPBUDDY_ENGINE_ROOT||resolve(root,'../tour-planner');
const env={...process.env,NEXT_TELEMETRY_DISABLED:'1',TRIPBUDDY_ENGINE_ROOT:engineRoot,TRIPBUDDY_ENGINE_PYTHON:process.env.TRIPBUDDY_ENGINE_PYTHON||resolve(engineRoot,'.venv/bin/python'),TRIPBUDDY_MODE:process.env.TRIPBUDDY_MODE||'demo'};
if(env.TRIPBUDDY_MODE==='live'&&env.TRIPBUDDY_ALLOW_PAID!=='1'){console.error('실제 모델 모드는 비용이 발생합니다. 사용자 승인 후 TRIPBUDDY_ALLOW_PAID=1을 명시해야 합니다.');process.exit(1)}
const children=[spawn(python,['-m','uvicorn','tripbuddy_backend.server:app','--app-dir',resolve(root,'backend'),'--host','127.0.0.1','--port','8001'],{cwd:root,env,stdio:'inherit'}),spawn('npm',['run','dev'],{cwd:resolve(root,'frontend'),env,stdio:'inherit'})];
let stopping=false;function stop(code=0){if(stopping)return;stopping=true;for(const child of children)child.kill('SIGTERM');setTimeout(()=>process.exit(code),1200)}
for(const child of children){child.on('error',e=>{console.error(e.message);stop(1)});child.on('exit',code=>{if(!stopping)stop(code||0)})}process.on('SIGINT',()=>stop());process.on('SIGTERM',()=>stop());
console.log('TripBuddy: http://127.0.0.1:5174 · API: http://127.0.0.1:8001 · mode='+env.TRIPBUDDY_MODE);
