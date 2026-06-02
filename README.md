# zven-imagegen

Zven Imagegen 是这个 skill 的展示名。

一个面向 Codex 的图像生成 skill，支持 `base_url + key` 和 `stream`
流式传输，用来降低长连接超时断连的概率。

它主要解决两件事：

- 用独立的 `IMAGEGEN_OPENAI_API_KEY` / `IMAGEGEN_OPENAI_BASE_URL` 配置生图端点，
  不污染 Codex 或项目里其它 OpenAI 配置。
- 用流式 Images API 接收 partial image 事件，持续打印进度，降低长连接被
  Cloudflare、反代、网关或空闲超时杀掉的概率。

## 适合谁

如果你是中文用户，并且通过中转、反代、自建网关、兼容 OpenAI 的服务商、
Cloudflare 代理等方式使用 Codex，结果发现 Codex 的原生生图 skill 不能很好地
吃到你的 `base_url + key`，这个 skill 就是给你准备的。

## 安装

仓库发布到 GitHub 后，最简单的方式是直接让 Codex 安装：

```text
$skill-installer install https://github.com/zvensmoluya/zven-imagegen/tree/main/zven-imagegen
```

如果安装后 Codex 没有识别到，重启 Codex。

手动安装时，把 `zven-imagegen` 文件夹复制到用户级 skill 目录：

```powershell
New-Item -ItemType Directory -Force "$HOME\.agents\skills" | Out-Null
Copy-Item -Recurse .\zven-imagegen "$HOME\.agents\skills\zven-imagegen"
```

如果只想让某个项目使用它，也可以复制到该项目的：

```text
.agents/skills/zven-imagegen
```

一些旧版本地 Codex 环境也会扫描 `$HOME\.codex\skills`。只有在你的 Codex
确实使用这个目录时，才优先放那里。

## Python 环境

脚本已经内置在 skill 里：

```text
zven-imagegen/scripts/imagegen_stream.py
```

普通项目里不需要、也不应该再放一份 `scripts/imagegen_stream.py`。Codex 使用这个
skill 时默认调用跨平台的 `invoke_imagegen.py`，wrapper 会固定调用 skill 自己内置的
helper。`invoke-imagegen.ps1` 只是 Windows PowerShell 兼容入口。

wrapper 会在 skill 目录里创建一个托管 `.venv`，首次真实调用时自动安装
`openai>=2.0.0`。只有在机器上找不到 Python 时，才需要设置 `IMAGEGEN_PYTHON`
指向 Python 3.10+ 可执行文件。

## 配置

推荐使用专门的生图环境变量：

```powershell
setx IMAGEGEN_OPENAI_BASE_URL "https://your-image-endpoint.example/v1"
setx IMAGEGEN_OPENAI_API_KEY "your image API key"
```

也可以在项目根目录创建私有配置文件，文件名任选一个：

```text
.agentonlyenv
.imagegen.env
.env.imagegen
```

内容示例：

```dotenv
IMAGEGEN_OPENAI_BASE_URL=https://your-image-endpoint.example/v1
IMAGEGEN_OPENAI_API_KEY=your-image-api-key
```

这些文件已经在本仓库 `.gitignore` 里，真实 key 不要提交。

## 使用

先 dry-run，确认路由、参数和输出路径：

```bash
python "$HOME/.agents/skills/zven-imagegen/scripts/invoke_imagegen.py" generate \
  --prompt "A small leaf sticker, soft pastel illustration, no text" \
  --out output/imagegen/leaf.png \
  --dry-run
```

流式生成：

```bash
python "$HOME/.agents/skills/zven-imagegen/scripts/invoke_imagegen.py" generate \
  --prompt "A small leaf sticker, soft pastel illustration, no text" \
  --size 1024x1024 \
  --quality low \
  --partial-images 1 \
  --out output/imagegen/leaf.png
```

编辑图片：

```bash
python "$HOME/.agents/skills/zven-imagegen/scripts/invoke_imagegen.py" edit \
  --image input.png \
  --prompt "Change only the background to a clean white studio backdrop" \
  --out output/imagegen/edited.png
```

调试 skill 本身时，也可以直接跑内置 helper：

```powershell
python .\zven-imagegen\scripts\imagegen_stream.py generate `
  --prompt "A simple blue app icon, no text" `
  --out output\imagegen\icon.png
```

## Codex 会怎么用

安装后，Codex 会读取 `zven-imagegen/SKILL.md` 的 frontmatter 和正文。当用户要求
生成或编辑图片，并且场景涉及自定义 `base_url`、中转、Cloudflare、独立生图 key、
`IMAGEGEN_*` 配置或需要流式防断连时，Codex 就应该触发这个 skill。

`invoke_imagegen.py` 会转发所有参数，并按顺序选择：

1. 本 skill 内置的 `scripts/imagegen_stream.py`

它不会自动发现当前项目里的 `scripts/imagegen_stream.py`，也不会回退到系统
`imagegen` skill。普通用户只要安装 skill，不需要再把脚本复制到自己的项目里。
生成和编辑默认都是流式；只有端点明确不支持 stream 时才加 `--no-stream`。

`invoke-imagegen.ps1` 只是在 Windows 上调用 `invoke_imagegen.py` 的兼容 shim。

## 凭据优先级

wrapper 会按顺序读取：

1. `IMAGEGEN_OPENAI_API_KEY`
2. `IMAGEGEN_OPENAI_BASE_URL`
3. 项目里的 `.agentonlyenv`、`.imagegen.env` 或 `.env.imagegen`
4. Codex `auth.json` 里的 API key
5. Codex `config.toml` 里的 base URL

Python helper 自身只主动读取 `IMAGEGEN_*` 和项目私有 env 文件；wrapper 会在子进程里
把这些值映射成 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。

## 开发与验证

```powershell
python .\zven-imagegen\scripts\invoke_imagegen.py generate --prompt "test" --dry-run
powershell -ExecutionPolicy Bypass -File .\zven-imagegen\scripts\invoke-imagegen.ps1 generate --prompt "test" --dry-run
python -m py_compile .\zven-imagegen\scripts\imagegen_stream.py
python -m pytest
```

如果本机有 Codex 的 skill-creator，可以校验 skill 元数据：

```powershell
python "$HOME\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\zven-imagegen
```

## 许可证

本仓库采用 MIT License，详见 [LICENSE](LICENSE)。
