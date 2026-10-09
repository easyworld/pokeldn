---
title: Desktop builds
---

# 桌面应用

发行版包含 PKHeX，以及 ESP32、ESP32-S3、ESP32-C3 和 ESP32-C6 的合并固件。用户须提供自己的 `prod.keys`。

打开应用，在“设置”中选择 `prod.keys`。在“开发板”页选择通过 USB 连接的开发板并安装“无线”固件。选择游戏和工具，生成宝可梦或选择文件，然后按照游戏机上的操作步骤点击“开始”。接收到的宝可梦保存在“设置”中选择的文件夹，点击“输出”旁的文件夹按钮可打开。安装时会检测芯片并选择对应的内置固件；写入自定义固件前也会检查芯片是否匹配。S3、C3 和 C6 请使用原生 USB Serial/JTAG 接口；不支持 S2。

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

清理包含应用的 `session/` 工作文件（抓包、串口跟踪、临时交换提议和会话元数据）、`logs/`，以及 `pokemon/` 中未使用的生成或导入提议。生成时间不足一分钟的提议会保留，以便尚未完成的生成任务保存选择；已保存的功能设置和队列引用的提议也会保留。接收文件及其所选文件夹、宝可梦银行、Switch 密钥、所选固件和设置均保留，即使位于清理目录中也如此。更换接收文件夹后，应用命名的临时提议以外的宝可梦记录和二进制转储仍保留。生成提议根据生成器的时间戳及随机后缀识别。清理跳过符号链接，保留检查后发生变化的文件，并移除空子目录。

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

## 宝可梦银行

银行页面保存各游戏交换接收的宝可梦，并可将其交换到 HOME 允许传送的目标游戏。记录保存在 `Documents/pokeldn/Bank`（`pokeldn.app.bank`），每只使用所属游戏的格式（`.pk3`、`.pb7`、`.pk8`、`.pb8`、`.pa8`、`.pk9`、`.pa9`），旁边附带 `.json` 文件。清理本地文件不会处理此目录；设置 `POKELDN_DATA` 时，银行改为该目录中的 `Bank`。

| 步骤 | 行为 |
|---|---|
| 完成交换 | 会话面板通过 PKHeX 读取每个接收文件并存入副本；原接收文件保留，相同字节的数据不会重复存入 |
| 存入宝可梦 | `.json` 保存种类、摘要、PKHeX 检查结果、源文件、数据的 SHA-256 及随机 63 位 HOME 追踪器 |
| 页面列出目标游戏 | 辅助程序的 `destinations` 命令尝试传送到全部七个游戏，并报告各项拒绝原因 |
| 选择目标游戏的交换功能 | 辅助程序的 `move` 命令转换记录，结果以 `"bank": id` 加入该功能的交换队列，应用随后打开此功能 |
| 本次运行的第 N 次交换完成 | `[done] trade N complete` 日志移除队列中对应第 N 次交换的银行宝可梦；运行结束时移除其队列条目 |
| 运行提前失败或停止 | 宝可梦保留在银行和队列中 |

传送使用 PKHeX 自身的 HOME 转换（`EntityConverter.ConvertToType`，经由 `PKH`），随后进行目标游戏的合法性检查；不合法的结果会被拒绝，并显示 PKHeX 的原因。传送过程中：

- 来自其他游戏的宝可梦取得银行分配的 HOME 追踪器。缺少追踪器时，PKHeX 将其标为无效（`HomeTrackerUtil.IsRequired`、`HOMETransferSettings.HOMETransferTrackerNotPresent`）。
- 应用的训练家成为最近持有人，与移入目标存档时相同（`IHandlerUpdate` 及 `PB8.UpdateHandler`）。如果当前持有人是原训练家时仍未通过检查，则把应用训练家设为最近持有人；《剑／盾》要求此设置。
- 传送后若存在无效招式，采用 PKHeX 为目标游戏推荐的招式配置。
- 保留 PID、加密常数、原始训练家及 ID。提供银行宝可梦的运行命令不包含 `--fresh-pid`。

| 拒绝原因 | 来源 |
|---|---|
| 无法传回《火红／叶绿》或《Let's Go》 | `EntityConverter.IsConvertibleToFormat` |
| 蛋 | HOME 的《火红／叶绿》导入画面；转换器原本会使其孵化 |
| 《火红／叶绿》的宝可梦携带道具或学有秘传招式 | HOME 的《火红／叶绿》导入画面 |
| 目标游戏不存在的种类或形态 | 目标游戏的种族数据表 |
| 没有转换路径 | PKHeX.Core 26.8.26 尚不能将《传说 Z-A》的记录转出到其他游戏 |

