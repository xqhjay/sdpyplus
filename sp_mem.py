# 零声母记忆友好化实验:
#   V1 = 自然码式规则零声母 (a→AA ai→AI an→AN ang→AH ao→AO o→OO ou→OU e→EE ei→EI en→EN eng→EG er→ER)
#        结构约束: A/O/E 不得有声母 => zh/ch/sh ∈ {I,U,V} (自然码/小鹤/搜狗同款)
#   V2 = 首道式零声母 (用户已熟悉的编码), zh/ch/sh 自由
#   V0 = 零声母全自由 (sp_extreme 的结果, 记忆负担最重, 作为成本上限对照)
# 目标: 极致当量(互击自由) 三靶点: 纯单字 / 纯连续 / 均衡(d1+d2)
import json, time, random, math
from collections import defaultdict
from itertools import permutations

src = open('/workspace/sp_opt.py', encoding='utf-8').read()
exec(src.split("if __name__")[0])
t0 = time.time()

ZERO_NAT = {'a': 'AA', 'ai': 'AI', 'an': 'AN', 'ang': 'AH', 'ao': 'AO',
            'o': 'OO', 'ou': 'OU', 'e': 'EE', 'ei': 'EI', 'en': 'EN',
            'eng': 'EG', 'er': 'ER'}

def decode_all(s):
    zh = {'zh': s[0], 'ch': s[1], 'sh': s[2]}
    fmap = {f: s[3 + i] for i, f in enumerate(FINALS)}
    zero = {z: s[31 + 2 * i: 33 + 2 * i] for i, z in enumerate(ZEROS)}
    return zh, fmap, zero

ZRM = decode_all('VIUVLZVKBQXTTJFNPHGYSWCMDSWYRDOAAAIANAHAOOOOUEEEIENEGER')  # 自然码
XH = decode_all('VIUVDWVCZQPTTJFBYHGKSXNMLSXKRLOAAAIANAHAOOOOUEEEIENEGER')   # 小鹤
assert ZRM[2] == ZERO_NAT, 'ZERO_NAT 与自然码官方零声母不一致'

def no_collide(fmap, zh, zero):
    SK = dict(NATURAL); SK.update(zh)
    seen = set()
    for b, a, c in freq:
        if b == '': kb, ka = zero[a][0], zero[a][1]
        else: kb, ka = SK[b], (fmap.get(a) or FIXED[a])
        if kb + ka in seen: return False
        seen.add(kb + ka)
    return True

# ---- V1: fmap 约束检查 (零声母冲突结构上不可能: A/O/E 无声母) ----
def fmap_ok2(X, k, fmap):
    if sum(1 for Y in FINALS if fmap.get(Y) == k) >= 2: return False
    for Y in ALLF:
        if Y == X: continue
        if (fmap.get(Y) or FIXED.get(Y)) == k and CM[(X, Y)] > 0: return False
    return True

def repair_v1(fmap, zh):
    """把可能带冲突的初始 fmap 修成 V1 合法 (冲突韵母迁到 cost1 最小的合法键)"""
    fmap = dict(fmap)
    for _ in range(60):
        SK = dict(NATURAL); SK.update(zh)
        seen = {}; bad = None
        for b, a, c in freq:
            kb, ka = (ZERO_NAT[a][0], ZERO_NAT[a][1]) if b == '' else (SK[b], fmap.get(a) or FIXED[a])
            code = kb + ka
            if code in seen: bad = (seen[code], (b, a)); break
            seen[code] = (b, a)
        if bad is None: return fmap
        (b1, a1), (b2, a2) = bad
        Xs = [x for x in (a1, a2) if x in FINALS]
        assert Xs, '固定韵母间冲突?!'
        X = min(Xs, key=lambda x: sum(c for _, c in final_syls[x]))
        t = build(zh, ZERO_NAT)
        bestk = None
        for k in LETTERS:
            if k == fmap[X] or not fmap_ok2(X, k, fmap): continue
            if bestk is None or t['cost1'][X, k] < t['cost1'][X, bestk]: bestk = k
        assert bestk, f'repair: {X} 无合法键'
        fmap[X] = bestk
    raise RuntimeError('repair 未收敛')

