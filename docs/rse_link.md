---
title: 交换与联合房间
parent: 红宝石、蓝宝石与绿宝石
nav_order: 1
---
<a id="emerald-trade-and-the-union-room"></a>
# 绿宝石交换与联合房间

绿宝石的无线连接与火红相同（见[连接](frlg_link.md)）；本页说明差异。启动器为 `bin/frlg_trade_host.py`、`bin/frlg_trade_join.py`，使用 `--version emerald`。测量针对模拟游戏机上的 [Switch 构建版](rse_switch_build.md)。

<a id="joining-a-host"></a>
## 加入主机

广播记录、`RfuGameData` 与火红相同 [include/link_rfu.h:80-113]。主机版本不是 3 时，绿宝石将其列为“尚未准备好”，除非玩家已成为冠军且主机广播 `canLinkNationally` [union_room.c:1266-1283; trade.c:2514-2521]。`--version emerald`（或 `ruby`、`sapphire`）广播对应版本，并按配置设置 `canLinkNationally`、`hasNationalDex`、`gameClear`（`[16:20]` 字的第 16、17、24 位；`RfuGameData` 第 7、8、9 位）。火红、叶绿将这些位清零。

设置 `FLAG_SYS_POKEDEX_GET`（`0x861`）之前，宝可梦中心二楼的所有接待员都回复“正在调整” [cable_club.inc:803, 885, 901, 1152]。

<a id="trade"></a>
## 交换

线上格式与火红相同（训练家卡片的神奇卡片 ID 位于 `0x60`），有两项差异：

- 未获得全国图鉴时，绿宝石拒绝伙伴提供的蛋或非丰缘种类 [trade.c:1584-1589]。交换画面提示对方训练家的宝可梦暂时无法交换，玩家按 A 后，游戏机发送 `READY_CANCEL_TRADE`。`LinkPlayer.progressFlags & 0xF` 报告图鉴状态。`pokeldn.rse.constants.HOENN_DEX` 保存 202 项种类，主机记录被拒绝的交换提议。
- 绿宝石在交换后运行五轮待机 [trade.c:4686-4797]；Switch 火红为六轮，最后一轮之后调用 `svc_FinishSave`。Switch 构建版保留五轮：游戏机发送 `READY_EXIT_STANDBY` 5 至 9，如果主机等待第六轮，游戏机会停在“通信待机”。`--version emerald` 使主机运行五轮；`--save-rounds N` 可覆盖该值。

版本为 3 时，绿宝石绘制主机训练家卡片，在 `0x3A` 显示对战开拓区象征，`0x3C` 显示对战点数。接收队列有 32 个槽位（火红为 20），除 `0x0002`、`0x7F7D` 外还接受序列号 `0x0000`。

模拟游戏机上的 Switch 构建版能与主机完成直接交流区交换：依次交换 LinkPlayer、训练家卡片、席位路由、队伍、邮件、奖章数据块，再进行交换、五轮待机、`READY_CLOSE_LINK`、RFU 断开帧和 Pia 离开，最后写入模拟器存储中的存档。

<a id="the-union-room"></a>
## 联合房间

房间、活动菜单和交换公告板的运行方式与火红相同（见[联合房间](frlg_link.md#the-union-room)）。`--union-room --union-room-keepalive 120` 生成 POKELDN 的角色，玩家与其对话后游戏机连接。菜单有 GREETINGS、BATTLE、CHAT、EXIT；绿宝石不从该菜单提供交换。

| 活动 | 参数 | 模拟游戏机上的测量结果 |
|---|---|---|
| GREETINGS | `--union-room` | 双方训练家卡片、待机屏障、返回房间 |
| EXIT | `--union-room` | `READY_CLOSE_LINK`，正常断开 |
| 交换公告板 | `--union-room --board-type TYPE` | 游戏机选择 POKELDN 的挂牌，传输宝可梦、邮件数据块，完成交换和保存，关闭连接 |
| CHAT | `--union-room-chat` | 未运行 |
| BATTLE | `--union-room-battle` | 未运行 |

主机响应游戏机从 POKELDN 挂牌发起的公告板交换，不会主动请求游戏机自身的挂牌。`--board-type` 指定主机希望换取的属性，游戏机只提供该属性的宝可梦。

使用 `--union-room-keepalive 600` 时，双方训练家卡片数据块传输完成后，游戏机停在“Communicating with POKELDN...”，不显示菜单；120 则能进入菜单。

<a id="unresolved"></a>
## 尚未解决的问题

- 正式 Switch 绿宝石发行版在交换后的待机轮数。
- 绿宝石联合房间的聊天和对战。
