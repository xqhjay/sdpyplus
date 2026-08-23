#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在田生工具默认配置下, 对双拼布局做全局优化(模拟退火)。
变量空间: 23声母(互异键) + 33韵母(每键至多2个) + 12零声母音节编码, 键池=33键。
目标: 最小化 单字当量+连续当量 (与官方口径一致)。
"""
import re, random, numpy as np
from sp_eval import (E, KEY2POS, freq, sheng_sd, yun_sd, specials_sd, evaluate)

KEYS = list('QWERTYUIOP[]' + "ASDFGHJKL;'" + 'ZXCVBNM,./')   # 33个物理键
KI = {k: i for i, k in enumerate(KEYS)}          # 键字母 -> 0..32
NL = len(KEYS)

# ---- 单元定义 ----
inits = ['b','p','m','f','d','t','n','l','g','k','h','j','q','x','zh','ch',
         'sh','r','z','c','s','y','w']           # 23 声母
finals = ['a','o','e','i','u','ü','ai','ei','ui','ao','ou','iu','ie','üe','ue',
          'an','en','in','un','ang','eng','ing','ong','ia','iao','ian','iang',
          'iong','ua','uai','uan','uang','uo']   # 33 韵母(工具口径, üe/ue分离)
FI = {f: i for i, f in enumerate(finals)}
II = {s: i for i, s in enumerate(inits)}
sp_syls = ['a','ai','an','ang','ao','o','ou','e','ei','en','eng','er']  # 12 零声母

# ---- 音节数组 ----
reg_idx, sp_idx = [], []
for b, a, c in freq:
    if b == '':
        sp_idx.append((sp_syls.index(a), c))
    else:
        reg_idx.append((II[b], FI[a], c))
reg_init = np.array([r[0] for r in reg_idx]); reg_final = np.array([r[1] for r in reg_idx])
reg_c = np.array([r[2] for r in reg_idx], float)
sp_row = np.array([s[0] for s in sp_idx]); sp_c = np.array([s[1] for s in sp_idx], float)
tot = reg_c.sum() + sp_c.sum()

Em = np.array([[E[KEY2POS[KEYS[i]]][KEY2POS[KEYS[j]]] for j in range(NL)]
               for i in range(NL)], float)

def metrics(sheng, yun, sp):
    """sheng: (23,)键下标; yun: (33,)键下标; sp: (12,2)键下标"""
    kb = np.empty(len(reg_idx) + len(sp_idx), int)
    ka = np.empty_like(kb)
    n = len(reg_idx)
    kb[:n] = sheng[reg_init]; ka[:n] = yun[reg_final]
    kb[n:] = sp[:, 0];        ka[n:] = sp[:, 1]
    c = np.concatenate([reg_c, sp_c])
    dcs = c @ Em[kb, ka] / tot
    G = np.bincount(ka, weights=c, minlength=NL)
    H = np.bincount(kb, weights=c, minlength=NL)
    dcd = (G @ Em @ H) / (tot * tot)
    return dcs, dcd

def sa(seed, iters=400000, init=None):
    rng = random.Random(seed)
    np.random.seed(seed)
    if init is None:
        sheng = np.array(rng.sample(range(NL), 23))
        yun = np.array(rng.sample(range(NL), 33))
    else:
        sheng, yun, sp0 = init
        sheng = sheng.copy(); yun = yun.copy()
        sp0 = sp0.copy()
    sp = np.array([[rng.randrange(NL), rng.randrange(NL)] for _ in range(12)]) \
        if init is None else sp0
    key2finals = {k: [] for k in range(NL)}
    for f, k in enumerate(yun): key2finals[k].append(f)
    cur = metrics(sheng, yun, sp); curS = cur[0] + cur[1]
    best = (curS, cur, sheng.copy(), yun.copy(), sp.copy())
    T0, T1 = 0.06, 0.0005
    for it in range(iters):
        T = T0 * (T1 / T0) ** (it / iters)
        r = rng.random()
        if r < 0.45:                                   # 声母: 迁移/交换
            u = rng.randrange(23); t = rng.randrange(NL)
            old = sheng[u]
            occ = np.where(sheng == t)[0]
            sheng[u] = t
            if len(occ): sheng[occ[0]] = old
        elif r < 0.90:                                 # 韵母: 迁移/交换
            f = rng.randrange(33); t = rng.randrange(NL)
            old = yun[f]
            if old == t: continue
            fl = key2finals[t]
            if len(fl) >= 2:                           # 交换
                f2 = fl[rng.randrange(len(fl))]
                yun[f] = t; yun[f2] = old
                key2finals[t].remove(f2); key2finals[t].append(f)
                key2finals[old].remove(f); key2finals[old].append(f2)
            else:                                      # 迁移
                yun[f] = t
                key2finals[old].remove(f); key2finals[t].append(f)
        else:                                          # 零声母编码
            i = rng.randrange(12); sp[i, 0] = rng.randrange(NL); sp[i, 1] = rng.randrange(NL)
        m = metrics(sheng, yun, sp); S = m[0] + m[1]
        if S < curS or rng.random() < pow(2.718281828, (curS - S) / T):
            curS, cur = S, m
            if S < best[0]:
                best = (S, m, sheng.copy(), yun.copy(), sp.copy())
        else:                                          # 回滚
            if r < 0.45:
                sheng[:] = best[2] if S > 1e9 else sheng  # 占位(不触发)
                # 直接重算上一状态(简单起见, 用best恢复太粗暴, 这里重新构造)
    return best

def sa_clean(seed, iters=400000, init=None):
    """无回滚bug版本: 保存/恢复完整状态"""
    rng = random.Random(seed)
    if init is None:
        sheng = list(rng.sample(range(NL), 23))
        yun = list(rng.sample(range(NL), 33))
        sp = [[rng.randrange(NL), rng.randrange(NL)] for _ in range(12)]
    else:
        sheng, yun, sp = [list(x) for x in init]
    key2finals = {k: [] for k in range(NL)}
    for f, k in enumerate(yun): key2finals[k].append(f)
    sha = np.array(sheng); yua = np.array(yun); spa = np.array(sp)
    cur = metrics(sha, yua, spa); curS = cur[0] + cur[1]
    best = (curS, cur, sheng[:], yun[:], [p[:] for p in sp])
    T0, T1 = 0.06, 0.0005
    for it in range(iters):
        T = T0 * (T1 / T0) ** (it / iters)
        r = rng.random()
        bak = (sheng[:], yun[:], [p[:] for p in sp],
               {k: v[:] for k, v in key2finals.items()})
        if r < 0.45:
            u = rng.randrange(23); t = rng.randrange(NL)
            occ = [u2 for u2 in range(23) if sheng[u2] == t]
            sheng[u] = t
            if occ: sheng[occ[0]] = bak[0][u]
        elif r < 0.90:
            f = rng.randrange(33); t = rng.randrange(NL)
            old = yun[f]
            if old != t:
                fl = key2finals[t]
                if len(fl) >= 2:
                    f2 = fl[rng.randrange(len(fl))]
                    yun[f] = t; yun[f2] = old
                    key2finals[t].remove(f2); key2finals[t].append(f)
                    key2finals[old].remove(f); key2finals[old].append(f2)
                else:
                    yun[f] = t
                    key2finals[old].remove(f); key2finals[t].append(f)
        else:
            i = rng.randrange(12)
            sp[i] = [rng.randrange(NL), rng.randrange(NL)]
        sha = np.array(sheng); yua = np.array(yun); spa = np.array(sp)
        m = metrics(sha, yua, spa); S = m[0] + m[1]
        if S < curS or rng.random() < pow(2.718281828, (curS - S) / T):
            curS, cur = S, m
            if S < best[0]:
                best = (S, m, sheng[:], yun[:], [p[:] for p in sp])
        else:
            sheng, yun, sp, key2finals = bak
    return best

# ---- 首道作为种子 ----
sheng0 = [KI[sheng_sd[u]] for u in inits]
yun0 = [KI[yun_sd[f]] for f in finals]
sp0 = [[KI[specials_sd[s][0]], KI[specials_sd[s][1]]] for s in sp_syls]
d0 = metrics(np.array(sheng0), np.array(yun0), np.array(sp0))
print(f'首道(校验): 单字 {d0[0]:.2f}, 连续 {d0[1]:.2f}, 合计 {d0[0]+d0[1]:.2f}')

results = []
for tag, seed, init in [('首道种子', 1, (sheng0, yun0, sp0)),
                        ('随机种子A', 2, None), ('随机种子B', 3, None)]:
    S, m, sh, yu, sp = sa_clean(seed, 400000, init)
    print(f'{tag}: 单字 {m[0]:.2f}, 连续 {m[1]:.2f}, 合计 {S:.2f}')
    results.append((S, m, sh, yu, sp))

S, m, sh, yu, sp = min(results, key=lambda r: r[0])
print('\n===== 最优布局 =====')
print(f'单字当量 {m[0]:.2f}/10, 连续当量 {m[1]:.2f}/10 (首道: 13.03/13.70, 首皇: ~12.89/13.67)')
inv_s = {v: k for k, v in zip(inits, sh)}
print('\n声母: ' + ' '.join(f'{u}→{KEYS[k]}' for u, k in zip(inits, sh) if KEYS[k] not in ',./[]\''))
print('韵母: ' + ' '.join(f'{f}→{KEYS[k]}' for f, k in zip(finals, yu)))
print('零声母: ' + ' '.join(f'{s}→{KEYS[a]}{KEYS[b]}' for s, (a, b) in zip(sp_syls, sp)))
# 共键韵母(潜在重码)检查
from collections import defaultdict
kk = defaultdict(list)
for f, k in enumerate(yu): kk[k].append(finals[f])
sylset = {(b, a) for b, a, c in freq}
coll = 0.0
for k, fl in kk.items():
    if len(fl) > 1:
        for b in inits:
            if (b, fl[0]) in sylset and (b, fl[1]) in sylset:
                w = sum(c for bb, aa, c in freq if bb == b and aa in fl)
                coll += w
                print(f'  共键冲突: {KEYS[k]}={fl} 与声母{b} (频率{w:,})')
print(f'共键韵母总冲突频率: {coll:,} ({coll/tot*100:.3f}%)')
