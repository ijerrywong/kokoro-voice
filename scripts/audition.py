#!/usr/bin/env python3
"""候选声音对比页：同一句台词 × 多组参数 → 一个 HTML 试听页。
用法：python scripts/audition.py candidates.json [--open]
candidates.json：
  {"text": "Look! A big red bus!",
   "candidates": {"A": {"voice": "bf_lily", "formant": 1.2, "pitch": 1.3}, "B": "child_girl_lively", ...}}
候选可以是参数字典，也可以是已有预设名。输出到 $KOKORO_VOICE_HOME/auditions/<时间>/index.html，最后一行打印路径。"""
import os, sys, json, html, time, webbrowser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kokoro_tts as K

spec = json.load(open(sys.argv[1], encoding='utf-8'))
texts = spec['text'] if isinstance(spec['text'], list) else [spec['text']]
out = os.path.join(K.HOME, 'auditions', time.strftime('%Y%m%d-%H%M%S'))
os.makedirs(out, exist_ok=True)

rows = []
for name, c in spec['candidates'].items():
    p = K.params(c)
    cells = []
    for i, t in enumerate(texts):
        f = f'{len(rows):02d}_{i}.mp3'
        audio, _ = K.render(t, p, spec.get('say_as'))
        K.save(audio, os.path.join(out, f), p, kbps=96)
        cells.append(f'<audio controls preload="none" src="{f}"></audio>')
    rows.append((name, p, c if isinstance(c, str) else '', cells))
    print(f'✓ {name}', flush=True)

json.dump({n: p for n, p, _, _ in rows}, open(os.path.join(out, 'candidates.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
desc = lambda p: ' · '.join(f'{k} {json.dumps(v, ensure_ascii=False)}' for k, v in p.items())
body = ''.join(f'''<section><h2>{html.escape(n)}{f' <small>（预设 {html.escape(src)}）</small>' if src else ''}</h2>
<code>{html.escape(desc(p))}</code>{''.join(cells)}</section>''' for n, p, src, cells in rows)
heads = ''.join(f'<li>{html.escape(t)}</li>' for t in texts)
open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(f'''<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>声音候选对比</title><style>
:root{{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--mute:#6b6a66;--line:#e2e0da}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161615;--card:#1f1f1d;--ink:#ecebe7;--mute:#9a9893;--line:#33322f}}}}
body{{margin:0 auto;max-width:760px;padding:20px 16px;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"PingFang SC",system-ui,sans-serif}}
section{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:12px 0}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:17px;margin:0 0 4px}} small,code,ol{{color:var(--mute);font-size:12px}}
code{{display:block;word-break:break-all;margin-bottom:6px}} audio{{width:100%;height:34px;margin-top:4px}}
</style></head><body><h1>声音候选对比</h1><ol>{heads}</ol>
<p><small>听完告诉 Claude 选哪个，或者说想怎么改（再小一点 / 更活泼 / 别那么尖…）。</small></p>{body}</body></html>''')
path = os.path.join(out, 'index.html')
if '--open' in sys.argv:
    webbrowser.open('file://' + path)
print(path)
