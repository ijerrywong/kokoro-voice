#!/usr/bin/env python3
"""批量配音：一份台本 → 一批音频 + manifest.json（时长、每个词的时间，可做跟读高亮）。
用法：python scripts/batch.py script.json OUT_DIR [--wav]
script.json：
  {"voices": {"girl": "child_girl_lively", "narrator": {"voice": "af_heart", "speed": 0.95}},
   "say_as": {"Xu": "ʃˈu"},                      # 可选：特殊读音（Kokoro 音标）
   "lines": [["girl", "Hello!"], {"id": "intro", "role": "narrator", "text": "Once upon a time..."}]}
文件名 = id（没有就用 序号_角色）。参数和台词都没变的会跳过，不重新生成。"""
import os, re, sys, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kokoro_tts as K

spec = json.load(open(sys.argv[1], encoding='utf-8'))
out = sys.argv[2]
ext = '.wav' if '--wav' in sys.argv else '.mp3'
os.makedirs(out, exist_ok=True)
man_path = os.path.join(out, 'manifest.json')
old = {e['file']: e for e in json.load(open(man_path, encoding='utf-8'))} if os.path.exists(man_path) else {}
say_as = spec.get('say_as') or {}
voices = {r: K.params(v) for r, v in spec['voices'].items()}

manifest, made = [], 0
for i, ln in enumerate(spec['lines'], 1):
    ln = ln if isinstance(ln, dict) else {'role': ln[0], 'text': ln[1]}
    role, text = ln['role'], ln['text']
    if role not in voices:
        sys.exit(f'✗ 第 {i} 行的角色 {role!r} 没在 voices 里定义')
    p = voices[role]
    f = (ln.get('id') or f'{i:03d}_{role}') + ext
    sig = hashlib.sha1(json.dumps([p, say_as, text], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    if os.path.exists(os.path.join(out, f)) and old.get(f, {}).get('sig') == sig:
        manifest.append(old[f]); continue
    dur, words = K.speak(text, p, os.path.join(out, f), say_as)
    n = len(re.findall(r"[A-Za-z']+|\d+", text))  # 数字也算，Kokoro 不给数字词时间
    if len(words) < n:
        print(f'  ⚠ 词时间不全 {len(words)}/{n}：{f}')
    manifest.append({'file': f, 'role': role, 'text': text, 'sig': sig, 'dur': round(float(dur), 3),
                     'words': [[w, round(float(a), 3), round(float(b), 3)] for w, a, b in words]})
    made += 1
    print(f'✓ {f}  {dur:.2f}s  {text[:50]}', flush=True)

json.dump(manifest, open(man_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'完成：新生成 {made}，沿用 {len(manifest) - made}，共 {len(manifest)} 条 → {man_path}')
