---
title: Mystery Gift files
---
# 神秘礼物文件

`.pokegift` 文件存储火红／叶绿或剑／盾或 FRLG ARM 游戏机的完整神秘礼物分布及其目标游戏和本地记录。
## 桌面应用程序

游戏中，神秘礼物是每场游戏一个工具，有三种选择礼物的方式，剑／盾有四种。一名建造者负责两种游戏；每个游戏的模块提供其预设及其形式（`pokeldn/frlg/gift/builder.py`、`pokeldn/swsh/gift_builder.py`，绑定在`pokeldn/app/gift_builder.py`中）。

|模式 |它发送什么 |
|---|---|
|使用预设 |内置礼物； FRLG Wonder Cards、神奇新闻和游戏机代码作为标志进入启动器 |
|官方活动 |一张真正的剑／盾活动卡（[官方活动卡](swsh_gift.md#official-event-cards)），像礼物一样编译|
|打造您自己的 |该表单在 Start 处编译为 `session/gifts/<tool>.pokegift` 并作为 `--gift-file` | 传递
|打开文件 |剑／盾上的共享`.pokegift`，或`.wc8` |

FRLG 游戏增强是常驻挂钩 ([`install-resident`](frlg_rom.md#install-resident))。可以同时勾选多个；它们作为一条链运行（[一次有多个钩子](frlg_rom.md#several-hooks-at-once)）。每个都带有成为启动器的 `--resident-param` 标志的设置，并且面板显示了游戏机具有的 1024 个勾选设置所占用的字节。

|提升|设置|参数|
|---|---|---|
|加快游戏速度（`turbo-lite`）|速度x1至x4；主世界、战斗或两者兼而有之；始终开启或按住 R、B 或 Select 时；更快的文本| `field` 和 `battle` = 速度 - 1，`budget=228` 来自 x3，`hold`，`extra=4` |
|穿墙| R、B 或选择 | `hold` |
| 异色倒计时|减速按钮；慢 2 倍、4 倍或 8 倍 | `slow`、`slow_frames` 1、3 或 7 |
|没有狂野的遭遇，Lead的IV出现在屏幕上，宝可梦的追随者|无 | |

不提供 L：只有 R 的帮助系统切换开关有一个钩子保持关闭的标志。保存增强以供以后发送 `save-write --resident` 代替 `install-resident`：该集进入 `filler_B20` 并安装在同一会话中。一组过去的 `install-resident` 会话（876 字节），以及跟随者，总是经过保存。妈妈恢复你的提升绑定妈妈的加载器，并在任何引导安装保存保存的任何设置后与妈妈交谈。再次发送提升将取代设置运行。该应用程序在保存选项旁边和发送之前显示恢复步骤，包括必须保存的集。预设名称和描述会换行，因此它们的说明仍然可见。
`tests/test_gift_builder.py` 通过所有四个弹药筒的发射器发送每种增强组合及其每种设置。

读取保存的训练家 ID (TID) 和秘密 ID (SID)、训练家详细信息和比赛时间，以及最后保存的队伍性质、IV 和 EV。结果出现在会话日志中；两个转储预设还将读取的数据写入 Received 中。该小组将通常隐藏的 SID、IV 解释为从 0 到 31 的六个单独值，将 EV 解释为训练点。这些读取保留了保存和神奇关联（[读取保存](frlg_rom.md#reading-the-save)）。

本机 `.wc3` 和 `.wc8` 扩展在 JSON 检测之前选择游戏的二进制读取器。 WC8的二元密封可以以`{`开头；它仍然是本地记录。 `.pokegift` 文件使用 JSON 读取器，带有 JSON 左大括号的未知扩展名仍然可以保存共享礼物。

自定义将预设复制到表单中。 FRLG卡预设仅在形式表达每一步时提供它：宝可梦、物品、蛋、狂野战斗和消息步骤的无条件阶段，没有事件脚本，也没有来访的训练家。每个剑／盾预设都是一个形态状态。

FRLG 形式构建了神奇关联、神奇新闻或游戏机代码。

|部分|内容 |
|---|---|
|卡 |标题，副标题，四行文本，图标种类，卡片ID 1000至1019，再次收到，可共享|
|谁把它交给了|宝可梦中心的送货员、玩家家的妈妈、南托盘镇的男人 |
|步骤| 宝可梦（种类、等级、持有物品、四招）、物品及数量、彩蛋、野战、留言 |
|新闻 |标题，最多十行，新闻 ID |
| 游戏机代码 | ARM 源或预构建的 `.bin`，其构建的盒式磁带，预期答案，发回的字节 |

每个步骤都是其自己的交付阶段，因此完整的队伍或袋子会停在该步骤处，并且玩家仅重试剩下的部分。送货员以外的人扶着台阶通过
`initramscript` 绑定；该卡在绑定时不会显示。绑定脚本不带有收据标志：该人每次都会给出步骤，直到另一个礼物替换绑定。种类使用盒式磁带的内部编号 (`pokeldn/frlg/save/species_names.py`)。卡片和新闻均适用于所有四种墨盒； 游戏机代码可针对所有四个或选定的一个进行编译。

当控制台代码位于 PATH、Homebrew 文件夹或 Arm 的 Windows 安装文件夹下时，控制台代码使用 `arm-none-eabi-as` 进行汇编；如果没有它，该表单将采用预构建的 `.bin` 并显示在此系统上安装汇编器的命令：

|系统|命令 |
|---|---|
| macOS | `brew install arm-none-eabi-binutils` |
|软呢帽| `sudo dnf install arm-none-eabi-binutils-cs` |
| Debian、Ubuntu 及其衍生产品 | `sudo apt install binutils-arm-none-eabi` |
|窗户 | `winget install Arm.ArmGnuToolchain` |

另一个 Linux 发行版获得了 Arm 的下载页面。 Fedora 44 和 Ubuntu 24.04 软件包将默认模板组装为 `01 00 a0 e3 1e ff 2f e1`。离线检查在模拟游戏机（`pokeldn/frlg/rom/custom_code.py`）上运行一次代码并显示答案和字节。在开始之前和保存文件之前运行相同的检查：出错或从不返回 1 的代码将被拒绝。

剑/盾形态可以构建一个宝可梦（可以选择超极巨化）、一个蛋、最多六件包物品、官方服装、战斗点数或金钱，以及卡ID。宝可梦、蛋、物品、服装和战斗积分类型写入列出并兑换的零售剑的记录字节（[剑和盾 神秘礼物](swsh_gift.md#a-card-delivered-to-a-retail-console))；皮卡丘预设是启动器自己的默认记录的逐字节。服装来自成对的官方服装卡（[服装](swsh_gift.md#clothing)），每个玩家性别最多六件。 PKHeX 拒绝在没有 Gigantamax 形式的物种上使用 Gigantamax 标志。

在发送之前列出游戏机获得的内容、运行时间以及礼品提供的墨盒。保存礼物文件将所选礼物写入为 `.pokegift`，无板且无开关键。 FRLG 预设会通过启动器自己的构建器，因此该文件包含他们构建的每个墨盒变体。游戏机的游戏代码在礼物握手期间选择变体；在发送礼物数据之前，文件中不存在的磁带会被拒绝。预设的卡 ID 位于“高级”选项卡上（`--flag-id`，1000 到 1019）。

该应用程序不会在导入时修改礼品文件。文件保留在所选路径中。

从零售游戏机上打开的文件交付：法国火红上的时拉比卡和游戏机代码文件，剑上的皮卡丘卡。以保存的训练家 ID 回答的形式构建的控制台代码。
## 命令行

两个礼品发射器均接受 `--gift-file FILE`。 剑／盾保留`--record`作为别名。
`--export-gift FILE` 在使用收音机之前保存所选的礼物并退出。

```bash
./.venv/bin/python bin/frlg_mg_host.py --gift celebi --export-gift celebi.pokegift
./.venv/bin/python bin/frlg_mg_host.py --news berry --export-gift news.pokegift
./.venv/bin/python bin/swsh_gift_host.py --species 25 --level 25 --export-gift pikachu.pokegift
./.venv/bin/python -m pokeldn.gifts inspect celebi.pokegift
```
 FRLG 礼品文件一起定义了卡旗 ID、脚本、问卷和拒绝消息。诸如 `--flag-id`、`--questionnaire` 和 `--hunt-*` 之类的有效负载覆盖将被拒绝。无线收发设备、教练身份和磁带选择选项仍然是会话设置。
### 控制台代码

导出内置的发票及其配置的字节和响应设置：

```bash
./.venv/bin/python bin/frlg_mg_host.py --buffer-script save-dump --dump-size 64 \
  --export-gift save-dump.pokegift
```
 作者可以使用显式的卡带目标打包自己的原始 ARM 代码：

```bash
arm-none-eabi-as -march=armv4t -mcpu=arm7tdmi -o payload.o payload.s
arm-none-eabi-objcopy -O binary -j .text payload.o payload.bin
./.venv/bin/python -m pokeldn.gifts import --game frlg --code payload.bin \
  --build BPRF --name "Custom payload" --expect 66 -o custom.pokegift
```
 最小的 `payload.s` 将 66 写入响应参数并在一次调用中完成：

```asm
.syntax unified
.arm
.text
.global _start
_start:
    mov r3, #66
    str r3, [r0]
    mov r0, #1
    bx lr
```
 代码必须是位置独立的 ARMv4T、字对齐且最多 1024 字节。游戏机通过`r0 = &param`、`r1 = gSaveBlock2Ptr`和`r2 = gSaveBlock1Ptr`；它每帧调用一次 SAT，直到返回 1。执行合约请参见[控制台代码](frlg_rom.md)。没有
`--expect`，接受任何返回的参数。重新指向字节缓冲区的响应的栏在打包时使用 `--dump-size N`。

共享 `.pokegift` 文件。收件人在 FRLG、神秘礼物上打开它，或者用
`--gift-file custom.pokegift`。 `--dump-file PATH` 选择主机写入返回转储的位置。在发送代码之前强制执行墨盒变体。包装验证结构和尺寸；作者必须在实时运行之前使用 `buffer_script.emulate_repeating` 离线执行新的有效负载。文件哈希并不能证明本机代码返回或保持保存完好无损。
### 原生格式

转换器导入剑／盾WC8记录、FRLG `.wc3`文件以及所使用的配对FRLG文件
`pokemon-gen3-mysterygift-tool`。 `.wc3` 或 `.wc8` 也可直接在应用程序的“打开文件”和 `--gift-file` 中打开。

其可达代码不包含绝对地址的 FRLG 脚本为所有四个磁带提供服务 (`BPRF`、
`BPGF`、`BPRE`、`BPGE`)：其跳转和文本是相对于其自身的 `vgoto`/`vmessage` 操作数
`setvaddress` [scrcmd.c:171]，物品来自 `callstd`。带有 `goto`、`call` 的脚本，
`message`、`callnative`或其他绝对指针属于一个墨盒，需要`--build`；一个
`.wc3`之类的直接打开是拒绝的。

```bash
./.venv/bin/python -m pokeldn.gifts import --game swsh --record event.wc8 -o event.pokegift
./.venv/bin/python -m pokeldn.gifts import --game frlg --wc3 "FL - Item AuroraTicket (FRE).wc3" -o aurora.pokegift
./.venv/bin/python -m pokeldn.gifts import --game frlg --card WonderCard.bin \
  --script Script.bin --name "Event gift" -o event.pokegift
./.venv/bin/python -m pokeldn.gifts export celebi.pokegift --build BPRF --out-dir native-gift
./.venv/bin/python -m pokeldn.gifts export celebi.pokegift --wc3 --out-dir native-gift
./.venv/bin/python bin/frlg_mg_host.py --gift celebi --export-gift celebi.wc3
```
 保存到以 `.wc3` 或 `.wc8` 结尾的路径会写入该本机文件而不是 `.pokegift`：
`--export-gift`，在保存礼品文件和`pokeldn.gifts.save`中。 `.wc3` 容纳一个卡带的卡和脚本；如果没有 `--build`，礼物的每个变体都必须携带相同的字节，就像相关脚本一样。 `.wc3` 元数据块除其图标外均写入零，该图标重复卡片的图标。游戏接受的每个国际图库文件在导入和导出后都会返回相同的卡片、脚本和图标字节。

`.wc3` 为 1420 字节 (`0x58C`)：

|偏移|尺寸|内容 |
| --- | --- | --- |
| `0x000` | 336 | 336卡的CRC16，2个填充字节，332字节 `struct WonderCard` |
| `0x150` | 80|保存端卡元数据；没有读过|
| `0x1A0` | 1004 | 1004 CRC16，2 个填充字节，`struct RamScriptData`（魔法 51，地图组，地图编号，对象 id，995 字节脚本），1 个填充字节 |

宝可梦项目EventsGallery的全部54个国际文件中，文件中的脚本CRC占1000字节，包括填充字节；游戏本身涵盖999 [script.c:488]。导入接受其中之一。
导入时的 `--icon N` 或在应用程序中打开文件下的卡图标，将卡的 `iconSpecies`（卡的偏移量 2）设置为从 0 到 411 的内部物种 ID； 0 不绘制图标
[mystery_gift_show_card.c:466]。

日语 `.wc3` 文件为 1252 字节 (`0x4E4`)，被拒绝：Switch 卡带为法语和英语。每个国际画廊的脚本都是相对的，并服务于所有四个墨盒。画廊的标记 id 为 4 到 8 的调试卡被拒绝：送货员只为标记 id 1000 到 1019 [mystery_gift.c:241] 提供礼物。极光和神秘门票在首次名人堂之后无法保存（[极光和神秘门票](frlg_gift.md#the-aurora-and-mystic-tickets)）。

FRLG 对包含一个 336 字节的卡和一个 1004 字节的 RAM 脚本结构。导入会验证 CRC 和脚本未绑定的神秘礼物标头。原生配对不能携带邮票、客座训练家、神秘事件脚本、问卷门或神奇新闻。导出到该对拒绝与这些额外内容一起分发。 `.pokegift` 将它们保存在一起。
## 版本 2

该文件是 UTF-8 JSON，具有五个必填字段：

|领域 |价值|
| --- | --- |
| `format` | `pokeldn.gift` |
| `version` |整数 `2` |
| `game` | `frlg` 或 `swsh` |
| `name` |非空显示名称，最多 180 个字符 |
| `variants` |对象将目标代码映射到本机数据和选项|

每个变体都有 `data` 和 `options` 对象。 `data` 中的组件具有 `hex`（编码为十六进制的本机字节）和 `sha256`（其小写 SHA-256 摘要）。 JSON 字段顺序没有意义。导出对确定性文件的字段进行排序。

|游戏|变体键 |数据组件|选项|
| --- | --- | --- | --- |
| FRLG 礼品 |支持的墨盒代码 | `card`、`ram_script`、`stamp`、`activation_script`、`install_activation_script`、`trainer`、`news`、`mevent` | `questionnaire`，`denied_message` |
| FRLG 游戏机代码 |支持的墨盒代码 | `buffer_code`, `buffer_lead_1`.. |下面的响应设置 |
| 剑／盾 | `swsh` | `wc8` |无 |

FRLG 卡变体具有相同的旗帜 ID 和礼品类型。 神奇新闻和游戏机编码每次独自旅行。捕获、密钥、文件系统路径和会话计时不属于此格式。

FRLG 游戏机代码变体只有一个 `buffer_code` 组件，并且在与 `buffer_lead_1`、`buffer_lead_2` 等相同的会话中，在其之前运行最多 8 个有效负载，编号无间隙（保存中保存的驻留钩子将 `filler_B20` 与它们一起写入，然后安装它）。其可选响应设置为 `buffer_expect`（32 位无符号整数或 `trainer-id`）、`buffer_dump_size`、
`buffer_dump_blocks`、`buffer_dump_address`、`buffer_dump_addresses` 和 `buffer_decode`。转储大小为每个块 1 到 1024 字节，最多 32 个块；分散转储为每个块命名一个地址。解码器名称来自现有的响应解码器。转储输出路径和本地 ROM 比较路径保留在主机上，并且从共享文件中排除。

读者还接受包含卡片、新闻或 WC8 的版本 1 文件。导出使用版本 2，添加了游戏机代码和整数响应设置。版本 1 读者拒绝版本 2 文件。

读者拒绝未知的版本、字段和目标代码、重复的 JSON 字段、无效的哈希值、大于 256 KiB 的文件、无效的本机大小和无效的组件组合。 FRLG 验证还检查卡字段、训练家校验和和神秘事件终止。 剑／盾传送在打开收音机之前仍然需要共享PKHeX礼物验证。

哈希检测损坏的字节。它们不会验证分发者或证明导入的 FRLG 脚本可以安全执行。本机脚本导入保留指令并需要明确的盒式磁带目标。
## 执行

`pokeldn.gifts` 拥有信封、验证发送、读取器、写入器和转换器。游戏特定的编解码器位于 `pokeldn.frlg.gift.file` 和 `pokeldn.swsh.gift_file` 中。共享应用程序适配器调用启动器自己的构建器； GUI 对这两款游戏都使用一个选择器和导出控制。

FRLG 文件适配器构建现有的 `MysteryGiftDistribution`，包括其磁带选择和拒绝路径。剑／盾适配器提供现有的WC8广告生成器。无线协议和书签布局保持不变。
