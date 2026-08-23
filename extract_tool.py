# 从田生双拼当量计算工具(https://tiansh.github.io/lqbz/sp/)源码中提取全部评测数据
# 并在本地 100% 复现其计算逻辑,用于后续精确优化
import re, json

html = open('/workspace/sp_tool.html', encoding='utf-8').read()

# ---- 1. 提取当量矩阵 (33x33, 行=前一键位置, 列=后一键位置, 值为当量x10) ----
rows_raw = [(p, v) for p, v in re.findall(r"\['([0-9A-C]{2})',\s*([0-9][0-9,\s]*)\]", html)
            if len([x for x in v.split(',') if x.strip()]) == 33]
assert len(rows_raw) == 33, len(rows_raw)
POS = ['11','12','13','14','15','16','17','18','19','1A','1B','1C',
       '21','22','23','24','25','26','27','28','29','2A','2B',
       '32','33','34','35','36','37','38','39','3A','3B']
matrix = {}
for pos, vals in rows_raw:
    nums = [float(x) for x in vals.split(',')]
    assert len(nums) == 33, (pos, len(nums))
    matrix[pos] = dict(zip(POS, nums))
assert len(matrix) == 33

# ---- 2. QWERTY 布局: 位置码 -> 键名 ----
layout_str = "QWERTYUIOP[] ASDFGHJKL;'  ZXCVBNM,./"
dom_pos = ['%s%X' % ('123'[i//13], 1 + i % 13) if False else None for i in range(0)]
# DOM 顺序: 行1 K11..K1D(13), 行2 K21..K2C(12), 行3 K31..K3B(11)
dom_pos = ['1' + format(i, 'X') for i in range(1, 14)] + \
          ['2' + format(i, 'X') for i in range(1, 13)] + \
          ['3' + format(i, 'X') for i in range(1, 12)]
assert len(dom_pos) == 36 and len(layout_str) == 36
pos2key = dict(zip(dom_pos, layout_str))
key2pos = {v: k for k, v in pos2key.items() if v.strip()}

# 左右手 (工具 calcLR 的 lr 函数逻辑: 列1-5 或 36 为左手)
def hand(pos):
    return 'L' if (('0' < pos[1] < '6') or pos == '36') else 'R'

# ---- 3. 读音频率表 (声母,韵母,频次; 零声母音节声母为空) ----
freq_html = re.search(r'<textarea class="ct" id="count">(.*?)</textarea>', html, re.S).group(1)
freq = []
for line in freq_html.strip().split('\n'):
    parts = line.strip().split(',')
    b, a, c = parts[0], parts[1], int(parts[2])
    freq.append((b, a, c))
print('音节数(含零声母):', len(freq), ' 总频次:', sum(f[2] for f in freq))

# ---- 4. 声母/韵母/零声母 定义顺序 (与工具 UI 输入框顺序一致) ----
SHENG = ['zh','ch','sh']                      # 可自定义声母 (20个自然声母固定原位)
FINALS = ['ü','ai','ei','ui','ao','ou','iu','ie','üe','ue','an','en','in','un',
          'ang','eng','ing','ong','ia','iao','ian','iang','iong','ua','uai','uan','uang','uo']
ZERO = ['a','ai','an','ang','ao','o','ou','e','ei','en','eng','er']

# ---- 5. 方案解码: 3字符(zh, ch, sh) + 28字符(韵母) + 24字符(零声母x2) ----
def decode(scheme_str):
    assert len(scheme_str) == 55
    d = {'zh': scheme_str[0], 'ch': scheme_str[1], 'sh': scheme_str[2]}
    for i, f in enumerate(FINALS):
        d[f] = scheme_str[3 + i]
    for i, z in enumerate(ZERO):
        d['0' + z] = scheme_str[31 + 2 * i: 33 + 2 * i]   # '0'+韵母 = 零声母音节
    return d

presets = {
    '智能ABC': 'AEVVLQMKBRXMMJFCNHGYSDZWTSDCPTOOAOLOJOHOKOOOBOEOQOFOGOR',
    '微软拼音': 'VIUYLZVKBQXVTJFNPHG;SWCMDSWYRDOOAOLOJOHOKOOOBOEOZOFOGOR',
    '搜狗拼音': 'VIUYLZVKBQXTTJFNPHG;SWCMDSWYRDOAAAIANAHAOOOOUEEEIENEGER',
    '小鹤双拼': 'VIUVDWVCZQPTTJFBYHGKSXNMLSXKRLOAAAIANAHAOOOOUEEEIENEGER',
    '自然码':  'VIUVLZVKBQXTTJFNPHGYSWCMDSWYRDOAAAIANAHAOOOOUEEEIENEGER',
}

# 首道双拼 (https://shoudaoshuangpin.github.io/ 键位图 + 零声母编码表)
shoudao_layout = {  # 韵母->键
    'iu':'Q','ua':'W','ie':'R','uan':'T','ang':'Y','iao':'P','ou':'S','ao':'D',
    'eng':'F','uai':'G','ing':'G','ong':'H','iong':'H','an':'J','en':'K','ia':'K',
    'ai':'L','ue':'L','un':'Z','iang':'X','uang':'X','in':'C','ü':'V','ui':'V',
    'üe':'B','ian':'N','ei':'M','uo':'O',
}
shoudao_zero = {'a':'AA','ai':'AI','an':'AN','ang':'AY','ao':'AO','o':'OO',
                'ou':'OU','e':'UE','ei':'UI','en':'EN','eng':'UF','er':'ER'}

def build_scheme(final_map, zh='V', ch='I', sh='E', zero=shoudao_zero):
    d = {'zh': zh, 'ch': ch, 'sh': sh}
    d.update(final_map)
    d.update({'0' + k: v for k, v in zero.items()})
    return d

# ---- 6. 复现工具计算 ----
NATURAL = {  # 20个自然声母固定原位
    'b':'B','p':'P','m':'M','f':'F','d':'D','t':'T','n':'N','l':'L','g':'G',
    'k':'K','h':'H','j':'J','q':'Q','x':'X','r':'R','z':'Z','c':'C','s':'S','y':'Y','w':'W'}

FIXED = {'a':'A','o':'O','e':'E','i':'I','u':'U'}   # 5个单韵母固定原位

def evaluate(d, verbose=False):
    d = dict(d); d.update(FIXED)
    # 音节 -> (第一键=声母键 kb, 第二键=韵母键 ka, 频次)
    syls = []
    for b, a, c in freq:
        if b == '':                       # 零声母音节
            code = d['0' + a]
            kb, ka = code[0], code[1]
        else:
            kb = d.get(b) or NATURAL[b]   # 声母键
            ka = d[a]                     # 韵母键
        syls.append((kb, ka, c))
    T = sum(s[2] for s in syls)
    # 单字当量: sum P(s)*M[声母位][韵母位]
    dz = sum(c * matrix[key2pos[kb]][key2pos[ka]] for kb, ka, c in syls) / T
    # 连续当量: sum P(甲)P(乙)*M[甲韵母位][乙声母位]
    from collections import defaultdict
    fa = defaultdict(float); sb = defaultdict(float)
    for kb, ka, c in syls:
        fa[key2pos[ka]] += c              # 第二键(韵母位)分布
        sb[key2pos[kb]] += c              # 第一键(声母位)分布
    lx = sum(fa[p1] * sb[p2] * matrix[p1][p2] for p1 in matrix for p2 in matrix) / (T * T)
    # 双手互击率: 声韵异手音节占比 (工具 RDH = (LR+RL)/t)
    dh = sum(c for kb, ka, c in syls if hand(key2pos[kb]) != hand(key2pos[ka])) / T
    # 击键排位统计
    row = {'1': 0, '2': 0, '3': 0}
    for kb, ka, c in syls:
        row[key2pos[kb][0]] += c; row[key2pos[ka][0]] += c
    tot2 = 2 * T
    rows = {k: v / tot2 * 100 for k, v in row.items()}
    return {'单字当量': round(dz, 2), '连续当量': round(lx, 2),
            '双手互击率%': round(dh * 100, 2),
            '上排%': round(rows['1'], 2), '中排%': round(rows['2'], 2), '下排%': round(rows['3'], 2)}

# ---- 7. 验证: 与工具官方公布数据对比 ----
# 官方公布(首道双拼官网/文章引用田生工具实测):
published = {
    '自然码':  (13.67, 13.82),
    '小鹤双拼': (13.57, 13.82),
    '智能ABC': (13.42, 13.87),
    '微软拼音': (13.67, 13.86),
    '搜狗拼音': (13.67, 13.86),
    '首道双拼': (13.03, 13.70),
}
print('\n=== 复现验证 (本地计算 vs 田生工具公布值) ===')
for name, s in presets.items():
    r = evaluate(decode(s))
    p = published.get(name)
    ok = '✓' if p and abs(r['单字当量'] - p[0]) < 0.02 and abs(r['连续当量'] - p[1]) < 0.02 else '✗'
    print(f"{ok} {name}: 本地 单字{r['单字当量']} 连续{r['连续当量']} 互击{r['双手互击率%']}%"
          + (f" | 公布 {p[0]}/{p[1]}" if p else ""))

sd = build_scheme(shoudao_layout)
r = evaluate(sd)
print(f"{'✓' if abs(r['单字当量']-13.03)<0.02 and abs(r['连续当量']-13.70)<0.02 else '✗'} 首道双拼: 本地 单字{r['单字当量']} 连续{r['连续当量']} 互击{r['双手互击率%']}% 下排{r['下排%']}% | 公布 13.03/13.70 互击56.72%")

# 保存提取数据
json.dump({'matrix': matrix, 'freq': freq, 'pos2key': pos2key},
          open('/workspace/sp_data.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('\n数据已保存 -> /workspace/sp_data.json')
