"""CCTV 실측 결과로 슬라이드 그림 · 요약을 만든다. python3 make_figs.py results/cctv-4B-*.json [results/cctv-0.8B-*.json]
   timeline.png  쓰러짐 · 다툼 · 물건 방치 클립의 시간축(정답 띠 + 급함 · 쓰러짐 · 다툼 확률)
   summary.json  클립 분류 일치 · 지연 · 알람 규칙 결과"""
import json, sys, pathlib, statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

HERE = pathlib.Path(__file__).parent
for w in ('Regular', 'Bold'):
    fm.fontManager.addfont(str(pathlib.Path.home() / f'Library/Fonts/NotoSansCJKkr-{w}.otf'))
INK, MUTED, GREEN, ORANGE, PURPLE, GOLD = '#19272D', '#64736D', '#466A62', '#AA5238', '#7A5BA6', '#C9A227'
plt.rcParams.update({'font.family': 'Noto Sans CJK KR', 'font.size': 11, 'axes.unicode_minus': False,
    'axes.edgecolor': '#AAB6B0', 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.titlesize': 12.5, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left', 'xtick.color': MUTED, 'ytick.color': MUTED})
KO = {'passing': '지나감', 'lingering': '머무름', 'meeting': '만남', 'person_down': '쓰러짐', 'fighting': '다툼', 'left_object': '물건 방치', 'empty': '사람 없음'}
GT = json.load(open(HERE / 'gt.json'))
big = json.load(open(sys.argv[1]))
small = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None

def alarms(ws, down_at=0.9, k=2):
    hit = [w['down'] >= down_at for w in ws]
    return [ws[i]['t1'] for i in range(k - 1, len(ws)) if all(hit[i - j] for j in range(k))]

def rule_table(R):
    rows = []
    for th, k in ((0.5, 2), (0.7, 3), (0.9, 2)):
        tp, fa = [], []
        for n, ws in R['windows'].items():
            if not ws: continue
            al, d = alarms(ws, th, k), GT[n]['down_s']
            if d:
                ok = [a for a in al if d[0] <= a <= d[-1] + 8]; tp.append((n, ok[0] if ok else None))
            elif al: fa.append((n, al[0]))
        n_pos = sum(1 for n, ws in R['windows'].items() if ws and GT[n]['down_s']); n_neg = sum(1 for n, ws in R['windows'].items() if ws and not GT[n]['down_s'])
        rows.append({'rule': f'down ≥ {th} · {k}번 연속', 'caught': sum(1 for _, a in tp if a), 'n_pos': n_pos, 'false': len(fa), 'n_neg': n_neg, 'detail': tp, 'false_detail': fa})
    return rows

summ = {'clips': {}, 'rules': {}}
for tag, R in (('4B', big), ('0.8B', small)):
    if not R: continue
    ok = sum(R['clips'][n]['scene'] == GT[n]['clip_label'] for n in GT)
    ms_clip = [R['clips'][n]['ms'] for n in GT]; ms_win = [w['ms'] for ws in R['windows'].values() for w in ws]
    summ['rules'][tag] = rule_table(R)
    summ[tag] = {'clip_ok': ok, 'n': len(GT), 'ms_clip_median': statistics.median(ms_clip), 'ms_win_median': statistics.median(ms_win), 'n_windows': len(ms_win)}
MAIN = small or big  # 시간축 그림은 학생이 T4에서 돌릴 0.8B 기록으로
for n in sorted(GT):
    c = big['clips'][n]
    summ['clips'][n] = {'gt': GT[n]['clip_label'], 'scene': c['scene'], 'p': round(c['scene_probs'][c['scene']], 3), 'down': round(c['down'], 3),
                        'staff': round(c['staff'], 3), 'urgency': round(c['urgency'], 2), 'alarm_t_main': (alarms(MAIN['windows'][n]) or [None])[0] if MAIN['windows'].get(n) else None,
                        'small_scene': small['clips'][n]['scene'] if small else None}
(HERE / 'summary.json').write_text(json.dumps(summ, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in summ.items() if k != 'clips'}, ensure_ascii=False))
for n, v in summ['clips'].items():
    print(f"{n:22s} 정답 {KO[v['gt']]:5s} 4B {KO[v['scene']]:5s} {v['p']:.2f} down {v['down']:.2f} urg {v['urgency']:.2f} | 0.8B {KO.get(v['small_scene'], '-')} 알람 {v['alarm_t_main']}")
for tag, rows in summ['rules'].items():
    for r in rows: print(tag, r['rule'], f"잡음 {r['caught']}/{r['n_pos']} 헛알람 {r['false']}/{r['n_neg']}")

