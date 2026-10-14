"""Kokoro 合成核心：一句话 → 音频 + 每个词的起止时间；可混合声音、分开调共鸣/音高/起伏。
模型权重由 kokoro 库从 HuggingFace (hexgrad/Kokoro-82M, Apache-2.0) 下载，本仓库不附带。"""
import re, subprocess, tempfile, os, warnings
import numpy as np
import soundfile as sf

warnings.filterwarnings('ignore')
SR = 24000
_pipes = {}


def pipe(voice):
    # 声音名第一个字母决定口音：a 美音，b 英音
    lang = voice[0]
    if lang not in _pipes:
        from kokoro import KPipeline
        _pipes[lang] = KPipeline(lang_code=lang, repo_id='hexgrad/Kokoro-82M')
    return _pipes[lang]


WORD = re.compile(r"[A-Za-z']+")


def mark(text, say_as):
    """人名注音：把 SAY_AS 里的词换成 Kokoro 的 [词](/音标/) 写法（只影响读音，词本身不变）"""
    for w, ph in say_as.items():
        text = re.sub(rf"(?<![\w\[]){re.escape(w)}(?![\w\]])", f'[{w}](/{ph}/)', text)
    return text


def synth(text, voice, speed=1.0, say_as=None):
    """返回 (音频 float32 数组, [(词, t0, t1), ...])"""
    chunks, toks, offset = [], [], 0.0
    for r in pipe(voice)(mark(text, say_as or {}), voice=voice, speed=speed):
        a = r.audio.numpy() if hasattr(r.audio, 'numpy') else np.asarray(r.audio)
        for t in (r.tokens or []):
            if t.start_ts is not None and t.end_ts is not None and WORD.search(t.text or ''):
                toks.append((t.text, offset + t.start_ts, offset + t.end_ts))
        chunks.append(a)
        offset += len(a) / SR
    return np.concatenate(chunks) if chunks else np.zeros(1, np.float32), toks


def align(text, toks):
    """把 Kokoro 的词时间对回原句：返回 [[字符起, 字符止, t0, t1], ...]"""
    norm = lambda s: re.sub(r"[^a-z]", '', s.lower())
    out, j = [], 0
    for m in WORD.finditer(text):
        w = norm(m.group())
        for k in range(j, min(j + 4, len(toks))):
            if norm(toks[k][0]) == w:
                out.append([m.start(), m.end(), round(toks[k][1], 3), round(toks[k][2], 3)])
                j = k + 1
                break
    return out