一只实机《剑》交换接收的宝可梦移至《传说 Z-A》后，保留了 PID 并使用银行追踪器；实机 Z-A 的交换盒子正确显示其等级和原始训练家，交换也已完成。

`tests/test_bank.py` 使用真实辅助程序测试六组游戏间传送，检查目标游戏的启动器是否接受记录、各项拒绝原因，以及交换完成后从银行移除宝可梦的行为。

### 尚未解决

- 携带银行生成的追踪器，或由银行传送过的宝可梦，之后存入 Pokémon HOME 时能否被接受。尚未向 HOME 发送任何数据。
- HOME 自身的《火红／叶绿》导入规则是否还有画面所列蛋、携带道具及秘传招式以外的限制。
- HOME 为从 Switch 版《火红／叶绿》导入的宝可梦显示的来源图标，究竟由哪个记录字段保存。通过 Pokémon Bank 转移的卡带宝可梦没有该图标（依据玩家截图，本项目尚未测量）。PKHeX.Core 26.8.26 通过伙伴公园迁移链转换 `.pk3`，因此银行从《火红／叶绿》转出的记录可能与 HOME 写入的记录不同。

## 开发板和固件

“开发板”页列出连接到此电脑的全部开发板。所选开发板顶部显示固件名称、版本，以及“已是最新版本”或“有可用更新”，并提供相应操作。“固件”卡片按 `gui.board.FIRMWARES` 的顺序列出“无线”和“手柄”：标记已安装项，注明芯片不支持的固件，其余项可在确认后安装。“从文件安装”接受 pokeldn `.bin`，依据应用描述符中的项目名称识别。

| 开发板 | 检测方式 | 版本来源 |
|---|---|---|
| 无线固件 | 串口 | HELLO 回复 |
| 经典 ESP32 手柄固件 | 无线检测失败后通过串口检测 | 串口状态帧 |
| ESP32-S3 手柄固件 | USB 总线（`0f0d:0092`：macOS 使用 `ioreg`，Linux 使用 `/sys/bus/usb/devices`，Windows 使用 `Win32_PnPEntity`）；没有串口 | 通过蓝牙读取状态 |
| 未安装 pokeldn 固件 | 串口，无响应时判断 | 无 |

应用携带的版本来自镜像 ESP-IDF 应用描述符的 `version` 字段（魔数 `0xABCD5432`，合并镜像中位于 `0x10020`）。“有可用更新”表示此版本高于开发板上的版本。串口安装由 esptool 重置芯片进入下载模式；运行手柄固件的 S3 通过蓝牙接收 download 命令，最多等待 20 秒出现下载端口，再以 `--from-loader` 刷写。

## 手柄控制

“手柄控制”页通过运行手柄固件的开发板控制 Switch 按键并运行宏（见[手柄开发板](hardware_pad.md)）。在“开发板”页为 ESP32-S3 或经典 ESP32 安装手柄固件。S3 连接到 Switch 的 USB-C 接口，点击“连接”后，应用通过蓝牙 LE 连接开发板；经典 ESP32 保持 USB 连接到电脑，并作为 Pro 手柄与 Switch 配对。

状态行显示开发板连接到电脑、Switch，还是两者都未连接。应用先检查电脑 USB 总线，再判断已配置 USB 且不在电脑总线上的设备是否连接到 Switch；固件的 `mounted` 只表示某个 USB 主机已配置设备。

| 部分 | 功能 |
|---|---|
| 屏幕手柄 | 按住按键即在主机上保持按下；摇杆支持八个方向的最大倾斜，L3 和 R3 位于中心 |
| 键盘控制 | 开启后，以宏的默认按住时长轻按按键：方向键控制十字键，X → A，Z → B，S → X，A → Y，Q → L，W → R，1 → ZL，2 → ZR，Enter → +，Backspace → -，H → HOME，C → 截图 |
| 录制到宏 | 每次按键成为步骤，记录按住时长；下次按键前的间隔成为此步骤的操作后间隔 |
| 宏编辑器 | 支持按键、摇杆、等待和嵌套重复；“运行一次”只执行一次，“循环”重复指定次数或直到手动停止 |
| 在开发板上运行 | 编译、加载并启动宏；开发板按自身时钟运行，电脑睡眠或断开后继续执行 |