SHOW = ['Rest_FallOnFloor', 'Fight_OneManDown', 'LeftBag', 'Walk1']
fig, axes = plt.subplots(len(SHOW), 1, figsize=(11, 2.05 * len(SHOW)), sharex=False)
for ax, n in zip(axes, SHOW):
    g, ws = GT[n], MAIN['windows'][n]
    for key, color in (('down_s', ORANGE), ('fight_s', PURPLE), ('left_s', GOLD)):
        for s in g[key]: ax.axvspan(s, s + 1, color=color, alpha=0.16, lw=0)
    mid = [w['t1'] for w in ws]  # 판단이 나오는 시각 = 창이 끝나는 시각
    ax.plot(mid, [w['urgency'] / 3 for w in ws], '-o', ms=3.5, color=INK, lw=1.8, label='급함 (urgency ÷ 3)')
    ax.plot(mid, [w['down'] for w in ws], '--', color=ORANGE, lw=1.6, label='쓰러짐 확률 (down)')
    ax.plot(mid, [w['scene_probs']['fighting'] for w in ws], ':', color=PURPLE, lw=1.8, label='다툼 확률')
    ax.plot(mid, [w['scene_probs']['left_object'] for w in ws], '-.', color=GOLD, lw=1.4, label='물건 방치 확률')
    a = alarms(ws)
    if a: ax.axvline(a[0], color=ORANGE, lw=1.2); ax.text(a[0] + 0.3, 0.72, f'알람 {a[0]}초', color=ORANGE, fontsize=9.5)
    ax.set_ylim(0, 1.05); ax.set_xlim(0, g['dur_s']); ax.set_yticks([0, 0.5, 1])
    ax.set_title(f"{n} · 정답 {KO[g['clip_label']]}" + ('' if g['clip_label'] in ('person_down', 'fighting', 'left_object') else ' (평상시)'))
axes[0].legend(loc='upper left', ncol=4, fontsize=8.8, frameon=False, bbox_to_anchor=(0, 1.0))
axes[-1].set_xlabel('초 (8초 창이 끝나는 시각 = 판단이 나오는 시각) · 옅은 띠 = 정답 구간 · 세로선 = 알람(쓰러짐 0.9 이상 두 번 연속)')
fig.suptitle('OneJev-0.8B · RTX A4000 float16 · CAVIAR CCTV', x=0.01, ha='left', fontsize=10, color=MUTED)
plt.tight_layout()
plt.savefig(HERE / 'timeline.png', dpi=180, bbox_inches='tight')
print('-> timeline.png')

# 슬라이드용 가로 그림(2×2)
fig, axes = plt.subplots(2, 2, figsize=(15, 6.4))
for ax, n in zip(axes.flat, SHOW):
    g, ws = GT[n], MAIN['windows'][n]
    for key, color in (('down_s', ORANGE), ('fight_s', PURPLE), ('left_s', GOLD)):
        for s in g[key]: ax.axvspan(s, s + 1, color=color, alpha=0.16, lw=0)
    x = [w['t1'] for w in ws]
    ax.plot(x, [w['down'] for w in ws], '-', color=ORANGE, lw=2.4, label='쓰러짐 확률 (down)')
    ax.plot(x, [w['scene_probs']['fighting'] for w in ws], ':', color=PURPLE, lw=2.2, label='다툼 확률')
    ax.plot(x, [w['scene_probs']['left_object'] for w in ws], '-.', color=GOLD, lw=1.8, label='물건 방치 확률')
    ax.plot(x, [w['urgency'] / 3 for w in ws], '-', color=INK, lw=1.2, alpha=0.55, label='급함 ÷ 3')
    ax.axhline(0.9, color=MUTED, lw=0.8, ls='--')
    a = alarms(ws)
    if a: ax.axvline(a[0], color=ORANGE, lw=1.4); ax.text(a[0] + 0.4, 0.62, f'알람 {a[0]}초', color=ORANGE, fontsize=11, fontweight='bold')
    ax.set_ylim(0, 1.05); ax.set_xlim(0, g['dur_s']); ax.set_yticks([0, 0.5, 0.9, 1])
    ax.set_title(f"{n} · 정답 {KO[g['clip_label']]}", fontsize=13)
axes[0, 0].legend(loc='upper left', ncol=2, fontsize=9.5, frameon=False)
for ax in axes[1]: ax.set_xlabel('초 (판단이 나오는 시각) · 옅은 띠 = 정답 구간 · 점선 0.9 = 알람 기준')
plt.tight_layout(); plt.savefig(HERE / 'timeline_wide.png', dpi=170, bbox_inches='tight'); print('-> timeline_wide.png')
