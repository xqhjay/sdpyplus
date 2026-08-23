#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""田生双拼当量计算工具的本地复现 + 首道双拼校验
数据来源: https://tiansh.github.io/lqbz/sp/ (源码已下载到 sp_tool.html)
公式(源码 calcLD):
  单字当量 = Σ f(s)·E[声母键][韵母键] / Σ f
  连续当量 = Σ f(s1)f(s2)·E[s1韵母键][s2声母键] / (Σ f)^2
E 为 33x33 有向当量矩阵(值以 0.1 为单位), 键位编号:
  11..1C = Q W E R T Y U I O P [ ]
  21..2B = A S D F G H J K L ; '
  32..3B = Z X C V B N M , . /
"""
import re, json

html = open('/workspace/sp_tool.html', encoding='utf-8').read()

# ---- 解析字频表 ----
m = re.search(r'<textarea class="ct" id="count">(.*?)</textarea>', html, re.S)
freq = []
for line in m.group(1).strip().split('\n'):
    parts = line.strip().split(',')
    if len(parts) == 3:
        freq.append((parts[0], parts[1], int(parts[2])))

# ---- 解析当量矩阵 ----
keys = ['11','12','13','14','15','16','17','18','19','1A','1B','1C',
        '21','22','23','24','25','26','27','28','29','2A','2B',
        '32','33','34','35','36','37','38','39','3A','3B']
m = re.search(r'\[\s*\[\'11\',.*?\]\s*\]\.map', html, re.S)
rows = re.findall(r'\[\'([0-9A-C]+)\',\s*([0-9,\s]+)\]', m.group(0))
E = {}  # E[前键][后键]
for k, vals in rows:
    E[k] = dict(zip(keys, [int(v) for v in vals.split(',')]))

KEY2POS = {'Q':'11','W':'12','E':'13','R':'14','T':'15','Y':'16','U':'17','I':'18',
           'O':'19','P':'1A','[':'1B',']':'1C','A':'21','S':'22','D':'23','F':'24',
           'G':'25','H':'26','J':'27','K':'28','L':'29',';':'2A',"'":'2B',
           'Z':'32','X':'33','C':'34','V':'35','B':'36','N':'37','M':'38',
           ',':'39','.':'3A','/':'3B'}

def evaluate(sheng, yun, specials, name=''):
    """sheng: 声母->键; yun: 韵母->键; specials: 音节->两键串"""
    codes = []  # (kb第一键, ka第二键, freq)
    for b, a, c in freq:
        syl = b + a
        if syl in specials:
            kb, ka = specials[syl][0], specials[syl][1]
        else:
            kb, ka = sheng[b], yun[a]
        codes.append((kb, ka, c))
    # 单字当量
    num = sum(c * E[KEY2POS[kb]][KEY2POS[ka]] for kb, ka, c in codes)
    den = sum(c for _, _, c in codes)
    dcs = num / den
    # 连续当量
    num2 = 0.0
    for kb1, ka1, c1 in codes:
        row = E[KEY2POS[ka1]]
        for kb2, ka2, c2 in codes:
            num2 += c1 * c2 * row[KEY2POS[kb2]]
    dcd = num2 / (den * den)
    print(f'{name}: 单字当量 {dcs:.2f}/10, 连续当量 {dcd:.2f}/10')
    return dcs, dcd

# ---- 首道双拼布局 ----
sheng_sd = dict(b='B', p='P', m='M', f='F', d='D', t='T', n='N', l='L',
                g='G', k='K', h='H', j='J', q='Q', x='X', r='R', z='Z',
                c='C', s='S', y='Y', w='W', zh='V', ch='I', sh='E')
yun_sd = {'iu':'Q', 'ua':'W', 'e':'E', 'ie':'R', 'uan':'T', 'ang':'Y', 'u':'U',
          'i':'I', 'o':'O', 'uo':'O', 'iao':'P', 'a':'A', 'ou':'S', 'ao':'D',
          'eng':'F', 'uai':'G', 'ing':'G', 'ong':'H', 'iong':'H', 'an':'J',
          'en':'K', 'ia':'K', 'ai':'L', 'ue':'L', 'un':'Z', 'iang':'X',
          'uang':'X', 'in':'C', 'ü':'V', 'ui':'V', 'üe':'B', 'ian':'N', 'ei':'M'}
specials_sd = {'a':'AA','ai':'AI','an':'AN','ang':'AY','ao':'AO','e':'UE',
               'ei':'UI','en':'EN','eng':'UF','er':'ER','o':'OO','ou':'OU'}

if __name__ == '__main__':
    total = sum(c for _, _, c in freq)
    print(f'音节数 {len(freq)}, 语料总量 {total:,}')
    print(f"de 占比 {12648125/total*100:.2f}%, 最大音节: ", max(freq, key=lambda x: x[2]))
    evaluate(sheng_sd, yun_sd, specials_sd, '首道双拼(本复现)')
    print('官方公布值: 单字 13.03, 连续 13.70')
