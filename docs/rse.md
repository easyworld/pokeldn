---
title: 红宝石、蓝宝石与绿宝石
has_children: true
---
<a id="ruby-sapphire-and-emerald"></a>
# 红宝石、蓝宝石与绿宝石

红宝石、蓝宝石与绿宝石尚无 Switch 发行版。pokeldn 根据 [pret/pokeemerald](https://github.com/pret/pokeemerald) 和 [pret/pokeruby](https://github.com/pret/pokeruby)，为它们在火红、叶绿所用 GBA 应用中的可能发行版预备了支持。这里的地址均来自 GBA 英文版。应用仅在源码运行时显示这些游戏（见[未发行游戏](gui.md#unreleased-titles)）。

为该应用构建的绿宝石可以替换火红卡带运行，并连接 pokeldn 主机（见 [Switch 构建版](rse_switch_build.md)）。在正式发行版出现前，这些页面以此构建版作为实验工具。

| 页面 | 内容 |
|---|---|
| [交换与联合房间](rse_link.md) | 加入主机、连接交换、联合房间 |
| [神秘礼物](rse_gift.md) | 协议差异、礼物、菜单解锁条件 |
| [Switch 构建版](rse_switch_build.md) | 适用于火红应用的绿宝石：移植、构建、运行及测试存档 |

GBA 应用已有涵盖第三世代五个游戏代码的游玩报告表，包括 `AXV?`、`AXP?`、`BPE?`（见[游戏机上的代码](frlg_rom.md)）。十二个火红、叶绿游戏共享首个本地通信 ID `0x01006fa0233f8000`（见 [ROM 地址表](frlg_rom_map.md)）。

<a id="what-each-game-can-do-over-the-link"></a>
## 各游戏支持的连接功能

| 功能 | 红宝石／蓝宝石 | 绿宝石 |
|---|---|---|
| 无线适配器（RFU）代码 | 无，仅支持 SIO 多人连接线 | 与火红相同的 `link_rfu_2.c` |
| 连接交换 | 连接线 | 与火红相同的直接交流区和联合房间 |
| 神秘礼物（神奇卡片、神奇新闻） | 无 | 与火红相同的协议与结构 |
| 神秘事件 | 通过连接线使用 e-Reader，以 MYSTERY EVENT IS EXCITING 解锁 | 标题菜单不提供 |

启动器使用无线适配器协议，因此只能连接绿宝石。连接层之上，红宝石／蓝宝石的连接线协议共享 `LinkPlayer` 记录、200、200、100、220、40 字节的数据块大小、连接命令字和交换数据块 [pokeruby link.c, trade.c]。红宝石／蓝宝石的 11 字节姓名覆盖了火红、绿宝石读取进度标志的位置，因此后两者遇到红宝石／蓝宝石伙伴时会清零这些标志。

<a id="identifiers"></a>
## 标识

| 字段 | 红宝石 | 蓝宝石 | 绿宝石 |
|---|---|---|---|
| 游戏代码 | `AXV` + 语言 | `AXP` + 语言 | `BPE` + 语言 |
| ROM 头部标题 | `POKEMON RUBY` | `POKEMON SAPP` | `POKEMON EMER` |
| `gGameVersion` | 2 | 1 | 3 |
| `LinkPlayer.version` | `0x4002` | `0x4001` | `0x4003` |

语言字母为 `E`、`F`、`D`、`I`、`S` 或 `J` [include/constants/global.h:8-12]。

<a id="the-save"></a>
## 存档

闪存布局、签名 `0x08012025` 和校验和均与火红相同 [save.c]。SaveBlock1 为 `0x3D88` 字节，SaveBlock2 为 `0xF2C` 字节；各扇区按 ID 顺序校验 `0xF2C`、三次 `0xF80`、`0xF08`、八次 `0xF80`、`0x7D0` 字节。队伍数量位于 `0x234`，队伍位于 `0x238`，金钱位于 `0x490`（与 SaveBlock2 `+0xAC` 异或），标志位于 `0x1270`，变量位于 `0x139C`，游戏统计位于 `0x159C`，神秘礼物位于 `0x322C`。SaveBlock2 没有 `filler_B20`。

| 字段 | 偏移 | 含义 |
|---|---|---|
| SaveBlock1 `continueGameWarp` | `0x0C` | `WarpData`：s8 地图组、s8 地图编号、s8 传送点 ID、填充、s16 x、s16 y |
| SaveBlock2 `specialSaveWarpFlags` | `0x09` | 第 0 位 `CONTINUE_GAME_WARP`：继续游戏时传送至 `continueGameWarp` [overworld.c:1739] |

未设置 `CONTINUE_GAME_WARP` 时，继续游戏会根据 `pos`、`location` 恢复 SaveBlock1 中的地图视图和对象事件。只修改 `pos`、`location` 来移动玩家，会加载旧地图并使玩家不可见。

<a id="emerald-link-features-pokeldn-lacks"></a>
## pokeldn 尚未支持的绿宝石连接功能

混合记录、树果混合器、华丽大赛、对战塔连接多人对战、树果粉碎、宝可梦跳跃与嘟嘟利摘树果（连接组 12 至 21，活动 14、23 至 29）。

<a id="unresolved"></a>
## 尚未解决的问题

- 是否会发行 Switch 版本，以及其标题 ID、游戏代码和软件版本。
- 是否沿用火红应用的通信 ID、场景 ID 和广播打包方式。
- Switch 版本如何承载红宝石、蓝宝石的连接线通信。
- Switch 绿宝石的全部 ROM 与 RAM 地址。