运行手柄固件的开发板在连接到此电脑时显示于开发板页。检测和切换方式见[开发板和固件](#boards-and-firmware)。未连接手柄时，页面说明当前连接情况，并提供开发板页入口。

宏保存在 `Documents/pokeldn/Macros`（设置 `POKELDN_DATA` 时为该目录内的 `Macros`），每个宏一个 `.pokemacro` 文件，每次编辑都会保存。导出生成可分享的副本；导入先检查文件，再以不冲突的名称复制到库中。格式见[手柄开发板：宏](hardware_pad.md#macros)。

连接断开时，例如开发板从电脑移动到 Switch 期间断电，页面会持续重新搜索，直到开发板响应或点击“停止搜索”。

页面通过子进程 `pokeldn.pad.service` 持有蓝牙连接，服务地址为 `127.0.0.1:47800`。macOS 要求应用声明 `NSBluetoothAlwaysUsageDescription`，否则终止使用蓝牙的进程；打包应用已声明，仅未声明的子进程会停止。应用关闭其标准输入后，子进程退出。

macOS 26 的 `bluetoothd` 对签名为应用包主可执行文件的后台进程使用被动“ThirdPartyApp scan”，不返回发现结果，无论是否设置服务 UUID 过滤。未绑定 Info.plist 的独立签名二进制文件（`Info.plist=not bound`）则获得主动扫描。因此打包应用从 `Contents/Helpers/pokeldn-bluetooth` 启动服务：这是以独立标识签名的可执行文件副本，`_internal` 链接到 `../Frameworks`，沿用应用蓝牙权限。主程序扫描发现 0 个设备，辅助程序发现 19 个，其中包含开发板。若应用发现现有服务运行其他版本代码（状态回复中的 `code`），则要求其退出并启动自身版本。

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

启动时，应用在后台向 `api.github.com/repos/Decryptu/pokeldn/releases/latest` 查询最新稳定版，超时为 5 秒。高于应用 `pokeldn.__version__` 的标签会在侧栏增加更新入口，打开后显示发布说明，以及“立即更新”或“下载”。

立即更新（`pokeldn.app.update`）会在原位置安装发布版本：

1. 将适用于此电脑的压缩包（`pokeldn-macos-arm64.zip`、`pokeldn-windows-x64.zip`、`pokeldn-linux-x64.tar.gz`）和发布版本的 `SHA256SUMS` 下载到数据目录的 `update/`。
2. 只有压缩包 SHA-256 与 `SHA256SUMS` 中对应名称的记录一致时才接受文件。
3. 解压：macOS 使用 `ditto -x -k` 保留应用包的符号链接和权限；Linux 使用带 `data` 过滤器的 `tarfile`；Windows 使用 `zipfile`。
4. 以新应用启动辅助程序：`pokeldn --apply-update NEW TARGET PID VERSION`（`gui/updating.py`）。小型“正在更新 pokeldn”窗口创建 `update/helper.ready`；旧应用看到该文件后退出，未出现时则等待最多 15 秒，确保屏幕上一直有窗口。
5. 辅助程序等待旧进程结束（120 秒）；Windows 上还会等待所有从安装目录启动的进程（包括 PKHeX 服务），并在 10 秒后终止残留进程。随后将现有应用重命名为旁边的 `.<name>.old`（Windows 释放文件夹期间重试最多 30 秒），把新应用复制到原位置，删除旧副本并打开新应用。失败时恢复并打开旧应用；无论辅助窗口是否成功显示，替换都会执行。辅助程序从解压副本目录运行：Windows 不允许重命名被任何进程用作工作目录的文件夹，而资源管理器会以应用自身目录启动应用。
6. 打开的应用读取一次 `update/outcome.json`，显示“pokeldn 已更新到 X”，或说明为何保留旧应用。移除此文件后辅助程序关闭（最多等待 60 秒）；应用随后等待辅助进程结束，清理解压副本及 `.old` 文件夹。

应用下载的文件不带 macOS 隔离属性或 Windows 的 Mark of the Web，因此 Gatekeeper 和 SmartScreen 不会再次询问。`SHA256SUMS` 与压缩包来自同一 GitHub 发布版本：该检查能发现损坏或截断的下载，不验证发布者身份。

| 情况 | 行为 |
|---|---|
| 预发布、草稿或不符合 `vX.Y.Z` 的标签 | 不提供更新 |
| 无网络、HTTP 错误或回复不是发布版本 | 启动时不显示提示；立即检查会报告 GitHub 未响应 |
| 设置中关闭更新 | 启动时不请求，立即检查仍可查询 |
| 没有适用于此电脑的压缩包，或发布版本没有 `SHA256SUMS` | 下载按钮打开文件或发布页面 |
| 源码运行、从“下载”目录运行的 macOS 应用（App Translocation）、无写入权限的文件夹 | 显示下载按钮和原因 |
| 会话、刷写或清理正在运行 | 立即更新要求先结束操作 |
| 校验和不符或下载失败 | 应用不变，对话框提供下载按钮 |

设置、密钥和已接收的宝可梦存放在应用外部并保留。尚未测量 macOS 在替换 `/Applications` 中的应用时是否要求“应用管理”权限；权限被拒绝时保留旧应用，并在对话框显示错误。

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

打包应用时，为 `esp32`、`esp32s3`、`esp32c3`、`esp32c6` 安装 ESP-IDF v6.1 并激活环境，使用独立配置构建四个无线固件镜像及手柄镜像（`firmware/pad`，通过组件管理器获取 `espressif/esp_tinyusb`）：

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
cd ../pad
idf.py -B build -D SDKCONFIG="$PWD/build/sdkconfig" set-target esp32s3
idf.py -B build -D SDKCONFIG="$PWD/build/sdkconfig" build
idf.py -B build merge-bin -o "$POKELDN_IMAGES/pokeldn-pad-s3.bin"
cd ../..
python scripts/build_client.py
python scripts/build_unicorn.py
python scripts/pack_app.py
```

绝对输出路径使镜像保留在 `gui/firmware`。打包器要求全部五个镜像、`scripts/build_client.py` 构建的客户端，以及 `scripts/build_unicorn.py` 构建的 Unicorn（需要 CMake）；冻结应用自检确认它们均已包含，且随包客户端支持 `flet_drop`。发布工作流分别构建各目标，再向每个平台的桌面打包器提供全部五个镜像。

应用版本为 `pokeldn.__version__`，显示在设置及 macOS、Windows 软件包元数据中。准备发布前，与 `.github/release-notes.md` 一起更新。工作流为三种桌面下载和五个固件镜像生成 `SHA256SUMS`。手动运行只生成构建产物；`v*` 标签发布名为 `pokeldn vX.Y.Z` 的版本，以 `.github/release-notes.md` 为正文；其首行必须为 `# pokeldn X.Y.Z`（工作流和 `tests/test_release.py` 均检查），每次提供相同的九个文件。只有包含连字符的标签（例如 `v0.3.0-rc1`）标记为预发布；GitHub 在仓库侧栏将最新的其他发行版显示为 Latest。

应用采用 PyInstaller 单目录构建：macOS 为 `pokeldn.app`，Linux 和 Windows 为包含 `pokeldn` 或 `pokeldn.exe` 以及 `_internal` 的 `pokeldn` 目录。单文件每次启动都把整个软件包（约 180 MB）解压到临时目录；每次运行功能都会重新启动应用自身，因此再次付出解压开销。在 M4 上，单目录应用到达“游戏”页需 0.7 秒，单文件为 2.9 秒；功能进程启动需 0.08 秒，而非 1.5 秒。Flet 打包器在 macOS 上拒绝 `--onedir`；`scripts/pack_app.py` 在 Flet 的 `--onefile` 之后向 PyInstaller 传入该参数，后面的参数优先。软件包的 Python 进程不会向 Dock 注册：若作为前台应用运行，会显示第二个图标并一直跳动至退出。打包器在 `Info.plist` 中设置 `LSBackgroundOnly`，因此只有界面客户端显示 Dock 图标，与单文件启动器一致。

| 部分 | 大小 | 缩减方式 |
|---|---|---|
| Flet 界面客户端（`scripts/build_client.py`） | 31 MB，macOS 压缩包为 9.4 MB | 去除视频、地图、相机、网页视图等可选扩展，仅保留核心控件；macOS 仅保留构建机器的架构，分离 Dart 符号（`--split-debug-info`），并使用 xz 压缩 |
| Unicorn（`scripts/build_unicorn.py`） | 3 MB | 从已安装版本源码仅构建 ARM 和 ARM64 引擎；wheel 的库包含全部 CPU 架构（16 MB） |
| PKHeX 辅助程序（`services/pkhex`） | 16 MB | 完整裁剪未使用的框架和 PKHeX.Core 代码；关闭 EventSource、调试器及热重载支持 |
| Python | 模块共 8 MB | 排除 Flet 的网页服务、认证和图像扩展（`flet_web`、FastAPI、Uvicorn、Pydantic、httpx、Pillow）、pytest、Pygments、rich 的语法、Markdown 和回溯模块、`multiprocessing`、`_pydecimal`，macOS 还排除东亚编码；macOS 库移除本地符号（`strip -x`） |

裁剪会关闭 .NET 基于反射的 JSON；辅助程序的回复需要该功能，因此项目通过 `JsonSerializerIsReflectionEnabledByDefault` 重新启用。否则每条命令都会返回 `JsonTypeInfo metadata for type 'System.String' was not provided`。第三世代活动表是 PKHeX.Core 内部类型，按名称读取；`DynamicDependency` 属性使其在裁剪后保留。

macOS 打包器使用 xz 压缩界面客户端，文件名仍为 Flet 使用的 `flet-macos.tar.gz`（9.4 MB，而非 13.6 MB）；flet_desktop 1.0.2 以 `r:gz` 打开它，因此冻结应用向 flet_desktop 提供能由 `open` 自动识别压缩格式的 `tarfile`（`gui/flet_client.py`）。可执行文件和 PKHeX 辅助程序不移除符号：两者的 Mach-O 映像后都附带压缩包。Flet 的 macOS 项目每次构建运行 `dart run rive_native:setup`，移除 Rive 后此步骤会失败，因此客户端构建将其替换为 `exit 0`。

界面客户端每个构建只解压一次到 `~/.flet/client/flet-desktop-full-<version>-<fingerprint>`，Flet 不会删除旧构建目录。冻结应用每次启动，以 `pokeldn-drop` 标记自身目录，移除其他含该标记的目录，或早期 macOS 构建中含 `pokeldn.app` 的目录（`gui/flet_client.py`）；其他 Flet 应用的客户端保留。

Flet 1.0.2 打包器重新签名 macOS 客户端时会丢失原有权限。`scripts/pack_flet.py` 中的打包包装器在修改元数据后签名时保留它们。冻结应用自检从嵌入客户端读取签名中的 `com.apple.security.files.user-selected.read-write` 权限；没有它，选择 `prod.keys` 会抛出 `ENTITLEMENT_NOT_FOUND`。

Linux 启动器把 `LD_LIBRARY_PATH` 设为软件包目录，其中含有构建机器的 `libstdc++.so.6`（Ubuntu 22.04）。优先加载该库会让 Fedora 44 的 Mesa 缺少 EGL 客户端扩展，使 Flet 客户端在 libepoxy 中终止（`No provider of eglGetPlatformDisplayEXT`）。`pokeldn/app/paths.py` 为应用启动的每个程序恢复用户的 `LD_LIBRARY_PATH`，并把 `FLET_LINUX_DISTRO` 设为随包客户端版本；否则 Flet 会按 glibc 选择客户端，并下载软件包中没有的版本。Linux 冻结应用自检检查这两项。

应用随包携带 Unicorn，用于“离线检查”。它按名称加载架构模块，因此打包器收集子模块，并按 wheel 的文件名把仅含 ARM 的库放入 `unicorn/lib`；冻结应用自检确认 ARM64 存在而 x86 不存在。PyInstaller 的 Windows 启动器链接时启用 Control Flow Guard（DllCharacteristics `0xC160`），Unicorn 在第一次 `uc_mem_map` 时以 `0xC0000409` 终止启用 CFG 的进程（[unicorn#2281](https://github.com/unicorn-engine/unicorn/issues/2281)）；64 MiB 线程栈无法改变这一结果。打包器在 `pokeldn.exe` 清除 `GUARD_CF`，得到 `python.exe` 所用的标志 `0x8160`。冻结应用自检在每个平台运行一段 Unicorn 载荷。Unicorn 在此过程中自行触发并处理访问异常：自检时不能启用 `faulthandler`，否则它会把异常写入 stderr，导致检查失败。
