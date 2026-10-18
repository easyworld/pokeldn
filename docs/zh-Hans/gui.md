---
title: Desktop builds
---

# 桌面应用

发行版包含 PKHeX，以及 ESP32、ESP32-S3、ESP32-C3 和 ESP32-C6 的合并固件。用户须提供自己的 `prod.keys`。

打开应用，在“设置”中选择 `prod.keys`。在“开发板”页选择通过 USB 连接的开发板并安装“无线”固件。选择游戏和工具，生成宝可梦或选择文件，然后按照游戏机上的操作步骤点击“开始”。接收到的宝可梦保存在“设置”中选择的文件夹，点击“输出”旁的文件夹按钮可打开。安装时会检测芯片并选择对应的内置固件；写入自定义固件前也会检查芯片是否匹配。S3、C3 和 C6 请使用原生 USB Serial/JTAG 接口；不支持 S2。

神秘礼物工具共用礼物制作界面：可以选择预设、自行制作或打开 `.pokegift` 文件；剑／盾还支持 `.wc8` 卡片。无需连接开发板，点击“保存礼物文件”即可导出 `.pokegift`，也可根据扩展名导出火红／叶绿的 `.wc3` 或剑／盾的 `.wc8`。[神秘礼物文件](gifts.md#desktop-app)介绍了表单、卡带版本及原生格式转换。

<a id="first-launch"></a>

## 首次启动

棋盘格背景覆盖整个窗口，包括透明的标题栏；导航栏与其他面板一样，以玻璃质感面板悬浮在背景上。标题栏不显示应用名称；拖动空白区域可移动窗口，双击可最大化或还原。macOS 保留系统原生窗口按钮，Windows 和 Linux 使用应用标题栏中的按钮。一体化标题栏已在 macOS 上进行外观检查，Windows 和 Linux 窗口管理器的行为尚未验证。

- macOS：应用未签名。先打开一次并关闭警告，再进入“系统设置 → 隐私与安全性 → 安全性”，点击 pokeldn 旁的“仍要打开”，输入密码确认。之后可正常启动。
- Windows：完整解压 ZIP，运行 `pokeldn` 文件夹中的 `pokeldn.exe`，保留旁边的 `_internal`。若 SmartScreen 阻止，选择“更多信息 → 仍要运行”。开发板没有 COM 端口时，参见 [Windows USB 驱动](#windows-usb-drivers)。
- Linux：若发行版未提供，请安装 GTK 3 和 libsecret。串口访问需执行 `sudo usermod -aG dialout $USER`（Arch 使用 `uucp` 组），修改组后退出并重新登录。缺少串口或与 brltty 冲突时，参见 [Linux 串口](#linux-serial-ports)。

<a id="android-setup-requirements"></a>

## Android 设置要求

[Android 应用](../examples/android/README.md)在手机上使用同一套界面。其“开发板”页遵循下表，并在连接或拔出开发板、关闭 Android USB 授权提示、从系统设置返回时重新读取 USB 状态。原生 USB 开发板（`303a:1001`）接入后会打开应用。在已测试的 OnePlus CPH2621 上，启用手机的 OTG 连接设置后，无需重新插线即可为连接的 ESP32C6 供电并识别设备。

| 检测状态 | 所需引导 |
|---|---|
| 无兼容 USB 设备 | 检查支持数据传输的线缆与连接；提供该手机 USB 主机或 OTG 设置说明，包括 OnePlus 的 OTG 连接开关。仅设备缺失无法确定是哪项检查失败 |
| 设备存在，缺少或拒绝 USB 权限 | 解释 Android USB 访问提示，并提供明确的重试操作 |
| 已授权，开发板握手失败 | 检查开发板连接与支持的无线固件，显示实际错误 |
| 开发板回应握手 | 显示检测到的开发板和固件，再继续游戏流程 |
| 开发板断开或用户从设置返回 | 刷新检测及权限状态，更新引导；开发板就绪后继续设置 |

仅通过 CP210x、CH34x 或 FTDI 桥接芯片连接的开发板（经典 ESP32）会被标为手机应用无法驱动。PKHeX 已编译为 Android 版本，在手机上运行。接收的宝可梦通过 Android 文件选择器保存。

设置引导应使用已验证的厂商路径或可搜索的设置名称，并在 Android 支持时提供设置快捷入口。流程显示下一步操作和当前进度。ADB、无线调试等开发工具不属于用户设置流程。

Android 的“打开文件夹”会将目录保存为 ZIP，由玩家选择保存位置；文件选择器使用 Android 系统界面。

<a id="ios-setup"></a>

## iOS 设置

[iOS 应用](../examples/ios/README.md)在 iPhone、iPad 上提供同一套界面，通过 AltStore 或 SideStore 安装。iPhone 无法打开 USB 串口设备，因此应用通过蓝牙连接开发板。开发板必须运行**蓝牙无线**固件，先从桌面应用“开发板”页安装一次：ESP32-C6 使用 `pokeldn-radio-ble-c6.bin`，经典 ESP32 使用 `pokeldn-radio-ble.bin`。之后 USB 仅用于供电。手机连接后，“开发板”页会将它列为“蓝牙无线开发板”；首次启动会请求蓝牙访问权限。手机占用开发板期间，开发板不回应 USB 数据线上的请求；从电脑或 Android 手机使用前，请先关闭 iOS 应用。文件选择器使用 iOS 系统界面，所选文件会复制到应用中；应用文件位于“文件 → 我的 iPhone → pokeldn”。

<a id="phones"></a>

## 手机界面

窗口宽度小于 760 点时，应用使用底部标签栏切换页面；每页一次显示一个面板，可通过上方的切换器选择。“游戏”页包括“游戏”“选项”“会话”，选择工具后自动显示选项，点击“开始”后显示会话。对话框占用屏幕宽度。Android 和 iOS 不提供“手柄”和“更新”页面。

<a id="app-language"></a>

## 应用语言

“设置 → 应用语言”列出内置语言与已安装的社区语言包。选择社区语言包会启用对应插件，重启应用后生效。缺少的字符串回退到英语。训练家语言另行控制生成的宝可梦；语言包格式和翻译模板见[语言包](plugins.md#language-packs-15)。上游默认仅提供英语，本中文版内置并默认使用简体中文。随包提供的 [Noto Sans CJK SC](https://github.com/notofonts/noto-cjk/tree/main/Sans/OTF/SimplifiedChinese) 后备字体可离线显示中、日、韩文字，其 SIL 开放字体许可证位于 `gui/assets/fonts/LICENSE`。

<a id="your-trainer"></a>

## 你的训练家

设置中的初训家用于所有生成的宝可梦，包括姓名、性别、语言及两组按游戏显示输入的 ID。传说 Z-A 仅在初训家性别、ID 和姓名均一致时，视接收宝可梦为玩家所有（[接收的记录](za.md#what-the-trade-writes-into-a-received-record)）。传说 阿尔宙斯的数据交换记录包含该性别及对应外观（[记录](pla.md#the-games-reader-and-the-pre-handler-phase)）；实机交换画面没有显示伙伴性别。记录以 16 位 TID、16 位 SID 存储，分别为 32 位 ID 的低、高半部。

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
| 存入宝可梦 | `.json` 保存种类、摘要、PKHeX 检查结果、源文件、数据的 SHA-256、在“生成”设置下传送时使用的随机 63 位 HOME 追踪码，以及 `home_tracker`（`empty`、`made` 或空值） |
| 页面列出目标游戏 | 辅助程序的 `destinations` 命令尝试传送到全部七个游戏，并报告各项拒绝原因 |
| 选择目标游戏的交换功能 | 辅助程序的 `move` 命令转换记录，结果以 `"bank": id` 加入该功能的交换队列，应用随后打开此功能 |
| 本次运行的第 N 次交换完成 | `[done] trade N complete` 日志移除队列中对应第 N 次交换的银行宝可梦；运行结束时移除其队列条目 |
| 运行提前失败或停止 | 宝可梦保留在银行和队列中 |

传送使用 PKHeX 自身的 HOME 转换（`EntityConverter.ConvertToType`，经由 `PKH`），随后进行目标游戏的合法性检查；不合法的结果会被拒绝，并显示 PKHeX 的原因。各招式的错误行合并为一项（如“有 2 个招式不合法”），同一问题只列一次。传送过程中：

- 来自其他游戏的宝可梦按 [HOME 追踪码设置](#the-home-tracker-setting) 处理：留空，或使用银行分配的追踪码。
- 应用的训练家成为最近持有人，与移入目标存档时相同（`IHandlerUpdate` 及 `PB8.UpdateHandler`）。如果当前持有人是原训练家时仍未通过检查，则把应用训练家设为最近持有人；《剑／盾》要求此设置。
- 传送后若存在无效招式，采用 PKHeX 为目标游戏推荐的招式配置。
- 保留 PID、加密常数、初训家及 ID。提供银行宝可梦的运行命令不包含 `--fresh-pid`。

| 拒绝原因 | 来源 |
|---|---|
| 无法传回《火红／叶绿》 | `EntityConverter.IsConvertibleToFormat` |
| 无法传入《Let's Go》 | HOME 只允许从该游戏转出；单独调用转换器却能把 `PK3` 转成 `PB7`，因为 Let's Go 的格式编号 (7) 高于火红 (3) |
| 蛋 | HOME 的《火红／叶绿》导入画面；转换器原本会使其孵化 |
| 《火红／叶绿》的宝可梦携带道具或学有秘传招式 | HOME 的《火红／叶绿》导入画面 |
| 目标游戏不存在的种类或形态 | 目标游戏的种族数据表 |
| 没有转换路径 | PKHeX.Core 26.8.26 尚不能将《传说 Z-A》的记录转出到其他游戏 |

“编辑”可修改游戏本身允许玩家更改的项目：昵称（留空恢复种类名称）、等级（只能提高）、招式和携带道具。辅助程序的 `check` 命令应用字段并运行 PKHeX 合法性检查；若修改会使原本合法的宝可梦变得不合法，则拒绝并保留原记录。保存时重写记录及其 `.json`（摘要、检查结果和 SHA-256），随后重新检查可传送的游戏。已加入交换队列的宝可梦不能编辑。

<a id="the-home-tracker-setting"></a>

### HOME 追踪码设置

宝可梦缺少所需的 HOME 追踪码时，PKHeX 会将其判定为不合法（`HomeTrackerUtil.IsRequired`、`LegalityCheckResultCode.TransferTrackerMissing`，严重级别 `HOMETransferTrackerNotPresent`）：例如从其他游戏传入的宝可梦，或只能通过 HOME 进入游戏的活动礼物。HOME 3.1.0 及之后会拒绝非 HOME 签发的追踪码（错误 10015）。“设置 → 高级设置 → HOME 追踪码”决定应用写入什么（`Settings.home_tracker`）；`pokeldn.pokemon.Service` 在每次辅助程序请求中发送 `home_tracker`，运行会通过 `POKELDN_HOME_TRACKER` 继承此设置。

| 设置 | 银行传送、导入与生成器的礼物修复 | 合法性 | 显示的提示 |
|---|---|---|---|
| `empty`（默认） | 不写入追踪码 | 仅在缺少追踪码是 PKHeX 唯一检查问题时接受，其他问题仍被拒绝 | PKHeX 提示缺少 HOME 追踪码 |
| `made` | 生成随机 63 位追踪码；银行中的宝可梦使用银行分配的追踪码 | 判定规则保持不变 | 无法存入 HOME |

每条辅助程序回复包含 `home_tracker`（`empty`、`made` 或空值）；`destinations` 按游戏返回此字段。提示显示在生成或加载的提供记录、银行条目、目标游戏以及导入条目上。追踪码留空也会影响其他检查结果：将 `tests/data/bank_import.json` 中《黑２》的探探鼠传入《传说 Z-A》时，PKHeX 26.8.26 在没有追踪码的情况下拒绝其隐藏特性，有追踪码时则接受。

模拟神秘礼物也遵循此设置（[神秘礼物 - 模拟](#mystery-gift---simulated)）。PKHeX 仅要求 HOME 发放的礼物具有追踪码：`empty` 留空，`made` 生成追踪码（`services/pkhex/Program.cs` 中的 `MendGift`）。生成追踪码时同步应用 HOME 对见过的宝可梦进行的修改，以满足 PKHeX 检查 [HomeQuirks]：朱／紫的身高等于体型值，传说 Z-A 的身高和体重等于体型值，头目带头目之证（`HomeSeen`）。PKHeX.Core 26.8.26 包含剑／盾此类礼物 16 份，晶灿钻石／明亮珍珠、传说 阿尔宙斯和传说 Z-A 各 4 份，朱／紫 5 份，均通过两种设置的检查。剑／盾通过“官方活动 → Pokémon HOME”发送社区整理的 16 张卡片；游戏机自行生成宝可梦，因此无论设置如何都没有追踪码（[Pokémon HOME](swsh_gift.md#pokemon-home)）。

<a id="importing"></a>

### 导入

银行页的加号按钮，或拖到网格上的文件，可导入宝可梦文件或游戏存档。辅助程序的 `import` 命令用 PKHeX 读取：先执行 `SaveUtil.TryGetSaveFile`，文件名辅助识别（3DS 存档是无扩展名、名为 `main` 的文件）；再通过 `FileUtil.TryGetPKM` 读取 PKHeX 支持的任意单只记录（`.pk1` 到 `.pk9`、`.pb7`、`.pb8`、`.pa8`、`.pa9`、`.ck3`、`.xk3`、`.bk4`、`.rk4` 等）。存档按同行队伍已占用位置、再按盒子已占用位置读取，原文件只读。

| 记录 | 银行保存的内容 |
|---|---|
| 银行支持游戏的记录（`PK3`、`PB7`、`PK8`、`PB8`、`PA8`、`PK9`、`PA9`） | PKHeX 判定合法时，原样保存，保留携带道具和招式 |
| 其他格式 | 按宝可梦不携带道具进入 HOME 的方式移除道具；第三、四世代记录还会忘记秘传招式，因为伙伴公园和宝可传送不接受这些招式。PKHeX 判定合法后，按银行传送规则转到首个可接收的游戏，顺序为火红／叶绿、朱／紫、剑／盾、晶灿钻石／明亮珍珠、传说 阿尔宙斯、传说 Z-A |

PKHeX 判定其原格式不合法时，使用 PKHeX 的理由拒绝；传送时的建议招式不会替代原游戏不允许的招式。错误校验和、来自其他游戏的蛋、任何可到达游戏都没有的种类也会被拒绝。导入宝可梦的 `.json` 包含 `imported`：文件名、位置、源格式及移除的内容。

`Bank/.imported` 为每条导入记录保存键：移除任何内容前，解密后存储字节的 SHA-256。已有键不会再次导入，即使宝可梦已交换出银行；已有相同字节的记录也不会重复存入。游玩后重新导入存档，只会导入发生变化的记录。

一只从火红存档导入的百变怪，通过银行页成功交换到实机《朱》；再次导入该存档时，其 104 条记录都没有重复存入。

一只实机《剑》交换接收的宝可梦移至《传说 Z-A》后，保留了 PID 并使用银行追踪器；实机 Z-A 的交换盒子正确显示其等级和初训家，交换也已完成。

`tests/test_bank.py` 使用真实辅助程序测试六组游戏间传送，检查目标游戏启动器是否接受记录、各项拒绝原因、编辑保存与拒绝，以及交换完成后从银行移除宝可梦。还会导入黑２存档，以及由 PKHeX 遭遇生成器构建的第四、六世代文件（`tests/data/bank_import.json`）：移除道具及秘传招式，拒绝不合法记录，第二次导入不重复存入。

### 尚未解决

- 使用自行生成追踪码传送的宝可梦能否被 Pokémon HOME 接受。HOME 3.1.0 及之后拒绝非 HOME 签发的追踪码（错误 10015），自行生成的追踪码属于此类。
- HOME 能否接受已传送到其他游戏、但追踪码留空的宝可梦。
- HOME 自身的《火红／叶绿》导入规则是否还有画面所列蛋、携带道具及秘传招式以外的限制。
- HOME 为从 Switch 版《火红／叶绿》导入的宝可梦显示的来源图标，究竟由哪个记录字段保存。通过 Pokémon Bank 转移的卡带宝可梦没有该图标（依据玩家截图，本项目尚未测量）。PKHeX.Core 26.8.26 通过伙伴公园迁移链转换 `.pk3`，因此银行从《火红／叶绿》转出的记录可能与 HOME 写入的记录不同。

## GTS

GTS 页面显示其他玩家的有效挂牌，可按提供或想要的宝可梦种类筛选；“我的挂牌与报价”列出我方挂牌和交换请求。“存入宝可梦”选择银行中合法且未加入交换队列的宝可梦；挂牌详情列出符合需求的我方宝可梦。挂牌或等待交换期间，宝可梦位于 `Documents/pokeldn/GTS`，暂时移出银行。一旦有挂牌或交换请求，应用运行时会在任何页面回应请求。事件格式和规则见 [GTS](online.md#the-gts)。

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

“手柄控制”页通过运行手柄固件的开发板控制 Switch 按键并运行宏（[手柄开发板](hardware_pad.md)）。在“开发板”页为 ESP32-S3 或经典 ESP32 安装手柄固件。S3 连接到 Switch 的 USB-C 接口，点击“连接”后通过蓝牙 LE 连接；经典 ESP32 保持 USB 连接到电脑，并从 HOME → 手柄 → 更改握法／顺序与 Switch 配对，“连接”通过其串口通信。重新安装固件会清除配对。

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

<a id="pokemon-sprites"></a>

## 宝可梦精灵图

宝可梦图像来自 [PokeAPI](https://github.com/PokeAPI/sprites)，按需下载。下载的图像缓存在应用数据目录的 `sprites/` 中，离线时也可使用。

“设置 → 宝可梦图像”可关闭下载，已有缓存仍会显示；同一区域提供清除精灵图缓存按钮。

种类或形态没有可用图像时显示占位图。缺少异色图时，显示相同形态的普通图。图像缺失不会影响生成或交换宝可梦。

<a id="raid-events"></a>

## 团体战活动

《朱／紫》的“太晶团体战（主持）”入口通过“团体战活动”卡片主持 Project Pokemon [EventsGallery](https://github.com/projectpokemon/EventsGallery) 中的活动（[活动团体战](sv_raid.md#event-raids)）。应用将活动库中的团体战活动保存为数据目录下的 `EventsGallery/` 副本（`pokeldn.app.events_gallery`）；“清除本地文件”会保留此目录。

| 操作 | 行为 |
|---|---|
| 下载 | 向 `api.github.com` 查询 master 分支中最后修改 `Released/Gen 9/SV/Raid Events` 的提交，下载 `codeload.github.com/projectpokemon/EventsGallery/zip/<commit>`（2026 年 10 月为 22 MB），解压各活动最新补丁的四张表，约 17 MB；`gallery.json` 保存提交和日期 |
| 检查更新 | 请求一次最新提交；若与本地副本不同则有更新，活动库其他目录的修改不计入 |
| 更新 | 重新执行下载 |

新副本只有在完整下载后才替换旧副本；失败或取消时保留旧副本。活动目录名最长达 152 个字符，因此 Windows 上使用 `\\?\` 路径打开文件。

活动列表包含副本中除 `000 Base Data`（游戏自己的表）外的全部活动：2026-09-06 时为 152 个。默认按时间降序排列，旁边箭头可切换顺序。每项上方显示去除编号的目录名称，多轮活动显示为“活动 · 轮次”，下方显示首领；输入文字可同时筛选活动和首领。选择后：

- 团体战卡片只提供该活动支持的游戏版本、帕底亚地区、所选结晶可生成的进度，并用该版本的活动结晶替换普通结晶选项。各结晶对应一个分发组，显示星级和首领（如“7 星：喷火龙”“4-5 星：花洁夫人、谜拟丘”）。无法生成的值会调整为最接近的可用值（`raid_event.constrain`）。
- “查找团体战”仅搜索活动结晶，每个阶段对应一种进度，种类列表使用活动首领。“奖励”区域提供该活动奖励表中的道具和数量（[查找种子](sv_raid.md#finding-a-seed)；`gui/views/reward_filter.py`）。“可获得的体型证章”会将所选结晶、星级和种类的首领不可能获得的证章选项置灰（[体型证章](sv_raid.md#size-marks)）。
- 若某首领每个存档只能捕获一次，则显示“允许再次捕获”（`--raid-catch-normal`）。每次启动应用或更换活动时都默认不勾选（[活动团体战](sv_raid.md#event-raids)）。

折叠卡片后暂时停用活动（工具值中的 `#raid-event-folded`，`GamesView.show_raid_event`）：团体战卡片、“查找团体战”和命令都改为普通团体战，标题显示“已关闭：活动”。展开后恢复活动。启动时若正在使用活动，卡片自动展开。副本中缺少的活动（尚未下载，或更新后被移除）仍保持选中：标题以红色显示“缺失：活动”，在下载到该活动或改选其他活动前禁止运行（`pokeldn.app.command.code_error`）。

<a id="hosted-raid-rewards"></a>

## 主持团体战的奖励

“太晶团体战（主机）”工具的“奖励”卡片提供培育道具、太晶碎块（包括星晶）、秘传调味料、贵重道具及精灵球模板。选择组合会替换当前奖励列表。“每种道具数量”统一设置该组合内每行的数量，范围为 1 至 999。单独修改道具或数量会切换到“自定义奖励”；可添加或移除奖励，最多 45 行。未填写完整的奖励或无效数量会阻止启动，保存时会保留各项道具和数量。

“团体战原有奖励”会清除覆盖设置，使用所选团体战的奖励表（[主持](sv_raid.md#hosting)；`gui/views/rewards.py`）。

<a id="raid-npc-partners"></a>

## 团体战 NPC 搭档

“太晶团体战（主持）”工具在“加入的游戏机数量”下方提供 NPC 搭档卡片，为游戏机留下的空位选择训练家：一台时两名、两台时一名、三台时没有（[NPC 搭档](sv_raid.md#partners)；`gui/views/raid_partners.py`）。未选择时不传递参数，主持方按游戏机的方式从剧情进度对应池中抽取。

- 搭档进度：五个解锁阶段，不含游戏初期；默认跟随剧情进度，黑色结晶或七星活动使用六星。选择其他阶段时传递 `--raid-partner-progress`。
- 对应阶段的训练家卡片每行三张，窄窗口每行两张。卡片显示训练家、宝可梦、等级（我方宝可梦等级的五分之四，`command.raid_pokemon_level`）和太晶属性，再逐行列出特性及三个招式。推荐搭档末尾有金色或银色星标与理由（[推荐搭档](sv_raid.md#favoured-partners)），提示中提供更详细的说明。

点击选择训练家，并按占用空位的顺序编号；再次点击改为随机安排。每个选择依次传递 `--raid-partner`。增加加入游戏机数量会移除最后一项；对应阶段没有的训练家（四星以下的 Dylan、Luke）也会移除。折叠只隐藏卡片（`GamesView.show_raid_partners`），仍将选择传入团体战，标题显示当前选择。

<a id="mystery-gift---simulated"></a>

## 神秘礼物 - 模拟

Let's Go、晶灿钻石／明亮珍珠、传说 阿尔宙斯、朱／紫和传说 Z-A 的“神秘礼物 - 模拟”卡片列出 PKHeX 活动表中的礼物宝可梦（[模拟神秘礼物](gift_simulated.md#the-gifts)；`gui/views/event_gifts.py`）。每行两张，按时间从新到旧排序；显示精灵图、卡片标题、宝可梦、初训家和日期，悬停显示招式。每次显示二十四张，“显示更多”再添加同样数量；可搜索卡片内容、精灵球、招式及卡片编号。十张以内完整显示，超过时在独立区域滚动（`event_gifts.FIT`）。

点击后按设置中的训练家新生成副本，追加到列表上方的队列，并显示合法性、招式和 OT。一场主持会话最多依次交换六份礼物；同一活动可多次选择，每次独立生成副本。开始前可用关闭按钮移除队列中的礼物；队列满时须先移除一项才能继续添加。副本保留生成时的训练家，修改训练家设置后需移除并重新选择。以接收玩家为初训家、却未向设置语言分发的礼物，如 Let's Go 中国大陆美录坦和美录梅塔对应其他语言存档，会标为不合法并说明原因；点击后提示原因并保留原提供记录（[卡片覆盖的存档](gift_simulated.md#saves-a-card-reached)）。“高级”中的“按接收玩家生成”默认开启，交换时按游戏机存档重新生成此类礼物（[按接收玩家生成](gift_simulated.md#made-for-the-receiving-player)）。具有固定初训家的礼物按原样提供；所有队列礼物均按原样提供时，关闭、锁定并淡化开关，说明原因（`command.locked`），启动时不传递 `--for-receiver`。队列包含可按接收玩家生成的礼物时，恢复之前开关状态，主机对各份符合条件的卡片应用此选项。

除 Let's Go 外，HOME 礼物按 [HOME 追踪码设置](#the-home-tracker-setting) 处理。卡片以琥珀色边框标出，卡片和选中副本均显示“PKHeX 提示缺少 HOME 追踪码”或“无法存入 HOME”。交换仍按普通提供记录处理（[交换提供的副本](gift_simulated.md#the-copy-a-trade-offers)）。

<a id="private-logs"></a>

## 日志隐私

“设置 → 隐藏日志中的个人信息”默认启用，会在应用显示和复制的会话日志、开发板日志中遮罩以下内容（`pokeldn/app/redact.py`）：

| 遮罩内容 | 替换显示 | 保留内容 |
|---|---|---|
| 路径中的用户目录（`/Users/NAME`、`/home/NAME`、`C:\Users\NAME`） | `~` | 路径的其余部分 |
| iOS 应用容器（`/var/mobile/Containers/Data/Application/UUID`） | `<app>` | |
| MAC 地址的设备部分，支持带冒号和不带冒号的格式 | `**:**:**`、`******` | 厂商部分（任天堂、乐鑫） |
| `ot_name`、`ht_name`、`OT`、`nickname`、`trainer`、`player` 或 `name` 后带引号的值（`'…'`、`"…"`、`b'…'`） | `***` | 应用自身名称 `POKELDN`、`PKLDN`，不区分大小写 |
| `TID`、`SID`、`tid`、`sid`、`trainer_id` 后的值 | `***` | |
| 本次运行中曾出现的训练家姓名，以及设置中的训练家姓名，再次作为完整单词出现时 | `***` | |

昵称只在其原位置被遮罩，不会在其他位置替换，因为它经常与宝可梦种类名称相同。会话录制（`captures/`）保存原始消息，不进行遮罩。本地连接地址（`169.254.x.x`、`127.0.0.x`）不用于识别个人，因此保留。

<a id="pop-ups"></a>

## 弹窗

应用启动的任务、其他子进程或应用自身代码，可在当前页面上显示弹窗（`pokeldn.popup`，插件 API 1.2 起支持）。有三种类型：

| 类型 | 按钮 | 回调 |
|---|---|---|
| `acknowledge(title, text)` | 单个 `label` 按钮（OK） | `on_ack`：按钮、Esc 或点击外部 |
| `confirm(title, text, agree, disagree)` | 调用方指定的同意和不同意按钮 | `on_agree`、`on_disagree` 或由 Esc、点击外部触发的 `on_dismiss` |
| `choose(title, text, options)`（1.7） | 2 至 8 个选项按钮，按调用方顺序在文字下方铺满宽度 | `on_choice(index)`，或由 Esc、点击外部触发 `on_dismiss` |

打开弹窗不会阻塞，立即返回弹窗 ID；用户回答通过回调稍后到达。默认在读取应用回答的线程执行；`set_dispatcher(dispatch)` 可将其交给程序自身循环。应用中的回调由工作线程执行，以免窗口阻塞。回调异常会打印堆栈。

| 选项 | 行为 |
|---|---|
| `id` | 标识程序自身的弹窗；使用仍打开的 ID 时原地替换并移除旧回调，未指定则新生成 |
| `tone` | `info`、`warning` 或 `error`，决定图标 |

`cancel(id)` 关闭弹窗；`cancel` 返回后不触发回调，已交给调度器的旧回答除外。同时等待回答的弹窗达到 32 个时，程序收到 `RuntimeError`。标题标明来源工具、开发板安装程序或手柄服务；应用自身弹窗不标来源。

程序退出后，确认和选择弹窗关闭，通知弹窗保留但不再返回回答。没有应用时（终端中 `available()` 为假），弹窗仅作为 `[pop-up]` 输出行，无回答且不计入 32 个上限。

`runner.Process(..., popups=app.popups, label=...)` 在子进程设置 `POKELDN_POPUPS=1`。子进程在 stdout 发送 `[popup]` 行和 JSON；应用从日志中过滤此行，即使它夹在其他线程输出中也能识别。应用通过子进程 stdin 回复 `[popup] {"id", "n", "answer"}`（选择弹窗的回答为选项索引 `"0"` 至 `"7"`），由 `pokeldn.app.runner.child` 读取。`n` 区分同一 ID 下重新打开的弹窗，替换后迟到回答不会触发旧回调。应用代码通过 `popup.attach` 直接访问管理器。`pokeldn.app.popups.Manager` 保存打开的弹窗，`gui.popups.Dialogs` 绘制它们。`page.pop_dialog()` 只关闭应用自己的顶部对话框，不会关闭之后覆盖其上的程序弹窗。

<a id="progress"></a>

## 进度

任务打印 `[progress] DONE TOTAL UNIT TITLE`（`pokeldn.progress.show`，插件 API 1.7；`UNIT` 为 `bytes` 或 `items`），会在会话面板中显示进度条，代替日志行；内容包括已完成数量（如 `1.05 of 5.20 GB`）、最近 30 秒的速率和剩余时间。`show` 对每个标题每秒最多打印四行，最后一行始终打印。存档备份和恢复的 `[save]` 行使用同一进度条。

模拟神秘礼物按接收玩家生成失败、改用设置中的训练家时，会弹出原因：无法识别存档，或在卡片、PKHeX、提供记录检查、加载器阶段失败（[交换流程](gift_simulated.md#the-trade)）。每台游戏机一个弹窗（`receiver_gift.pop_up`），新原因替换旧提示。应用自身也会为更新失败和已停用插件显示弹窗。

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
| 源码检出、从 Downloads 运行的 macOS 应用（App Translocation）、macOS 或 Linux 中用户不可写的文件夹 | 显示“下载”及原因 |
| Windows 中用户不可写的文件夹（`C:\Program Files`） | 显示“立即更新”；辅助程序启动前 Windows 请求管理员权限（UAC），拒绝后应用保持原样 |
| 会话、刷写或清理正在运行 | 立即更新要求先结束操作 |
| 校验和不符或下载失败 | 应用不变，对话框提供下载按钮 |

在 Windows 中，若文件夹仅管理员可写，辅助程序通过 `ShellExecuteExW` 的 `runas` 动词启动，在解压出的副本旁读写更新结果（管理员辅助程序可能以其他用户运行），并通过 Explorer 打开新应用，恢复用户自身权限。`scripts/check_update.py ARCHIVE FOLDER` 以 127.0.0.1 提供的发行版测试打包应用自己的更新流程；Update check 工作流使用 Release 运行的压缩包，在 Windows 的用户文件夹和 `C:\Program Files`，以及 Linux 上运行此检查。

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

<a id="the-docs-page"></a>

## 文档页面

“文档”页显示应用指南和网站导航中列出的全部文档。页面列表上方的搜索框按章节搜索：匹配每个标题及其下方的正文，查询中的每个词都必须出现。标题或页面名称包含关键词的结果优先显示。点击结果会定位到对应标题；`page.md#heading` 形式的链接也会滚动到相应章节（`gui/views/docs.py`）。

<a id="unreleased-titles"></a>

## 尚未发布的游戏

为尚未推出 Switch 版本的游戏预先准备的支持，仅在从源码目录运行时显示于游戏列表、银行和文档页（`pokeldn/app/preview.py`）。发行包已冻结且不含 `.git`，因此默认不显示。`POKELDN_PREVIEW=1` 可在任何环境显示；`POKELDN_PREVIEW=0` 可在源码目录隐藏。对应文档设置 `nav_exclude` 和 `search_exclude`。

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
export POKELDN_BLE=1   # the Bluetooth builds for the iOS app (hardware_esp32.md, Bluetooth)
BLE_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.ble"
idf.py -B build/ble -D SDKCONFIG="$PWD/build/ble/sdkconfig" -D SDKCONFIG_DEFAULTS="$BLE_DEFAULTS" set-target esp32
idf.py -B build/ble -D SDKCONFIG="$PWD/build/ble/sdkconfig" -D SDKCONFIG_DEFAULTS="$BLE_DEFAULTS" build
idf.py -B build/ble merge-bin -o "$POKELDN_IMAGES/pokeldn-radio-ble.bin"
idf.py -B build/ble-c6 -D SDKCONFIG="$PWD/build/ble-c6/sdkconfig" -D SDKCONFIG_DEFAULTS="$BLE_DEFAULTS" set-target esp32c6
idf.py -B build/ble-c6 -D SDKCONFIG="$PWD/build/ble-c6/sdkconfig" -D SDKCONFIG_DEFAULTS="$BLE_DEFAULTS" build
idf.py -B build/ble-c6 merge-bin -o "$POKELDN_IMAGES/pokeldn-radio-ble-c6.bin"
unset POKELDN_BLE
cd ../pad
idf.py -B build -D SDKCONFIG="$PWD/build/sdkconfig" set-target esp32s3
idf.py -B build -D SDKCONFIG="$PWD/build/sdkconfig" build
idf.py -B build merge-bin -o "$POKELDN_IMAGES/pokeldn-pad-s3.bin"
cd ../..
python scripts/build_client.py
python scripts/build_unicorn.py
python scripts/pack_app.py
```

绝对输出路径使镜像保留在 `gui/firmware`。打包器要求无线、蓝牙无线和手柄固件镜像、`scripts/build_client.py` 构建的客户端，以及 `scripts/build_unicorn.py` 构建的 Unicorn（需要 CMake）；冻结应用自检确认它们均已包含，且随包客户端支持 `flet_drop`。发布工作流分别构建各目标，再向每个平台的桌面打包器提供全部镜像。

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
