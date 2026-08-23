#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""碰撞感知的模拟退火: 产出可用的双拼方案(零重码)。
约束: 声母键互异; 同键韵母不得与任何共有声母组合成有效音节(零冲突);
      12个零声母编码不与任何常规编码/彼此冲突。
目标: 最小化 单字当量+连续当量 (田生工具默认配置)。
"""
import random, json, sys
import numpy as np
from sp_eval import E, KEY2POS, freq, sheng_sd, yun_sd, specials_sd

KEYS = list('QWERTYUIOP' + 'ASDFGHJKL' + 'ZXCVBNM') if 'letters' in sys.argv \
    else list('QWERTYUIOP[]' + "ASDFGHJKL;'" + 'ZXCVBNM,./')
KI = {k: i for i, k in enumerate(KEYS)}
NL = len(KEYS)
LEFT = {KI[c] for c in 'QWERTASDFGZXCVB'}

inits = ['b','p','m','f','d','t','n','l','g','k','h','j','q','x','zh','ch',
         'sh','r','z','c','s','y','w']
finals = ['a','o','e','i','u','ü','ai','ei','ui','ao','ou','iu','ie','üe','ue',
          'an','en','in','un','ang','eng','ing','ong','ia','iao','ian','iang',
          'iong','ua','uai','uan','uang','uo']
FI = {f: i for i, f in enumerate(finals)}
II = {s: i for i, s in enumerate(inits)}
sp_syls = ['a','ai','an','ang','ao','o','ou','e','ei','en','eng','er']

reg, spq = [], []
for b, a, c in freq:
    (spq if b == '' else reg).append(
        (sp_syls.index(a), c) if b == '' else (II[b], FI[a], c))
reg_init = np.array([r[0] for r in reg]); reg_final = np.array([r[1] for r in reg])
reg_c = np.array([r[2] for r in reg], float)
sp_c = np.array([s[1] for s in spq], float)
tot = reg_c.sum() + sp_c.sum()
N, M = len(reg), len(spq)

Em = np.array([[E[KEY2POS[KEYS[i]]][KEY2POS[KEYS[j]]] for j in range(NL)]
               for i in range(NL)], float)

# 每个声母可搭配的韵母集合(静态)
finals_of = {u: frozenset(FI[a] for b, a, c in freq if b == u) for u in inits}
# 共键冲突频率(静态): 两个韵母共键时发生重码的音节频率
freq_of = {}
for b, a, c in freq:
    freq_of[(b, a)] = c
coll = [[0]*33 for _ in range(33)]
for i, f1 in enumerate(finals):
    for j, f2 in enumerate(finals):
        if i < j:
            w = sum(freq_of[(b, f1)] + freq_of[(b, f2)]
                    for b in inits if (b, f1) in freq_of and (b, f2) in freq_of)
            coll[i][j] = coll[j][i] = w

def metrics(sheng, yun, sp):
    kb = np.empty(N + M, int); ka = np.empty_like(kb)
    kb[:N] = sheng[reg_init]; ka[:N] = yun[reg_final]
    kb[N:] = sp[:, 0];        ka[N:] = sp[:, 1]
    c = np.concatenate([reg_c, sp_c])
    dcs = c @ Em[kb, ka] / tot
    G = np.bincount(ka, weights=c, minlength=NL)
    H = np.bincount(kb, weights=c, minlength=NL)
    return dcs, (G @ Em @ H) / (tot * tot)

def specials_ok(sheng, yun, sp):
    """零声母编码不与常规编码、彼此冲突"""
    for x in range(M):
        k1, k2 = sp[x]
        u = sheng.tolist().index(k1) if k1 in sheng.tolist() else None
        if u is not None:
            b = inits[u]
            for f in finals_of[b]:
                if yun[f] == k2:
                    return False
        for y in range(x + 1, M):
            if sp[y][0] == k1 and sp[y][1] == k2:
                return False
    return True

def rand_valid_yun(rng):
    """随机生成合法韵母布局(共键零冲突, 每键≤2)"""
    for _ in range(400):
        yun, key2f = [-1]*33, {k: [] for k in range(NL)}
        order = list(range(33)); rng.shuffle(order)
        good = True
        for f in order:
            cand = [k for k in range(NL)
                    if len(key2f[k]) < 2 and all(coll[f][g] == 0 for g in key2f[k])]
            if not cand: good = False; break
            k = rng.choice(cand); yun[f] = k; key2f[k].append(f)
        if good: return yun
    return None

def sa(seed, iters, init=None):
    rng = random.Random(seed)
    if init is None:
        sheng = rng.sample(range(NL), 23)
        yun = rand_valid_yun(rng)
    else:
        sheng, yun, sp0 = init
        sheng, yun, sp0 = sheng[:], yun[:], [p[:] for p in sp0]
    sp = sp0 if init else None
    if sp is None:
        for _ in range(200):
            cand = [[rng.randrange(NL), rng.randrange(NL)] for _ in range(M)]
            if specials_ok(np.array(sheng), np.array(yun), np.array(cand)):
                sp = cand; break
        if sp is None: sp = [[KI['A'], KI['A']]] * M
    key2f = {k: [] for k in range(NL)}
    for f, k in enumerate(yun): key2f[k].append(f)
    sha, yua, spa = np.array(sheng), np.array(yun), np.array(sp)
    cur = metrics(sha, yua, spa); curS = sum(cur)
    best = (curS, cur, sheng[:], yun[:], [p[:] for p in sp])
    T0, T1 = 0.05, 0.0004
    for it in range(iters):
        T = T0 * (T1 / T0) ** (it / iters)
        r = rng.random()
        bakS, bakY = sheng[:], yun[:]
        bakK = {k: v[:] for k, v in key2f.items()}
        bakSP = [p[:] for p in sp]
        ok = True
        if r < 0.40:                                   # 声母迁移/交换
            u = rng.randrange(23); t = rng.randrange(NL)
            occ = sheng.index(t) if t in sheng else None
            old = sheng[u]; sheng[u] = t
            if occ is not None: sheng[occ] = old
        elif r < 0.88:                                 # 韵母迁移/交换(零冲突)
            f = rng.randrange(33); t = rng.randrange(NL)
            old = yun[f]
            if old == t:
                ok = False
            elif len(key2f[t]) == 2:                   # 与目标键上的韵母交换
                f2 = key2f[t][rng.randrange(2)]
                f3 = [g for g in key2f[t] if g != f2][0]
                if len(key2f[old]) == 2:               # f 的旧搭档(修复: f 可能在首位)
                    oldmate = key2f[old][0] if key2f[old][0] != f else key2f[old][1]
                else:
                    oldmate = None
                if coll[f][f3] == 0 and (oldmate is None or coll[f2][oldmate] == 0):
                    yun[f] = t; yun[f2] = old
                    key2f[old].remove(f); key2f[old].append(f2)
                    key2f[t].remove(f2); key2f[t].append(f)
                else:
                    ok = False
            elif len(key2f[t]) == 1:
                f2 = key2f[t][0]
                if coll[f][f2] == 0:
                    yun[f] = t; key2f[old].remove(f); key2f[t].append(f)
                else:
                    ok = False
            else:
                yun[f] = t; key2f[old].remove(f); key2f[t].append(f)
        else:                                          # 零声母编码
            i = rng.randrange(M)
            sp[i] = [rng.randrange(NL), rng.randrange(NL)]
        if ok:
            sha, yua, spa = np.array(sheng), np.array(yun), np.array(sp)
            if not specials_ok(sha, yua, spa):
                ok = False
        if ok:
            m = metrics(sha, yua, spa); S = sum(m)
            if S < curS or rng.random() < pow(2.718281828, (curS - S) / T):
                curS, cur = S, m
                if S < best[0]:
                    best = (S, m, sheng[:], yun[:], [p[:] for p in sp])
                continue
        sheng, yun, sp, key2f = bakS, bakY, bakSP, bakK
    return best

# 种子: 首道
sheng0 = [KI[sheng_sd[u]] for u in inits]
yun0 = [KI[yun_sd[f]] for f in finals]
sp0 = [[KI[specials_sd[s][0]], KI[specials_sd[s][1]]] for s in sp_syls]
d0 = metrics(np.array(sheng0), np.array(yun0), np.array(sp0))
print(f'首道: 单字 {d0[0]:.2f}, 连续 {d0[1]:.2f}, 合计 {sum(d0):.2f}')

results = []
for tag, seed, init in [('首道种子', 11, (sheng0, yun0, sp0)),
                        ('随机A', 22, None), ('随机B', 33, None),
                        ('随机C', 44, None)]:
    S, m, sh, yu, sp = sa(seed, 500000, init)
    print(f'{tag}: 单字 {m[0]:.2f}, 连续 {m[1]:.2f}, 合计 {S:.2f}')
    results.append((S, m, sh, yu, sp))

S, m, sh, yu, sp = min(results, key=lambda r: r[0])
# 双手占比(音节内)
sha, yua = np.array(sh), np.array(yu)
kb = sha[reg_init]; ka = yua[reg_final]
dh = sum(reg_c[i] for i in range(N)
         if (kb[i] in LEFT) != (ka[i] in LEFT)) / reg_c.sum()
print(f'\n===== 零重码最优方案 =====')
print(f'单字当量 {m[0]:.2f}/10, 连续当量 {m[1]:.2f}/10, 音节内双手率 {dh*100:.1f}%')
print(f'(首道 13.03/13.70/56.7%, 首皇 ~12.89/13.67)')
print('\n声母: ' + ' '.join(f'{u}→{KEYS[k]}' for u, k in zip(inits, sh)))
print('韵母: ' + ' '.join(f'{f}→{KEYS[k]}' for f, k in zip(finals, yu)))
print('零声母: ' + ' '.join(f'{s}→{KEYS[a]}{KEYS[b]}' for s, (a, b) in zip(sp_syls, sp)))
json.dump({'dcs': m[0], 'dcd': m[1], 'sheng': {u: KEYS[k] for u, k in zip(inits, sh)},
           'yun': {f: KEYS[k] for f, k in zip(finals, yu)},
           'specials': {s: KEYS[a]+KEYS[b] for s, (a, b) in zip(sp_syls, sp)}},
          open('/workspace/best_scheme.json', 'w'), ensure_ascii=False, indent=1)
print('\n已保存 best_scheme.json')
