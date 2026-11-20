import {spawnSync} from 'node:child_process';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const engine=process.env.TRIPBUDDY_ENGINE_ROOT||resolve(root,'../tour-planner');
const python=process.env.TRIPBUDDY_ENGINE_PYTHON||resolve(engine,'.venv/bin/python');
const args=process.argv.slice(2);
const regression=['scripts/replay_regressions.py','--suite',resolve(root,'data/regressions/suite'),'--output',resolve(root,'data/regressions/reports')];
if(args.includes('--strict-known'))regression.push('--strict-known');
const checks=args.includes('--regressions-only')?[]:[
 ['엔진 단위 테스트',python,['-m','pytest','-q'],engine],
 ['API 테스트','npm',['run','test:api'],root],
 ['프런트엔드 타입 검사','npm',['run','typecheck'],root]
];
checks.push(['저장 사례 오프라인 재생',python,regression,engine]);
let failed=false;
for(const [label,command,commandArgs,cwd] of checks){
 process.stdout.write(`\n[${label}]\n`);
 const result=spawnSync(command,commandArgs,{cwd,stdio:'inherit',env:process.env});
 if(result.error||result.status!==0){failed=true;process.stderr.write(`검사 종료 코드: ${result.status??'실행 실패'}\n`);}
}
process.stdout.write('\n회귀 보고서: '+resolve(root,'data/regressions/reports/latest.md')+'\n');
process.exitCode=failed?1:0;
