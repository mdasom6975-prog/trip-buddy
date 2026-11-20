import {spawnSync} from 'node:child_process';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const engine=process.env.TRIPBUDDY_ENGINE_ROOT||resolve(root,'../tour-planner');
const python=process.env.TRIPBUDDY_ENGINE_PYTHON||resolve(engine,'.venv/bin/python');
const result=spawnSync(python,['scripts/compare_distance_policies.py','--suite',resolve(root,'data/regressions/suite'),'--output',resolve(root,'data/regressions/policy-comparison')],{cwd:engine,stdio:'inherit'});
if(result.error)process.stderr.write('거리 기준 비교 실행 실패: 엔진 경로와 가상환경을 확인해 주세요.\n');
process.exitCode=result.status??1;
