---
title: Plugins
---

<a id="plugins"></a>

# 插件

插件可以在不修改 pokeldn 的情况下添加工具、游戏和无线通信后端，也可加入或主持自己的 LDN 网络。插件由 Python 文件和 `plugin.toml` 组成，以单个 `.pokeplugin` 文件分发，用户可在应用的“插件”页面添加。本项目不分发、审核第三方插件，也不提供插件支持。

代码：`pokeldn/plugins.py`（加载器和 API）、`pokeldn/app/plugin_store.py`（插件包）、`pokeldn/ldn/radios.py`（无线通信后端查询）、`gui/views/plugins.py`（页面）。

可以从两个示例开始：`examples/plugins/hello` 是最小插件，以两个文件提供一个工具；`examples/plugins/test_kit` 使用了 API 的所有部分。

<a id="installing-a-plugin"></a>

## 安装插件

1. 打开侧边菜单底部的“插件”。
2. 在“浏览”中点击已关注来源所列插件的“安装”；也可在“已安装”页拖入 `.pokeplugin` 文件，或点击“添加插件”选择文件。
3. 阅读插件内容和风险，勾选确认项，再点击“安装”。

插件工具立即显示在游戏页，带插头图标和“来自插件…”标注。各插件卡片提供启用开关和菜单，可打开工具、从新文件更新、查看文件夹、访问页面及移除。每次安装或更新都重新显示风险说明。手动复制到插件目录的插件显示“手动添加”，首次启用时也需确认相同说明。

如果插件在启动时使应用关闭或无响应，应用下次启动会停用该插件并显示其名称。移除插件时会询问是否一并删除插件保存的数据。

插件在 pokeldn 内以 Python 运行，与应用具有相同的文件、密钥、网络和开发板访问权限。插件包安装并启用之前，其中的代码不会运行。

<a id="sources"></a>

### 来源

来源是他人发布的 JSON 插件列表。“插件”页的“来源”标签用于关注来源；“浏览”列出其中的全部插件，提供“安装”“更新到 N”“已安装”和移除按钮。应用默认关注 `Decryptu/pokeldn-decrypt-plugins`，此内置来源无法移除。移除其他来源不会移除已经从中安装的插件。

| 在“来源”中输入 | 读取的列表 |
|---|---|
| `OWNER/REPO` 或 `https://github.com/OWNER/REPO` | `https://raw.githubusercontent.com/OWNER/REPO/HEAD/pokeldn-source.json` |
| 以 `.json` 结尾的 HTTPS 地址 | 该文件 |
| 其他 HTTPS 地址 | 对应文件夹中的 `pokeldn-source.json` |

```json
{
  "schema": 1,
  "name": "My plugins",
  "homepage": "https://github.com/me/my-plugins",
  "plugins": [
    {"id": "my-plugin", "name": "My plugin", "version": "1.0.0", "api": "1.6",
     "description": "...", "author": "me",
     "download": "https://github.com/me/my-plugins/releases/download/my-plugin-1.0.0/my-plugin-1.0.0.pokeplugin",
     "sha256": "64 hex digits", "size": 46302,
     "icon": "https://.../icon.png", "homepage": "https://..."}
  ]
}
```

必须提供 `id`、`version`、HTTPS `download` 和包的 `sha256`；缺少其中一项或 ID 重复的条目会被忽略。其他 `schema` 版本的列表会被拒绝。下载文件的 SHA-256 与列表不同，会在读取前被拒绝；插件包 ID 与条目不同，会在显示风险确认页前被拒绝。列表不能证明作者身份：风险提示和签名检查与从文件安装时相同。

应用启动时（“设置 → 更新”已启用）和页面刷新时读取全部已关注来源，将最近一次列表缓存到 `plugins/.source-cache/`，来源不响应时显示缓存。关注列表保存在 `plugins/.sources.json`。已安装插件会记录来源，并从该来源获取更新；从文件安装的插件先从首个列出它的来源获取更新，再尝试自身的 `updates` 地址。

`scripts/plugin_source.py` 以与应用相同的方式读取插件包并生成列表：

```bash
python scripts/plugin_source.py my-plugin-1.0.0.pokeplugin -o pokeldn-source.json --name "My plugins" \
    --download "https://github.com/me/my-plugins/releases/download/{id}-{version}/{file}"
```