def sa_v1(w1, w2, fmap0, zh, iters, seed):
    rng = random.Random(seed)
    fmap = dict(fmap0)
    t = build(zh, ZERO_NAT)
    d1, d2, alt = metrics_from(t, fmap)
    cur = w1 * d1 + w2 * d2
    best = (cur, dict(fmap))
    T0, T1 = 0.035, 0.00025
    for it in range(iters):
        temp = T0 * (T1 / T0) ** (it / iters)
        if rng.random() < 0.62:
            X = rng.choice(FINALS); k = rng.choice(LETTERS)
            a = fmap[X]
            if k == a or not fmap_ok2(X, k, fmap): continue
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
            if not (fmap_ok2(X, b, tf) and fmap_ok2(Y, a, tf)): continue
            nd1 = d1 + (t['cost1'][X, b] - t['cost1'][X, a] + t['cost1'][Y, a] - t['cost1'][Y, b]) / T
            nd2 = d2 + (t['PX'][X] * (t['W'][POS(b)] - t['W'][POS(a)])
                        + t['PX'][Y] * (t['W'][POS(a)] - t['W'][POS(b)])) / (T * T)
            nj = w1 * nd1 + w2 * nd2
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                fmap = tf; d1, d2, cur = nd1, nd2, nj
        if cur < best[0]: best = (cur, dict(fmap))
    return best

def polish_v1(fmap, zh, w1, w2, max_rounds=15):
    t = build(zh, ZERO_NAT)
    d1, d2, alt = metrics_from(t, fmap)
    cur = w1 * d1 + w2 * d2
    fmap = dict(fmap)
    for _ in range(max_rounds):
        improved = False
        for X in FINALS:
            for k in LETTERS:
                a = fmap[X]
                if k == a or not fmap_ok2(X, k, fmap): continue
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
                if not (fmap_ok2(X, b, tf) and fmap_ok2(Y, a, tf)): continue
                nd1 = d1 + (t['cost1'][X, b] - t['cost1'][X, a] + t['cost1'][Y, a] - t['cost1'][Y, b]) / T
                nd2 = d2 + (t['PX'][X] * (t['W'][POS(b)] - t['W'][POS(a)])
                            + t['PX'][Y] * (t['W'][POS(a)] - t['W'][POS(b)])) / (T * T)
                nj = w1 * nd1 + w2 * nd2
                if nj < cur - 1e-12:
                    fmap = tf; d1, d2, cur = nd1, nd2, nj; improved = True
        if not improved: break
    return fmap

# ---- V2: 零声母=首道固定, zh/ch/sh 自由 (FREESLOTS), fmap 含零声母冲突检查 ----
def sa_v2(w1, w2, fmap0, zh0, iters, seed):
    rng = random.Random(seed)
    fmap = dict(fmap0); zh = dict(zh0)
    t = build(zh, SD_ZERO)
    d1, d2, alt = metrics_from(t, fmap)
    cur = w1 * d1 + w2 * d2
    best = (cur, dict(fmap), dict(zh))
    T0, T1 = 0.035, 0.00025
    for it in range(iters):
        temp = T0 * (T1 / T0) ** (it / iters)
        r = rng.random()
        if r < 0.60:
            X = rng.choice(FINALS); k = rng.choice(LETTERS)
            a = fmap[X]
            if k == a or not fmap_ok(X, k, fmap, zh, SD_ZERO, 0): continue
            nd1 = d1 + (t['cost1'][X, k] - t['cost1'][X, a]) / T
            nd2 = d2 + t['PX'][X] * (t['W'][POS(k)] - t['W'][POS(a)]) / (T * T)
            nj = w1 * nd1 + w2 * nd2
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                fmap[X] = k; d1, d2, cur = nd1, nd2, nj
        elif r < 0.82:
            X, Y = rng.choice(FINALS), rng.choice(FINALS)
            if X == Y: continue
            a, b = fmap[X], fmap[Y]
            tf = dict(fmap); tf[X], tf[Y] = b, a
            if not (fmap_ok(X, b, tf, zh, SD_ZERO, 0) and fmap_ok(Y, a, tf, zh, SD_ZERO, 0)): continue
            nd1 = d1 + (t['cost1'][X, b] - t['cost1'][X, a] + t['cost1'][Y, a] - t['cost1'][Y, b]) / T
            nd2 = d2 + (t['PX'][X] * (t['W'][POS(b)] - t['W'][POS(a)])
                        + t['PX'][Y] * (t['W'][POS(a)] - t['W'][POS(b)])) / (T * T)
            nj = w1 * nd1 + w2 * nd2
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                fmap = tf; d1, d2, cur = nd1, nd2, nj
        else:
            m = rng.choice(['zh', 'ch', 'sh'])
            k = rng.choice(FREESLOTS)
            if k in zh.values() or k == zh[m]: continue
            old = zh[m]; zh[m] = k
            tf_ = build(zh, SD_ZERO)
            if any(not zero_ok(z, SD_ZERO[z][0], SD_ZERO[z][1], fmap, tf_['SK'], tf_['sk_of']) for z in ZEROS):
                zh[m] = old; continue
            nd1, nd2, nalt = metrics_from(tf_, fmap)
            nj = w1 * nd1 + w2 * nd2
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                t = tf_; d1, d2, cur = nd1, nd2, nj
            else: zh[m] = old
        if cur < best[0]: best = (cur, dict(fmap), dict(zh))
    return best

