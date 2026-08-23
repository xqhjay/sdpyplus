# 深度收敛: 三种记忆友好零声母框架的极致当量优化
#   V1 = 自然码式零声母 (12全规则)     => zh/ch/sh 强制 ∈ {I,U,V}
#   V2 = 首道式零声母 (8规则+4特例)    => zh/ch/sh ∈ {E,I,V} (A/O/U被零声母结构锁死)
#   V3 = 自然式+2特例 (e→UE, ei→UI)   => zh/ch/sh ∈ {E,I,V}
# 外层穷举 zh 排列 × 内层快速fmap-SA(40万次×4种子) × polish
import json, time, random, math
from collections import defaultdict
from itertools import permutations

src = open('/workspace/sp_opt.py', encoding='utf-8').read()
exec(src.split("if __name__")[0])
t0 = time.time()

ZERO_NAT = {'a': 'AA', 'ai': 'AI', 'an': 'AN', 'ang': 'AH', 'ao': 'AO',
            'o': 'OO', 'ou': 'OU', 'e': 'EE', 'ei': 'EI', 'en': 'EN',
            'eng': 'EG', 'er': 'ER'}
ZERO_V3 = dict(ZERO_NAT); ZERO_V3['e'] = 'UE'; ZERO_V3['ei'] = 'UI'

def decode_all(s):
    zh = {'zh': s[0], 'ch': s[1], 'sh': s[2]}
    fmap = {f: s[3 + i] for i, f in enumerate(FINALS)}
    zero = {z: s[31 + 2 * i: 33 + 2 * i] for i, z in enumerate(ZEROS)}
    return zh, fmap, zero

ZRM = decode_all('VIUVLZVKBQXTTJFNPHGYSWCMDSWYRDOAAAIANAHAOOOOUEEEIENEGER')

def make_ok(zh, zero, tol=0):
    SK = dict(NATURAL); SK.update(zh)
    sheng_on = defaultdict(list)
    for m, k in SK.items(): sheng_on[k].append(m)
    zlist = [(zero[z][0], zero[z][1]) for z in ZEROS]
    def ok(X, k, fmap):
        if sum(1 for Y in FINALS if fmap.get(Y) == k) >= 2: return False
        for Y in ALLF:
            if Y == X: continue
            if (fmap.get(Y) or FIXED.get(Y)) == k and CM[(X, Y)] > tol: return False
        for P, Q in zlist:
            if Q == k:
                for m in sheng_on.get(P, ()):
                    if m in freq_map.get(X, {}): return False
        return True
    return ok

def repair_z(fmap, zh, zero):
    fmap = dict(fmap)
    ok = make_ok(zh, zero)
    for _ in range(60):
        SK = dict(NATURAL); SK.update(zh)
        seen = {}; bad = None
        for b, a, c in freq:
            kb, ka = (zero[a][0], zero[a][1]) if b == '' else (SK[b], fmap.get(a) or FIXED[a])
            code = kb + ka
            if code in seen: bad = (seen[code], (b, a)); break
            seen[code] = (b, a)
        if bad is None: return fmap
        (b1, a1), (b2, a2) = bad
        Xs = [x for x in (a1, a2) if x in FINALS]
        assert Xs, f'不可修复冲突: {bad}'
        X = min(Xs, key=lambda x: sum(c for _, c in final_syls[x]))
        t = build(zh, zero)
        bestk = None
        for k in LETTERS:
            if k == fmap[X] or not ok(X, k, fmap): continue
            if bestk is None or t['cost1'][X, k] < t['cost1'][X, bestk]: bestk = k
        assert bestk, f'repair: {X} 无合法键'
        fmap[X] = bestk
    raise RuntimeError('repair 未收敛')

def sa_fast(w1, w2, fmap0, zh, zero, iters, seed):
    rng = random.Random(seed)
    fmap = dict(fmap0)
    ok = make_ok(zh, zero)
    t = build(zh, zero)
    d1, d2, alt = metrics_from(t, fmap)
    cur = w1 * d1 + w2 * d2
    best = (cur, dict(fmap))
    T0, T1 = 0.035, 0.00025
    for it in range(iters):
        temp = T0 * (T1 / T0) ** (it / iters)
        if rng.random() < 0.62:
            X = rng.choice(FINALS); k = rng.choice(LETTERS)
            a = fmap[X]
            if k == a or not ok(X, k, fmap): continue
            nd1 = d1 + (t['cost1'][X, k] - t['cost1'][X, a]) / T
            nd2 = d2 + t['PX'][X] * (t['W'][POS(k)] - t['W'][POS(a)]) / (T * T)
            nj = w1 * nd1 + w2 * nd2
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                fmap[X] = k; d1, d2, cur = nd1, nd2, nj
        else:
            X, Y = rng.choice(FINALS), rng.choice(FINALS)
            if X == Y: continue
            a, b = fmap[X], fmap[Y]
            tf = dict(fmap); tf[X], tf[Y] = b, a
            if not (ok(X, b, tf) and ok(Y, a, tf)): continue
            nd1 = d1 + (t['cost1'][X, b] - t['cost1'][X, a] + t['cost1'][Y, a] - t['cost1'][Y, b]) / T
            nd2 = d2 + (t['PX'][X] * (t['W'][POS(b)] - t['W'][POS(a)])
                        + t['PX'][Y] * (t['W'][POS(a)] - t['W'][POS(b)])) / (T * T)
            nj = w1 * nd1 + w2 * nd2
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                fmap = tf; d1, d2, cur = nd1, nd2, nj
        if cur < best[0]: best = (cur, dict(fmap))
    return best

