---
title: Desktop builds
---
# 桌面应用

发行版包含 PKHeX，以及 ESP32、ESP32-S3、ESP32-C3 和 ESP32-C6 的合并固件。用户须提供自己的 `prod.keys`。

打开应用，在“设置”中选择 `prod.keys`。在“开发板”页选择通过 USB 连接的开发板并刷写固件。选择游戏和工具，生成宝可梦或选择文件，然后按照游戏机上的操作步骤点击“开始”。接收到的宝可梦保存在“设置”中选择的文件夹，点击“输出”旁的文件夹按钮可打开。刷写时会检测芯片并选择对应的内置固件；写入自定义固件前也会检查芯片是否匹配。S3、C3 和 C6 请使用原生 USB Serial/JTAG 接口；不支持 S2。

神秘礼物工具共用礼物制作界面：可以选择预设、自行制作或打开 `.pokegift` 文件；剑／盾还支持 `.wc8` 卡片。无需连接开发板，点击“保存礼物文件”即可导出 `.pokegift`，也可根据扩展名导出火红／叶绿的 `.wc3` 或剑／盾的 `.wc8`。[神秘礼物文件](gifts.md#desktop-app)介绍了表单、卡带版本及原生格式转换。

## 你的训练家

“设置”中的训练家是应用生成的每只宝可梦的初训家，包括名称、语言和两组 ID。请按游戏显示的数值填写。记录实际保存一个 16 位 TID 和一个 16 位 SID，分别组成 32 位 ID 的低半部和高半部。

| 游戏 | 显示的 ID | 里 ID | 保存的 ID |
|---|---|---|---|
| 火红、叶绿 | TID，0 至 65535 | SID，0 至 65535 | `SID << 16 \| TID` |
| Let's Go!、剑／盾、晶灿钻石／明亮珍珠、传说 阿尔宙斯、朱／紫、传说 Z-A | ID 对 10^6 取余，六位数字 | ID 除以 10^6 的整数商，0 至 4294 | `secret * 10^6 + ID`，须小于 2^32 |

Switch 游戏的 ID 对由 `pokeldn/app/settings.py` 中的 `Settings.ids` 按各游戏转换。旧设置没有单独的 Switch ID 对时，会根据第一组 ID 推导，确保生成记录保存的实际 ID 一致。

所有连接游戏机的工具都会使用此训练家作为本机玩家，替换参考消息中的名称（`tests/test_gui_catalog.py`）。火红／叶绿、Let's Go!、剑／盾和晶灿钻石／明亮珍珠的启动器会将 ID 写入相应记录。火红和叶绿名称最多七个第三世代字符，过长会截断为七个；名称含不受支持的字符时改用 `POKELDN`（`Settings.name`）。

## Linux 串口

该应用程序以用户身份打开开发板，无需 root 也无需内核网络。打开端口需要`dialout`组（Arch上为`uucp`）；用户可能无法打开的端口会失败并显示 `EACCES`，然后 Board 页面会命名该组而不是繁忙端口。

|服务 |董事会|效果|
|---|---|---|
| brltty 6.4（Ubuntu 22.04）| CH340 `1a86:7523` |由 `85-brltty.rules` 声称；安装 brltty 时不会出现 `/dev/ttyUSB*` ([LP 1990357](https://bugs.launchpad.net/bugs/1990357))。修复：`sudo apt remove brltty` |
| brltty 6.6（Ubuntu 24.04）| CP210x `10c4:ea60`，CH340 | CP210x 规则已注释掉（[LP 1958224](https://bugs.launchpad.net/bugs/1958224)）； CH340声称仅在`1a40:0101`集线器后面|
|调制解调器管理器 1.23 (Ubuntu 24.04) |全部 | `10c4`、`1a86` 或 `303a` 没有忽略规则；其严格过滤器仅通过接口协议 1 至 6 的 `cdc_acm` 端口 (`mm-filter.c`) |

由于 Linux 上没有列出串行端口，主板页面显示为 `/sys/bus/usb/devices` 并命名了一个已知的桥接器，该桥接器的接口下没有 tty，并针对 CH340 进行了 brltty 修复 (`gui/board.py` `bridges_without_port`)。
## 本地存储

设置、存储显示可回收本地文件占用的空间。清除本地文件要求确认，删除检查中的文件并报告释放了多少空间。在清除之前保存错误报告所需的记录。

清理包括应用程序的 `session/` 工作文件（捕获、串行跟踪、临时提议和会话元数据）、`logs/` 以及 `pokemon/` 中未使用的生成或导入的提议。保留不到一分钟的已构建提议，因此仍在完成的构建可以保存其选择。保留已保存工具设置和队列引用的提议。接收到的文件及其选定的文件夹、开关键、选定的固件和设置都会被保留，包括当它们存储在清理文件夹下时。 即使在“已接收”文件夹发生更改后，宝可梦记录和二进制转储仍会保留在应用程序的命名临时提议之外。生成的提议由构建者的时间戳和随机后缀标识。符号链接被跳过；保留检查后更改的文件。空的子文件夹将被删除。

在清理之前完成所有活动会话、闪存或电路板检查。清理在后台运行，并推迟新的会话和闪烁，直到完成。报告无法删除的文件并可以重试。宝可梦精灵缓存在高级设置下有自己的清除缓存按钮。
## Your saves

> 本节已随上游更新，以下内容暂保留英文。

The FireRed and LeafGreen Mystery Gift tool's Your save tab backs the console's save up, or puts one
back, over the Wonder Cards, Friend path ([Save backup and restore](frlg_gift.md#save-backup-and-restore)).
The saves live in `Documents/pokeldn/Saves` (`pokeldn.app.saves`), one `.sav` each with a `.json`
beside it holding its name, where it came from and the console's game code. Clear local files never
touches the folder; with `POKELDN_DATA` set, the library is `Saves` inside that folder instead.

| action | what happens |
|---|---|
| Back up from the Switch | the launcher writes `backup-<run>.sav` and its `.json`; a backup the link cut short is kept in `Saves/.partial` and the next one goes on from it |
| Put a save on the Switch | the chosen save goes to `--save-restore`; Start stays blocked until one is chosen |
| `+`, or a `.sav` dropped on the card | the file is copied in; a 16-byte emulator footer is dropped, any other size than 128 KB is refused |
| Rename, Export .sav, Delete | the name is cosmetic and kept in the `.json`; Delete removes both files from this computer only |
| View and edit | PKHeX reads the trainer, party and PC boxes; see below |

During a run the Session panel draws the launcher's `[save] backup N of 128 KB` or
`[save] restore N of M sectors` lines as a progress bar, and the list refreshes when the run ends.

A restore is blocked when the save has no whole copy, and when PKHeX finds a party Pokemon not legal,
until Restore anyway is turned on. A save's name defaults to the trainer and the cartridge, which only
a backup knows.

The editor changes the trainer's name, gender, money and coins, and the party: reorder, remove, or add
a Pokemon PKHeX builds for this save's own trainer (name, ID, secret ID and language). Each party
Pokemon shows PKHeX's verdict; Check legality runs it over one box, which takes seconds. Keep as a new
save writes the result through PKHeX, which recomputes every sector checksum, checks that the game's
own sector test passes and adds it to the library as a new entry; the original is unchanged.

## 宝可梦精灵

精灵是 `sprites.front_default` 和 `sprites.front_shiny` 后面的 96x96 PNG
`https://pokeapi.co/api/v2/pokemon/{id}`，读取`raw.githubusercontent.com/PokeAPI/sprites`（`sprites/pokemon/{id}.png`，`sprites/pokemon/shiny/{id}.png`）。未获取 JSON（每个物种 300 KB）；精灵路径由 id 固定。从 1 到 1025 采样的 12 个 National Dex 号码都具有两种精灵； 1026 返回 404。当缺少异色精灵时，将显示正常的精灵。

|哪里 |尺寸|
|---|---|
|当异色开启时，交换选择器，在物种、异色旁边 | 96 px，整个画布 |
|物种场卡片（剑／盾 神秘礼物），工具异色开关打开时异色 | 46 像素瓷砖 |
|会话面板，产品：按交换顺序排列的每个提议，其摘要作为工具提示 | 46 像素瓷砖 |
|会话面板，已收到：运行保存的每个宝可梦文件，由 PKHeX 读取，及其摘要 | 46 像素瓷砖 |

精灵是通过最近邻过滤以 1:1 的比例绘制的，绝不会采用介于两者之间的尺寸。 46 像素图块会在可见像素 (`pokeldn.app.sprites.bounds`) 周围裁剪画布，并在适合 46 像素时以 1:1 的比例绘制它们，否则以 1:2 的比例绘制它们。在采样的 33 个精灵中，可见框的尺寸从 36x29（伊布）到完整的 96 像素宽度（洛奇亚，莱希拉姆）。精灵以 1:2 的比例落在 2 倍显示屏的整个设备像素上。

已接收列表与运行的 `{stamp}` 匹配文件，每个工具的输出路径都包含该文件；启动器添加 `-N` 交换 N (`pokeldn.pokemon.trade_path`) 或写入如此命名的文件夹或前缀。下一秒再次读取仍在增长的文件。该列表包含的是启动器所写的内容：一些启动器会在游戏机选择游戏机的提议时、在交换完成之前写入游戏机的提议。

缓存为应用程序数据文件夹中的 `sprites/`，`normal/` 和 `shiny/` 下每个精灵一个文件。精灵在首次使用时下载，然后从磁盘读取，无需网络访问。规则：

|情况|行为 |
|---|---|
|没有网络，没有缓存| Pixelarticons `circle-question` 图标；没有错误；下一次尝试等待 60 秒 |
| HTTP 404 | HTTP 404 `{id}.none` 标记； 7 天没有再询问 |
|回复不是 PNG，或超过 200 KB |未缓存|
|损坏的缓存文件 |删除了，重新下载|
|数据文件夹不可写|精灵在会话中显示但未保存 |
|设置，宝可梦精灵关闭|缓存已读取，未下载任何内容 |

设置有开关和清空缓存的按钮。 `POKELDN_SPRITE_BASE` 替换精灵主机，用于测试（`tests/test_sprites.py`）。
## 更新

> 本节已随上游更新，以下内容暂保留英文。

At launch the app asks `api.github.com/repos/Decryptu/pokeldn/releases/latest` for the newest stable
release, in the background with a 5 s timeout. A tag above the app's `pokeldn.__version__` adds an
Update entry to the sidebar; it opens the release notes or downloads this computer's archive from the
release (`pokeldn-macos-arm64.zip`, `pokeldn-windows-x64.zip`, `pokeldn-linux-x64.tar.gz`), or the
release page when none fits. The user replaces the app with the download; settings, keys and received
Pokemon live outside it.

| situation | behaviour |
|---|---|
| pre-release or draft, or a tag that is not `vX.Y.Z` | not offered |
| no network, HTTP error, reply that is not a release | nothing shown at launch; Check now says GitHub did not answer |
| Settings, Updates off | no request at launch; Check now still asks |

The request carries no user data. GitHub allows 60 unauthenticated requests per hour per address.
`POKELDN_UPDATE_URL` replaces the endpoint, for tests (`tests/test_app_update.py`).

## 文件掉落

从桌面拖动的文件落在这些目标上：

|目标|需要|
|---|---|
|交换的宝可梦提供|一个宝可梦文件（导入为或使用宝可梦文件）或一个 `.txt` 的 Showdown 集（读取为导入粘贴）；更多文件转到以下行业 |
|添加交换 |每个文件一个新的交换，首先填充最后未触及的交易，直到会话限制|
|神秘礼物工具的礼品卡| `.pokegift`、或`.wc8`（剑／盾）或`.wc3`（火红／叶绿）卡；它切换到打开文件 |
|刷新固件 | `.bin`，用作自定义图像 |
|任何路径字段，欢迎对话框|该字段要求的文件；文件夹字段采用拖放文件的文件夹 |

Flet 1.0.2 的桌面客户端不会发生文件丢失。 `scripts/build_client.py` 在已安装的版本中检查 Flet 的源代码，将 `gui/flet_drop` （围绕 [desktop_drop](https://pub.dev/packages/desktop_drop) 的 Flet 扩展）添加到其客户端，并将其构建到
`gui/client/<platform>`。 `gui/drop.py` 声明匹配的 `FileDrop` 控件。 `gui/main.py` 在构建时运行该客户端，否则运行 Flet 自己的客户端，其中不显示目标；冻结的应用程序总是带有构建的应用程序。该脚本需要Flutter，版本为
`python -m flet_cli.cli --version --json` 名称（Flet 1.0.2 为 3.44.8）。它将 macOS 客户端的部署目标从 11.0 提高到 12.0：Xcode 27 不会构建任何旧版本。 Linux 客户端是 Flet 的轻量版，因为 Flet 自己的 CI 构建了它。
## 从源代码运行

对于源开发，请安装 Python 3.13 和 .NET 10 SDK：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r gui/requirements.txt
dotnet build -c Release services/pkhex -warnaserror
python scripts/build_client.py    # optional: file drops; needs Flutter
python gui/main.py
```
 源签出没有固件映像（`gui/firmware` 是构建输出）。 Board 页面的“下载固件”从带有经典 ESP32 映像和 `SHA256SUMS` 的最新非草稿版本中获取每个已知映像，对照该版本的 `SHA256SUMS` 检查每个映像，并仅在全部匹配时才写入它们。早于芯片的版本没有任何图像。来自较旧版本的映像可以携带较旧的串行协议；然后板检查报告固件已过期。
## 构建一个桌面应用程序

> 本节已随上游更新，以下内容暂保留英文。

To package an app, install ESP-IDF v6.1 for `esp32`, `esp32s3`, `esp32c3` and `esp32c6` and activate its
environment. Build all four images with separate configurations:

```sh
mkdir -p gui/firmware
POKELDN_IMAGES="$PWD/gui/firmware"
cd firmware/esp32
idf.py -B build/esp32 -D SDKCONFIG="$PWD/build/esp32/sdkconfig" set-target esp32
idf.py -B build/esp32 -D SDKCONFIG="$PWD/build/esp32/sdkconfig" build
idf.py -B build/esp32 merge-bin -o "$POKELDN_IMAGES/pokeldn-radio.bin"
idf.py -B build/esp32s3 -D SDKCONFIG="$PWD/build/esp32s3/sdkconfig" set-target esp32s3
idf.py -B build/esp32s3 -D SDKCONFIG="$PWD/build/esp32s3/sdkconfig" build
idf.py -B build/esp32s3 merge-bin -o "$POKELDN_IMAGES/pokeldn-radio-s3.bin"
idf.py -B build/esp32c3 -D SDKCONFIG="$PWD/build/esp32c3/sdkconfig" set-target esp32c3
idf.py -B build/esp32c3 -D SDKCONFIG="$PWD/build/esp32c3/sdkconfig" build
idf.py -B build/esp32c3 merge-bin -o "$POKELDN_IMAGES/pokeldn-radio-c3.bin"
idf.py -B build/esp32c6 -D SDKCONFIG="$PWD/build/esp32c6/sdkconfig" set-target esp32c6
idf.py -B build/esp32c6 -D SDKCONFIG="$PWD/build/esp32c6/sdkconfig" build
idf.py -B build/esp32c6 merge-bin -o "$POKELDN_IMAGES/pokeldn-radio-c6.bin"
cd ../..
python scripts/build_client.py
python scripts/build_unicorn.py
python scripts/pack_app.py
```

The absolute output paths keep the images in `gui/firmware`. The packer requires all four images,
the client from `scripts/build_client.py` and the Unicorn from `scripts/build_unicorn.py` (needs CMake); the frozen app check verifies all are included and
that the bundled client carries `flet_drop`. The release workflow builds each target separately
and supplies all four images to every desktop packer.

The app version is `pokeldn.__version__`. It appears in Settings and in the macOS and Windows
package metadata. Update it and `.github/release-notes.md` together before preparing a release.
The workflow produces `SHA256SUMS` for the three desktop downloads and four firmware images.
Manual workflow runs produce artifacts; `v*` tags publish a release named `pokeldn vX.Y.Z` with
`.github/release-notes.md` as its body, whose first line must be `# pokeldn X.Y.Z` (the workflow and
`tests/test_release.py` check it), and with the same eight files every time.
Only tags with a hyphen, such as `v0.3.0-rc1`, are marked as pre-releases; GitHub shows the
newest other release as Latest in the repository sidebar.

The apps are one-folder PyInstaller builds: `pokeldn.app` on macOS, a `pokeldn` folder holding
`pokeldn` or `pokeldn.exe` and `_internal` on Linux and Windows. A single file unpacks its whole bundle (about 180 MB) to a temporary folder at every launch, and every
run is the app relaunching itself, so a run paid it again. On an M4 the one-folder app reaches the
Games page in 0.7 s instead of 2.9 s, and a run's process starts in 0.08 s instead of 1.5 s. Flet's
packer refuses `--onedir` on macOS; `scripts/pack_app.py` passes it to PyInstaller after Flet's own
`--onefile`, and the later flag wins. The bundle's Python process never checks in with the Dock: as a
foreground app it shows a second icon that bounces until the app quits. The packer sets
`LSBackgroundOnly` in its `Info.plist`, so only the viewer has a Dock icon, as under the single-file
bootloader.

| part | size | what keeps it small |
|---|---|---|
| Flet viewer (`scripts/build_client.py`) | 33 MB | no optional Flet extension (video, maps, camera, webview and the rest; the app draws core controls only), and on macOS only the build machine's architecture |
| Unicorn (`scripts/build_unicorn.py`) | 3 MB | the installed release built from source with the ARM and ARM64 engines only; the wheel's library carries every CPU family (16 MB) |
| PKHeX helper (`services/pkhex`) | 18 MB | partial trimming: framework code PKHeX.Core never reaches is dropped |
| Python | | the packer excludes Flet's web server, auth and image extras (`flet_web`, FastAPI, Uvicorn, Pydantic, httpx, Pillow) and pytest |

Trimming turns off reflection-based JSON in .NET; the helper's replies need it, so the project turns it
back on (`JsonSerializerIsReflectionEnabledByDefault`). Without it every command answers
`JsonTypeInfo metadata for type 'System.String' was not provided`. Flet's macOS project runs
`dart run rive_native:setup` on every build; with Rive gone that step fails, so the client build
replaces it with `exit 0`.

The viewer is unpacked once per build into `~/.flet/client/flet-desktop-full-<version>-<fingerprint>`,
and Flet never removes an older build's folder. At each launch the frozen app marks its own folder
with `pokeldn-drop` and removes the other folders carrying that marker or, from earlier macOS builds,
a `pokeldn.app` (`gui/flet_client.py`); another Flet app's viewer stays.

Flet 1.0.2's packer re-signs the macOS viewer without its existing entitlements. The packaging
wrapper in `scripts/pack_flet.py` retains them when signing the viewer after its metadata changes.
The frozen check reads the sealed `com.apple.security.files.user-selected.read-write` entitlement
from the embedded viewer; without it, choosing `prod.keys` raises `ENTITLEMENT_NOT_FOUND`.

The Linux bootloader sets `LD_LIBRARY_PATH` to the bundle folder, which carries the build
machine's `libstdc++.so.6` (Ubuntu 22.04). Loaded first, it leaves Fedora 44's Mesa with no EGL
client extensions, and the Flet viewer aborts in libepoxy (`No provider of eglGetPlatformDisplayEXT`).
`pokeldn/app/paths.py` restores the user's `LD_LIBRARY_PATH` for every program the app starts, and
sets `FLET_LINUX_DISTRO` to the bundled viewer's build: Flet otherwise picks a viewer by glibc and
downloads one the bundle does not carry. The frozen check asserts both on Linux.

The app bundles Unicorn for Check offline. It loads its architecture modules by name, so the
packer collects its submodules and adds the ARM-only library to `unicorn/lib` itself, under the wheel's
file names; the frozen check asserts ARM64 is there and x86 is not. PyInstaller's Windows bootloader
is linked with Control Flow Guard (DllCharacteristics `0xC160`), and Unicorn ends a CFG process
with `0xC0000409` on its first `uc_mem_map`
([unicorn#2281](https://github.com/unicorn-engine/unicorn/issues/2281)); a 64 MiB thread stack
does not change it. The packer clears `GUARD_CF` in `pokeldn.exe`, giving `0x8160`, the flags of
`python.exe`. The frozen check runs a payload under Unicorn on every platform. Unicorn raises and
handles an access violation of its own there: never enable `faulthandler` in the frozen check, it
logs that exception to stderr and fails the check.
