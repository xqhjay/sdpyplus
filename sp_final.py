# 最终整编: 锁定互击>=60% 的 J 最小化 + 连续加权变体, 并用 extract_tool 独立交叉验证
import json, time
src = open('/workspace/sp_opt.py', encoding='utf-8').read()
exec(src.split("if __name__")[0])
t0 = time.time()

OLD_S1 = ({'iu':'R','ua':'D','ie':'C','uan':'Q','ang':'H','iao':'B','ou':'F','ao':'P',
           'eng':'M','uai':'T','ing':'G','ong':'K','iong':'K','an':'Y','en':'N','ia':'J',
           'ai':'L','ue':'L','un':'V','iang':'X','uang':'G','in':'S','ü':'T','ui':'S',
           'üe':'W','ian':'D','ei':'J','uo':'O'},
          {'zh':'A','ch':'V','sh':'E'},
          {'a':'OS','ai':'IE','an':'EK','ang':'UE','ao':'OG','o':'UI','ou':'IF',
           'e':'AJ','ei':'EX','en':'US','eng':'UH','er':'EJ'})
res = json.load(open('/workspace/sp_results.json'))
def get(n): r = next(x for x in res if x['name'] == n); return (r['fmap'], r['zh'], r['zero'])
FLAG = get('均衡·互击推高')          # 主流程 S5
NEW_S1 = get('均衡双优'); D1E = get('单字极值'); D2E = get('连续极值')
refi = json.load(open('/workspace/sp_flagship.json'))
REFI = (refi['fmap'], refi['zh'], refi['zero'])
ALT_MAX = get('互击率极限')

ITERS = 200000
def run(name, w1, w2, altT, init, seeds):
    best = None
    for s in seeds:
        b = sa(w1, w2, altT, 0, *init, iters=ITERS, seed=s)
        fmap, zh, zero = b[1], b[2], b[3]
        fmap, zh, zero, _ = polish(fmap, zh, zero, w1, w2, altT, 0)
        v = full_eval(fmap, zh, zero)
        assert not v['collide'], f'{name}/{s}: {v["collide"][:3]}'
        J = v['d1'] + v['d2']
        if best is None or J < best[0]: best = (J, v['alt'], fmap, zh, zero, v)
        print(f"  [{name} s{s}] 单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% J={J:.4f} ({time.time()-t0:.0f}s)")
    return best

print('== A: 锁互击>=60% 的 J 最小化 ==')
cands = []
for tag, init in (('精修旗舰', REFI), ('旧S1', OLD_S1), ('单字极值', D1E), ('新S1', NEW_S1)):
    b = run(tag, 1.0, 1.0, 0.60, init, (301, 302))
    cands.append(b)
print('== B: 连续加权 1:1.6 变体 ==')
for tag, init in (('精修旗舰', REFI), ('新S1', NEW_S1)):
    b = run(tag + '·w1.6', 1.0, 1.6, 0.60, init, (401, 402))
    cands.append(b)

cands.sort(key=lambda x: x[0])
print('\n=== 终选排序 (J=d1+d2) ===')
for J, alt, fmap, zh, zero, v in cands:
    print(f"J={J:.4f}  单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{alt*100:.2f}%")

J, alt, fmap, zh, zero, v = cands[0]
print(f"\n=== 旗舰终版 ===")
print(f"单字{v['d1']:.4f} 连续{v['d2']:.4f} 互击{v['alt']*100:.2f}% "
      f"下排{v['down']*100:.1f}% 小指QAPZ{v['pinky']*100:.1f}% 歧义{v['collide']}")
km = defaultdict(list)
for X, k in fmap.items(): km[k].append(X)
print('键位:', ' '.join(f"{k}:{'/'.join(vs)}" for k, vs in sorted(km.items())))
print('zh/ch/sh:', zh)
print('零声母:', zero)
scheme = (zh['zh'] + zh['ch'] + zh['sh'] + ''.join(fmap[X] for X in FINALS)
          + ''.join(zero[z] for z in ZEROS))
print('方案串:', scheme)
json.dump({'name': '旗舰终版', 'fmap': fmap, 'zh': zh, 'zero': zero,
           'scheme': scheme, 'metrics': v},
          open('/workspace/sp_flagship.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1, default=str)

# ---- extract_tool 独立交叉验证 ----
print('\n=== extract_tool 独立交叉验证 ===')
import importlib.util
spec = importlib.util.spec_from_file_location('et', '/workspace/extract_tool.py')
et = importlib.util.module_from_spec(spec)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(et)
def et_eval(fmap, zh, zero):
    d = dict(zh); d.update(fmap); d.update({'0' + k: v for k, v in zero.items()})
    return et.evaluate(d)
for name, (f2, z2, r2) in (('首道双拼', (SD_FMAP, SD_ZH, SD_ZERO)), ('旗舰终版', (fmap, zh, zero))):
    r = et_eval(f2, z2, r2)
    print(f"{name}: 工具复算 单字{r['单字当量']} 连续{r['连续当量']} 互击{r['双手互击率%']}% "
          f"上排{r['上排%']}% 中排{r['中排%']}% 下排{r['下排%']}%")
print('旗舰终版已保存 -> /workspace/sp_flagship.json')
