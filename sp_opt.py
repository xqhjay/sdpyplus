# 田生工具口径下的双拼方案全局优化器 v2
# 核心洞察: 声母层冻结 => 三指标对韵母赋值线性 => 容量受限指派问题
# 下界: 匈牙利算法(每键容量2, 忽略互补约束)  上界: 增量模拟退火(全约束)
import json, random, math
from collections import defaultdict
from itertools import permutations

data = json.load(open('/workspace/sp_data.json'))
MTX = data['matrix']
key2pos = {v: k for k, v in data['pos2key'].items() if v.strip()}
# 约束: 方案只涉及26个字母键盘 (排除工具支持的 ;[]',./ 等标点键)
LETTERS = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
POS = lambda k: key2pos[k]
HAND = lambda k: ('L' if ('0' < key2pos[k][1] < '6' or key2pos[k] == '36') else 'R')
freq = [tuple(x) for x in data['freq']]
T = sum(f[2] for f in freq)
PINKY = ('Q', 'A', 'P', 'Z')   # 首道文章关注的小指键

NATURAL = {'b':'B','p':'P','m':'M','f':'F','d':'D','t':'T','n':'N','l':'L','g':'G',
           'k':'K','h':'H','j':'J','q':'Q','x':'X','r':'R','z':'Z','c':'C','s':'S','y':'Y','w':'W'}
FIXED = {'a':'A','o':'O','e':'E','i':'I','u':'U'}
FINALS = ['ü','ai','ei','ui','ao','ou','iu','ie','üe','ue','an','en','in','un',
          'ang','eng','ing','ong','ia','iao','ian','iang','iong','ua','uai','uan','uang','uo']
ZEROS = ['a','ai','an','ang','ao','o','ou','e','ei','en','eng','er']
ALLF = FINALS + list(FIXED)
FREESLOTS = ['A','E','I','O','U','V']

final_syls = defaultdict(list); sheng_total = defaultdict(float)
for b, a, c in freq:
    if b: final_syls[a].append((b, c)); sheng_total[b] += c
zero_freq = {a: c for b, a, c in freq if b == ''}
freq_map = {X: dict(lst) for X, lst in final_syls.items()}
def conflict_mass(X, Y):
    fx, fy = freq_map.get(X, {}), freq_map.get(Y, {})
    return sum(min(c, fy[m]) for m, c in fx.items() if m in fy)
CM = {(X, Y): conflict_mass(X, Y) for X in ALLF for Y in ALLF}

# 固定韵母(a o e i u)音节: 贡献为常数(随zh/ch/sh位置变化), 不参与韵母指派
FIXSYL = [(b, FIXED[a], c) for b, a, c in freq if b and a in FIXED]
FIXA = defaultdict(float)
for b, ka, c in FIXSYL: FIXA[POS(ka)] += c

SD_ZH = {'zh':'V','ch':'I','sh':'E'}
SD_FMAP = {'iu':'Q','ua':'W','ie':'R','uan':'T','ang':'Y','iao':'P','ou':'S','ao':'D',
           'eng':'F','uai':'G','ing':'G','ong':'H','iong':'H','an':'J','en':'K','ia':'K',
           'ai':'L','ue':'L','un':'Z','iang':'X','uang':'X','in':'C','ü':'V','ui':'V',
           'üe':'B','ian':'N','ei':'M','uo':'O'}
SD_ZERO = {'a':'AA','ai':'AI','an':'AN','ang':'AY','ao':'AO','o':'OO','ou':'OU',
           'e':'UE','ei':'UI','en':'EN','eng':'UF','er':'ER'}

