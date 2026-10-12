---
title: Plugins
---

<a id="plugins"></a>

# 插件

插件可以在不修改 pokeldn 的情况下添加工具、游戏和无线通信后端。插件由 Python 文件和 `plugin.toml` 组成，以单个 `.pokeplugin` 文件分发，用户可在应用的“插件”页面添加。本项目不分发、审核第三方插件，也不提供插件支持。

代码：`pokeldn/plugins.py`（加载器和 API）、`pokeldn/app/plugin_store.py`（插件包）、`pokeldn/ldn/radios.py`（无线通信后端查询）、`gui/views/plugins.py`（页面）。

可以从两个示例开始：`examples/plugins/hello` 是最小插件，以两个文件提供一个工具；`examples/plugins/test_kit` 使用了 API 的所有部分。

<a id="installing-a-plugin"></a>

## 安装插件

1. 打开侧边菜单底部的“插件”。
2. 将 `.pokeplugin` 文件拖到页面上，或点击“添加插件”选择文件。
3. 阅读插件内容和风险，勾选确认项，再点击“安装”。

插件工具会立即出现在“游戏”页面，带有插头图标和“来自插件……”标记。每个插件卡片都有启用开关，以及打开工具、从新版文件更新、显示文件夹、访问页面和移除的菜单。每次安装或更新都会再次展示风险确认页。手动复制到插件文件夹的插件显示“手动添加”，首次启用时也需确认。

如果插件在启动时使应用关闭或无响应，应用下次启动会停用该插件并显示其名称。移除插件时会询问是否一并删除插件保存的数据。

插件在 pokeldn 内以 Python 运行，与应用具有相同的文件、密钥、网络和开发板访问权限。插件包安装并启用之前，其中的代码不会运行。

<a id="guardrails"></a>

### 防护机制

两项检查用于阻止明显有害的操作。它们都不是沙箱，恶意编写的插件可能绕过限制。

安装页面会读取插件包的 Python 文件，列出网络访问、启动其他程序、删除文件、调用原生代码（`ctypes`、`cffi`）、执行运行时生成的代码（`exec`、`eval`、`compile`、`marshal`）、引用 `prod.keys`，以及附带扫描无法读取的编译文件等行为。列表为空只表示没有发现这些行为，不能证明插件安全。

在应用以及每次运行中，只要调用栈上存在插件代码，审计钩子（`pokeldn/plugin_guard.py`）就会对以下操作抛出 `PermissionError`：

| 拒绝 | 允许 |
|---|---|
| 删除、清空、移动或覆盖插件文件夹以外的文件 | 在插件自身文件夹、数据文件夹、会话文件夹、日志文件夹和临时文件夹内进行这些操作 |
| 直接或通过 shell 命令启动 `rm`、`del`、`rd`、`Remove-Item`、`shred`、`dd`、`format`、`mkfs`、`diskutil`、`diskpart`、`sudo`、`su` 等程序，或执行带有 `-delete`、`--no-preserve-root` 的命令 | 启动其他程序 |
| | 在任意位置创建新文件 |

调用栈上没有插件时，代码不会被此机制拒绝，包括 pokeldn 自身代码；但插件调用的 pokeldn 代码也受限制。插件若需要被拒绝的操作，应请用户自行执行。

<a id="making-a-plugin"></a>

## 制作插件

<a id="the-folder"></a>

### 文件夹

    my-plugin/
        plugin.toml        what the plugin is
        plugin.py          register(api): what it adds
        hello.py           a tool's script
        icon.png           optional, shown on the Plugins page and the Games page
        mylib_common.py    optional, any module the scripts share

<a id="plugintoml"></a>

### plugin.toml

```toml
id = "my-plugin"            # required: lowercase letters, digits, dots, dashes, underscores
name = "My plugin"          # shown in the app
version = "1.0.0"           # compared on update: 1.2.0 updates 1.0.0
author = "Your name"
description = "One or two sentences shown on the install screen and the plugin's card."
homepage = "https://example.org/my-plugin"   # optional, opened from the plugin's menu
updates = "https://github.com/you/my-plugin" # optional, where newer versions are published (Updates)
api = "1.1"                 # required: the plugin API it needs (see Versions); 1 means 1.0
icon = "icon.png"           # optional; a square PNG, 96 x 96 looks sharp
module = "plugin"           # optional; the module holding register()
```

