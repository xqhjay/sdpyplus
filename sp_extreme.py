# 极致当量: 完全忽略互击率 (altT=0 无惩罚), 三靶点: 纯单字 / 纯连续 / 均衡(d1+d2)
# 约束不变: 零歧义 + 26字母 + 键容2 + 共居互补 + 工具默认
import json, time
src = open('/workspace/sp_opt.py', encoding='utf-8').read()
exec(src.split("if __name__")[0])
t0 = time.time()

res = json.load(open('/workspace/sp_results.json'))
def get(n):
    r = next(x for x in res if x['name'] == n)
    return (r['fmap'], r['zh'], r['zero'])
flag = json.load(open('/workspace/sp_flagship.json'))
FLAG = (flag['fmap'], flag['zh'], flag['zero'])
SD_CLEAN = (sanitize(SD_FMAP, SD_ZH, SD_ZERO), SD_ZH, SD_ZERO)

ITERS = 200000
def run(tag, w1, w2, init, seeds):
    best = None
    for s in seeds:
        b = sa(w1, w2, 0.0, 0, *init, iters=ITERS, seed=s)   # altT=0: 互击完全自由
        fmap, zh, zero = b[1], b[2], b[3]
        fmap, zh, zero, _ = polish(fmap, zh, zero, w1, w2, 0.0, 0)
        v = full_eval(fmap, zh, zero)
        assert not v['collide'], f'{tag}/{s}: {v["collide"][:3]}'
        score = w1 * v['d1'] + w2 * v['d2']
        if best is None or score < best[0]:
            best = (score, fmap, zh, zero, v)
        print(f"  [{tag} s{s}] 单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% "
              f"下排{v['down']*100:.1f}% 小指{v['pinky']*100:.1f}% ({time.time()-t0:.0f}s)")
    return best

targets = {}
print('== 靶点1: 纯单字当量极值 (w=1:0) ==')
for tag, init in (('单字极值旧', get('单字极值')), ('旗舰', FLAG), ('首道净', SD_CLEAN)):
    targets.setdefault('纯单字', []).append(run(tag, 1.0, 0.0, init, (501, 502)))
print('== 靶点2: 纯连续当量极值 (w=0:1) ==')
for tag, init in (('连续极值旧', get('连续极值')), ('旗舰', FLAG), ('首道净', SD_CLEAN)):
    targets.setdefault('纯连续', []).append(run(tag, 0.0, 1.0, init, (601, 602)))
print('== 靶点3: 均衡极致 d1+d2 (w=1:1) ==')
for tag, init in (('旗舰', FLAG), ('均衡双优旧', get('均衡双优')), ('首道净', SD_CLEAN)):
    targets.setdefault('均衡极致', []).append(run(tag, 1.0, 1.0, init, (701, 702)))

out = []
for name, cands in targets.items():
    best = min(cands, key=lambda x: x[0])
    _, fmap, zh, zero, v = best
    scheme = (zh['zh'] + zh['ch'] + zh['sh'] + ''.join(fmap[X] for X in FINALS)
              + ''.join(zero[z] for z in ZEROS))
    km = defaultdict(list)
    for X, k in fmap.items(): km[k].append(X)
    print(f"\n=== [{name}] 终选 ===")
    print(f"单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% "
          f"下排{v['down']*100:.1f}% 小指QAPZ{v['pinky']*100:.1f}% 歧义{v['collide']}")
    print('  zh/ch/sh:', zh, ' 零声母:', zero)
    print('  键位:', ' '.join(f"{k}:{'/'.join(vs)}" for k, vs in sorted(km.items())))
    print('  方案串:', scheme)
    out.append({'name': name, 'fmap': fmap, 'zh': zh, 'zero': zero,
                'scheme': scheme, 'metrics': v})
json.dump(out, open('/workspace/sp_extreme.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1, default=str)

print(f"\n=== 汇总 vs 首道/旗舰 ({time.time()-t0:.0f}s) ===")
print(f"{'方案':<12}{'单字':>9}{'连续':>9}{'互击%':>8}{'下排%':>7}{'小指%':>7}")
print(f"{'首道双拼':<12}{13.0332:>9.4f}{13.7024:>9.4f}{56.72:>8.2f}{20.4:>7.1f}{8.0:>7.1f}")
fm = flag['metrics']
print(f"{'旗舰终版':<12}{fm['d1']:>9.4f}{fm['d2']:>9.4f}{fm['alt']*100:>8.2f}{fm['down']*100:>7.1f}{fm['pinky']*100:>7.1f}")
for r in out:
    m = r['metrics']
    print(f"{r['name']:<12}{m['d1']:>9.4f}{m['d2']:>9.4f}{m['alt']*100:>8.2f}{m['down']*100:>7.1f}{m['pinky']*100:>7.1f}")
print(f"{'容量下界':<12}{12.4939:>9.4f}{13.3168:>9.4f}")
print('已保存 -> /workspace/sp_extreme.json')