# ---------------- 精确评测(与工具逐位一致) + 完整审计 ----------------
def full_eval(fmap, zh, zero):
    SK = dict(NATURAL); SK.update(zh)
    d1 = alt = 0.0; A = defaultdict(float); B = defaultdict(float)
    seen = {}; collide = []
    kuse = defaultdict(float); rows = defaultdict(float)
    for b, a, c in freq:
        if b == '': kb, ka = zero[a][0], zero[a][1]
        else: kb, ka = SK[b], (fmap.get(a) or FIXED[a])
        code = kb + ka
        if code in seen: collide.append((seen[code][0], f'{b}{a}', code, min(c, seen[code][1])))
        else: seen[code] = (f'{b}{a}', c)
        d1 += c * MTX[POS(kb)][POS(ka)]
        alt += c if HAND(kb) != HAND(ka) else 0
        B[POS(kb)] += c; A[POS(ka)] += c
        kuse[kb] += c; kuse[ka] += c
        rows[key2pos[kb][0]] += c; rows[key2pos[ka][0]] += c
    d2 = sum(A[p1] * sum(B[p2] * MTX[p1][p2] for p2 in B) for p1 in A) / (T * T)
    tot2 = 2 * T
    return {'d1': d1 / T, 'd2': d2, 'alt': alt / T, 'collide': collide,
            'down': rows['3'] / tot2, 'mid': rows['2'] / tot2, 'up': rows['1'] / tot2,
            'pinky': sum(kuse[k] for k in PINKY) / tot2}

# ---------------- 约束检查 ----------------
def fmap_ok(X, k, fmap, zh, zero, tol):
    SK = dict(NATURAL); SK.update(zh)
    cnt = 0
    for Y in FINALS:
        if fmap.get(Y) == k: cnt += 1
    if cnt >= 2: return False                        # 每键最多2个自定义韵母
    for Y in ALLF:
        if Y == X: continue
        yk = fmap.get(Y) or FIXED.get(Y)
        if yk == k and CM[(X, Y)] > tol: return False  # 共居需分布互补(容错内)
    for z in ZEROS:
        P, Q = zero[z]
        if Q == k and P in [SK[m] for m in freq_map.get(X, {})]: return False
    return True

def zero_ok(z, P, Q, fmap, SK, sk_of):
    if any(o != z and code == P + Q for o, code in
           [(z2, fmap.get('x', '')) for z2 in []]): pass
    for m in sk_of.get(P, []):
        for Y in ALLF:
            if (fmap.get(Y) or FIXED.get(Y)) == Q and m in freq_map.get(Y, {}):
                return False
    return True

# ---------------- 匈牙利算法 (n<=m) ----------------
def hungarian(a):
    n = len(a); m = len(a[0])
    INF = float('inf')
    u = [0.0]*(n+1); v = [0.0]*(m+1); p = [0]*(m+1); way = [0]*(m+1)
    for i in range(1, n+1):
        p[0] = i; j0 = 0
        minv = [INF]*(m+1); used = [False]*(m+1)
        while True:
            used[j0] = True
            i0 = p[j0]; delta = INF; j1 = -1
            for j in range(1, m+1):
                if not used[j]:
                    cur = a[i0-1][j-1] - u[i0] - v[j]
                    if cur < minv[j]: minv[j] = cur; way[j] = j0
                    if minv[j] < delta: delta = minv[j]; j1 = j
            for j in range(m+1):
                if used[j]: u[p[j]] += delta; v[j] -= delta
                else: minv[j] -= delta
            j0 = j1
            if p[j0] == 0: break
        while j0:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
    tot = 0.0; assign = {}
    for j in range(1, m+1):
        if p[j]: tot += a[p[j]-1][j-1]; assign[p[j]-1] = j - 1
    return tot, assign

# ---------------- 表构建 ----------------
def build(zh, zero):
    SK = dict(NATURAL); SK.update(zh)
    cost1 = {}; alt1 = {}; PX = {}
    for X in FINALS:
        PX[X] = sum(c for _, c in final_syls[X])
        for k in LETTERS:
            p = POS(k)
            cost1[X, k] = sum(c * MTX[POS(SK[m])][p] for m, c in final_syls[X])
            alt1[X, k] = sum(c for m, c in final_syls[X] if HAND(SK[m]) != HAND(k))
    # 固定韵母音节贡献 (a o e i u): 只随 zh/ch/sh 位置变化
    fix1 = sum(c * MTX[POS(SK[b])][POS(ka)] for b, ka, c in FIXSYL)
    fixalt = sum(c for b, ka, c in FIXSYL if HAND(SK[b]) != HAND(ka))
    zb1 = sum(zero_freq[z] * MTX[POS(zero[z][0])][POS(zero[z][1])] for z in ZEROS)
    za = sum(zero_freq[z] * (HAND(zero[z][0]) != HAND(zero[z][1])) for z in ZEROS)
    B = defaultdict(float)
    for m, k in SK.items(): B[POS(k)] += sheng_total[m]
    for z in ZEROS: B[POS(zero[z][0])] += zero_freq[z]
    W = {POS(k): sum(B[p2] * MTX[POS(k)][p2] for p2 in B) for k in LETTERS}
    fix2 = sum(pa * W[p] for p, pa in FIXA.items())
    zA = fix2 + sum(zero_freq[z] * W[POS(zero[z][1])] for z in ZEROS)
    sk_of = defaultdict(list)
    for m, k in SK.items(): sk_of[k].append(m)
    return dict(SK=SK, cost1=cost1, alt1=alt1, PX=PX, fix1=fix1, fixalt=fixalt,
                zb1=zb1, za=za, W=W, zA=zA, B=B, sk_of=sk_of)