<a id="pluginpy"></a>

### plugin.py

插件启用时，`register(api)` 会在应用及应用启动的每次运行中执行。

```python
from pokeldn.plugins import Field, Game, Tool


def register(api):
    api.add_tool("frlg", Tool(
        "my-hello",                                   # a key no other tool uses
        "Hello",                                      # the name on the Games page
        "hello.py",                                   # the script, relative to the plugin folder
        "Says hello.",                                # the line under the tool's name
        ("Nothing to do on the console.", "Press Start."),   # the console steps the app lists
        fields=(Field("--name", "Your name", default="Red"),),
        fixed=("--trainer", "{ot}"),                  # always passed; {ot} is the trainer name in Settings
    ))
```

<a id="a-tools-script"></a>

### 工具脚本

应用先导入脚本，读取“高级”页的选项，再在会话文件夹中以子进程运行。脚本须定义 `build_parser()`，并在 `if __name__ == "__main__"` 中执行任务；顶层任务会在导入时运行，导致“游戏”页面出错。

```python
import argparse


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name")
    parser.add_argument("--trainer")
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    print(f"Hello {args.name}, from {args.trainer}'s pokeldn.")
```

| 脚本行为 | 应用行为 |
|---|---|
| 输出一行 | 在会话输出中显示 |
| 输出 `[done] trade N complete`（`pokeldn.ldn.show_done()`） | 将一个排队交换标记为完成 |
| 以代码 0 退出 | 将会话标记为完成 |
| 以其他代码退出或抛出异常 | 显示会话失败，并在输出中显示异常堆栈 |
| 收到 `KeyboardInterrupt` | 用户点击了“停止”；应在 15 秒内正常退出，否则进程会被结束 |

共享模块应使用其他包未使用的名称（例如 `mylib_common`，避免 `utils`），因为插件文件夹会被加入 Python 搜索路径。

<a id="what-a-plugin-can-import"></a>

### 插件可以导入的模块

官方发布的应用自带 Python 3.13，不包含 `pip`。插件可导入：

| 内容 | 来源 |
|---|---|
| 标准库 | 已打包，但不含 `multiprocessing`、`tkinter`、`curses`、`venv`、`ensurepip`、`profile`、`cProfile`、`pstats`、`trace`、`compileall`、`modulefinder`、`pyclbr`、`tabnanny` 和其他平台专用模块（`scripts/pack_app.py`、`PLUGIN_STDLIB`） |
| `trio`、`pycryptodome`（`Crypto`）、`zstandard`、`pyserial`（`serial`）、`websockets`、`certifi`、`bleak`、`unicorn`、`flet` | pokeldn 自身的依赖，版本见 `requirements.txt` |
| `ldn` 和 `pokeldn` | pokeldn 自身；仅下方 API 表列出的接口保持稳定 |
| 任意纯 Python 模块 | 随插件文件夹提供 |

包含编译代码的包（如 `numpy`、`Pillow`）只在已安装相应依赖的源码运行环境中可用。发布插件前应在发布版应用中测试；Plugin Test Kit 的自测也可在其中以相同方式运行。

<a id="fields"></a>

### 字段

`Field` 是工具“基本”页中的一个输入项，应用将其值放在对应参数之后。

| `kind` | 输入项 | 传递方式 |
|---|---|---|
| `text`（默认） | 文本框 | `--flag VALUE` |
| `number` | 数字框 | `--flag VALUE` |
| `choice` | 使用 `choices=((value, label), ...)` 的下拉框 | `--flag VALUE` |
| `switch` | 开关 | 启用时传递 `--flag` |
| `file` | 文件选择器，`exts=("bin",)` | `--flag PATH` |

<a id="what-a-plugin-keeps"></a>

### 插件保存的数据

