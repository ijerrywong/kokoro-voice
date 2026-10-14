# kokoro-voice

A Claude Code skill for designing custom voices with [Kokoro TTS](https://huggingface.co/hexgrad/Kokoro-82M) — child voices, elderly voices, storytellers, cartoon characters — and batch-generating voice-over with per-word timings. Everything runs locally.

一个 Claude Code skill：用本机的 Kokoro TTS 调出它没有预设的声音（童声、老人、讲故事、卡通角色……），再按台本批量生成配音，并附带每个词的时间轴。所有处理都在本机完成。

## How it works / 原理

Kokoro ships adult voices only. This skill reshapes them:

| Param | Stage | Effect |
|---|---|---|
| `voice` | Kokoro | a voice name, or a weighted blend such as `{"af_bella": 0.5, "am_puck": 0.5}` |
| `speed` | Kokoro | speaking rate, generated natively by the model |
| `formant` | Praat | vocal-tract length; >1 sounds like a smaller body |
| `pitch` | Praat | pitch only, with formants left unchanged |
| `range` | Praat | how much the intonation rises and falls |
| `highpass` / `bright` | ffmpeg | thinner / brighter timbre |

A child voice is roughly formant ×1.2 + pitch ×1.3–1.5 + slower speed + livelier intonation. Durations are preserved, so word timings stay accurate. Why this works (source–filter model, how Kokoro style vectors and Praat PSOLA are used, where the limits are): [docs/principles.md](docs/principles.md). Recipes and the feedback-to-parameter cheat sheet: [references/voice-params.md](references/voice-params.md). Both are in Chinese.

原理详见 [docs/principles.md](docs/principles.md)，配方速查见 [references/voice-params.md](references/voice-params.md)。

## Install / 安装

```bash
brew install ffmpeg espeak-ng            # or: sudo apt install ffmpeg espeak-ng
git clone https://github.com/<you>/kokoro-voice ~/.claude/skills/kokoro-voice
bash ~/.claude/skills/kokoro-voice/scripts/setup.sh
```

The setup script creates a Python environment (about 1 GB) in `~/.local/share/kokoro-voice` and runs a self-test, which downloads the Kokoro model (about 330 MB) on first run. Uninstall by deleting that directory and the skill folder.

安装脚本会在 `~/.local/share/kokoro-voice` 建一个约 1GB 的 Python 环境，并做一次自检；首次自检会下载约 330MB 的 Kokoro 模型。卸载时删掉这个目录和 skill 文件夹即可。

## Use / 使用

In Claude Code, just ask, e.g.:
- "Make me three candidate voices for a playful 7-year-old boy"
- "给这份台本配音，女孩用 child_girl_lively，旁白用 storyteller_warm"

Claude asks what you need, renders a comparison page for you to listen to, adjusts the parameters based on your feedback, saves the voices you pick as presets, and then batch-renders your script.

Tools (also usable without Claude), where `PY=~/.local/share/kokoro-voice/.venv/bin/python`:

```bash
$PY scripts/lab.py                                  # slider lab at http://localhost:8765
$PY scripts/audition.py candidates.json --open      # A/B comparison page
$PY scripts/batch.py script.json out/ [--wav]       # batch render + manifest.json
```

Built-in presets in `presets.json` are **starting points that no human has listened to yet**; tune them by ear. Presets you save go to `~/.local/share/kokoro-voice/presets.json`.

## Limits / 局限

- English only (American `a` and British `b` voices).
- The voices are simulated from adult voices. Heavy reshaping (formant > 1.35) gets robotic.
- No voice cloning of real people.

## License / 许可

The code is MIT-licensed. This repo contains **no model weights or voice files**: Kokoro-82M (Apache-2.0, by hexgrad) is downloaded from HuggingFace at runtime. Dependencies are installed from PyPI under their own licenses, including Praat/parselmouth (GPL), which is used as a separately installed library. You are responsible for how you use the generated audio.

本仓库代码采用 MIT 许可，**不包含任何模型权重或声音文件**。Kokoro-82M（Apache-2.0，作者 hexgrad）在运行时从 HuggingFace 下载；各依赖从 PyPI 安装，适用各自的许可，其中 Praat/parselmouth 为 GPL 许可，作为单独安装的库使用。生成音频的用途由使用者自行负责。
