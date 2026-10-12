"""CAVIAR CCTV 클립을 OneJev(동영상 입력 System One 판단 모델)에 물어 본다. A4000에서 실행. 2026-10-12.
   python cctv_run.py --port 8000 --tag 4B
   ① 클립 단위: 클립 전체에서 16프레임을 고르게 뽑아 한 번   ② 시간축: 8초 창(1fps, 8프레임)을 2초씩 밀며"""
import argparse, json, time, pathlib, statistics
from qev import Client, Choice, Noul, Score
from qev.media import data_uri

ap = argparse.ArgumentParser(); ap.add_argument('--port', default='8000'); ap.add_argument('--tag', default='4B')
ap.add_argument('--frames', default='frames'); ap.add_argument('--only', default='')
ap.add_argument('--win-clips', default=''); ap.add_argument('--stride', type=int, default=2); ap.add_argument('--timeout', type=float, default=120)
args = ap.parse_args()
C = Client(f'http://localhost:{args.port}', timeout=args.timeout)
Q = {
    'scene': Choice('What is happening in this CCTV video?', {
        'passing': 'people walking or passing through normally',
        'lingering': 'people standing, browsing, waiting or sitting calmly',
        'meeting': 'people meeting and talking calmly in a group',
        'person_down': 'a person has fallen down or is lying or slumped on the floor',
        'fighting': 'people fighting, pushing each other, chasing, or running away from a fight',
        'left_object': 'a bag or box is left behind on the floor without its owner',
        'empty': 'no people are visible'}),
    'down': Noul('In this video, is any person lying or slumped on the floor?'),
    'staff': Noul('Should a staff member go to this place right now to check on people?'),
    'urgency': Score('How urgently should staff respond?', ['no action needed', 'keep watching', 'check soon', 'respond immediately']),
}
STATE = {'camera': 'overhead fisheye CCTV of a building lobby; people look small from above', 'video': '<video:1>'}

def ask(frames, fps):
    t0 = time.time()
    r = C.system_one(state=STATE, media=[{'type': 'video', 'frames': [{'data': data_uri(p)} for p in frames], 'fps': fps}], questions=Q)
    ms = round((time.time() - t0) * 1000)
    a = r.answers
    return {'ms': ms, 'scene': a['scene'].choice, 'scene_probs': a['scene'].probabilities, 'down': a['down'].noul,
            'staff': a['staff'].noul, 'urgency': a['urgency'].score}

out = {'tag': args.tag, 'questions': {k: str(v) for k, v in Q.items()}, 'clips': {}, 'windows': {}}
clips = sorted(p for p in pathlib.Path(args.frames).iterdir() if p.is_dir() and (not args.only or p.name in args.only.split(',')))
ask(sorted(clips[0].glob('*.jpg'))[:8], 1.0)  # 데우기(기록 안 함)
for d in clips:
    fs = sorted(d.glob('*.jpg'))  # 2fps
    dur = len(fs) / 2
    pick = [fs[round(i * (len(fs) - 1) / 15)] for i in range(16)]
    out['clips'][d.name] = ask(pick, 16 / dur)
    c = out['clips'][d.name]; print(f"[clip] {d.name:22s} {c['ms']:5d}ms {c['scene']:12s} {c['scene_probs'][c['scene']]:.2f} down {c['down']:.2f} staff {c['staff']:.2f} urg {c['urgency']:.2f}", flush=True)
    ws = []
    if args.win_clips and d.name not in args.win_clips.split(','):
        out['windows'][d.name] = []; continue
    for start in range(0, max(1, int(dur) - 8 + 1), args.stride):
        frames = [fs[min(len(fs) - 1, (start + k) * 2)] for k in range(8)]
        w = ask(frames, 1.0); w['t0'] = start; w['t1'] = start + 8; ws.append(w)
    out['windows'][d.name] = ws
    print(f"   {len(ws)} windows · median {statistics.median(x['ms'] for x in ws)}ms · max urg {max(x['urgency'] for x in ws):.2f} · max down {max(x['down'] for x in ws):.2f}", flush=True)
p = pathlib.Path('results') / f"cctv-{args.tag}-{time.strftime('%Y%m%d-%H%M%S')}.json"
p.parent.mkdir(exist_ok=True); p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8'); print('->', p)
