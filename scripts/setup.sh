#!/usr/bin/env bash
# 建好 kokoro-voice 的运行环境。用法：bash scripts/setup.sh [--check]
#   --check  只检查，不安装；全部就绪时最后一行是 READY
# 环境装在 $KOKORO_VOICE_HOME（默认 ~/.local/share/kokoro-voice），约 1GB；模型权重首次合成时下载到 HuggingFace 缓存，约 330MB。
set -u
HOME_DIR="${KOKORO_VOICE_HOME:-$HOME/.local/share/kokoro-voice}"
VENV="$HOME_DIR/.venv"
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
ok=1
say() { printf '%s\n' "$*"; }

for t in ffmpeg espeak-ng; do
  if command -v $t >/dev/null; then say "✓ $t"; else
    ok=0; say "✗ 缺 $t —— macOS: brew install $t   Debian/Ubuntu: sudo apt install $t"; fi
done
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import kokoro, parselmouth, soundfile, en_core_web_sm" 2>/dev/null; then
  say "✓ Python 环境 $VENV"
  if [ "$("$VENV/bin/python" -c 'import kokoro_tts, os; print(os.path.dirname(os.path.abspath(kokoro_tts.__file__)))' 2>/dev/null)" = "$SCRIPTS" ]; then
    say "✓ kokoro_tts 指向 $SCRIPTS"; else say "✗ kokoro_tts 还没指向本目录"; ok=0; need_pth=1; fi
else
  ok=0; need_venv=1; say "✗ Python 环境还没装：$VENV"
fi

if [ "${1:-}" = "--check" ]; then
  [ $ok = 1 ] && say "READY python=$VENV/bin/python" || say "NOT READY"
  exit 0
fi
[ $ok = 1 ] && { say "READY python=$VENV/bin/python"; exit 0; }
command -v ffmpeg >/dev/null && command -v espeak-ng >/dev/null || { say "先装好上面缺的系统工具，再重跑本脚本。"; exit 1; }

mkdir -p "$HOME_DIR"
if [ "${need_venv:-0}" = 1 ]; then
  if command -v uv >/dev/null; then
    uv venv --python 3.12 "$VENV" && VIRTUAL_ENV="$VENV" uv pip install -r "$SCRIPTS/requirements.txt" || exit 1
  else
    PY=$(command -v python3.12 || command -v python3.11 || command -v python3.10) || { say "需要 Python 3.10–3.12，或者装 uv：https://docs.astral.sh/uv/"; exit 1; }
    "$PY" -m venv "$VENV" && "$VENV/bin/pip" install -q -r "$SCRIPTS/requirements.txt" || exit 1
  fi
fi
SP=$("$VENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')
echo "$SCRIPTS" > "$SP/kokoro_voice.pth"   # 让这个环境里任何脚本都能 import kokoro_tts
say "合成一句话自检（首次会下载模型，约 330MB）…"
"$VENV/bin/python" -c "
import kokoro_tts as K
a, t = K.render('Hello there!', {'voice': 'af_heart'})
assert len(a) > K.SR * 0.3 and t, 'no audio'
print('✓ 自检通过')" 2>&1 | grep -v -i warning || exit 1
say "READY python=$VENV/bin/python"
