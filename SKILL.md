---
name: kokoro-voice
description: 用本机的 Kokoro TTS 调出所需的声音（儿童、老人、旁白、卡通角色等），并为台本批量生成配音（mp3/wav，附带每个词的时间轴）。可混合声音，可分别调整共鸣、音高、语调起伏和语速，以模拟 Kokoro 没有预设的声音。当用户说「配音」「生成语音」「TTS」「给这段台词配个声音」「做个儿童声音 / 童声」「小孩的声音」「老人声音」「怪兽声音」「试听几个声音」「批量生成音频」「把台本读出来」，或者提到 Kokoro 时使用。Use for: voice-over, text-to-speech, child voice, character voices, batch audio with word timings, Kokoro.
---

# Kokoro 配音

解决两件事：**调出想要的声音**，再**用这些声音批量产出配音**。所有工作都在本机完成，不需要联网 API；模型权重首次使用时从 HuggingFace 下载（hexgrad/Kokoro-82M，Apache-2.0）。

记号约定：`$SKILL` = 本 skill 的目录（加载时给出的 base directory）；`$PY` = 运行环境里的 Python，由 setup 脚本最后一行打印。

**Claude 听不到声音。** 参数只是起点，好不好听只能由用户的耳朵来判断。不要说"这个声音很像小孩"之类的话，只描述你调了哪些参数、为什么这样调。

## 0. 环境

```
bash $SKILL/scripts/setup.sh --check
```
- 最后一行是 `READY python=...` → 记下这个 python 路径，就是 `$PY`。
- 是 `NOT READY` → 先告诉用户代价，**等用户同意后**再执行 `bash $SKILL/scripts/setup.sh`：
  - 占用磁盘约 1GB（Python 环境）+ 330MB（模型），首次安装需要几分钟；
  - 环境装在 `~/.local/share/kokoro-voice`，不想要了删掉这个目录即可；
  - 缺少 ffmpeg 或 espeak-ng 时，脚本会给出安装命令，这些要由用户自己装。

## 1. 问清需求（必须问，不要猜）

一次问完：
1. **要哪些声音**：每个角色的年龄、性别、口音（美音 / 英音）、性格，以及用在什么场景（儿童教材、故事、游戏……）。
2. **台词从哪来**：用户直接给、来自某个文件，还是只是先调声音、以后再用。
3. **产出**：mp3 还是 wav，放到哪个目录。

先看已有预设能不能直接用：`$PY -c "import kokoro_tts as K, json; print(json.dumps(K.presets(), ensure_ascii=False, indent=1))"`。内置预设都只是起点，**没有经过人耳确认**。

## 2. 调声音：候选 → 用户听 → 改

1. 读 `$SKILL/references/voice-params.md`。每个角色按其中的「配方起点」设计 3–4 个**互相差别明显**的候选，比如换不同底子、混合比例，或者共鸣和音高高一档、低一档。差别太小，用户听不出来。
   有多个角色时，先按手册「多角色区分」排好各角色的底子：每两个角色之间，底子或共鸣至少要有一样明显不同。耳朵认人主要靠底子音色和共鸣，只差音高的两个角色会被听成同一个人。
2. 写 candidates.json（格式见 `scripts/audition.py` 的文件开头说明）。台词要用接近真实使用场景的 1–2 句，然后生成对比页并打开：
   ```
   $PY $SKILL/scripts/audition.py /tmp/candidates.json --open
   ```
3. 请用户说出选哪个，或者想怎么改。按手册里的「听感反馈 → 调哪里」表来改，**每轮只动 1–2 个参数**，再出一版对比页。通常 2–3 轮就够了。
4. 如果用户想自己拖滑杆细调，就启动实验室：`$PY $SKILL/scripts/lab.py`（会打开 http://localhost:8765；用后台方式运行，用完关掉）。在实验室里存的预设会直接写进用户预设。
5. 定下来以后，问用户给这个声音起什么名字、写一句它适合什么场景，然后存为用户预设：
   ```
   $PY -c "import kokoro_tts as K; d=K.user_presets(); d['名字']={...参数..., 'note':'说明'}; K.save_user_presets(d)"
   ```
   用户预设保存在 `~/.local/share/kokoro-voice/presets.json`，和内置预设重名时，用户的优先。

用户问"为什么这样调能变声音""原理是什么"时，读 `$SKILL/docs/principles.md` 来回答。

## 3. 批量产出

写 script.json（格式见 `scripts/batch.py` 的文件开头说明：voices 填角色对应的预设名或参数，lines 填台词），然后运行：
```
$PY $SKILL/scripts/batch.py script.json 输出目录 [--wav]
```
- 输出目录里会生成音频文件和 `manifest.json`，后者记录每条台词的时长和每个词的起止秒数，可以拿来做跟读高亮。
- 重跑时，台词和参数都没变的条目会跳过，只生成改动过的。
- 如果出现 `⚠ 角色 … 只靠音高/语速区分`，告诉用户这两个角色可能被听成同一个人，问用户是否要换其中一个的底子。如果是故意的（比如同一个人的两种状态），可以不改。
- 如果出现 `⚠ 词时间不全`，通常是因为台词里有数字或缩写。把它们写成单词，比如 "3" 写成 "three"。
- 人名或生词读错了，用 `say_as` 指定读音（Kokoro 音标，例如 `{"Xu": "ʃˈu"}`），再让用户试听确认。

交付时说清楚：一共生成了多少条、放在哪里、用了哪些声音（预设名 + 参数）。

## 在代码里直接调用

`setup.sh` 已经把 `scripts/` 加进运行环境的搜索路径，所以任何项目的脚本只要用 `$PY` 来跑，都可以：
```python
from kokoro_tts import speak
dur, words = speak('Hello!', 'child_girl_lively', 'out.mp3')   # 第二个参数：预设名或参数字典
```

## 边界

- 只用 Kokoro 自带的合成声音。**不做**模仿真实人物的声音，用户要求克隆某个具体的人时直接说明做不到。
- 只支持英语（Kokoro 的 a/b 两种口音）。
- 变形幅度大会出现机器味。这一点在手册的「局限」一节里有说明，要如实告诉用户。
