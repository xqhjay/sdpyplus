# 旗舰精修: 恢复上轮最优方案做种子, 在互击率>=60.8%(贴天花板)约束下压最低 d1+d2
import json, time
src = open('/workspace/sp_opt.py', encoding='utf-8').read()
exec(src.split("if __name__")[0])

t0 = time.time()

# ---- 上轮保存的均衡双优 (J=26.4691, alt=60.68%, 已通过零歧义断言) ----
OLD_S1_FMAP = {'iu':'R','ua':'D','ie':'C','uan':'Q','ang':'H','iao':'B','ou':'F','ao':'P',
               'eng':'M','uai':'T','ing':'G','ong':'K','iong':'K','an':'Y','en':'N','ia':'J',
               'ai':'L','ue':'L','un':'V','iang':'X','uang':'G','in':'S','ü':'T','ui':'S',
               'üe':'W','ian':'D','ei':'J','uo':'O'}
OLD_S1_ZH = {'zh':'A','ch':'V','sh':'E'}
OLD_S1_ZERO = {'a':'OS','ai':'IE','an':'EK','ang':'UE','ao':'OG','o':'UI','ou':'IF',
               'e':'AJ','ei':'EX','en':'US','eng':'UH','er':'EJ'}

v = full_eval(OLD_S1_FMAP, OLD_S1_ZH, OLD_S1_ZERO)
print(f"上轮均衡双优复核: 单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% "
      f"歧义{v['collide']} J={v['d1']+v['d2']:.4f}")

# ---- 理论互击率上界 (忽略共居/容量/冲突约束, 每韵母独立选最优手) ----
Lmass = defaultdict(float); Rmass = defaultdict(float)
for b, a, c in freq:
    if not b: continue
    k = (dict(NATURAL) | OLD_S1_ZH)[b] if b in ('zh','ch','sh') else NATURAL[b]
    (Lmass if HAND(k) == 'L' else Rmass)[a] += c
# zh/ch/sh 键位可选(3左3右), 其音节质量按可任一手计入上界: 直接给"最优手"
bound = sum(zero_freq.values())
for X in ALLF:
    lb = Lmass[X]; rb = Rmass[X]
    if X in FINALS:
        bound += max(lb, rb)          # 韵母可放任一手 -> 取大者
    else:
        k = FIXED[X]                  # 固定韵母: 手固定, 按实际手计
        bound += lb if HAND(k) == 'L' else rb
print(f"理论互击率上界(逐韵母独立最优手): {bound/T*100:.2f}%  (零声母质量占比 {sum(zero_freq.values())/T*100:.2f}%)")

# ---- 精修: 从两个最优种子出发, altT=0.608 锁互击率, min(d1+d2) ----
res = json.load(open('/workspace/sp_results.json'))
S5 = next(r for r in res if r['name'] == '均衡·互击推高')
S5_init = (S5['fmap'], S5['zh'], S5['zero'])
OLD_init = (OLD_S1_FMAP, OLD_S1_ZH, OLD_S1_ZERO)

ITERS = 200000
cands = []
for name, init in (('旧S1', OLD_init), ('新S5', S5_init)):
    for seed in (201, 202, 203, 204):
        b = sa(1.0, 1.0, 0.608, 0, *init, iters=ITERS, seed=seed)
        fmap, zh, zero = b[1], b[2], b[3]
        fmap, zh, zero, _ = polish(fmap, zh, zero, 1.0, 1.0, 0.608, 0)
        vv = full_eval(fmap, zh, zero)
        assert not vv['collide'], f'{name}/{seed}: {vv["collide"][:3]}'
        cands.append((vv['d1'] + vv['d2'], vv['alt'], name, seed, fmap, zh, zero))
        print(f"[{name} seed{seed}] 单字{vv['d1']:.4f} 连续{vv['d2']:.4f} "
              f"互击{vv['alt']*100:.2f}% J={vv['d1']+vv['d2']:.4f} ({time.time()-t0:.0f}s)")

cands.sort(key=lambda x: (x[0], -x[1]))
J, alt, name, seed, fmap, zh, zero = cands[0]
v = full_eval(fmap, zh, zero)
print(f"\n=== 旗舰定稿 (源:{name} seed{seed}) ===")
print(f"单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% "
      f"下排{v['down']*100:.1f}% 小指QAPZ{v['pinky']*100:.1f}% 歧义{v['collide']}")
km = defaultdict(list)
for X, k in fmap.items(): km[k].append(X)
print('键位:', ' '.join(f"{k}:{'/'.join(vs)}" for k, vs in sorted(km.items())))
print('zh/ch/sh:', zh, ' 零声母:', zero)
scheme = (zh['zh'] + zh['ch'] + zh['sh'] + ''.join(fmap[X] for X in FINALS)
          + ''.join(zero[z] for z in ZEROS))
print('方案串:', scheme)
json.dump({'name': '旗舰·首道plus', 'fmap': fmap, 'zh': zh, 'zero': zero,
           'scheme': scheme, 'metrics': v},
          open('/workspace/sp_flagship.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1, default=str)
print('已保存 -> /workspace/sp_flagship.json')