def metrics_from(t, fmap):
    d1 = (t['fix1'] + t['zb1'] + sum(t['cost1'][X, fmap[X]] for X in FINALS)) / T
    d2 = (t['zA'] + sum(t['PX'][X] * t['W'][POS(fmap[X])] for X in FINALS)) / (T * T)
    alt = (t['fixalt'] + t['za'] + sum(t['alt1'][X, fmap[X]] for X in FINALS)) / T
    return d1, d2, alt

# ---------------- 零声母轻量重算 (复用 cost1/alt1/PX) ----------------
def zero_apply(base_t, zero):
    t = dict(base_t)
    B = defaultdict(float)
    for m, k in t['SK'].items(): B[POS(k)] += sheng_total[m]
    for z in ZEROS: B[POS(zero[z][0])] += zero_freq[z]
    W = {POS(k): sum(B[p2] * MTX[POS(k)][p2] for p2 in B) for k in LETTERS}
    zb1 = sum(zero_freq[z] * MTX[POS(zero[z][0])][POS(zero[z][1])] for z in ZEROS)
    za = sum(zero_freq[z] * (HAND(zero[z][0]) != HAND(zero[z][1])) for z in ZEROS)
    fix2 = sum(pa * W[p] for p, pa in FIXA.items())
    zA = fix2 + sum(zero_freq[z] * W[POS(zero[z][1])] for z in ZEROS)
    t.update(B=B, W=W, zb1=zb1, za=za, zA=zA)
    return t

# ---------------- 收敛打磨: 局部搜索至无改进 ----------------
def make_J(w1, w2, altT, lam=250.0):
    # J = w1*单字 + w2*连续 + lam*max(0, altT-互击)  软惩罚提供连续梯度
    return lambda a, b, c: w1 * a + w2 * b + lam * max(0.0, altT - c)

def sanitize(fmap, zh, zero, tol=0):
    """清除初始方案自带的同码歧义(首道: den/dia@DK 质量1): 冲突韵母迁至d1增量最小的合法键"""
    fmap = dict(fmap)
    t = build(zh, zero)
    for _ in range(20):
        pairs = [(CM[(X, Y)], X, Y) for i, X in enumerate(FINALS) for Y in FINALS[i + 1:]
                 if fmap[X] == fmap[Y] and CM[(X, Y)] > tol]
        if not pairs: break
        _, X, Y = pairs[0]
        best = None
        for Z in (X, Y):
            for k in LETTERS:
                if k == fmap[Z] or not fmap_ok(Z, k, fmap, zh, zero, tol): continue
                dc = t['cost1'][Z, k] - t['cost1'][Z, fmap[Z]]
                if best is None or dc < best[0]: best = (dc, Z, k)
        assert best, 'sanitize: 冲突韵母无合法迁移'
        fmap[best[1]] = best[2]
    return fmap

