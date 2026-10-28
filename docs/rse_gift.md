---
title: 绿宝石神秘礼物
parent: 红宝石、蓝宝石与绿宝石
nav_order: 2
---
<a id="emerald-mystery-gift"></a>
# 绿宝石神秘礼物

绿宝石的神秘礼物与火红相同（见[神秘礼物](frlg_gift.md)），使用绿宝石自己的编号。启动命令为 `bin/frlg_mg_host.py --version emerald`。

<a id="the-menu-gate"></a>
## 菜单解锁条件

设置 `FLAG_SYS_MYSTERY_GIFT_ENABLE`（`0x8DB`）后，标题菜单才会显示 MYSTERY GIFT。玩家获得宝可梦图鉴后，在友好商店柜台问卷中填写 LINK TOGETHER WITH ALL 即会设置该标志 [questionnaire.inc:30-37; easy_chat.c:693]。之后依次选择神秘礼物、神奇卡片、朋友。

<a id="the-protocol"></a>
## 协议

传输、脚本、332 字节 `WonderCard`、444 字节 `WonderNews` 和 `MysteryGiftSave`（`0x36C`）与火红相同。GameData `+0x0C`、`+0x10` 对卡片发送 4、`0x200`，对新闻发送 5、`0x201`；火红则发送 1 和版本代码 [mystery_gift.c:346-363]。绿宝石检查卡片时要求第 2 位和 `0x380` [mystery_gift.c:390]。主机根据游戏机报告的游戏代码采用对应规则。绿宝石的场景操作码仅在 `0xC7..0xCC`、`0xD0`、`0xD3..0xD5` 有差异，编号最高到 `0xE3`。

| 项目 | 火红／叶绿 | 绿宝石 |
|---|---|---|
| 卡片 flagId 1000（`sReceivedGiftFlags[0]`） | `0x2A7` | `0x13A` |
| `FLAG_MYSTERY_GIFT_DONE` | `0x3D8` | `0x1E4` |
| 礼物游标变量 | `0x40B6..0x40BC` | `0x40DE..0x40E4` |
| 最后一个道具 | 374 | 376（`ITEM_OLD_SEA_MAP`） |
| `StartLegendaryBattle` / `GetMysteryGiftCardStat` | 312 / 390 | 314 / 392 |
| `special` 索引检查 | 以 `gSpecialsEnd` 为界 [scrcmd.c:101] | 无；共 527 项 [scrcmd.c:119] |
| SaveBlock1 中的 RamScript | `0x361C` | `0x3728` |

`gift_composer` 接收 `GameRules` 表；`pokeldn.rse.constants.EMERALD_RULES` 使用绿宝石编号编译。主机会在发送前拒绝其他游戏的游戏机。绿宝石的神奇新闻不含奖励。

在模拟游戏机上，[Switch 构建版](rse_switch_build.md)会在朋友搜索中列出 POKELDN，报告自身为尚无卡片的绿宝石，接收陈旧的海图卡片后正常关闭 LDN；宝可梦中心二楼的配送员随后执行保存的脚本，交付 OLD SEA MAP。

<a id="gifts"></a>
## 礼物

`pokeldn.rse.gifts` 逐操作码重建 pokeemerald 的四个官方礼物脚本，使用 pokeldn 的文字（`tests/test_rse.py` 比较字节码）。宝可梦中心二楼的神秘礼物配送员运行保存的脚本。

| 预设 | 卡片 flagId | 效果 |
|---|---|---|
| 极光船票 | 1000 | 船票和 `FLAG_ENABLE_SHIP_BIRTH_ISLAND` |
| 神秘船票 | 1001 | 船票和 `FLAG_ENABLE_SHIP_NAVEL_ROCK` |
| 陈旧的海图 | 1002 | 海图和 `FLAG_ENABLE_SHIP_FARAWAY_ISLAND` |
| 变化洞窟传闻 | 1003 | 切换至洞窟九张野生宝可梦表中的下一张 |
| 无限船票 | 1007 | 游戏自身的交付流程 [cable_club.inc:33]：船票和 `FLAG_ENABLE_SHIP_SOUTHERN_ISLAND` |
| 大师球、神奇糖果 ×5、会冲浪的皮丘的蛋 | 1004..1006 | 使用 `EMERALD_RULES` 编译 |

    POKELDN_RADIO=esp32:auto ./.venv/bin/python -u bin/frlg_mg_host.py --live --version emerald --gift-file old-sea-map.pokegift --keys "$HOME/Documents/Switch/23.0.0 keys/prod.keys"

可用 `pokeldn.gifts.save(PATH, pokeldn.rse.gift_builder.compile(PRESET[key].state))` 将预设保存为文件。绿宝石礼物文件只有 `emerald` 一个变体（见[神秘礼物文件](gifts.md)）。绿宝石不接受原生代码、存档备份和火红预设。

<a id="unresolved"></a>
## 尚未解决的问题

- 日文版绿宝石的神秘礼物活动编号和卡片大小。
- 正式 Switch 发行版是否保留菜单解锁条件。
