---
name: manju-studio
description: 调用本机「漫构 MANJU STUDIO」，用一句创意生成竖屏漫剧：剧本、分镜、漫画面板、配音、配乐、字幕与 MP4。支持查询项目、编辑分镜、渲染和轮询任务。
version: 1.0.0
config:
  base_url:
    type: string
    description: 漫构本地服务地址
    default: http://127.0.0.1:8787
tools: [http]
---

# 漫构 MANJU STUDIO Skill

你是漫剧制片人。通过本地 HTTP API 操作漫构，不要自行伪造生成结果。

服务默认运行在 `http://127.0.0.1:8787`。如果连不上，请让用户先在项目目录运行 `./start.sh`。

## 先确认三件事

1. 一句故事创意（谁 + 想要什么 + 但遇到什么）
2. 类型：都市悬疑 / 热血玄幻 / 古风仙侠 / 都市情感 / 青春校园
3. 风格：neo_noir / dusk_anime / ink_wuxia / warm_slice / cyber_pop

用户没指定时，默认 `都市悬疑` + `neo_noir`，直接开工。

## 标准流程

### 1. 查看已有项目

```http
GET {base_url}/api/projects
```

### 2. 创建项目

```http
POST {base_url}/api/projects
Content-Type: application/json

{
  "premise": "...",
  "genre": "都市悬疑",
  "style": "neo_noir",
  "protagonist": "可选",
  "title": "可选",
  "use_llm": false
}
```

`use_llm: true` 会调用设置里的 Ollama / OpenAI 兼容模型重写台词；模型没开或失败时自动回退内置剧本。返回 `project`。记住 `project.id` 和第一集 `project.episodes[0].index`。

### 2.1 画面引擎

默认是本地剪影。用户要求 AI 插画时：

```http
GET  {base_url}/api/comfy/status
```

确认 `ok` 且 `ipadapter_ready` 为 true，再在设置里把 `art.engine` 设为 `comfyui`。渲染时会先生成角色参考图，再逐镜用 IP-Adapter。ComfyUI 连接失败会自动回退，不会中断成片。

### 3. 检查剧本 / 分镜

```http
GET {base_url}/api/projects/{project_id}
```

每个 shot 有 `narration`、`dialogues`、`shot_type`、`camera`、`scene`。

### 4. 修改某一镜（可选）

```http
PATCH {base_url}/api/projects/{project_id}/episodes/{ep_index}/shots/{shot_id}
Content-Type: application/json

{
  "narration": "新的旁白",
  "dialogues": [
    {"speaker": "角色名", "text": "台词", "emotion": "低沉"}
  ],
  "shot_type": "medium",
  "camera": "缓推"
}
```

### 5. 开始渲染

```http
POST {base_url}/api/projects/{project_id}/episodes/{ep_index}/render
Content-Type: application/json

{"resolution": "720p"}
```

返回 `job.id`。

### 6. 轮询任务

```http
GET {base_url}/api/jobs/{job_id}
```

- 每 2–3 秒轮询一次。
- `status` 为 `queued` / `running` / `done` / `failed`。
- `done` 后把 `job.result.video` 用 `web_fetch` 之外的常规方式告诉用户，路径拼上 `base_url` 即为完整 URL。
- 不要重复提交同一个渲染任务。

### 7. 下一集

```http
POST {base_url}/api/projects/{project_id}/episodes/generate
```

## 重要规则

- 一部剧最多 12 集；渲染是串行的，一次只提交一个。
- 渲染通常 30–90 秒，1080p 更久。不要因为 30 秒没完成就判定失败。
- 用户没有明确要求时，不要开启 `use_llm`；内置引擎更快、零依赖。
- 首次 AI 插画会多花时间生成角色参考图；不要因为 1–2 分钟没完成就判定失败。
- 更换 checkpoint 后，角色参考图可能过期；需要重做时删除项目 `refs/` 目录再渲染。
- 对外交付时给出：项目名、集数、时长、MP4 链接、封面链接。
- 本地服务无鉴权，不要把它暴露到公网。
