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

## Windows USB 驱动

经典 ESP32 开发板通过 USB 转串口芯片连接电脑，芯片型号印在 USB 接口旁。Windows 只有在安装该芯片的驱动后才会分配 COM 端口；未安装时，应用的开发板列表中不会显示它，设备管理器会显示警告（问题代码 28，未安装驱动）。ESP32-S3、C3 和 C6 使用原生 USB 接口时无需安装此类驱动。

| 桥接芯片 | USB ID | 驱动 | 安装方法 |
|---|---|---|---|
| Silicon Labs CP2102 / CP210x | `10c4:ea60` | [CP210x VCP 驱动](https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers)，下载 CP210x Universal Windows Driver 压缩包 | 解压，右键单击 `silabser.inf` 并选择“安装”，然后拔出并重新连接开发板 |
| WCH CH340 | `1a86:7523` | [CH341SER.EXE](https://www.wch-ic.com/downloads/CH341SER_EXE.html) | 运行并点击“安装”，然后拔出并重新连接开发板 |

没有列出 COM 端口时，开发板页面每 2 秒查询一次 Windows 中设备管理器报告异常的 USB 设备（`Get-CimInstance Win32_PnPEntity`、`ConfigManagerErrorCode <> 0`），识别已知桥接芯片并显示对应驱动的安装步骤（`gui/board.py` 的 `bridges_without_driver`）。

## Linux 串口

该应用程序以用户身份打开开发板，无需 root 也无需内核网络。打开端口需要`dialout`组（Arch上为`uucp`）；用户可能无法打开的端口会失败并显示 `EACCES`，然后 Board 页面会命名该组而不是繁忙端口。

|服务 |开发板|效果|
|---|---|---|
| brltty 6.4（Ubuntu 22.04）| CH340 `1a86:7523` |由 `85-brltty.rules` 声称；安装 brltty 时不会出现 `/dev/ttyUSB*` ([LP 1990357](https://bugs.launchpad.net/bugs/1990357))。修复：`sudo apt remove brltty` |
| brltty 6.6（Ubuntu 24.04）| CP210x `10c4:ea60`，CH340 | CP210x 规则已注释掉（[LP 1958224](https://bugs.launchpad.net/bugs/1958224)）； CH340声称仅在`1a40:0101`集线器后面|
|调制解调器管理器 1.23 (Ubuntu 24.04) |全部 | `10c4`、`1a86` 或 `303a` 没有忽略规则；其严格过滤器仅通过接口协议 1 至 6 的 `cdc_acm` 端口 (`mm-filter.c`) |

由于 Linux 上没有列出串行端口，主板页面显示为 `/sys/bus/usb/devices` 并命名了一个已知的桥接器，该桥接器的接口下没有 tty，并针对 CH340 进行了 brltty 修复 (`gui/board.py` `bridges_without_port`)。
## 本地存储

设置、存储显示可回收本地文件占用的空间。清除本地文件要求确认，删除检查中的文件并报告释放了多少空间。在清除之前保存错误报告所需的记录。

清理包括应用程序的 `session/` 工作文件（捕获、串行跟踪、临时提议和会话元数据）、`logs/` 以及 `pokemon/` 中未使用的生成或导入的提议。保留不到一分钟的已构建提议，因此仍在完成的构建可以保存其选择。保留已保存工具设置和队列引用的提议。接收到的文件及其选定的文件夹、开关键、选定的固件和设置都会被保留，包括当它们存储在清理文件夹下时。 即使在“已接收”文件夹发生更改后，宝可梦记录和二进制转储仍会保留在应用程序的命名临时提议之外。生成的提议由构建者的时间戳和随机后缀标识。符号链接被跳过；保留检查后更改的文件。空的子文件夹将被删除。

在清理之前完成所有活动会话、闪存或开发板检查。清理在后台运行，并推迟新的会话和闪烁，直到完成。报告无法删除的文件并可以重试。宝可梦精灵缓存在高级设置下有自己的清除缓存按钮。
## 存档管理

《火红／叶绿》神秘礼物工具的“存档”选项卡，经由“神奇卡片 → 朋友”路径备份主机存档或还原存档（[存档备份与还原](frlg_gift.md#save-backup-and-restore)）。存档位于 `Documents/pokeldn/Saves`（`pokeldn.app.saves`），每个 `.sav` 旁有一个 `.json`，记录名称、来源及主机游戏代码。“清理本地文件”不会改动该目录；设置 `POKELDN_DATA` 后，存档库改为该目录中的 `Saves`。

| 操作 | 行为 |
|---|---|
| 从 Switch 备份 | 启动器写入 `backup-<run>.sav` 及其 `.json`；连接中断的备份保留在 `Saves/.partial`，下次从中断处继续 |
| 还原到 Switch | 所选存档传给 `--save-restore`；未选择存档时无法开始 |
| `+`，或把 `.sav` 拖到卡片上 | 复制文件；移除 16 字节模拟器尾部后，大小不是 128 KB 的文件均被拒绝 |
| 重命名、导出 .sav、删除 | 名称仅用于显示并保存在 `.json` 中；删除仅移除此电脑上的两个文件 |
| 查看与编辑 | PKHeX 读取训练家、队伍和电脑盒子；见下文 |

运行时，会话面板把启动器的 `[save] backup N of 128 KB` 或 `[save] restore N of M sectors` 转换为进度条；运行结束后刷新列表。

若存档没有完整副本，或 PKHeX 检测到队伍中有不合法的宝可梦，会阻止还原；开启“仍然还原”后方可继续。存档名称默认由训练家与卡带版本组成，只有备份时能确定这些信息。

编辑器可修改训练家名称、性别、金钱、代币和队伍：排序、移除，或添加由 PKHeX 按当前存档训练家信息（名称、ID、秘密 ID、语言）生成的宝可梦。各队伍成员显示 PKHeX 判定；“检查合法性”检查一个盒子，耗时数秒。“另存为新存档”通过 PKHeX 写入结果，重新计算所有扇区校验和，确认通过游戏自身的扇区检查后，作为新条目加入存档库；原文件保持不变。

## 宝可梦精灵

精灵是 `sprites.front_default` 和 `sprites.front_shiny` 后面的 96x96 PNG
`https://pokeapi.co/api/v2/pokemon/{id}`，读取`raw.githubusercontent.com/PokeAPI/sprites`（`sprites/pokemon/{id}.png`，`sprites/pokemon/shiny/{id}.png`）。未获取 JSON（每个种类 300 KB）；精灵路径由 id 固定。从 1 到 1025 采样的 12 个 National Dex 号码都具有两种精灵； 1026 返回 404。当缺少异色精灵时，将显示正常的精灵。

|哪里 |尺寸|
|---|---|
|当异色开启时，交换选择器，在种类、异色旁边 | 96 px，整个画布 |
|种类场卡片（剑／盾 神秘礼物），工具异色开关打开时异色 | 46 像素瓷砖 |
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

启动时，应用在后台向 `api.github.com/repos/Decryptu/pokeldn/releases/latest` 查询最新稳定版，超时为 5 秒。标签版本高于应用的 `pokeldn.__version__` 时，侧栏出现“更新”，可打开更新说明，或下载适合本机的发行文件（`pokeldn-macos-arm64.zip`、`pokeldn-windows-x64.zip`、`pokeldn-linux-x64.tar.gz`）；没有匹配文件则打开发行页面。用户以下载内容替换应用；设置、密钥和已接收宝可梦位于应用之外。

| 情况 | 行为 |
|---|---|
| 预发布、草稿，或不是 `vX.Y.Z` 格式的标签 | 不提示更新 |
| 无网络、HTTP 错误、回复不是发行信息 | 启动时不显示；“立即检查”提示 GitHub 未响应 |
| “设置 → 更新”关闭 | 启动时不请求；“立即检查”仍会查询 |

请求不包含用户数据。GitHub 对每个地址每小时允许 60 次未认证请求。测试时用 `POKELDN_UPDATE_URL` 替换端点（`tests/test_app_update.py`）。

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

打包应用时，为 `esp32`、`esp32s3`、`esp32c3`、`esp32c6` 安装 ESP-IDF v6.1 并激活环境，使用独立配置构建全部四个固件镜像：

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

绝对输出路径使镜像保留在 `gui/firmware`。打包器要求全部四个镜像、`scripts/build_client.py` 构建的客户端，以及 `scripts/build_unicorn.py` 构建的 Unicorn（需要 CMake）；冻结应用自检确认它们均已包含，且随包客户端支持 `flet_drop`。发布工作流分别构建各目标，再向每个平台的桌面打包器提供全部四个镜像。

应用版本为 `pokeldn.__version__`，显示在设置及 macOS、Windows 软件包元数据中。准备发布前，与 `.github/release-notes.md` 一起更新。工作流为三种桌面下载和四个固件镜像生成 `SHA256SUMS`。手动运行只生成构建产物；`v*` 标签发布名为 `pokeldn vX.Y.Z` 的版本，以 `.github/release-notes.md` 为正文；其首行必须为 `# pokeldn X.Y.Z`（工作流和 `tests/test_release.py` 均检查），每次提供相同的八个文件。只有包含连字符的标签（例如 `v0.3.0-rc1`）标记为预发布；GitHub 在仓库侧栏将最新的其他发行版显示为 Latest。

应用采用 PyInstaller 单目录构建：macOS 为 `pokeldn.app`，Linux 和 Windows 为包含 `pokeldn` 或 `pokeldn.exe` 以及 `_internal` 的 `pokeldn` 目录。单文件每次启动都把整个软件包（约 180 MB）解压到临时目录；每次运行功能都会重新启动应用自身，因此再次付出解压开销。在 M4 上，单目录应用到达“游戏”页需 0.7 秒，单文件为 2.9 秒；功能进程启动需 0.08 秒，而非 1.5 秒。Flet 打包器在 macOS 上拒绝 `--onedir`；`scripts/pack_app.py` 在 Flet 的 `--onefile` 之后向 PyInstaller 传入该参数，后面的参数优先。软件包的 Python 进程不会向 Dock 注册：若作为前台应用运行，会显示第二个图标并一直跳动至退出。打包器在 `Info.plist` 中设置 `LSBackgroundOnly`，因此只有界面客户端显示 Dock 图标，与单文件启动器一致。

| 组成部分 | 大小 | 缩减体积的方式 |
|---|---|---|
| Flet 界面客户端（`scripts/build_client.py`） | 33 MB | 不包含可选 Flet 扩展（视频、地图、相机、网页视图等；应用只使用核心控件）；macOS 仅构建本机架构 |
| Unicorn（`scripts/build_unicorn.py`） | 3 MB | 从已安装版本的源码构建，仅保留 ARM 和 ARM64 引擎；wheel 自带库包含全部 CPU 架构（16 MB） |
| PKHeX 辅助程序（`services/pkhex`） | 18 MB | 部分裁剪：移除 PKHeX.Core 不会调用的框架代码 |
| Python | | 打包器排除 Flet 的网页服务器、认证及图像附加组件（`flet_web`、FastAPI、Uvicorn、Pydantic、httpx、Pillow）和 pytest |

裁剪会关闭 .NET 基于反射的 JSON，而辅助程序回复需要该功能，因此项目通过 `JsonSerializerIsReflectionEnabledByDefault` 重新启用。否则每个命令都回复 `JsonTypeInfo metadata for type 'System.String' was not provided`。Flet 的 macOS 项目每次构建运行 `dart run rive_native:setup`；移除 Rive 后该步骤失败，因此客户端构建将其替换为 `exit 0`。

界面客户端每个构建只解压一次到 `~/.flet/client/flet-desktop-full-<version>-<fingerprint>`，Flet 不会删除旧构建目录。冻结应用每次启动，以 `pokeldn-drop` 标记自身目录，移除其他含该标记的目录，或早期 macOS 构建中含 `pokeldn.app` 的目录（`gui/flet_client.py`）；其他 Flet 应用的客户端保留。

Flet 1.0.2 打包器重新签名 macOS 客户端时会丢失原有权限。`scripts/pack_flet.py` 中的打包包装器在修改元数据后签名时保留它们。冻结应用自检从嵌入客户端读取签名中的 `com.apple.security.files.user-selected.read-write` 权限；没有它，选择 `prod.keys` 会抛出 `ENTITLEMENT_NOT_FOUND`。

Linux 启动器把 `LD_LIBRARY_PATH` 设为软件包目录，其中含有构建机器的 `libstdc++.so.6`（Ubuntu 22.04）。优先加载该库会让 Fedora 44 的 Mesa 缺少 EGL 客户端扩展，使 Flet 客户端在 libepoxy 中终止（`No provider of eglGetPlatformDisplayEXT`）。`pokeldn/app/paths.py` 为应用启动的每个程序恢复用户的 `LD_LIBRARY_PATH`，并把 `FLET_LINUX_DISTRO` 设为随包客户端版本；否则 Flet 会按 glibc 选择客户端，并下载软件包中没有的版本。Linux 冻结应用自检检查这两项。

应用随包携带 Unicorn，用于“离线检查”。它按名称加载架构模块，因此打包器收集子模块，并按 wheel 的文件名把仅含 ARM 的库放入 `unicorn/lib`；冻结应用自检确认 ARM64 存在而 x86 不存在。PyInstaller 的 Windows 启动器链接时启用 Control Flow Guard（DllCharacteristics `0xC160`），Unicorn 在第一次 `uc_mem_map` 时以 `0xC0000409` 终止启用 CFG 的进程（[unicorn#2281](https://github.com/unicorn-engine/unicorn/issues/2281)）；64 MiB 线程栈无法改变这一结果。打包器在 `pokeldn.exe` 清除 `GUARD_CF`，得到 `python.exe` 所用的标志 `0x8160`。冻结应用自检在每个平台运行一段 Unicorn 载荷。Unicorn 在此过程中自行触发并处理访问异常：自检时不能启用 `faulthandler`，否则它会把异常写入 stderr，导致检查失败。
