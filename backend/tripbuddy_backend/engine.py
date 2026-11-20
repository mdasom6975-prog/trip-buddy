"""One persistent child process, serialized by the API job queue."""
import asyncio
import json
import os
from pathlib import Path


class Engine:
    def __init__(self, root: Path, python: Path, data: Path, mode='demo'):
        self.root, self.python, self.data, self.mode = root, python, data, mode
        self.process = None
        self.ready = False

    async def start(self):
        if not (self.root/'graph/runtime.py').is_file() or not self.python.is_file():
            raise RuntimeError('engine_source_missing')
        worker = Path(__file__).with_name('engine_worker.py')
        self.process = await asyncio.create_subprocess_exec(str(self.python), '-u', '-c',
            "import runpy,sys;runpy.run_path(sys.argv[1],run_name='__main__')", str(worker), cwd=self.root,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TRIPBUDDY_DATA_DIR':str(self.data),'TRIPBUDDY_MODE':self.mode},
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=4*1024*1024)
        try:
            line = await asyncio.wait_for(self.process.stdout.readline(),timeout=180 if self.mode=='live' else 20)
            if json.loads(line).get('type') != 'ready':
                raise RuntimeError('engine_not_ready')
            self.ready = True
        except Exception:
            await self.close()
            raise RuntimeError('engine_startup_failed') from None

    async def run(self, session_id, message):
        if not self.ready:
            raise RuntimeError('engine_not_ready')
        self.process.stdin.write((json.dumps({'session_id':session_id,'message':message},ensure_ascii=False)+'\n').encode())
        await self.process.stdin.drain()
        while True:
            line = await asyncio.wait_for(self.process.stdout.readline(),timeout=180)
            if not line:
                self.ready = False
                raise RuntimeError('engine_disconnected')
            event = json.loads(line)
            yield event
            if event['type'] in ('completed','failed'):
                break

    async def close(self):
        self.ready = False
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(),5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
