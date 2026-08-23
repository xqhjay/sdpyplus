# 定位 连续极值 阶段同码歧义的来源: 在SA每步接受后做独立全量校验
import json, random, math
from collections import defaultdict

src = open('/workspace/sp_opt.py', encoding='utf-8').read()
exec(src.split("if __name__")[0])

def all_dups(fmap, zh, zero):
    """独立全量校验: 枚举所有音节码找重复"""
    SK = dict(NATURAL); SK.update(zh)
    seen = {}
    for b, a, c in freq:
        if b == '': kb, ka = zero[a][0], zero[a][1]
        else: kb, ka = SK[b], (fmap.get(a) or FIXED[a])
        code = kb + ka
        seen.setdefault(code, []).append(f'{b}{a}')
    return {c: s for c, s in seen.items() if len(s) > 1}

print("CM[('en','ia')] =", CM[('en', 'ia')])
print("CM[('ia','en')] =", CM[('ia', 'en')])
print("freq_map['en']['d'] =", freq_map['en'].get('d'), " freq_map['ia']['d'] =", freq_map['ia'].get('d'))

# ---- 复刻 sa(w2=9.0, altT=0.568, tol=0, SD init, seed=11), 每步接受后全量校验 ----
def sa_debug(w2, altT, tol, fmap0, zh0, zero0, iters, seed):
    rng = random.Random(seed)
    fmap = dict(fmap0); zh = dict(zh0); zero = dict(zero0)
    t = build(zh, zero)
    d1, d2, alt = metrics_from(t, fmap)
    J = make_J(w2, altT)
    cur = J(d1, d2, alt)
    T0, T1 = 0.035, 0.00025
    for it in range(iters):
        temp = T0 * (T1 / T0) ** (it / iters)
        r = rng.random()
        moved = None
        if r < 0.60:
            X = rng.choice(FINALS); k = rng.choice(LETTERS)
            a = fmap[X]
            if k == a or not fmap_ok(X, k, fmap, zh, zero, tol): continue
            nd1 = d1 + (t['cost1'][X, k] - t['cost1'][X, a]) / T
            nd2 = d2 + t['PX'][X] * (t['W'][POS(k)] - t['W'][POS(a)]) / (T * T)
            nalt = alt + (t['alt1'][X, k] - t['alt1'][X, a]) / T
            nj = J(nd1, nd2, nalt)
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                fmap[X] = k; d1, d2, alt, cur = nd1, nd2, nalt, nj
                moved = f'move {X}->{k}'
        elif r < 0.78:
            X, Y = rng.choice(FINALS), rng.choice(FINALS)
            a, b = fmap[X], fmap[Y]
            if X == Y: continue
            tf = dict(fmap); tf[X], tf[Y] = b, a
            if not (fmap_ok(X, b, tf, zh, zero, tol) and fmap_ok(Y, a, tf, zh, zero, tol)): continue
            nd1 = d1 + (t['cost1'][X, b] - t['cost1'][X, a] + t['cost1'][Y, a] - t['cost1'][Y, b]) / T
            nd2 = d2 + (t['PX'][X] * (t['W'][POS(b)] - t['W'][POS(a)])
                        + t['PX'][Y] * (t['W'][POS(a)] - t['W'][POS(b)])) / (T * T)
            nalt = alt + (t['alt1'][X, b] - t['alt1'][X, a] + t['alt1'][Y, a] - t['alt1'][Y, b]) / T
            nj = J(nd1, nd2, nalt)
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                fmap = tf; d1, d2, alt, cur = nd1, nd2, nalt, nj
                moved = f'swap {X}:{a}<->{Y}:{b}'
        elif r < 0.86:
            m = rng.choice(['zh', 'ch', 'sh'])
            k = rng.choice(FREESLOTS)
            if k in zh.values() or k == zh[m]: continue
            a = zh[m]; zh[m] = k
            tf_ = build(zh, zero)
            bad = any(not zero_ok(z, zero[z][0], zero[z][1], fmap, tf_['SK'], tf_['sk_of']) for z in ZEROS)
            if bad: zh[m] = a; continue
            nd1, nd2, nalt = metrics_from(tf_, fmap)
            nj = J(nd1, nd2, nalt)
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                t = tf_; d1, d2, alt, cur = nd1, nd2, nalt, nj
                moved = f'zh {m}->{k}'
            else:
                zh[m] = a
        else:
            z = rng.choice(ZEROS)
            P = rng.choice(FREESLOTS); Q = rng.choice(LETTERS)
            old = zero[z]
            if P + Q == old: continue
            if any(zero[o] == P + Q for o in ZEROS if o != z): continue
            if not zero_ok(z, P, Q, fmap, t['SK'], t['sk_of']): continue
            zero[z] = P + Q
            tf_ = build(zh, zero)
            nd1, nd2, nalt = metrics_from(tf_, fmap)
            nj = J(nd1, nd2, nalt)
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                t = tf_; d1, d2, alt, cur = nd1, nd2, nalt, nj
                moved = f'zero {z}->{P+Q}'
            else:
                zero[z] = old
        if moved:
            dups = all_dups(fmap, zh, zero)
            if dups:
                print(f'\n[iter {it}] 首个违例 after: {moved}')
                print('  违例码:', dups)
                print('  fmap:', {X: fmap[X] for X in FINALS if fmap[X] in ('K',)})
                return fmap, zh, zero
    print('SA全程无违例')
    return fmap, zh, zero

fmap, zh, zero = sa_debug(9.0, 0.568, 0, SD_FMAP, SD_ZH, SD_ZERO, 150000, 11)