def to_mp3(audio, path, pitch=1.0, kbps=48):
    """写 mp3。pitch>1 时升调但不改语速（asetrate 升调 + atempo 拉回原速）"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sf.write(f.name, audio, SR)
        af = ['silenceremove=start_periods=1:start_threshold=-50dB']  # 去掉开头的静音，点了马上出声
        if abs(pitch - 1) > 1e-3:
            af += [f'asetrate={int(SR * pitch)}', f'aresample={SR}', f'atempo={1 / pitch:.5f}']
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', f.name, '-af', ','.join(af), '-ac', '1', '-b:a', f'{kbps}k', path], check=True)
        lead = leading_silence(audio)
    os.unlink(f.name)
    return lead


def leading_silence(audio, thr=10 ** (-50 / 20)):
    idx = np.argmax(np.abs(audio) > thr)
    return idx / SR


# ───────── 自定义声音：混合声音 + 分开调音高与共鸣 ─────────
# 参数（都可省略）：
#   voice    'af_bella' 或 {'af_bella': 0.7, 'am_liam': 0.3}（按比例混合声音向量）
#   speed    Kokoro 语速，模型直接按此速度生成（自然，不是拉伸）
#   formant  共鸣倍数：>1 声道变短、像更小的人；<1 像更大的人
#   pitch    音高倍数（只改音高，不改共鸣）
#   range    语调起伏倍数：>1 更活泼夸张，<1 更平
#   highpass 低切频率 Hz：切掉胸腔低音，声音更薄（0 关闭）
#   bright   高频增益 dB（3kHz 以上）：>0 更亮更脆，<0 更闷
import json
CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))           # skill 目录
HOME = os.path.expanduser(os.environ.get('KOKORO_VOICE_HOME', '~/.local/share/kokoro-voice'))  # 运行环境、用户预设、缓存
BUILTIN_PRESETS = os.path.join(CODE, 'presets.json')
PRESETS = os.path.join(HOME, 'presets.json')


def voice_pack(spec):
    if isinstance(spec, str):
        return spec
    tot = sum(spec.values())
    return sum(pipe(v).load_voice(v) * (w / tot) for v, w in spec.items() if w > 0)


def _lang(p):
    v = p.get('voice', 'af_bella')
    return p.get('lang') or (v if isinstance(v, str) else max(v, key=v.get))[0]


def render(text, p, say_as=None):
    """按参数 p 合成，返回 (音频 float32, [(词, t0, t1), ...])。时长不变，词时间仍然对得上"""
    pl = pipe(_lang(p))
    chunks, toks, offset = [], [], 0.0
    for r in pl(mark(text, say_as or {}), voice=voice_pack(p.get('voice', 'af_bella')), speed=p.get('speed', 1)):
        a = r.audio.numpy() if hasattr(r.audio, 'numpy') else np.asarray(r.audio)
        for t in (r.tokens or []):
            if t.start_ts is not None and t.end_ts is not None and WORD.search(t.text or ''):
                toks.append((t.text, offset + t.start_ts, offset + t.end_ts))
        chunks.append(a)
        offset += len(a) / SR
    audio = np.concatenate(chunks) if chunks else np.zeros(1, np.float32)
    return reshape(audio, p), toks


def reshape(audio, p):
    """用 Praat 的 Change gender 分开改共鸣、音高、起伏"""
    fm, pt, rg = p.get('formant', 1), p.get('pitch', 1), p.get('range', 1)
    if abs(fm - 1) < 1e-3 and abs(pt - 1) < 1e-3 and abs(rg - 1) < 1e-3:
        return audio
    import parselmouth
    from parselmouth.praat import call
    s = parselmouth.Sound(audio.astype(np.float64), SR)
    med = call(s.to_pitch(pitch_floor=60, pitch_ceiling=600), 'Get quantile', 0, 0, 0.5, 'Hertz')
    new_med = med * pt if med == med else 0  # 测不到音高(NaN)就不改
    out = call(s, 'Change gender', 60, 600, fm, new_med, rg, 1.0)
    return out.values[0].astype(np.float32)


def post_filters(p):
    af = []
    if p.get('highpass'):
        af.append(f"highpass=f={p['highpass']}")
    if p.get('bright'):
        af.append(f"treble=g={p['bright']}:f=3000")
    return af


def save(audio, path, p=None, kbps=48):
    """写 mp3（或 .wav）：去掉开头静音 + 低切/高频处理。返回去掉的开头秒数"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sf.write(f.name, audio, SR)
        af = ['silenceremove=start_periods=1:start_threshold=-50dB'] + post_filters(p or {})
        enc = ['-b:a', f'{kbps}k'] if path.endswith('.mp3') else []
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', f.name, '-af', ','.join(af), '-ac', '1', *enc, path], check=True)
    os.unlink(f.name)
    return leading_silence(audio)


def presets():
    """内置预设 + 用户预设（同名时用户的优先）"""
    out = {}
    for f in (BUILTIN_PRESETS, PRESETS):
        if os.path.exists(f):
            out.update(json.load(open(f, encoding='utf-8')))
    return out


def user_presets():
    return json.load(open(PRESETS, encoding='utf-8')) if os.path.exists(PRESETS) else {}


def save_user_presets(d):
    os.makedirs(HOME, exist_ok=True)
    tmp = PRESETS + '.tmp'
    json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, PRESETS)


def params(preset):
    """预设名或参数字典 → 参数字典（去掉 note）"""
    p = presets()[preset] if isinstance(preset, str) else preset
    return {k: v for k, v in p.items() if k != 'note'}


def speak(text, preset, path, say_as=None):
    """一步到位：按预设名（或参数字典）合成并存档。返回 (时长秒, [(词, t0, t1), ...]，时间已扣掉开头静音)"""
    p = params(preset)
    audio, toks = render(text, p, say_as)
    lead = save(audio, path, p)
    return len(audio) / SR - lead, [(w, max(0, a - lead), max(0, b - lead)) for w, a, b in toks]