def polish_v2(fmap, zh, w1, w2, max_rounds=15):
    t = build(zh, SD_ZERO)
    d1, d2, alt = metrics_from(t, fmap)
    cur = w1 * d1 + w2 * d2
    fmap = dict(fmap); zh = dict(zh)
    for _ in range(max_rounds):
        improved = False
        for X in FINALS:
            for k in LETTERS:
                a = fmap[X]
                if k == a or not fmap_ok(X, k, fmap, zh, SD_ZERO, 0): continue
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
                if not (fmap_ok(X, b, tf, zh, SD_ZERO, 0) and fmap_ok(Y, a, tf, zh, SD_ZERO, 0)): continue
                nd1 = d1 + (t['cost1'][X, b] - t['cost1'][X, a] + t['cost1'][Y, a] - t['cost1'][Y, b]) / T
                nd2 = d2 + (t['PX'][X] * (t['W'][POS(b)] - t['W'][POS(a)])
                            + t['PX'][Y] * (t['W'][POS(a)] - t['W'][POS(b)])) / (T * T)
                nj = w1 * nd1 + w2 * nd2
                if nj < cur - 1e-12:
                    fmap = tf; d1, d2, cur = nd1, nd2, nj; improved = True
        for m in ('zh', 'ch', 'sh'):
            for k in FREESLOTS:
                if k == zh[m] or k in zh.values(): continue
                old = zh[m]; zh[m] = k
                tf_ = build(zh, SD_ZERO)
                if any(not zero_ok(z, SD_ZERO[z][0], SD_ZERO[z][1], fmap, tf_['SK'], tf_['sk_of']) for z in ZEROS):
                    zh[m] = old; continue
                nd1, nd2, nalt = metrics_from(tf_, fmap)
                nj = w1 * nd1 + w2 * nd2
                if nj < cur - 1e-12:
                    t = tf_; d1, d2, cur = nd1, nd2, nj; improved = True
                else: zh[m] = old
        if not improved: break
    return fmap, zh

