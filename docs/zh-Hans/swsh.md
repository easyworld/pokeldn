---
title: Sword and Shield
nav_order: 6
has_children: true
---

# 剑和盾

宝可梦剑和盾通过通用的发布/订阅框架，直接在 Pia 上运行带有协议缓冲区消息的 C++ 游戏代码。

静态读数来自 Shield 1.3.2 EUR 映像（`01008db008c2c000`，更新 NCA，SDK 7.7.0.0）；测量值是针对法国剑 1.3.2 的。两者共享他们的网络代码；存在差异的地方会被标记出来。

零售 Sword 已与 pokeldn 进行过两种角色的交易（[主持交换](swsh_trade.md#hosting-a-trade)）。

|页 |内容 |
|---|---|
| [墨盒和会话](swsh_session.md) |键、图像、Pia 4、与第一个应用程序数据的关联 |
| [同步框架](swsh_protocol.md) |消息 ID、内容、持有者、路由、队列 |
| [交易](swsh_trade.md) |交换屏幕、盒子状态机、确认梯 |
| [神秘礼物](swsh_gift.md) |神秘礼物菜单的本地无线分支|
## 来源

ID、偏移量和地址来自 Shield 的 `main` 或空气，除非某个部分指定了客户端。
`pokeldn/swsh/trade.py` 中的 `SYNC_ANSWERS` 是 `andyjusa/nxldn-lab` 对游戏机到游戏机捕获的读取（消息 97 和 60000 与 pokeldn 的字节逐字节匹配）。四个客户端讲LAN模式，
`kwsch/PokePiaSWSH`、`lincoln-lm/swsh-lan-client`、`andyjusa/nxldn-lab`、`Slashcash/PSD`，从Pia站握手上去；没有一个涵盖 LDN 或主机迁移。
## 字段脚本

`bin/script/amx/*.amx`（1.3.2 中的 953）是具有 64 位单元的 Pawn 3.x：魔术 `0xF1E1`，版本 10，标志 `0x1C`（紧凑代码，睡眠，无检查）。紧凑编码：每字节 7 位，高位组在前，符号位于第一个字节的第 6 位。非分支单参数操作码也打包为
`(param << 32) | op`，按 3.x 顺序从 162 开始编号（`LOAD.pri` 162、`LOAD.S.pri` 164、`PUSH.C` 188、`PUSH.S` 190、`STACK` 191、`ADD.C` 197、`ZERO.S` 200、`EQ.C.pri` 201、`INC.S` 204、`HALT` 210、
`PUSH.ADR` 212); `halt 0` 在偏移 0 处将其引脚。

本机是十二个字节，`u64 0` 和 `u32` 名称哈希，由 `amx_Register` (`0x0066d970`) 解析：

    h = 0; for each byte c: h = (h * 0x83) ^ c        (32-bit)
 绑定表是 `.data` 中的 `(name, function)` 对，每个模块一个（吸气剂，例如
`0x014aea00`)：777 个名称，使用了 513 个哈希值中的 512 个。商品：`ItemAdd` (`0x014acea0`)、`ItemSub` (`0x014acf40`)、`ItemGetNum`、`ItemAddCheck`、`ItemGetCategory`、`GetPocketNumberFromItemNumber_`。变量：`WorkGet`/`WorkSet`（散列的 64 位密钥）、`TempWorkGet`/`TempWorkSet`（指示在脚本恢复之前 UI 填充）。每个参数的调用是 `PUSH`，从右到左，然后
`SYSREQ.N native, bytes`。
## 未解决

> 本节已随上游更新，以下内容暂保留英文。

- [Player profile](swsh_protocol.md#the-player-profile): the feature behind vtable `0x25614c0`
  (activity record kind 11, `0x00dedf3c`; sample state 3 or 4). Sample states 3, 4, 6 are named only
  by their setters. `a_wr0301` as the Crown Tundra wild area is read from the numbering; one beacon
  taken there settles it.
- [Battle Stadium](swsh_protocol.md#the-battle-stadium-block): what writes the team descriptor's
  `+0`, `+4`, `+6` (a save with a validated team shows it). Whether the `v1/validate` reply's 0x100
  bytes reach `match+0x98` past `0x014f808c`'s copy to `[x19+0xb0]+0x76`; its status 1 and up to six
  u32.
- Sword against Shield: binary readings are Shield's, the console is Sword; the
  [session constants](swsh_session.md#taking-a-seat) hold across the pair. Sword testing bit 0 of a
  card's version mask is inferred from Shield's code with version 44 (`0x2C`) for `0x007d4270`'s
  `0x2D`, and from PKHeX `RestrictVersion` (1 Sword, 2 Shield, 3 both).
- [Mystery Gift](swsh_gift.md#what-the-menu-refuses): what a retail console shows for a kind-1
  gift whose species is absent from the game, which the constructor flags corrupt.
- [The offered record](swsh_trade.md#the-offered-record): the encryption constant read at
  `0x011e3458` is not followed past the read, and 375 `memcmp` calls with a computed length are
  untraced; none lies in the pml, trade or box code.