def polish(fmap, zh, zero, w1, w2, altT, tol, max_rounds=12, lam=250.0):
    J = make_J(w1, w2, altT, lam)
    t = build(zh, zero)
    d1, d2, alt = metrics_from(t, fmap)
    cur = J(d1, d2, alt)
    fmap = dict(fmap); zh = dict(zh); zero = dict(zero)
    for rd in range(max_rounds):
        improved = False
        # 1) 单个韵母迁移
        for X in FINALS:
            for k in LETTERS:
                a = fmap[X]
                if k == a or not fmap_ok(X, k, fmap, zh, zero, tol): continue
                nd1 = d1 + (t['cost1'][X, k] - t['cost1'][X, a]) / T
                nd2 = d2 + t['PX'][X] * (t['W'][POS(k)] - t['W'][POS(a)]) / (T * T)
                nalt = alt + (t['alt1'][X, k] - t['alt1'][X, a]) / T
                nj = J(nd1, nd2, nalt)
                if nj < cur - 1e-12:
                    fmap[X] = k; d1, d2, alt, cur = nd1, nd2, nalt, nj; improved = True
        # 2) 两韵母交换
        for i, X in enumerate(FINALS):
            for Y in FINALS[i + 1:]:
                a, b = fmap[X], fmap[Y]
                if a == b: continue
                tf = dict(fmap); tf[X], tf[Y] = b, a
                if not (fmap_ok(X, b, tf, zh, zero, tol) and fmap_ok(Y, a, tf, zh, zero, tol)): continue
                nd1 = d1 + (t['cost1'][X, b] - t['cost1'][X, a] + t['cost1'][Y, a] - t['cost1'][Y, b]) / T
                nd2 = d2 + (t['PX'][X] * (t['W'][POS(b)] - t['W'][POS(a)])
                            + t['PX'][Y] * (t['W'][POS(a)] - t['W'][POS(b)])) / (T * T)
                nalt = alt + (t['alt1'][X, b] - t['alt1'][X, a] + t['alt1'][Y, a] - t['alt1'][Y, b]) / T
                nj = J(nd1, nd2, nalt)
                if nj < cur - 1e-12:
                    fmap = tf; d1, d2, alt, cur = nd1, nd2, nalt, nj; improved = True
        # 3) zh/ch/sh 移动 (三者必须互异)
        for m in ('zh', 'ch', 'sh'):
            for k in FREESLOTS:
                if k == zh[m] or k in zh.values(): continue
                old = zh[m]; zh[m] = k
                tf_ = build(zh, zero)
                if any(not zero_ok(z, zero[z][0], zero[z][1], fmap, tf_['SK'], tf_['sk_of']) for z in ZEROS):
                    zh[m] = old; continue
                nd1, nd2, nalt = metrics_from(tf_, fmap)
                nj = J(nd1, nd2, nalt)
                if nj < cur - 1e-12:
                    t = tf_; d1, d2, alt, cur = nd1, nd2, nalt, nj; improved = True
                else:
                    zh[m] = old
        # 4) 零声母重编码
        for z in ZEROS:
            old = zero[z]
            for P in FREESLOTS:
                for Q in LETTERS:
                    if P + Q == old or any(zero[o] == P + Q for o in ZEROS if o != z): continue
                    zero[z] = P + Q
                    if not zero_ok(z, P, Q, fmap, t['SK'], t['sk_of']):
                        zero[z] = old; continue
                    tt = zero_apply(t, zero)
                    nd1, nd2, nalt = metrics_from(tt, fmap)
                    nj = J(nd1, nd2, nalt)
                    if nj < cur - 1e-12:
                        t = tt; d1, d2, alt, cur = nd1, nd2, nalt, nj; improved = True
                    else:
                        zero[z] = old
        if not improved: break
    return fmap, zh, zero, cur