已列出的更高版本条目会保留。

<a id="guardrails"></a>

### 防护机制

两项检查用于阻止明显有害的操作。它们都不是沙箱，恶意编写的插件可能绕过限制。

安装页面会读取插件包的 Python 文件，列出网络访问、启动其他程序、删除文件、调用原生代码（`ctypes`、`cffi`）、执行运行时生成的代码（`exec`、`eval`、`compile`、`marshal`）、引用 `prod.keys`，以及附带扫描无法读取的编译文件等行为。列表为空只表示没有发现这些行为，不能证明插件安全。

在应用以及每次运行中，只要调用栈上存在插件代码，审计钩子（`pokeldn/plugin_guard.py`）就会对以下操作抛出 `PermissionError`：

| 拒绝 | 允许 |
|---|---|
| 删除、清空、移动或覆盖插件文件夹以外的文件 | 在插件自身文件夹、数据文件夹、资料库、会话文件夹、日志文件夹和临时文件夹内进行这些操作 |
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
library = "My files"        # optional (1.7): a folder the player sees, see A library
library_sort = "name"       # optional (1.8): its order until the player picks one, see A library
module = "plugin"           # optional; the module holding register()
exclude = ["tests"]         # optional; folders and files pack_plugin.py leaves out of the package
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
| 打印一行 | 显示在会话输出中 |
| 打印 `[done] trade N complete`（`pokeldn.ldn.show_done()`） | 标记一次队列交换完成 |
| 返回代码 0 | 会话结束并标为完成 |
| 返回其他代码或抛出异常 | 会话失败，输出中显示堆栈 |
| 收到 `KeyboardInterrupt` | 玩家按了停止；应在 15 秒内退出，否则进程被结束 |
| 打开弹窗（`pokeldn.popup`，1.2） | 覆盖当前页面显示，返回玩家回答 |
| 请求从多个选项中选择（`pokeldn.popup.choose`，1.7） | 每个选项显示一个按钮，返回所选索引 |
| 报告进度（`pokeldn.progress.show(done, total, title, unit)`，1.7） | 在会话面板中以进度条代替日志行，显示速率与剩余时间（[进度](gui.md#progress)） |
| 显示状态卡片或标注资料库文件（`pokeldn.panel`，1.8） | 显示在工具页，任务结束后保留（[状态卡片](#status-cards-18)） |

弹窗不会等待玩家：`acknowledge` 和 `confirm` 立即返回 ID，回答通过稍后的回调到达，可能随时在另一线程触发。脚本应保留自身状态，在回答到达时处理，并继续原有工作：

```python
import queue
from pokeldn import popup

answers = queue.Queue()
popup.set_dispatcher(answers.put)       # callbacks wait for the loop below instead of running on their own thread
asked = popup.confirm("Trade the shiny?", "Your partner offers a shiny Gholdengo.", "Trade", "Skip",
                      on_agree=lambda: print("trading"), on_disagree=lambda: print("skipping"),
                      tone="warning")
while not finished():                   # the script's own work goes on meanwhile
    try:
        answers.get(timeout=0.5)()
    except queue.Empty:
        pass
popup.cancel(asked)                     # no use for the answer any more: the pop-up closes, no callback fires
```

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

<a id="a-library-17"></a>

### 资料库（1.7）

插件可在 `plugin.toml` 中指定由玩家管理的文件目录，例如备份和下载文件：`library = "My files"` 对应 `Documents/pokeldn/My files`（设置 `POKELDN_DATA` 时为数据目录下的 `My files`）。在 `register` 中使用 `api.library`，或在工具脚本中调用 `pokeldn.plugins.library_folder("my-plugin")`，可获取该目录，首次使用时创建。

| 资料库 | 行为 |
|---|---|
| 防护机制 | 与数据目录一样，允许在其中写入、替换、重命名和删除 |
| 安装页 | 显示目录名称 |
| 移除插件 | 保留目录及其中全部文件 |
| 游戏页 | 在插件工具下列出文件；玩家可通过按钮或拖放添加文件，也可重命名、删除。以 `.` 开头和以 `.part` 结尾的文件不会显示：可先写入这类临时文件，再以完整文件替换 |
| 排序 | 可按名称、日期、大小升序或降序排列，并为每个插件保存选择。未选择时使用 `plugin.toml` 的 `library_sort`（1.8：`name`、`name-desc`、`date`、`date-desc`、`size`、`size-desc`），否则默认 `date-desc`，最新在前。名称采用自然排序，数字串按数值比较且忽略大小写，因此 `v65536` 在 `v131072` 前，`20.5.0` 在 `23.0.1` 前 |
| 文件标注 | `pokeldn.panel.annotate`（1.8，[状态卡片](#status-cards-18)） |
| 目录名 | 最多 40 个字母、数字、空格、点、连字符或下划线；拒绝 pokeldn 自用目录（`Bank`、`Saves`、`Received` 等）、Windows 设备名及其他已加载插件的资料库名称 |

`help=` 在输入框下显示说明，`default=` 填充默认值，`hidden=True` 将其移到高级页。内置工具的字段及 `Field` 其他选项见 `pokeldn/app/catalog.py`。工具的 `fixed` 参数可包含 `{ot}`、`{tid}`、`{sid}`、`{language}`、`{gender}`（设置中的训练家）、`{received}`（已接收文件夹）、`{stamp}`（启动时间）以及 1.7 新增的 `{keys}`（设置中指定的 `prod.keys` 文件）。脚本解析器接收 `--keys` 时，即使不使用此占位符，也会收到该文件路径。 API 1.5 新增 `Field.identity`，为标签会被翻译的位置参数提供稳定的设置键值。

<a id="status-cards-18"></a>

### 状态卡片（1.8）

任务可在工具页顶部、输入字段上方留下卡片，也可标注资料库文件。`pokeldn.panel` 将其打印为 `[panel]` 行，因此源码运行和发行版行为相同；应用将其保存在数据目录的 `plugin-panels/<id>.json` 中，任务结束后保留，移除插件时删除。在应用外只打印该行。

```python
from pokeldn import panel, plugins

icon = plugins.data_folder("my-plugin") / "icons" / "0100abcd.png"
panel.show("console", "Pokémon: Let's Go, Pikachu!", [
    "Group\tcapito27's Switch · 1 of 8 consoles",
    "System version\t23.0.1",
], image=icon, chips=[("Version", "1.0.2")], tone="ok")
panel.annotate("Game 1.0.2.nsp", state="ok", text="Every signature checks", image=icon)
```

| 调用 | 应用显示 |
|---|---|
| `panel.show(id, title, lines=(), *, image=None, chips=(), tone="info")` | 显示卡片 `id`，替换同 ID 的上一张卡片。每行可以是普通文本，也可用 `label<TAB>value` 显示两列；标签为 `(label, value)` 对；`tone` 可为 `info`、`ok`、`warning`、`error`，决定标题旁图标 |
| `panel.clear(id)` | 移除卡片 |
| `panel.annotate(name, *, state="ok", text="", image=None)` | 标注资料库文件 `name`：状态可为 `ok`、`bad`、`checking`，下方显示一行文字，并以图片替换文件图标 |
| `panel.unannotate(name)` | 移除标注 |

| 限制 | |
|---|---|
| 卡片 ID | 1 至 32 个小写字母、数字、`-` 和 `_` |
| 每个插件的卡片数 | 8；超过后忽略新 ID |
| 每张卡片 | 标题最多 80 字符、最多 12 行且每行 200 字符、最多 6 个标签且每侧 40 字符 |
| 图片 | 插件数据目录或资料库中的 PNG/JPEG，最大 2 MB；其他图片不显示 |
| 文件标注 | 与文件名关联；重命名或删除文件会移除标注 |

超出限制时脚本抛出 ValueError；应用无法读取的 `[panel]` 行会显示在会话输出中。

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

<a id="ldn-networks-17"></a>

### LDN 网络（1.7）

`pokeldn.ldn.network` 为插件加入或主持 LDN 网络，并提供无线后端的 IPv4 协议栈。它需要没有内核接口的无线后端：ESP32 开发板或 ldnrs。

```python
from pokeldn.ldn import network

with network.join(COMM_ID, keys=args.keys, password=PASSPHRASE, name="My game") as net:
    net.add_protocol(6, lambda src, dst, segment: segments.put((src, segment)))   # TCP, say
    while not net.send_ip(6, net.host_ip, first_segment):    # False until ARP finds the host
        time.sleep(0.1)
```

| 名称 | 含义 |
|---|---|
| `join(comm_id, *, keys, password, nickname, app_version, name, log, timeout)` | 扫描并仅加入广播 `comm_id` 的网络；`name` 用于显示给玩家的消息。没有响应时抛出 `RuntimeError` |
| `host(comm_id, *, keys, password, nickname, application_data, scene_id, app_version, max_participants, channel, protocol, log, timeout)` | 创建供游戏机加入的网络 |
| `Network.ip`, `.mac`, `.host_ip`, `.broadcast`, `.ssid`, `.comm_id`, `.application_data` | 地址与广播数据：加入时来自主持端，主持时为本机 |
| `Network.participants` | 主持网络中已就座的站点，各有 `.index`、`.ip`、`.mac`、`.name` |
| `Network.add_protocol(number, handler)`, `.remove_protocol(number)` | 在无线事件循环中将发往本机、已重组且协议号为 `number` 的 IPv4 包交给 `handler(src_ip, dst_ip, payload)`；应入队后立即返回。UDP（17）仍由协议栈处理。处理函数异常会记入日志并丢弃数据包 |
| `Network.send_ip(protocol, dst_ip, payload)` | 发送一个 IPv4 包，按 1500 字节分片；`dst_ip` 的地址未知时发送 ARP 请求并返回 `False` |
| `Network.udp_socket(port)` | 网络上的 UDP 套接字：`sendto`、`recvfrom`、`setblocking`、`settimeout`、`fileno`、`close` |
| `Network.set_application_data(data)` | 更新所主持网络的广播数据 |
| `Network.error`, `.close()` | 网络结束原因（运行时为空）；退出网络。`Network` 可用作上下文管理器 |
| `pokeldn.ldn.radio_lost()` | 无线后端退出进程的原因，或空字符串。任务会收到与玩家点击“停止”相同的 `KeyboardInterrupt`，此值可区分两者 |

通过开发板传输约为 0.5 MB/s；可用 `pokeldn.progress.show` 报告进度。

<a id="a-battle-server"></a>

### 对战服务器

对战服务器为主持启动器运行团体战，使游戏机与程序的宝可梦参与同一场对战（[提供对战服务](sv_raid.md#serving-the-battle)）。目前只有《朱／紫》（`"sv"`）支持。通过 `api.add_battle_server(game, name, factory, label)` 注册；运行 `bin/sv_host.py --raid-serve NAME`（仅指定 `--raid-serve` 时使用首个已加载服务器），在游戏机发来对战引导数据后，于网络事件循环之外调用 `factory(bootstrap, partners)`。`bootstrap` 为引导数据字节，`partners` 为两位 NPC 搭档各 0x158 字节的队伍记录。返回对象应提供：

| 成员 | 行为 |
|---|---|
| `start(now)` | 在 `now` 秒运行首帧，返回推动对战的帧数 |
| `run(until)` | 按每秒 30 帧运行到 `until` 秒（至少一帧），返回推动对战的帧数 |
| `t` | 服务器时钟，单位为秒 |
| `receive(slot, message)` | 从对战槽位 `slot` 接收站点消息，由 32 字节头部和正文组成 |
| `sent(slot)` | 自上次调用以来排队发往 `slot` 的消息，每条由 32 字节头部和正文组成 |

槽位 0 为程序宝可梦，1 为首领，2 为游戏机，3、4 为搭档。任一成员抛出异常会停止提供服务，游戏机随后自行运行对战。

```python
def register(api):
    api.add_battle_server("sv", "mine", MyServer, "My raid battle")
```

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

打包时会忽略隐藏文件，以及 `plugin.toml` 中由 `exclude = ["tests", "tools"]` 指定的目录。

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

<a id="language-packs-15"></a>

## 语言包（1.5）

语言包是只含数据的文件夹插件。`name` 是“设置 → 应用语言”中显示的名称，`locale` 是语言标签，保存的选择以插件 `id` 标识。

```toml
id = "community-zh-hans"
name = "简体中文"
version = "1.0.0"
api = "1.5"
locale = "zh-Hans"
strings = "strings.toml"
```

`strings.toml` 与 `plugin.toml` 位于同一目录。带点的键名必须加引号，以便 TOML 将其读为扁平表：

```toml
"bank.bank_676c47" = "宝可梦银行"
```

文件只含文本值，无需 Python 模块或 `register` 函数。安装、签名、作者密钥、移除及 `updates` 与其他插件使用同一套处理流程。无效 TOML、非文本值及无效格式语法会在安装前被拒绝；已安装语言包损坏时，显示加载错误并回退到英语。

在“插件”页面安装语言包，然后在“设置 → 应用语言”中选择并重启 pokeldn。选择语言包会启用对应插件，英语始终可选。语言包缺失、禁用或被移除时使用英语；本中文版还提供内置简体中文。训练家语言仍单独决定生成宝可梦的语言。

每次查找都有内联英语默认值。缺失键值使用默认文本，未使用的键值没有影响。`{value0}` 等具名占位符可在翻译中调整位置，但必须保留名称、转换标志及格式说明；`{{` 和 `}}` 表示字面量大括号。占位符无法格式化时，该次查找回退到英语默认值。

```bash
python scripts/extract_strings.py
python scripts/extract_strings.py --check
python scripts/pack_plugin.py examples/plugins/pseudo -o pseudo.pokeplugin
```

提取器按键名排序写入 `pokeldn/app/data/strings.en.toml`。测试检查模板与源码一致，并拒绝同一键出现两种英语默认值。文字改动时键名保持不变。可将模板复制到独立插件仓库并翻译其值，省略的键无需维护。`examples/plugins/pseudo` 中的部分伪语言用方括号包围部分字符串，其余用于验证回退。示例不包含在桌面包中。

查找范围包括桌面控件、对话框、本地错误、工具目录的标签与帮助，以及游戏机操作说明。参考 Markdown、PKHeX 和游戏模块提供的数据、第三方插件文字及上游异常信息保留其来源语言；本中文版另外维护中文文档与 PKHeX 中文数据展示。会话日志、无线脚本输出及 `[done]` 协议行保持原文本。

## Plugin Test Kit

使用 `scripts/pack_plugin.py` 打包的 `examples/plugins/test_kit` 提供：

| 位置 | 工具 | 行为 |
|---|---|---|
| Plugin Test Kit | Self-test | 检查 API 版本、自身加载、导入、各类字段、训练家占位符、会话目录、数据目录（更新后保留的运行计数器）、资料库及文件标注、无线后端；逐项输出 PASS 或 FAIL，并在工具页留下最近自检状态卡片 |
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
| 1.1 | `api.data`、`api.level`、`pokeldn.plugins.data_folder(plugin_id)` |
| 1.2 | `pokeldn.popup` |
| 1.3 | 程序接口：生成器、礼物文件、PKHeX 和开发板 |
| 1.4 | 银行导入、记录、目的地、提供记录和交换完成处理 |
| 1.5 | 语言包插件和字符串查找 |
| 1.6 | `add_battle_server` |
| 1.7 | `pokeldn.ldn.network`、`pokeldn.ldn.radio_lost`、`library` 和 `api.library`、`pokeldn.popup.choose`、`pokeldn.progress`、`{keys}` 占位符 |
| 1.8 | `pokeldn.panel`、`library_sort` |

<a id="the-api-version-1"></a>

## API，版本 1

| 名称 | 含义 |
|---|---|
| `api.add_tool(game, tool)` | 在键为 `game` 的游戏下添加 `Tool`：`frlg`、`lgpe`、`swsh`、`bdsp`、`pla`、`sv`、`za` 或插件添加的游戏 |
| `api.add_game(game, icon="")` | 添加游戏分组及工具 |
| `api.add_radio(scheme, install, label="")` | 添加无线适配器 |
| `api.add_battle_server(game, name, factory, label="")` | 添加团体战服务器（1.6） |
| `api.folder` | 插件文件夹（`Path`），Python 包则为 None |
| `api.version`、`api.level` | 当前 API 主版本和级别，`1` 和 `8` |
| `api.data` | 更新时保留的目录，首次使用时创建（1.1） |
| `pokeldn.plugins.data_folder(plugin_id)` | 从工具脚本访问同一目录（1.1） |
| `api.library`, `pokeldn.plugins.library_folder(plugin_id)` | 玩家可见的 `plugin.toml` 的 `library` 目录，首次使用时创建（1.7，[资料库](#a-library-17)） |
| `Tool`、`Field`、`Game` | 应用目录类型，从 `pokeldn.plugins` 导入 |
| `pokeldn.ldn.show_done()` | 打印标记一次交换完成的行 |
| `pokeldn.popup.acknowledge(title, text="", *, id, label="OK", on_ack, tone)` | 单按钮弹窗，返回 ID（1.2，[弹窗](gui.md#pop-ups)） |
| `pokeldn.popup.confirm(title, text, agree, disagree, *, id, on_agree, on_disagree, on_dismiss, tone)` | 使用调用方指定的同意、不同意按钮；Esc 或点击外部关闭，返回 ID（1.2） |
| `pokeldn.popup.choose(title, text, options, *, id, on_choice, on_dismiss, tone)` | 提供 2 至 8 个选项按钮；`on_choice(index)` 接收所选索引，Esc 或点击外部触发 `on_dismiss`；返回 ID（1.7） |
| `pokeldn.progress.show(done, total, title, unit="bytes")` | 会话面板中的进度条；`unit` 为 `bytes` 或 `items`（1.7） |
| `pokeldn.panel.show(id, title, lines=(), *, image, chips, tone)`, `clear(id)`, `annotate(name, *, state, text, image)`, `unannotate(name)` | 工具页状态卡片及资料库文件标注（1.8，[状态卡片](#status-cards-18)） |
| `pokeldn.ldn.network` | 通过 IPv4 协议栈加入或主持 LDN 网络（1.7，[LDN 网络](#ldn-networks-17)） |
| `pokeldn.ldn.radio_lost()` | 无线后端退出任务的原因，或空字符串（1.7） |
| `pokeldn.popup.cancel(id)`、`available()`、`set_dispatcher(dispatch)` | 关闭弹窗并移除回调；判断应用是否显示弹窗；指定回调执行位置（1.2） |

本表及下表列出的接口受兼容性保证。插件从 pokeldn 导入的其他内容可能在任何版本改变。

<a id="the-program-surface-13"></a>

<a id="the-program-surface-13-bank-added-in-14"></a>

## 程序接口（1.3，银行功能于 1.4 加入，语言包于 1.5 加入）

插件或基于 pokeldn 源码的独立程序（触摸屏前端、脚本）可使用与应用相同的代码生成礼物和宝可梦、管理开发板。API 主版本 1 内，这些名称保持含义不变；`tests/test_plugin_surface.py` 逐项验证解析。

| 名称 | 含义 |
|---|---|
| `python -m pokeldn --list`、`python -m pokeldn TOOL -- ARGS` | 列出工具键值，或使用设置中的训练家和 `--` 后参数运行工具 |
| `pokeldn.app.i18n.t(key, default, **fmt)`、`select(plugin_id)` | 使用内联英语默认值及具名格式参数查找字符串；按插件 ID 选择启用的语言包，空 ID 选择英语（1.5） |
| `pokeldn.app.catalog.GAMES` | 内置游戏，每个 `Game` 的 `.tools` 保存 `Tool`：`bin/` 下脚本及字段；应用传入的参数名保持不变 |
| `pokeldn.pokemon.SERVICE.species(game)`、`.names(game, kind)` | 游戏种类及 `moves`、`items`、`bag`、`held`、`balls`，以 `{"id", "name"}` 列表返回 |
| `pokeldn.pokemon.SERVICE.options(game, species, trainer)` | 对应种类可以使用的形态、性格、特性、道具和精灵球 |
| `pokeldn.pokemon.SERVICE.make(game, species, trainer, level, shiny, nickname, version, options)` | 生成对应游戏的合法宝可梦；`options` 接受性格、特性、性别、携带道具、精灵球、亲密度、招式、个体值和努力值；返回各字段及写入路径 `"file"` |
| `pokeldn.pokemon.SERVICE.paste(game, text, trainer)` | 解析 `text` 中的 Showdown 配置，各条返回 `make` 的字段及 `errors` |
| `pokeldn.pokemon.BuilderError` | PKHeX 拒绝或缺失时抛出，包含面向玩家的说明 |
| `pokeldn.pokemon.NATURES` | 按记录索引排列的 25 种性格名称 |
| `pokeldn.gifts.load(path, game=)`、`pokeldn.gifts.save(path, gift)` | 读写 `.pokegift`、`.wc3`、`.wc8`（[神秘礼物文件](gifts.md)） |
| `pokeldn.swsh.gift_builder.KINDS`、`PRESETS`、`PRESET`、`OUTFITS` | 剑／盾生成器的礼物类型 `(key, label, icon)`、预设（`.key`、`.label`、`.group`、`.summary`、`.state`）及服装 |
| `pokeldn.swsh.gift_builder.blank(**changes)`、`record(state)`、`compile(state)`、`describe(state, name)` | 表单状态、封装的 720 字节记录、供 `gifts.save` 使用的礼物及面向玩家的说明；无效状态抛出 `ValueError` 并指出字段。宝可梦状态接受 `nature`（0 至 24，省略则由游戏随机生成） |
| `pokeldn.swsh.events.load()`、`by_key()`、`gift(key)` | 剑／盾官方活动卡片及单张卡片的礼物 |
| `pokeldn.frlg.gift.builder.KINDS`、`PRESETS`、`PRESET`、`GIVERS`、`CARTRIDGES` | 火红／叶绿生成器的类型、预设、发放卡片角色及游戏机代码支持的卡带 |
| `pokeldn.frlg.gift.builder.blank()`、`compile(state)`、`describe(state, name)` | 神奇卡片、神奇新闻及游戏机代码对应的同类接口 |
| `gui.board.ports()`、`identify(port, blink=)`、`detect_chip(port)` | 串口及开发板运行内容：`.firmware`、`.firmware_version`、`.protocol`、`.current`（协议与当前 pokeldn 相同） |
| `gui.board.download_firmware(say=)`、`image_for(kind, chip)`、`image_version(path)`、`flash(port, kind=)` | 按 SHA-256 核验发布镜像、为芯片选择镜像、读取版本及检查芯片后刷写 |
| `pokeldn.app.bank.library()` | 默认银行目录，返回 `Path`；列出记录不会创建目录（1.4） |
| `pokeldn.app.bank.Entry`、`Imported`、`ImportedPokemon` | 下文说明的银行结果类型（1.4） |
| `pokeldn.app.bank.Imported.count(state)` | 指定状态的导入结果数量（1.4） |
| `pokeldn.app.bank.entries(folder=)`、`find(entry_id, folder=)`、`data(entry)` | 按时间从新到旧列出记录、查找记录或返回 `None`、读取原生字节（1.4） |
| `pokeldn.app.bank.import_file(path, trainers, folder=)` | 导入宝可梦文件或存档，不修改源文件，返回 `Imported`（1.4） |
| `pokeldn.app.bank.deposit(game, source, info, folder=)` | 存入接收文件副本及 PKHeX 检查结果，返回 `Entry`；已存入相同字节时返回 `None`（1.4） |
| `pokeldn.pokemon.SERVICE.check(game, path)` | 用 PKHeX 检查原生接收记录，返回供 `bank.deposit` 使用的 `info` 字典，包含合法性结论（1.4） |
| `pokeldn.app.bank.destinations(entry, trainer)`、`offer(entry, game, trainer)` | 各游戏转换可用性，以及转换到指定游戏的提供记录（1.4） |
| `pokeldn.app.bank.edit(entry, fields)`、`remove(entry_id, folder=)` | 修改昵称、提升等级、招式或携带道具，返回更新后的 `Entry`；明确删除记录及元数据（1.4） |
| `pokeldn.app.bank.TradeSession(offers, folder=)` | 保存单次任务按顺序排列的提供字典快照，包含没有银行 ID 的记录（1.4） |
| `pokeldn.app.bank.TradeSession.advance(count)` | 应用已确认的累计交换数，返回已处理最大计数 `.completed`；重复或更旧计数不改变记录（1.4） |
| `pokeldn.app.received.trades_done(line)` | 解析启动器 `[done] trade N complete` 中的累计计数，或返回 `None`（1.4） |

从应用或 `python -m pokeldn` 启动的任务各为独立进程：向该 PID 发送 SIGINT，15 秒后仍未退出再发 SIGTERM。不要按名称匹配启动器（`pkill -f`），否则会结束其他程序启动的任务。

<a id="bank-integrations-14"></a>

## 银行集成（1.4）

其他 Python 前端使用与桌面银行相同的 `pokeldn.app.bank` 模块，自行管理提供队列和进程生命周期。应用设置、队列辅助函数及银行元数据文件仍属内部实现。转换使用现有 PKHeX 辅助程序，源码安装通过 `dotnet build -c Release services/pkhex` 构建。

`Entry` 提供 `id`、`path`、`game`、`species_id`、`shiny`、`summary`、`legal`、`tracker`、`created`、`origin`、`home_tracker`。`game` 是游戏目录键值，`created` 是 Unix 秒数，`path` 指向原生记录。`home_tracker` 为 `empty`、`made` 或空字符串，见 [HOME 追踪码设置](gui.md#the-home-tracker-setting)。

`Imported` 提供 `name`、`save`、`pokemon` 和 `count(state)`。每个 `ImportedPokemon` 提供 `where`、`species`、`species_id`、`shiny`、`state`、`game`、`detail`，状态为 `banked`、`already` 或 `refused`。拒绝按记录判断，一只宝可梦失败不会阻止同一存档其他记录导入。`trainers` 将游戏键值映射到与生成器相同的训练家字典：`ot`、`tid`、`sid`、`language`、`gender`。导入会记住已导入记录，包括后来交换离开的记录。

`destinations` 返回按游戏键值索引的字典，各项包含 `ok`、`reason`、`home_tracker`。`offer` 返回 `file`、`summary`、`species`、`shiny`、`legal`、`encounter`、`moves`、`report`、`home_tracker`、`bank`。`file` 为准备好的原生记录路径，`bank` 为来源条目 ID。准备提供不会移除银行原记录；保留提供文件直到任务结束，通过启动器 `--offer-file` 传入。银行记录不使用 `--fresh-pid`，以保留身份。桌面命令构建器自动处理；`python -m pokeldn TOOL` 只组装默认值，不接收银行提供字典，因此其他前端直接运行目录工具对应的脚本。

```python
from pokeldn.app import bank, received

trainer = {"ot": "ASH", "tid": 1111, "sid": 2222, "language": 2, "gender": 0}
games = ("frlg", "lgpe", "swsh", "bdsp", "pla", "sv", "za")
result = bank.import_file("main", {game: trainer for game in games}, folder="tradebox-bank")
entry = next(iter(bank.entries(folder="tradebox-bank")), None)
if entry is None:
    raise ValueError("No Pokemon available in the Bank.")
routes = bank.destinations(entry, trainer)
if not routes["swsh"]["ok"]:
    raise ValueError(routes["swsh"]["reason"])
offer = bank.offer(entry, "swsh", trainer)
session = bank.TradeSession([offer], folder="tradebox-bank")

def on_launcher_line(line):
    count = received.trades_done(line)
    if count is not None:
        session.advance(count)
```

每次任务按精确提供顺序创建一个 `TradeSession`，也包含没有 `bank` 键值的生成记录。只传入已确认的完成计数，不使用进程退出码或队列数量。失败或停止时，未完成记录留在银行。累计计数可跳过中间消息；超出快照数量的继续交换仅计数，不移除额外记录。`advance` 以 `ValueError` 拒绝负数及非整数。每次成功移除后更新进度，遇到 `OSError` 可用相同计数重试。

文件访问错误抛出 `OSError`；PKHeX 失败及拒绝转换或修改时抛出 `pokeldn.pokemon.BuilderError`。`deposit` 使用 `pokeldn.pokemon.SERVICE.check` 的检查结果，不额外检查合法性；用户提供的存档和宝可梦文件通过 `import_file` 导入。带 `folder` 的方法接受路径，默认使用 `library()`。`data`、`edit`、`destinations`、`offer` 使用 `Entry` 内的路径。导入 pokeldn 前设置 `POKELDN_DATA`，也可隔离辅助程序输出及前端其他应用文件。

银行操作同步执行，PKHeX 工作应放在前端 UI 线程之外。同一银行目录同时只允许一个写入者，不支持不同应用并发导入、修改和交换。桌面应用运行时，TradeBox 应使用独立目录。其他前端自行移除队列中已完成的提供记录，`TradeSession` 仅修改银行。