更新会替换插件文件夹。设置、缓存和需要长期保存的内容应放在 `register` 提供的 `api.data`，或工具脚本调用 `pokeldn.plugins.data_folder("my-plugin")` 获得的目录中：它位于应用数据目录的 `plugin-data/<id>`，更新时保留，只有用户要求时才随插件移除。

`help=` 在输入项下显示说明，`default=` 提供默认值，`hidden=True` 将字段移到“高级”页。内置工具的字段及其余 `Field` 属性见 `pokeldn/app/catalog.py`。工具的 `fixed` 参数可包含 `{ot}`、`{tid}`、`{sid}`、`{language}`（设置中的训练家）、`{received}`（接收文件夹）及 `{stamp}`（开始运行的时间）。

<a id="a-game-of-its-own"></a>

### 独立游戏分组

```python
api.add_game(Game("my-game", "My game", "Mine", "", (tool_one, tool_two)), icon="icon.png")
```

`Game(key, name, short, doc, tools)` 创建的游戏分组列在内置游戏下方，按顺序展示工具。`api.add_tool("my-game", tool)` 可继续添加工具。

<a id="a-radio"></a>

### 无线通信后端

无线通信后端可替代 ESP32 开发板传输无线消息。`api.add_radio(scheme, install,
label)` 会将其列在“插件”页的“无线通信后端”中；使用此后端启动的运行，会在首次无线调用前执行 `install(argument, log)`。

```python
import contextlib
from ldn import wlan


def install(argument, log):
    @contextlib.asynccontextmanager
    async def factory():
        yield MyFactory()           # the interface of ldn.wlan.Factory
    wlan.set_factory(factory)


def register(api):
    api.add_radio("myradio", install, "My radio")
```

`pokeldn/ldn/esp32_wlan.py` 是开发板的工厂实现，可作为不使用内核接口的后端参考。应用通过 `POKELDN_RADIO=myradio:` 使用插件后端，参数为空；命令行中的参数为冒号后的内容。

<a id="packing-and-testing"></a>

### 打包与测试

```bash
python scripts/pack_plugin.py my-plugin --key ~/my-plugin-signing.pem
```

该命令生成已签名的 `my-plugin-1.0.0.pokeplugin`，并按应用安装前的方式检查。任何 ZIP 都可使用，只需 `plugin.toml` 位于顶层或唯一的顶层文件夹内，路径不能越出该文件夹，且不能含符号链接。

开发时可跳过打包，将文件夹写入 `POKELDN_PLUGINS`；此进程及其启动的运行都会启用插件，不受“插件”页面开关影响。

```bash
POKELDN_PLUGINS=~/my-plugin python -m pokeldn --plugins
POKELDN_PLUGINS=~/my-plugin python -m pokeldn my-hello -- --name Blue
POKELDN_PLUGINS=~/my-plugin python gui/main.py
```

`--plugins` 列出所有发现的插件及加载失败原因。插件若在 `register` 中抛出异常、要求其他 API 版本或占用已有键，不会添加任何内容；卡片显示错误，其他插件仍可加载。插件也可作为 Python 包分发，通过 `pokeldn.plugins` 入口点组指定包含 `register` 的模块。

<a id="signing"></a>

### 签名

`--key FILE` 使用作者的 Ed25519 密钥签名，首次运行时在 `FILE` 创建密钥，并输出指纹（`ABCD-EFGH-IJKL-MNOP`）。插件包包含 `plugin.sig`，其中保存公钥及覆盖插件 ID、版本和所有其他文件 SHA-256 的签名。

| 应用看到的内容 | 显示或处理方式 |
|---|---|
| 签名与文件不一致 | 拒绝文件：作者签名后文件被修改 |
| 从未见过的已签名插件 | 显示指纹，并记住该插件 ID 的密钥 |
| 使用已记住密钥签名的更新 | “由同一作者签名” |
| 使用其他密钥签名，或之前有签名而现在没有 | 显示红色警告；需额外确认才能安装 |
| 从未见过签名的未签名插件 | “未签名” |

请保密并备份密钥文件：密钥丢失会使后续版本看起来来自其他人；持有密钥的人都能以作者身份签名。可在插件页面公开指纹，供用户与安装页面显示的指纹比对。首次安装无法证明作者身份；签名证明后续版本来自同一作者。

