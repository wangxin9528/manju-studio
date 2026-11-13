# 本机 AI 插画环境

这套工作区已经实际安装并验证：

- ComfyUI 0.45.0
- ComfyUI_IPAdapter_plus
- AnythingV5（SD1.5 动漫底模，2.1GB）
- IP-Adapter Plus SD15（94MB）
- CLIP-ViT-H（2.4GB）
- 独立环境 `.tools/comfyui-venv`（torch 2.15 / MPS）

路径：

```text
.tools/ComfyUI/
.tools/comfyui-venv/
```

启动：

```bash
./scripts/start_comfyui.sh
```

默认地址 `http://127.0.0.1:8188`。首次加载模型会慢一些。

真实测速（M2 / 8GB）：

| 项目 | 耗时 |
|---|---|
| 角色参考图 512×768 / 8 steps | 约 82 秒（含模型加载） |
| IP-Adapter 分镜 512×768 / 8 steps | 约 56–100 秒 |
| 单镜 7.8 秒成片（含配音/配乐/MP4） | 约 68 秒 |

在漫构「本地设置」中：

1. 画面引擎：ComfyUI + IP-Adapter
2. 地址：`http://127.0.0.1:8188`
3. 点「测试 ComfyUI / 读取模型」
4. Checkpoint：`anything-v5.safetensors`
5. 先使用 512×896、12–20 steps 做速度测试

8GB M2 使用 MPS。若内存不足，可尝试：

```bash
./scripts/start_comfyui.sh --lowvram
```

注意：AnythingV5 是动漫向 SD1.5 模型；IP-Adapter 对角色服装和发型的锁定通常比脸更稳定，复杂双人镜头仍可能需要多抽几张。8 镜整集建议预留 15–25 分钟，并先用单镜测试。

真实测试静帧：`docs/comfyui-test/rooftop-ipadapter.jpg`；单镜视频：`output/ai_art_one_shot.mp4`。