# ================= 主流程 =================
if __name__ == '__main__':
    # 锚点: 自然码/小鹤 在 V1 框架下复算 (验证框架与零声母一致)
    for nm, (zh, fm, zz) in (('自然码', ZRM), ('小鹤', XH)):
        v = full_eval(fm, zh, zz)
        assert not v['collide']
        print(f"锚点{nm}: 单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}%")

    pool = [ZRM[1], XH[1]]
    for fn in ('sp_extreme.json', 'sp_flagship.json'):
        try:
            d = json.load(open(f'/workspace/{fn}'))
            for r in (d if isinstance(d, list) else [d]):
                pool.append(r['fmap'])
        except Exception:
            pass

    ITERS1, ITERS2 = 100000, 150000
    targets = [('纯单字', 1.0, 0.0), ('纯连续', 0.0, 1.0), ('均衡', 1.0, 1.0)]
    out = []

    # ---- V1: 自然码式零声母 ----
    print('\n== V1 自然码式零声母 (zh/ch/sh∈IUV) ==')
    for tname, w1, w2 in targets:
        best = None
        for zhc in permutations('IUV', 3):
            zh = {'zh': zhc[0], 'ch': zhc[1], 'sh': zhc[2]}
            cands = []
            for f in pool:
                try: cands.append(repair_v1(f, zh))
                except Exception: pass
            if not cands:
                cands = [repair_v1(ZRM[1], zh)]
            for ci, seed in ((0, 901), (len(cands) - 1, 902)):
                _, fmap = sa_v1(w1, w2, cands[ci], zh, ITERS1, seed)
                fmap = polish_v1(fmap, zh, w1, w2)
                v = full_eval(fmap, zh, ZERO_NAT)
                assert not v['collide'], (tname, zhc, v['collide'][:3])
                sc = w1 * v['d1'] + w2 * v['d2']
                if best is None or sc < best[0]:
                    best = (sc, fmap, zh, v)
        _, fmap, zh, v = best
        scheme = (zh['zh'] + zh['ch'] + zh['sh'] + ''.join(fmap[X] for X in FINALS)
                  + ''.join(ZERO_NAT[z] for z in ZEROS))
        print(f"[V1·{tname}] 单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% "
              f"下排{v['down']*100:.1f}% 小指{v['pinky']*100:.1f}% zh={zh} ({time.time()-t0:.0f}s)")
        out.append({'name': f'V1·{tname}', 'fmap': fmap, 'zh': zh,
                    'zero': ZERO_NAT, 'scheme': scheme, 'metrics': v})

    # ---- V2: 首道式零声母 ----
    print('\n== V2 首道式零声母 (zh/ch/sh自由) ==')
    init2 = (sanitize(SD_FMAP, SD_ZH, SD_ZERO), SD_ZH)
    for tname, w1, w2 in targets:
        best = None
        for seed in (911, 912, 913):
            _, fmap, zh = sa_v2(w1, w2, init2[0], init2[1], ITERS2, seed)
            fmap, zh = polish_v2(fmap, zh, w1, w2)
            v = full_eval(fmap, zh, SD_ZERO)
            assert not v['collide'], (tname, v['collide'][:3])
            sc = w1 * v['d1'] + w2 * v['d2']
            if best is None or sc < best[0]:
                best = (sc, fmap, zh, v)
        _, fmap, zh, v = best
        scheme = (zh['zh'] + zh['ch'] + zh['sh'] + ''.join(fmap[X] for X in FINALS)
                  + ''.join(SD_ZERO[z] for z in ZEROS))
        print(f"[V2·{tname}] 单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% "
              f"下排{v['down']*100:.1f}% 小指{v['pinky']*100:.1f}% zh={zh} ({time.time()-t0:.0f}s)")
        out.append({'name': f'V2·{tname}', 'fmap': fmap, 'zh': zh,
                    'zero': SD_ZERO, 'scheme': scheme, 'metrics': v})

    json.dump(out, open('/workspace/sp_mem.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1, default=str)

    # ---- 汇总 + 交叉验证 ----
    print(f"\n=== 汇总 vs V0(零声母自由) ({time.time()-t0:.0f}s) ===")
    print(f"{'方案':<16}{'单字':>9}{'连续':>9}{'互击%':>8}{'下排%':>7}")
    print(f"{'首道双拼':<16}{13.0332:>9.4f}{13.7024:>9.4f}{56.72:>8.2f}{20.4:>7.1f}")
    for nm, d1, d2, a in (('V0·纯单字', 12.7623, 13.7726, 60.70), ('V0·纯连续', 13.1139, 13.5781, 57.48),
                          ('V0·均衡', 12.7845, 13.6604, 60.85)):
        print(f"{nm:<16}{d1:>9.4f}{d2:>9.4f}{a:>8.2f}")
    for r in out:
        m = r['metrics']
        print(f"{r['name']:<16}{m['d1']:>9.4f}{m['d2']:>9.4f}{m['alt']*100:>8.2f}{m['down']*100:>7.1f}")

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
    print('已保存 -> /workspace/sp_mem.json')