<a id="updates"></a>

### 更新

`plugin.toml` 的 `updates` 指定新版发布位置：

| `updates` | 应用读取的内容 |
|---|---|
| `https://github.com/OWNER/REPO` | 最新 Release 的标签（`v1.3.0` 或 `1.3.0`）及第一个 `.pokeplugin` 附件 |
| 其他 HTTPS 地址 | JSON 文件 `{"version": "1.3.0", "url": "https://.../my-plugin-1.3.0.pokeplugin", "page": "..."}` |

启用“设置 → 更新”后，应用会在启动时和“插件”页点击刷新时查询各已安装插件的更新地址。有新版时，“插件”菜单变为绿色，卡片显示“更新到 1.3.0”；点击后下载文件，并打开包含签名检查的安装页。未经用户确认不会安装。为便于本地测试，仅 `127.0.0.1` 和 `localhost` 接受 HTTP。

<a id="the-plugin-test-kit"></a>

## Plugin Test Kit

使用 `scripts/pack_plugin.py` 打包的 `examples/plugins/test_kit` 提供：

| 位置 | 工具 | 行为 |
|---|---|---|
| Plugin Test Kit | Self-test | 检查 API 版本、自身加载、模块导入、所有字段类型、训练家占位符、会话目录、数据目录（保存更新后仍保留的运行计数）及无线后端；逐项输出 PASS 或 FAIL |
| Plugin Test Kit | Simulated session | 输出交换步骤，每次交换输出 `[done]` 行；点击“停止”后正常退出 |
| Plugin Test Kit | Fail on purpose | 抛出异常，或以代码 3 退出 |
| 火红／叶绿 | Hello from a plugin | 在内置工具中添加插件工具 |
| 无线通信后端 | Test Kit radio | 安装但不传输消息；使用该后端的会话会明确提示 |

<a id="versions"></a>

## 版本

插件 API 包含主版本和级别，写作 `1.1`。插件的 `api` 指定所需最低版本；应用在“插件”页和 `python -m pokeldn --plugins` 中显示自身版本。

| API 变化 | 应用行为 |
|---|---|
| 新增内容 | 提升级别；需要更高级别的插件会被拒绝，并提示“更新 pokeldn” |
| 删除内容或改变含义 | 提升主版本 |
| 仍支持的旧主版本 | `pokeldn/plugins.py` 的 `DEPRECATED` 指定停止支持的发布版本；插件仍可加载，卡片和安装页会提示 |
| 停止支持的旧主版本 | `API_OLDEST` 已高于它；拒绝插件，并提示“向作者获取新版” |

插件自身的 `version` 只与已安装副本比较，用来显示更新、重新安装或降级。

| API | 新增 |
|---|---|
| 1.0 | `add_tool`、`add_game`、`add_radio`、`folder`、`version` |
| 1.1 | `api.data`、`api.level`、`pokeldn.plugins.data_folder(id)` |

<a id="the-api-version-1"></a>

## API，版本 1

| 名称 | 含义 |
|---|---|
| `api.add_tool(game, tool)` | 在键为 `game` 的游戏下添加 `Tool`：`frlg`、`lgpe`、`swsh`、`bdsp`、`pla`、`sv`、`za`，或插件添加的游戏 |
| `api.add_game(game, icon="")` | 添加游戏分组及工具 |
| `api.add_radio(scheme, install, label="")` | 添加无线通信后端 |
| `api.folder` | 插件文件夹（`Path`）；Python 包插件为 None |
| `api.version`、`api.level` | 应用使用的主版本和级别，即 `1` 和 `1` |
| `api.data` | 更新时保留的文件夹，首次使用时创建（1.1） |
| `pokeldn.plugins.data_folder(id)` | 工具脚本访问同一文件夹的接口（1.1） |
| `Tool`、`Field`、`Game` | 应用目录类型，从 `pokeldn.plugins` 导入 |
| `pokeldn.ldn.show_done()` | 输出将一次交换标记为完成的行 |

此表是受支持的接口。插件从 pokeldn 导入的其他内容可能在任意版本变化。