def polish_fast(fmap, zh, zero, w1, w2, max_rounds=15):
    ok = make_ok(zh, zero)
    t = build(zh, zero)
    d1, d2, alt = metrics_from(t, fmap)
    cur = w1 * d1 + w2 * d2
    fmap = dict(fmap)
    for _ in range(max_rounds):
        improved = False
        for X in FINALS:
            for k in LETTERS:
                a = fmap[X]
                if k == a or not ok(X, k, fmap): continue
                nd1 = d1 + (t['cost1'][X, k] - t['cost1'][X, a]) / T
                nd2 = d2 + t['PX'][X] * (t['W'][POS(k)] - t['W'][POS(a)]) / (T * T)
                nj = w1 * nd1 + w2 * nd2
                if nj < cur - 1e-12:
                    fmap[X] = k; d1, d2, cur = nd1, nd2, nj; improved = True
        for i, X in enumerate(FINALS):
            for Y in FINALS[i + 1:]:
                a, b = fmap[X], fmap[Y]
                if a == b: continue
                tf = dict(fmap); tf[X], tf[Y] = b, a
                if not (ok(X, b, tf) and ok(Y, a, tf)): continue
                nd1 = d1 + (t['cost1'][X, b] - t['cost1'][X, a] + t['cost1'][Y, a] - t['cost1'][Y, b]) / T
                nd2 = d2 + (t['PX'][X] * (t['W'][POS(b)] - t['W'][POS(a)])
                            + t['PX'][Y] * (t['W'][POS(a)] - t['W'][POS(b)])) / (T * T)
                nj = w1 * nd1 + w2 * nd2
                if nj < cur - 1e-12:
                    fmap = tf; d1, d2, cur = nd1, nd2, nj; improved = True
        if not improved: break
    return fmap

if __name__ == '__main__':
    pool = [ZRM[1]]
    for fn in ('sp_extreme.json', 'sp_flagship.json', 'sp_mem.json'):
        try:
            d = json.load(open(f'/workspace/{fn}'))
            for r in (d if isinstance(d, list) else [d]):
                pool.append(r['fmap'])
        except Exception:
            pass

    VARIANTS = [
        ('V1·自然零声母', ZERO_NAT, 'IUV'),
        ('V2·首道零声母', SD_ZERO, 'EIV'),
        ('V3·自然+2特例', ZERO_V3, 'EIV'),
    ]
    targets = [('纯单字', 1.0, 0.0), ('纯连续', 0.0, 1.0), ('均衡', 1.0, 1.0)]
    ITERS, SEEDS = 400000, (921, 922, 923, 924)
    out = []

    for vname, zero, slots in VARIANTS:
        print(f'\n== {vname} (zh/ch/sh∈{slots}) ==')
        for tname, w1, w2 in targets:
            best = None
            for zhc in permutations(slots, 3):
                zh = {'zh': zhc[0], 'ch': zhc[1], 'sh': zhc[2]}
                cands = []
                for f in pool:
                    try: cands.append(repair_z(f, zh, zero))
                    except Exception: pass
                if not cands: continue
                for f0 in (cands[0], cands[-1]):
                    for seed in SEEDS:
                        _, fmap = sa_fast(w1, w2, f0, zh, zero, ITERS, seed)
                        fmap = polish_fast(fmap, zh, zero, w1, w2)
                        v = full_eval(fmap, zh, zero)
                        assert not v['collide'], (vname, tname, zhc, v['collide'][:3])
                        sc = w1 * v['d1'] + w2 * v['d2']
                        if best is None or sc < best[0]:
                            best = (sc, fmap, zh, v)
            _, fmap, zh, v = best
            scheme = (zh['zh'] + zh['ch'] + zh['sh'] + ''.join(fmap[X] for X in FINALS)
                      + ''.join(zero[z] for z in ZEROS))
            print(f"[{vname}·{tname}] 单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% "
                  f"下排{v['down']*100:.1f}% 小指{v['pinky']*100:.1f}% zh={zh} ({time.time()-t0:.0f}s)")
            out.append({'name': f'{vname}·{tname}', 'fmap': fmap, 'zh': zh, 'zero': zero,
                        'scheme': scheme, 'metrics': v})
            json.dump(out, open('/workspace/sp_mem2.json', 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1, default=str)

    print(f"\n=== 汇总 ({time.time()-t0:.0f}s) ===")
    print(f"{'方案':<22}{'单字':>9}{'连续':>9}{'互击%':>8}")
    print(f"{'首道双拼':<22}{13.0332:>9.4f}{13.7024:>9.4f}{56.72:>8.2f}")
    print(f"{'V0·纯单字(零声母自由)':<20}{12.7623:>9.4f}{13.7726:>9.4f}{60.70:>8.2f}")
    print(f"{'V0·纯连续(零声母自由)':<20}{13.1139:>9.4f}{13.5781:>9.4f}{57.48:>8.2f}")
    print(f"{'V0·均衡(零声母自由)':<20}{12.7845:>9.4f}{13.6604:>9.4f}{60.85:>8.2f}")
    for r in out:
        m = r['metrics']
        print(f"{r['name']:<22}{m['d1']:>9.4f}{m['d2']:>9.4f}{m['alt']*100:>8.2f}")

    import importlib.util, io, contextlib
    spec = importlib.util.spec_from_file_location('et', '/workspace/extract_tool.py')
    et = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(et)
    print('\nextract_tool 独立复算:')
    for r in out:
        d = dict(r['zh']); d.update(r['fmap']); d.update({'0'+k: v for k, v in r['zero'].items()})
        m = et.evaluate(d)
        print(f"  {r['name']}: 单字{m['单字当量']} 连续{m['连续当量']} 互击{m['双手互击率%']}%")
    print('已保存 -> /workspace/sp_mem2.json')
