---
title: Mystery Gift files
---
# 神秘礼物文件

`.pokegift` 文件存储火红／叶绿或剑／盾或 FRLG ARM 游戏机的完整神秘礼物分布及其目标游戏和本地记录。
## 桌面应用程序

> 本节已随上游更新，以下内容暂保留英文。

Games, Mystery Gift is one tool per game with three ways to choose the gift, four on Sword/Shield.
One builder serves both games; each game's module supplies its presets and its form
(`pokeldn/frlg/gift/builder.py`, `pokeldn/swsh/gift_builder.py`, bound in `pokeldn/app/gift_builder.py`).

| mode | what it sends |
|---|---|
| Use a preset | a built-in gift; FRLG Wonder Cards, Wonder News and console code go to the launcher as flags |
| Official events | a real Sword/Shield event card ([Official event cards](swsh_gift.md#official-event-cards)), compiled like a built gift |
| Build your own | the form, compiled to `session/gifts/<tool>.pokegift` at Start and passed as `--gift-file` |
| Open a file | a shared `.pokegift`, or a `.wc8` on Sword/Shield |

The FRLG Game boosts are the resident hooks ([`install-resident`](frlg_rom.md#install-resident)).
Several can be ticked at once; they run as one chain ([Several hooks at once](frlg_rom.md#several-hooks-at-once)).
Each carries settings that become the launcher's `--resident-param` flags, and the panel shows the
bytes the ticked set takes of the 1024 the console has.

| boost | settings | parameters |
|---|---|---|
| Speed up the game (`turbo-lite`) | speed x1 to x4; overworld, battles or both; always on or while R, B or Select is held; faster text | `field` and `battle` = speed - 1, `budget=228` from x3, `hold`, `extra=4` |
| Walk through walls | R, B or Select | `hold` |
| Shiny countdown | the slow-down button; x2, x4 or x8 slower | `slow`, `slow_frames` 1, 3 or 7 |
| No wild encounters, Lead's IVs on screen, Pokemon follower | none | |

L is not offered: only R's Help System toggle has a flag the hooks hold off. Save boosts for later
sends `save-write --resident` in place of `install-resident`: the set goes into `filler_B20` and is
installed in the same session. A set past one `install-resident` session (876 bytes), and the
follower, always go through the save. Mom restores your boosts binds Mom's loader, and talking to Mom
after any boot installs whatever set the save holds. Sending boosts again replaces the set running.
The app shows the restore steps beside the save option and in Before you send, including for sets
that must be saved. Preset names and descriptions wrap so their instructions remain visible.
`tests/test_gift_builder.py` sends every combination of boosts, and every setting of each, through the
launcher for all twelve cartridges.

Read the save offers Trainer ID (TID) and Secret ID (SID), trainer details and play time, and the
last saved party's natures, IVs and EVs. Results appear in the Session log; the two dump presets
also write the read data into Received. The group explains the normally hidden SID, IVs as six
individual values from 0 to 31, and EVs as training points. These reads preserve the save and
Wonder Card ([Reading the save](frlg_rom.md#reading-the-save)).

Native `.wc3` and `.wc8` extensions select the game's binary reader before JSON detection.
A WC8's binary seal can start with `{`; it remains a native record. `.pokegift` files use the
JSON reader, and an unknown extension with a JSON opening brace can still hold a shared gift.

Customize copies a preset into the form. A FRLG card preset offers it only when the form expresses
every step: unconditional stages of Pokemon, item, egg, wild battle and message steps, no event
script and no visiting trainer. Every Sword/Shield preset is a form state.

The FRLG form builds a Wonder Card, Wonder News or console code.

| part | contents |
|---|---|
| card | title, subtitle, four text lines, icon species, card id 1000 to 1019, received again, shareable |
| who hands it over | the delivery man in any Pokemon Center, Mom in the player's house, or the man in south Pallet Town |
| steps | Pokemon (species, level, held item, four moves), item and quantity, egg, wild battle, message |
| news | title, up to ten lines, news id |
| console code | ARM source or a prebuilt `.bin`, the cartridge it is built for, expected answer, bytes sent back |

Each step is its own delivery stage, so a full party or bag stops at that step and the player
retries only what is left. A person other than the delivery man holds the steps through an
`initramscript` binding; the card is not shown while it is bound. A bound script carries no
receipt flag: that person gives the steps every time until another gift replaces the binding. Species use the cartridge's
internal numbering (`pokeldn/frlg/save/species_names.py`). Card and news compile for all four
cartridges; console code compiles for all four or for the one chosen.

Console code is assembled with `arm-none-eabi-as` when it is on the PATH, in Homebrew's folders or
under Arm's Windows install folder; without it, the form takes a prebuilt `.bin` and shows the
command that installs the assembler on this system:

| system | command |
|---|---|
| macOS | `brew install arm-none-eabi-binutils` |
| Fedora | `sudo dnf install arm-none-eabi-binutils-cs` |
| Debian, Ubuntu and derivatives | `sudo apt install binutils-arm-none-eabi` |
| Windows | `winget install Arm.ArmGnuToolchain` |

Another Linux distribution gets Arm's download page. The Fedora 44 and Ubuntu 24.04 packages
assemble the default template to `01 00 a0 e3 1e ff 2f e1`. Check offline runs the code once on the simulated console
(`pokeldn/frlg/rom/custom_code.py`) and shows the answer and the bytes. The same check runs before
Start and before a file is saved: code that faults, or never returns 1, is refused.

The Sword/Shield form builds a Pokemon (optionally able to Gigantamax), an egg, up to six bag items,
official outfits, Battle Points or money, with a card id. The Pokemon, egg, item, clothing and Battle
Points kinds write the bytes of a record a retail Sword listed and redeemed
([Sword and Shield Mystery Gift](swsh_gift.md#a-card-delivered-to-a-retail-console)); the
Pikachu preset is byte for byte the launcher's own default record. Clothing comes from the pairs of
the official outfit cards ([Clothing](swsh_gift.md#clothing)), at most six pieces for each player
gender. PKHeX refuses a Gigantamax flag on a species without a Gigantamax form.

Before you send lists what the console gets, when it runs, and the cartridges the gift serves. Save
gift file writes the selected gift as `.pokegift` with no board and no Switch keys. FRLG presets go
through the launcher's own builder, so the file holds every cartridge variant they build. The
console's game code chooses the variant during the gift handshake; a cartridge absent from the file
is refused before gift data is sent. A preset's card id is on the Advanced tab (`--flag-id`, 1000 to
1019).

The app does not modify gift files on import. Files remain at the chosen paths.

Delivered from an opened file on retail consoles: a Celebi card and a console code file on a French
FireRed, a Pikachu card on a Sword. Console code built in the form answered with the save's trainer id.

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

> 本节已随上游更新，以下内容暂保留英文。

The converter imports Sword/Shield WC8 records, FRLG `.wc3` files and paired FRLG files used by
`pokemon-gen3-mysterygift-tool`. A `.wc3` or `.wc8` also opens directly, in the app's Open a file and
in `--gift-file`.

An FRLG script whose reachable code holds no absolute address can serve each cartridge with the
same card layout: its jumps and text are `vgoto`/`vmessage` operands relative to its own
`setvaddress` [scrcmd.c:171], and items come through `callstd`. A script with a `goto`, `call`,
`message`, `callnative` or other absolute pointer belongs to one cartridge and needs `--build`; a
`.wc3` of that kind is refused when opened directly.

```bash
./.venv/bin/python -m pokeldn.gifts import --game swsh --record event.wc8 -o event.pokegift
./.venv/bin/python -m pokeldn.gifts import --game frlg --wc3 "FL - Item AuroraTicket (FRE).wc3" -o aurora.pokegift
./.venv/bin/python -m pokeldn.gifts import --game frlg --card WonderCard.bin \
  --script Script.bin --name "Event gift" -o event.pokegift
./.venv/bin/python -m pokeldn.gifts export celebi.pokegift --build BPRF --out-dir native-gift
./.venv/bin/python -m pokeldn.gifts export celebi.pokegift --wc3 --build BPRJ --out-dir native-gift
./.venv/bin/python bin/frlg_mg_host.py --gift celebi --console-build BPRJ --export-gift celebi.wc3
```

Saving to a path ending in `.wc3` or `.wc8` writes that native file instead of a `.pokegift`: in
`--export-gift`, in Save gift file and in `pokeldn.gifts.save`. A `.wc3` holds one cartridge's card
and script; without `--build` every variant of the gift must carry the same bytes. The GUI asks
which cartridge to export when variants differ. `.pokegift` retains every language variant. The `.wc3` metadata block is written as zero except its icon, which repeats the card's.
Every international gallery file the game accepts comes back with the same card, script and icon
bytes after an import and an export.

An international `.wc3` is 1420 bytes (`0x58C`):

| offset | size | content |
| --- | --- | --- |
| `0x000` | 336 | CRC16 of the card, 2 pad bytes, the 332-byte `struct WonderCard` |
| `0x150` | 80 | save-side card metadata; not read |
| `0x1A0` | 1004 | CRC16, 2 pad bytes, `struct RamScriptData` (magic 51, map group, map number, object id, 995-byte script), 1 pad byte |

The script CRC in the files covers 1000 bytes, pad byte included, in all 54 international files of
Project Pokemon's EventsGallery; the game's own covers 999 [script.c:488]. Import accepts either.
`--icon N` on import, or Card icon under Open a file in the app, sets the card's `iconSpecies`
(offset 2 of the card) to an internal species id from 0 to 411; 0 draws no icon
[mystery_gift_show_card.c:466].

Japanese `.wc3` files are 1252 bytes (`0x4E4`): the card structure is 164 bytes, its CRC wrapper
is 168 bytes, metadata starts at `0x0A8`, and the 1004-byte RAM-script structure starts at `0x0F8`.
Direct import offers Japanese files to `BPRJ` and `BPGJ`; international files offer the ten Latin
cartridges. An explicit `--build` must match the card layout. The gallery's
debug cards with flag ids 4 to 8 are refused: the delivery man hands a gift only for flag ids 1000 to
1019 [mystery_gift.c:241]. The Aurora and Mystic Tickets are no-ops on a save past its first Hall of
Fame ([The Aurora and Mystic Tickets](frlg_gift.md#the-aurora-and-mystic-tickets)).

The FRLG pair contains a 336-byte international or 168-byte Japanese card and a 1004-byte RAM-script structure. Import verifies both
CRCs and the script's unbound Mystery Gift header. The native pair cannot carry stamps, visiting
trainers, Mystery Event scripts, questionnaire gates or Wonder News. Export to that pair refuses
a distribution with those extras. `.pokegift` preserves them together.

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
