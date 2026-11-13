"""Sample project and the built-in zero-key story engine."""
from __future__ import annotations

import random
import re
import uuid
from datetime import datetime, timezone


STYLE_IDS = ["neo_noir", "dusk_anime", "ink_wuxia", "warm_slice", "cyber_pop"]

GENRES = {
    "都市悬疑": {
        "palette": "neo_noir",
        "places": ["雨夜天台", "记忆实验室", "旧城区巷道", "无人车站"],
        "props": ["一枚没有编号的记忆芯片", "一段被反复删除的录音", "一把生锈的储物柜钥匙"],
        "lines": [
            "这座城市最不缺的，就是被卖掉的人生。",
            "你确定，你删掉的只是一段记忆？",
            "别相信你看见的，先相信你听见的。",
            "有些真相，一旦想起来，就再也睡不着了。",
        ],
    },
    "热血玄幻": {
        "palette": "ink_wuxia",
        "places": ["断魂崖", "荒原古城", "雷池", "无名剑冢"],
        "props": ["一柄没有影子的剑", "半枚染血的令牌", "一枚仍在跳动的火种"],
        "lines": [
            "命是弱者的借口，运是强者的谦词。",
            "这一剑，我替三年前的人问。",
            "天道不公，那我就自己写一个。",
            "你怕的不是死，是白活一场。",
        ],
    },
    "古风仙侠": {
        "palette": "ink_wuxia",
        "places": ["云海仙门", "落星潭", "藏经阁", "九重天阶"],
        "props": ["一盏不灭的魂灯", "半卷无字天书", "一枚裂纹玉佩"],
        "lines": [
            "仙路尽头，不过是一句放不下。",
            "我修的不是长生，是一个答案。",
            "你渡得了天下人，为何渡不了我？",
            "若天命如此，我便逆一次给你看。",
        ],
    },
    "都市情感": {
        "palette": "warm_slice",
        "places": ["深夜便利店", "旧公寓", "末班地铁", "医院长廊"],
        "props": ["一张过期的电影票", "一杯凉掉的咖啡", "一部没有电量的旧手机"],
        "lines": [
            "我们之间，到底是谁先松的手？",
            "有些再见，说出口就真的再也见不到了。",
            "我不是不爱你，我是来不及了。",
            "如果那天我回头，你会不会还在？",
        ],
    },
    "青春校园": {
        "palette": "dusk_anime",
        "places": ["夏日天台", "放学后的教室", "操场看台", "图书馆角落"],
        "props": ["一封没有署名的信", "一张褪色的合照", "半块橡皮"],
        "lines": [
            "那年夏天，我以为我们会一直这样。",
            "有些喜欢，藏在一句‘明天见’里。",
            "你后来才知道，他那天等了很久。",
            "毕业不是结束，是我终于敢承认。",
        ],
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _shot(
    idx: int,
    *,
    scene: str,
    location: str,
    time: str,
    shot_type: str,
    camera: str,
    characters: list[str],
    pose: str,
    focus: str,
    narration: str = "",
    narration_speaker: str = "旁白",
    dialogues: list[dict] | None = None,
    sfx: list[str] | None = None,
    caption: str = "",
) -> dict:
    return {
        "id": f"s{idx:02d}",
        "index": idx,
        "scene": scene,
        "location": location,
        "time": time,
        "shot_type": shot_type,
        "camera": camera,
        "characters": characters,
        "pose": pose,
        "focus": focus,
        "narration": narration,
        "narration_speaker": narration_speaker,
        "dialogues": dialogues or [],
        "sfx": sfx or [],
        "caption": caption,
        "image_prompt": "",
        "image": None,
        "video": None,
        "duration": None,
    }


def sample_project() -> dict:
    """A hand-directed sample episode used as the studio's showreel."""
    pid = "wucheng-memory"
    shots = [
        _shot(
            1,
            scene="rooftop",
            location="雾城 · 天台",
            time="23:47",
            shot_type="wide",
            camera="航拍缓推",
            characters=["linwu"],
            pose="stand_back",
            focus="city",
            narration="雾城没有夜晚，只有还没卖掉的梦。",
            narration_speaker="林雾",
            sfx=["rain", "city"],
            caption="雾城 · 雨夜",
        ),
        _shot(
            2,
            scene="rooftop",
            location="雾城 · 天台边缘",
            time="23:49",
            shot_type="medium",
            camera="横移",
            characters=["linwu", "shenyan"],
            pose="stand_back",
            focus="shenyan",
            dialogues=[
                {"speaker": "沈砚", "text": "听说你能修补任何记忆。", "emotion": "低沉"},
                {"speaker": "林雾", "text": "死人除外。", "emotion": "冷淡"},
            ],
            sfx=["rain"],
            caption="雨没有停过",
        ),
        _shot(
            3,
            scene="prop",
            location="天台 · 雨中",
            time="23:50",
            shot_type="detail",
            camera="微距",
            characters=["shenyan"],
            pose="reach",
            focus="chip",
            dialogues=[
                {"speaker": "沈砚", "text": "这段记忆，被它的主人亲手删了。", "emotion": "低沉"},
            ],
            sfx=["rain", "spark"],
            caption="委托物 · 07 号记忆芯片",
        ),
        _shot(
            4,
            scene="lab",
            location="林雾 · 记忆修复室",
            time="00:12",
            shot_type="medium",
            camera="缓慢环绕",
            characters=["linwu"],
            pose="sit",
            focus="linwu",
            dialogues=[
                {"speaker": "白噪", "text": "记忆完整度百分之三，建议放弃。", "emotion": "轻快"},
                {"speaker": "林雾", "text": "我从不放弃。", "emotion": "冷静"},
            ],
            sfx=["hum", "glitch"],
            caption="修复进行中",
        ),
        _shot(
            5,
            scene="memory",
            location="记忆 · 白色走廊",
            time="三年前",
            shot_type="wide",
            camera="手持跟拍",
            characters=["girl"],
            pose="run",
            focus="corridor",
            narration="不对。这段记忆里，有我的气味。",
            narration_speaker="林雾",
            sfx=["alarm", "heartbeat"],
            caption="异常记忆 · 03 年前",
        ),
        _shot(
            6,
            scene="lab",
            location="记忆修复室",
            time="00:13",
            shot_type="close",
            camera="急推",
            characters=["linwu"],
            pose="closeup",
            focus="linwu",
            dialogues=[
                {"speaker": "白噪", "text": "心率一百四十七。林雾，你在害怕。", "emotion": "失真"},
            ],
            sfx=["glitch", "heartbeat"],
            caption="她认得这条走廊",
        ),
        _shot(
            7,
            scene="lab_door",
            location="修复室 · 门口",
            time="00:14",
            shot_type="medium",
            camera="固定 · 浅景深",
            characters=["shenyan"],
            pose="stand",
            focus="shenyan",
            dialogues=[
                {"speaker": "沈砚", "text": "现在，想起我了吗？", "emotion": "低沉"},
            ],
            sfx=["hum"],
            caption="阴影里的人",
        ),
        _shot(
            8,
            scene="chip",
            location="07 号记忆芯片",
            time="00:00:07",
            shot_type="detail",
            camera="微距推进",
            characters=[],
            pose="static",
            focus="chip",
            dialogues=[
                {"speaker": "林雾", "text": "你到底是谁？", "emotion": "颤抖"},
                {"speaker": "沈砚", "text": "三年前，你也是这么问的。", "emotion": "低沉"},
            ],
            narration="",
            sfx=["heartbeat", "alarm"],
            caption="倒计时 00:07",
        ),
    ]

    characters = [
        {
            "id": "linwu",
            "name": "林雾",
            "role": "主角 / 记忆修复师",
            "age": "27",
            "persona": "冷静、克制，靠修补别人的记忆谋生。三年前亲手删掉了自己的一段记忆。",
            "appearance": "银灰短发，白色机能风衣，右耳一枚黑色记忆接口，眼神很静。",
            "appearance_en": "young Chinese woman, silver-gray bob hair, white technical trench coat, black memory port behind right ear, calm restrained eyes, cyberpunk noir",
            "voice": "zh-CN-XiaoxiaoNeural",
            "accent": "#63F2DE",
            "color": "#DDE7E6",
        },
        {
            "id": "shenyan",
            "name": "沈砚",
            "role": "委托人 / 旧日搭档",
            "age": "30",
            "persona": "寡言，像一把收在雨里的刀。他知道林雾忘记的全部。",
            "appearance": "黑色长风衣，苍白瘦削，左眼下有一道很浅的旧伤，声音低哑。",
            "appearance_en": "tall lean Chinese man, black long trench coat, black fedora, pale skin, faint scar under left eye, mysterious noir client",
            "voice": "zh-CN-YunjianNeural",
            "accent": "#FF4D3D",
            "color": "#1B1D24",
        },
        {
            "id": "bainao",
            "name": "白噪",
            "role": "AI 助手",
            "age": "--",
            "persona": "住在林雾耳机里的修复系统。语气轻快，偶尔像人一样多嘴。",
            "appearance": "没有实体，以白色声波纹与全息噪点出现。",
            "appearance_en": "abstract AI assistant hologram, white sound wave rings and digital noise, no physical body",
            "voice": "zh-CN-YunxiNeural",
            "accent": "#F5EFE4",
            "color": "#F5EFE4",
        },
    ]

    episode = {
        "id": "ep01",
        "index": 1,
        "title": "第七码",
        "summary": "林雾接下沈砚的委托，却发现芯片里被删除的记忆，属于她自己。",
        "hook": "芯片倒计时只剩七秒，而沈砚叫出了她三年前的名字。",
        "shots": shots,
        "status": "draft",
        "video": None,
        "srt": None,
        "cover": None,
        "duration": None,
    }

    return {
        "id": pid,
        "title": "雾城记忆",
        "premise": "在记忆可以买卖的雾城，记忆修复师林雾接到一单诡异的生意——修复一段被抹去的记忆，而记忆里的主角，正是她自己。",
        "genre": "都市悬疑",
        "style": "neo_noir",
        "style_name": "霓虹黑",
        "aspect": "9:16",
        "resolution": "720p",
        "logline": "她靠修补别人的记忆为生，直到有一天，她在一段陌生记忆里看见了自己。",
        "characters": characters,
        "episodes": [episode],
        "cover": None,
        "sample": True,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def _pick_name(premise: str, fallback: str = "顾言") -> str:
    match = re.search(r"(?:主角|主人公|女主|男主)[：:\s]*([\u4e00-\u9fa5]{2,4})", premise)
    return match.group(1) if match else fallback


def compose_story(
    premise: str,
    genre: str,
    style: str,
    protagonist: str = "",
    title: str = "",
) -> dict:
    """A deterministic 8-shot micro drama generator.

    It is intentionally simple and fully offline. If an LLM is configured in
    settings, the API layer uses that instead of this function.
    """
    meta = GENRES.get(genre, GENRES["都市悬疑"])
    rng = random.Random(f"{premise}-{genre}-{style}")
    name = protagonist.strip() or _pick_name(premise)
    place_a = rng.choice(meta["places"])
    place_b = rng.choice([p for p in meta["places"] if p != place_a])
    prop = rng.choice(meta["props"])
    line_a, line_b, line_c, line_d = rng.sample(meta["lines"], 4)
    clean_premise = premise.strip().rstrip("。！？") or "一个普通人突然被命运点名"
    title = title.strip() or clean_premise[:10]
    logline = f"{name}以为这只是一次普通的相遇，直到{prop}把TA拖进一个无法撤回的夜晚。"

    shots = [
        _shot(
            1,
            scene="establish",
            location=place_a,
            time="23:47",
            shot_type="wide",
            camera="缓慢推进",
            characters=[name],
            pose="stand_back",
            focus="city",
            narration=f"{clean_premise}。{line_a}",
            sfx=["rain"],
            caption=place_a,
        ),
        _shot(
            2,
            scene="confront",
            location=place_a,
            time="23:49",
            shot_type="medium",
            camera="横移",
            characters=[name],
            pose="stand",
            focus=name,
            dialogues=[{"speaker": name, "text": "这件事，和我无关。", "emotion": "克制"}],
            sfx=["wind"],
            caption="她原本可以转身离开",
        ),
        _shot(
            3,
            scene="detail",
            location=place_a,
            time="23:50",
            shot_type="detail",
            camera="微距",
            characters=[],
            pose="static",
            focus="prop",
            dialogues=[{"speaker": "陌生人", "text": f"你认得它，对吗？{prop}。", "emotion": "低沉"}],
            sfx=["spark"],
            caption="关键物件",
        ),
        _shot(
            4,
            scene="interior",
            location=place_b,
            time="00:12",
            shot_type="medium",
            camera="固定",
            characters=[name],
            pose="sit",
            focus=name,
            dialogues=[{"speaker": name, "text": line_b, "emotion": "动摇"}],
            sfx=["hum"],
            caption="她开始查那晚的事",
        ),
        _shot(
            5,
            scene="memory",
            location="记忆深处",
            time="三年前",
            shot_type="wide",
            camera="手持",
            characters=[],
            pose="run",
            focus="corridor",
            narration="画面突然失真。她看见一个不该出现在这里的自己。",
            sfx=["glitch", "heartbeat"],
            caption="被抹掉的那一页",
        ),
        _shot(
            6,
            scene="close",
            location=place_b,
            time="00:13",
            shot_type="close",
            camera="急推",
            characters=[name],
            pose="closeup",
            focus=name,
            dialogues=[{"speaker": "陌生人", "text": line_c, "emotion": "逼近"}],
            sfx=["heartbeat"],
            caption="呼吸停了一拍",
        ),
        _shot(
            7,
            scene="confront",
            location=place_b,
            time="00:14",
            shot_type="medium",
            camera="浅景深",
            characters=[name],
            pose="stand",
            focus=name,
            dialogues=[{"speaker": name, "text": line_d, "emotion": "决绝"}],
            sfx=["impact"],
            caption="她做了决定",
        ),
        _shot(
            8,
            scene="void",
            location="真相之前",
            time="00:00:07",
            shot_type="detail",
            camera="静止",
            characters=[],
            pose="static",
            focus="prop",
            dialogues=[{"speaker": "陌生人", "text": "别急着想起来。你还没有付得起代价。", "emotion": "低语"}],
            narration="",
            sfx=["heartbeat", "alarm"],
            caption="下一集 · 代价",
        ),
    ]

    char_id = re.sub(r"\s", "", name) or "protagonist"
    characters = [
        {
            "id": char_id,
            "name": name,
            "role": "主角",
            "age": "27",
            "persona": f"被卷入「{clean_premise[:24]}」的人。表面冷静，一旦决定就不会回头。",
            "appearance": "深色短发，长外套，眼神克制，习惯站在光与暗的交界处。",
            "appearance_en": "Chinese protagonist, short dark hair, long coat, restrained eyes, standing between light and shadow, cinematic noir",
            "voice": "zh-CN-XiaoxiaoNeural",
            "accent": "#63F2DE",
            "color": "#DDE7E6",
        },
        {
            "id": "stranger",
            "name": "陌生人",
            "role": "关键人物",
            "age": "30",
            "persona": "知道主角过去的人。说话很慢，像在替某个人传话。",
            "appearance": "黑色长风衣，身形清瘦，半张脸藏在阴影里。",
            "appearance_en": "lean mysterious stranger, black long coat, half of face hidden in shadow, noir film still",
            "voice": "zh-CN-YunjianNeural",
            "accent": "#FF4D3D",
            "color": "#1B1D24",
        },
    ]

    episode = {
        "id": f"ep{uuid.uuid4().hex[:6]}",
        "index": 1,
        "title": title,
        "summary": logline,
        "hook": "她以为自己在修一段记忆，实际上是在拆一颗定时炸弹。",
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
        "aspect": "9:16",
        "resolution": "720p",
        "logline": logline,
        "characters": characters,
        "episodes": [episode],
        "cover": None,
        "sample": False,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