# ---------------- 模拟退火 (全增量) ----------------
def sa(w1, w2, altT, tol, fmap0, zh0, zero0, iters=250000, seed=1, lam=250.0):
    rng = random.Random(seed)
    fmap = dict(fmap0); zh = dict(zh0); zero = dict(zero0)
    t = build(zh, zero)
    d1, d2, alt = metrics_from(t, fmap)
    J = make_J(w1, w2, altT, lam)
    cur = J(d1, d2, alt)
    best = (cur, dict(fmap), dict(zh), dict(zero))
    T0, T1 = 0.035, 0.00025
    M = MTX
    for it in range(iters):
        temp = T0 * (T1 / T0) ** (it / iters)
        r = rng.random()
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
        elif r < 0.86:
            m = rng.choice(['zh', 'ch', 'sh'])
            k = rng.choice(FREESLOTS)
            if k in zh.values() or k == zh[m]: continue
            a = zh[m]; zh[m] = k
            tf_ = build(zh, zero)                       # 结构变化重建(低频路径)
            bad = any(not zero_ok(z, zero[z][0], zero[z][1], fmap, tf_['SK'], tf_['sk_of']) for z in ZEROS)
            if bad: zh[m] = a; continue
            nd1, nd2, nalt = metrics_from(tf_, fmap)
            nj = J(nd1, nd2, nalt)
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                t = tf_; d1, d2, alt, cur = nd1, nd2, nalt, nj
            else: zh[m] = a
        else:
            z = rng.choice(ZEROS)
            P = rng.choice(FREESLOTS); Q = rng.choice(LETTERS)
            old = zero[z]
            if P + Q == old: continue
            if any(zero[o] == P + Q for o in ZEROS if o != z): continue
            if not zero_ok(z, P, Q, fmap, t['SK'], t['sk_of']): continue
            zero[z] = P + Q
            tf_ = zero_apply(t, zero)                  # 轻量重算(复用cost1/alt1/PX)
            nd1, nd2, nalt = metrics_from(tf_, fmap)
            nj = J(nd1, nd2, nalt)
            if nj <= cur or rng.random() < math.exp((cur - nj) / temp):
                t = tf_; d1, d2, alt, cur = nd1, nd2, nalt, nj
            else: zero[z] = old
        if cur < best[0]: best = (cur, dict(fmap), dict(zh), dict(zero))
    return best

# ---------------- 容量受限下界 (匈牙利) ----------------
def capacity_lb(zh, zero, cap=2):
    t = build(zh, zero)
    cols = []
    for k in LETTERS:
        for _ in range(cap): cols.append(k)
    A1 = [[t['cost1'][X, k] for k in cols] for X in FINALS]
    A2 = [[t['PX'][X] * t['W'][POS(k)] for k in cols] for X in FINALS]
    h1, _ = hungarian(A1)
    h2, _ = hungarian(A2)
    return (t['fix1'] + t['zb1'] + h1) / T, (t['zA'] + h2) / (T * T)

