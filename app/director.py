"""Story generation: a local deterministic director, with optional local LLM."""
from __future__ import annotations

import json
import re
import uuid

import httpx

from .config import load_config
from .seed import GENRES, compose_story, now_iso


def _clean_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("模型没有返回 JSON")
    return json.loads(text[start:end + 1])


def _llm_generate(premise: str, genre: str, style: str, protagonist: str, title: str) -> dict:
    cfg = load_config()["llm"]
    system = (
        "你是一位擅长竖屏漫剧的编剧和分镜导演。只输出合法 JSON，不要 Markdown。"
        "每集 8 个镜头，每镜 3-8 秒。台词必须短、有钩子，适合中文配音。"
    )
    example = '{"scene":"lab","location":"记忆修复室","time":"00:12","shot_type":"medium","camera":"缓推","characters":["程野"],"pose":"stand","focus":"程野","narration":"","narration_speaker":"旁白","dialogues":[{"speaker":"程野","text":"这块表，不是我修的。","emotion":"颤抖"}],"sfx":["hum"],"caption":"修复室"}'
    prompt = f"""把下面的创意做成一部可拍摄的竖屏漫剧。
创意：{premise}
类型：{genre}
视觉风格：{style}
主角名：{protagonist or "由你决定"}
剧名：{title or "由你决定"}

严格返回以下结构（不要额外字段，不要解释）：
{{
  "title": "剧名",
  "logline": "一句话故事",
  "characters": [
    {{"id":"拼音id","name":"姓名","role":"身份","age":"年龄","persona":"性格与秘密","appearance":"可视化外形","appearance_en":"English visual description","voice":"zh-CN-XiaoxiaoNeural","accent":"#63F2DE","color":"#DDE7E6"}}
  ],
  "episode": {{
    "title": "第一集标题",
    "summary": "本集梗概",
    "hook": "结尾钩子",
    "shots": [
      {{
        "scene": "rooftop|alley|lab|lab_door|memory|apartment|void|chip|prop|close",
        "location": "地点，如 雾城·天台",
        "time": "时间",
        "shot_type": "wide|medium|close|detail",
        "camera": "运镜，如 缓推/横移/急推/固定",
        "characters": ["角色名"],
        "pose": "stand|stand_back|run|reach|sit|closeup",
        "focus": "画面主体",
        "narration": "旁白，没有就空字符串",
        "narration_speaker": "旁白或角色名",
        "dialogues": [{{"speaker":"角色名","text":"台词","emotion":"冷淡/低沉/轻快/颤抖"}}],
        "sfx": ["rain","city","heartbeat","alarm","glitch","impact","spark","wind","hum"],
        "caption": "画面角标"
      }}
    ]
  }}
}}
硬性要求：
1. 必须是 8 个镜头。
2. 地点至少 4 个不同，不能所有镜头都写同一地点；雨夜天台、室内、记忆、物件特写要交替。
3. 至少 6 个镜头要有 dialogues 对白，每镜 1-2 句；不能只写旁白。每个主要角色至少说出 1 句台词。
4. narration 只用于 3 个以内的镜头；有对白的镜头优先用对白推进剧情。
5. 最后一镜必须是强钩子，留悬念。
6. 不要写暴力或色情内容。
示例（只示范对白格式）：
{example}
"""
    base = cfg["base_url"].rstrip("/")
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    payload = {
        "model": cfg.get("model", "qwen2.5:3b"),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=cfg.get("timeout", 90)) as client:
            r = client.post(f"{base}/chat/completions", headers=headers, json=payload)
            if r.status_code == 400 and "response_format" in r.text:
                payload.pop("response_format", None)
                r = client.post(f"{base}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
    except Exception:
        # Ollama's native endpoint fallback
        with httpx.Client(timeout=cfg.get("timeout", 90)) as client:
            r = client.post(
                f"{base}/chat/completions",
                headers=headers,
                json={
                    "model": cfg.get("model", "qwen2.5:3b"),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {"num_ctx": 8192, "num_predict": 3000},
                },
            )
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
    return _clean_json(content)


def _normalize_llm_project(raw: dict, premise: str, genre: str, style: str) -> dict:
    style_names = {
        "neo_noir": "霓虹黑",
        "dusk_anime": "晚霞日漫",
        "ink_wuxia": "水墨朱砂",
        "warm_slice": "暖调都市",
        "cyber_pop": "赛博波普",
    }
    title = str(raw.get("title") or "未命名漫剧").strip()[:24]
    characters = []
    for i, char in enumerate(raw.get("characters") or []):
        if not isinstance(char, dict):
            continue
        cid = re.sub(r"[^a-zA-Z0-9_]", "", str(char.get("id") or f"char{i + 1}")) or f"char{i + 1}"
        characters.append(
            {
                "id": cid,
                "name": str(char.get("name") or f"角色{i + 1}"),
                "role": str(char.get("role") or ""),
                "age": str(char.get("age") or ""),
                "persona": str(char.get("persona") or ""),
                "appearance": str(char.get("appearance") or ""),
                "appearance_en": str(char.get("appearance_en") or char.get("appearance") or ""),
                "voice": char.get("voice") or ("zh-CN-YunjianNeural" if i % 2 else "zh-CN-XiaoxiaoNeural"),
                "accent": char.get("accent") or ("#FF4D3D" if i % 2 else "#63F2DE"),
                "color": char.get("color") or ("#1B1D24" if i % 2 else "#DDE7E6"),
            }
        )
    if not characters:
        characters = [{"id": "hero", "name": "主角", "role": "主角", "age": "27", "persona": "", "appearance": "黑色外套，眼神克制", "voice": "zh-CN-XiaoxiaoNeural", "accent": "#63F2DE", "color": "#DDE7E6"}]
    ep = raw.get("episode") or {}
    shots = []
    for i, shot in enumerate(ep.get("shots") or []):
        if not isinstance(shot, dict):
            continue
        dialogues = []
        for d in shot.get("dialogues") or []:
            if isinstance(d, dict) and str(d.get("text", "")).strip():
                dialogues.append(
                    {
                        "speaker": str(d.get("speaker") or ""),
                        "text": str(d.get("text") or "").strip()[:80],
                        "emotion": str(d.get("emotion") or "neutral"),
                    }
                )
        shots.append(
            {
                "id": f"s{i + 1:02d}",
                "index": i + 1,
                "scene": str(shot.get("scene") or "rooftop"),
                "location": str(shot.get("location") or GENRES.get(genre, {}).get("places", ["未知地点"])[0]),
                "time": str(shot.get("time") or "夜"),
                "shot_type": str(shot.get("shot_type") or "medium"),
                "camera": str(shot.get("camera") or "固定"),
                "characters": [str(c) for c in (shot.get("characters") or [])][:2],
                "pose": str(shot.get("pose") or "stand"),
                "focus": str(shot.get("focus") or ""),
                "narration": str(shot.get("narration") or ""),
                "narration_speaker": str(shot.get("narration_speaker") or "旁白"),
                "dialogues": dialogues,
                "sfx": [str(x) for x in (shot.get("sfx") or [])],
                "caption": str(shot.get("caption") or ""),
                "image_prompt": str(shot.get("image_prompt") or ""),
                "image": None,
                "video": None,
                "duration": None,
            }
        )
    if not shots:
        raise ValueError("模型返回的分镜为空")
    episode = {
        "id": f"ep{uuid.uuid4().hex[:6]}",
        "index": 1,
        "title": str(ep.get("title") or "第一集"),
        "summary": str(ep.get("summary") or raw.get("logline") or premise),
        "hook": str(ep.get("hook") or ""),
        "shots": shots,
        "status": "draft",
        "video": None,
        "srt": None,
        "cover": None,
        "duration": None,
    }
    return {
        "id": uuid.uuid4().hex[:10],
        "title": title,
        "premise": premise,
        "genre": genre,
        "style": style,
        "style_name": style_names.get(style, "漫剧"),
        "aspect": "9:16",
        "resolution": "720p",
        "logline": str(raw.get("logline") or premise)[:120],
        "characters": characters,
        "episodes": [episode],
        "cover": None,
        "sample": False,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def _llm_rewrite(base: dict, premise: str) -> dict:
    """Use the LLM for what small models are good at: punchy dialogue.

    The built-in director supplies a reliable 8-shot structure; the model
    rewrites title/hook/narration and dialogue beats. This avoids asking a 3B
    model to emit a huge nested schema and silently dropping every line.
    """
    cfg = load_config()["llm"]
    chars = [c.get("name", "") for c in base.get("characters", [])]
    episode = base["episodes"][0]
    shot_lines = []
    for shot in episode["shots"]:
        current = " / ".join(d.get("text", "") for d in shot.get("dialogues", [])) or shot.get("narration", "")
        shot_lines.append(
            f"{shot['index']}. {shot.get('location','')} | {shot.get('shot_type','')} | 角色 {','.join(shot.get('characters') or []) or '无'} | 现有：{current or '无'}"
        )
    system = "你是擅长竖屏短剧的中文编剧。只输出合法 JSON，不要 Markdown，不要解释。"
    prompt = f"""把下面这部漫剧的第一集台词重写得更抓人，但不要改变镜头数量、顺序和场景。

创意：{premise}
类型：{base.get('genre','')}
现有角色：{', '.join(chars)}

现有 8 个镜头：
{chr(10).join(shot_lines)}

要求：
- 输出正好 8 个 shot，index 从 1 到 8，与上面一一对应。
- 至少 6 个镜头写对白 dialogues；每镜 1-2 句；每句不超过 22 个汉字。
- 对白 speaker 只能从现有角色里选，不能新增角色。
- 不要让全部台词都由主角说；让第二个角色在第 2、3、4、7、8 镜里至少说 3 句，形成真正的对话。
- narration 只给 2 个以内没有对白的镜头；有对白时 narration 留空。
- 最后一镜留强钩子，让人想看下一集。
- 不要写解释、不要用 Markdown。

返回结构：
{{
 "title": "四到八个字的剧名",
 "logline": "一句话故事",
 "episode_title": "本集标题",
 "hook": "结尾钩子",
 "shots": [
   {{"index": 1, "narration": "", "dialogues": [{{"speaker": "角色名", "text": "台词", "emotion": "冷淡"}}]}}
 ]
}}"""
    base_url = cfg["base_url"].rstrip("/")
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    payload = {
        "model": cfg.get("model", "qwen2.5:3b"),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.75,
        "max_tokens": 1800,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=cfg.get("timeout", 180)) as client:
        r = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        if r.status_code == 400 and "response_format" in r.text:
            payload.pop("response_format", None)
            r = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
    return _clean_json(content)


def _merge_rewrite(base: dict, raw: dict) -> dict:
    names = {c.get("name", "") for c in base.get("characters", [])}
    first = base.get("characters", [{}])[0].get("name", "主角")
    shots = raw.get("shots") or []
    by_index = {}
    for item in shots:
        if isinstance(item, dict):
            try:
                by_index[int(item.get("index"))] = item
            except Exception:
                continue
    total = 0
    for shot in base["episodes"][0].get("shots", []):
        item = by_index.get(shot["index"])
        if not item:
            continue
        ds = []
        for d in item.get("dialogues") or []:
            if not isinstance(d, dict):
                continue
            text = str(d.get("text") or "").strip()[:80]
            if not text:
                continue
            speaker = str(d.get("speaker") or "").strip()
            if speaker not in names:
                speaker = first
            ds.append({"speaker": speaker, "text": text, "emotion": str(d.get("emotion") or "冷淡")[:8]})
        if ds:
            # Preserve the built-in scene's intended second speaker when the
            # small model made everyone sound like the protagonist.
            base_speakers = [d.get("speaker") for d in shot.get("dialogues") or []]
            second = next((x for x in base_speakers if x and x != first), None)
            if second and all(x["speaker"] == first for x in ds):
                ds[0]["speaker"] = second
            shot["dialogues"] = ds[:2]
            shot["narration"] = ""
            total += len(shot["dialogues"])
        elif str(item.get("narration") or "").strip():
            shot["narration"] = str(item["narration"]).strip()
    if total < 4:
        raise ValueError("LLM 重写后对白不足，保留内置剧本")
    title = str(raw.get("title") or "").strip().removeprefix("剧名：").removeprefix("剧名:").strip()[:20]
    if title:
        base["title"] = title
    if str(raw.get("logline") or "").strip():
        base["logline"] = str(raw["logline"]).strip()[:120]
    ep = base["episodes"][0]
    if str(raw.get("episode_title") or "").strip():
        ep["title"] = str(raw["episode_title"]).strip()[:20]
    if str(raw.get("hook") or "").strip():
        ep["hook"] = str(raw["hook"]).strip()[:100]
    return base


def create_project(
    premise: str,
    genre: str = "都市悬疑",
    style: str = "neo_noir",
    protagonist: str = "",
    title: str = "",
    use_llm: bool = False,
) -> tuple[dict, str]:
    cfg = load_config()
    project = compose_story(premise, genre, style, protagonist, title)
    project["style_name"] = {
        "neo_noir": "霓虹黑",
        "dusk_anime": "晚霞日漫",
        "ink_wuxia": "水墨朱砂",
        "warm_slice": "暖调都市",
        "cyber_pop": "赛博波普",
    }.get(style, "漫剧")
    if use_llm and cfg["llm"].get("enabled"):
        try:
            raw = _llm_rewrite(project, premise)
            project = _merge_rewrite(project, raw)
            if title.strip():
                project["title"] = title.strip()[:20]
            project["generation_engine"] = "ollama"
            return project, "llm"
        except Exception as exc:  # noqa: BLE001
            print("LLM rewrite failed, falling back:", exc)
            project["generation_engine"] = "builtin"
            return project, "builtin"
    project["generation_engine"] = "builtin"
    return project, "builtin"


def compose_next_episode(project: dict) -> dict:
    """A deterministic chapter-two generator with a new location and cliffhanger."""
    chars = [c.get("name") for c in project.get("characters", []) if c.get("name")]
    hero = chars[0] if chars else "主角"
    rival = chars[1] if len(chars) > 1 else "陌生人"
    genre = project.get("genre") or "都市悬疑"
    meta = GENRES.get(genre, GENRES["都市悬疑"])
    places = meta["places"]
    idx = len(project.get("episodes", [])) + 1
    place = places[(idx * 2) % len(places)]
    prop = meta["props"][idx % len(meta["props"])]
    lines = meta["lines"]
    shots = []
    beats = [
        ("establish", place, "wide", "雨还在下，但这座城已经换了一副面孔。", "", ["rain"]),
        ("confront", place, "medium", "", f"{rival}：你以为你找回的是记忆，其实是一张账单。", ["wind"]),
        ("prop", place, "detail", "", f"{hero}：{prop}……它为什么在我手里？", ["spark"]),
        ("lab", "临时藏身处", "medium", "", f"{hero}：{lines[(idx + 1) % len(lines)]}", ["hum"]),
        ("memory", "记忆断层", "wide", "她终于看清了那个一直背对着她的人。", "", ["alarm", "heartbeat"]),
        ("void", "倒计时", "detail", "", f"{rival}：{lines[idx % len(lines)]}", ["heartbeat", "impact"]),
    ]
    for i, (scene, loc, stype, narration, dialogue, sfx) in enumerate(beats, 1):
        ds = []
        if dialogue:
            speaker, text = dialogue.split("：", 1)
            ds = [{"speaker": speaker.strip(), "text": text.strip(), "emotion": "低沉" if speaker == rival else "冷淡"}]
        shots.append(
            {
                "id": f"s{i:02d}",
                "index": i,
                "scene": scene,
                "location": loc,
                "time": "00:4" + str(i),
                "shot_type": stype,
                "camera": "缓推" if stype != "detail" else "微距",
                "characters": [hero] if beat_has_hero(scene, stype) else [],
                "pose": "stand" if stype == "medium" else "stand_back",
                "focus": hero,
                "narration": narration,
                "narration_speaker": hero,
                "dialogues": ds,
                "sfx": sfx,
                "caption": loc,
                "image_prompt": "",
                "image": None,
                "video": None,
                "duration": None,
            }
        )
    return {
        "id": f"ep{uuid.uuid4().hex[:6]}",
        "index": idx,
        "title": "账单",
        "summary": f"{hero}循着{prop}找到新的线索，却发现三年前那场交易里，自己才是被标价的人。",
        "hook": "倒计时归零前，她收到了一条来自自己的语音。",
        "shots": shots,
        "status": "draft",
        "video": None,
        "srt": None,
        "cover": None,
        "duration": None,
    }


def beat_has_hero(scene, shot_type):
    return scene in ("confront", "lab", "memory") and shot_type != "detail"
