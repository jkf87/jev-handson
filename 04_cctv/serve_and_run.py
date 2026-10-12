"""A4000: 모델 서버를 띄우고 cctv_run.py를 돌린 뒤 끈다. python serve_and_run.py <모델폴더> <태그> [dtype]"""
import subprocess, sys, time, urllib.request, os
model, tag = sys.argv[1], sys.argv[2]
dtype = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != '-' else None
extra = sys.argv[4:]
py = sys.executable
qev = os.path.join(os.path.dirname(py), 'qev.exe')
cmd = [qev, 'serve', '--model', model, '--multimodal', '--port', '8000', '--name', f'OneJev-{tag}']
if dtype: cmd += ['--dtype', dtype]
run_extra = [a for a in extra if not a.startswith('--no-cuda')]
if '--no-cuda-graphs' in extra: cmd += ['--no-cuda-graphs']
log = open(f'serve-{tag}.log', 'w', encoding='utf-8')
t0 = time.time(); srv = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
ok = False
for _ in range(240):
    time.sleep(5)
    if srv.poll() is not None: break
    try: urllib.request.urlopen('http://localhost:8000/health', timeout=3); ok = True; break
    except Exception: pass
print('server', 'ok' if ok else 'FAIL', round(time.time() - t0), 's', flush=True)
if ok:
    subprocess.run([py, 'cctv_run.py', '--tag', tag] + run_extra)
srv.terminate()
try: srv.wait(30)
except Exception: srv.kill()