if __name__ == '__main__':
    import time
    t_start = time.time()

    def encode(fmap, zh, zero):
        return (zh['zh'] + zh['ch'] + zh['sh']
                + ''.join(fmap[X] for X in FINALS)
                + ''.join(zero[z] for z in ZEROS))

    sd = full_eval(SD_FMAP, SD_ZH, SD_ZERO)
    print(f"基准·首道双拼 : 单字{sd['d1']:.4f} 连续{sd['d2']:.4f} 互击{sd['alt']*100:.2f}% "
          f"下排{sd['down']*100:.1f}% 小指QAPZ{sd['pinky']*100:.1f}% 歧义质量{sum(x[3] for x in sd['collide'])}")
    # 下界: 首道框架 + zh/ch/sh 全遍历
    lb1, lb2 = capacity_lb(SD_ZH, SD_ZERO)
    for zhc in permutations(FREESLOTS, 3):
        z = {'zh': zhc[0], 'ch': zhc[1], 'sh': zhc[2]}
        a1, a2 = capacity_lb(z, SD_ZERO)
        lb1, lb2 = min(lb1, a1), min(lb2, a2)
    print(f"容量下界(键容2, zh/ch/sh遍历, 零声母=首道): 单字{lb1:.4f} 连续{lb2:.4f}")
    print(f"方案串(首道): {encode(SD_FMAP, SD_ZH, SD_ZERO)}")

    out = []

    def save():
        json.dump(out, open('/workspace/sp_results.json', 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, default=str)

    def record(name, fmap, zh, zero):
        # 方案有效性硬校验: zh/ch/sh互异 + 键全在26字母 + 零歧义
        assert len({zh['zh'], zh['ch'], zh['sh']}) == 3, f'{name}: zh/ch/sh 同键'
        assert all(k in LETTERS for k in fmap.values()), f'{name}: 韵母越界键'
        assert all(c[0] in FREESLOTS and c[1] in LETTERS for c in zero.values()), f'{name}: 零声母越界键'
        v = full_eval(fmap, zh, zero)
        assert not v['collide'], f'{name}: 存在同码歧义 {v["collide"][:3]}'
        out.append({'name': name, 'fmap': fmap, 'zh': zh, 'zero': zero,
                    'scheme': encode(fmap, zh, zero), 'metrics': v})
        save()
        print(f"\n[{name}] 精确复核: 单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% "
              f"下排{v['down']*100:.1f}% 小指QAPZ{v['pinky']*100:.1f}% "
              f"({time.time()-t_start:.0f}s)")
        if v['collide']: print('  歧义:', v['collide'])
        print(f"  zh/ch/sh={zh}  零声母={zero}")
        km = defaultdict(list)
        for X, k in fmap.items(): km[k].append(X)
        print('  键位:', ' '.join(f"{k}:{'/'.join(vs)}" for k, vs in sorted(km.items())))
        print(f"  方案串: {encode(fmap, zh, zero)}")
        return v

    ITERS = 150000

    def optimize(name, w1, w2, altT, tol, init, seeds, lam=250.0):
        cand = None
        for s in seeds:
            b = sa(w1, w2, altT, tol, *init, iters=ITERS, seed=s, lam=lam)
            if cand is None or b[0] < cand[0]: cand = b
        _, fmap, zh, zero = cand
        fmap, zh, zero, _ = polish(fmap, zh, zero, w1, w2, altT, tol, lam=lam)
        return record(name, fmap, zh, zero), (fmap, zh, zero)

    # 初始点消毒: 首道自带 den/dia@DK 同码歧义(质量1), 消歧后作为干净起点
    clean_fmap = sanitize(SD_FMAP, SD_ZH, SD_ZERO)
    cv = full_eval(clean_fmap, SD_ZH, SD_ZERO)
    print(f"首道·消歧后 : 单字{cv['d1']:.4f} 连续{cv['d2']:.4f} 互击{cv['alt']*100:.2f}% "
          f"歧义数{len(cv['collide'])}")
    base = (clean_fmap, SD_ZH, SD_ZERO)

    # S1 旗舰: 单字+连续等权, 互击率不低于首道56.8%
    v1, s1 = optimize('均衡双优', 1.0, 1.0, 0.568, 0, base, (11, 22, 33, 44, 55))
    # S2 互击率天花板探针: 纯互击率最大化(无视当量)
    v2, s2 = optimize('互击率极限', 0.0, 0.0, 1.0, 0, base, (11, 22, 33), lam=1.0)
    # S3/S4 帕累托前沿两极
    v3, s3 = optimize('单字极值', 1.0, 0.0, 0.568, 0, base, (11, 22, 33))
    v4, s4 = optimize('连续极值', 0.0, 1.0, 0.568, 0, base, (11, 22, 33))
    # S5 旗舰高互击变体: 在S1邻域把互击率推向天花板
    v5, s5 = optimize('均衡·互击推高', 1.0, 1.0, 0.615, 0, s1, (77, 88, 99))

    print(f"\n=== 汇总 ({time.time()-t_start:.0f}s) ===")
    print(f"{'方案':<12}{'单字':>9}{'连续':>9}{'互击%':>8}{'下排%':>7}{'小指%':>7}")
    print(f"{'首道双拼':<12}{sd['d1']:>9.4f}{sd['d2']:>9.4f}{sd['alt']*100:>8.2f}{sd['down']*100:>7.1f}{sd['pinky']*100:>7.1f}")
    print(f"{'首道·消歧':<12}{cv['d1']:>9.4f}{cv['d2']:>9.4f}{cv['alt']*100:>8.2f}{cv['down']*100:>7.1f}{cv['pinky']*100:>7.1f}")
    for r in out:
        m = r['metrics']
        print(f"{r['name']:<12}{m['d1']:>9.4f}{m['d2']:>9.4f}{m['alt']*100:>8.2f}{m['down']*100:>7.1f}{m['pinky']*100:>7.1f}")
    print(f"{'下界':<12}{lb1:>9.4f}{lb2:>9.4f}")
    save()
    print('结果已保存 -> /workspace/sp_results.json')
