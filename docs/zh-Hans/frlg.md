---
title: FireRed and LeafGreen
nav_order: 4
has_children: true
---

# 火红和叶绿

> 本节已随上游更新，以下内容暂保留英文。

The Switch release of FireRed and LeafGreen is the original GBA ROM running inside an emulator, so
two link layers are stacked:

| layer | whose | documented in |
|---|---|---|
| LDN and Pia | the emulator's, shared with every other Switch title | [The wireless layer](ldn.md) |
| the GBA link: RFU frames, seats, block sends | the ROM's | these pages |

[pret/pokefirered](https://github.com/pret/pokefirered) is authoritative for the whole game-level
protocol at `REVISION >= 0xA`. Cartridge header, read off both consoles: software version `0x0A`,
game code `BPRF` (FireRed, French) and `BPGF` (LeafGreen, French). The host also selects measured
ROM and RAM addresses for the English, German, Italian, Spanish and Japanese pairs, twelve
cartridges in total. Mystery Gift detects the language from the cartridge code after the
player chooses pokeldn in the Friend list; the Basic screen shows this beside the version. The added languages have offline ROM and mGBA checks; wireless delivery
on those editions still requires retail verification. See [The cartridge maps](frlg_rom_map.md#the-international-revision-0x0a-cartridges).

A console that leaves about three seconds after associating, once the Pia session has finalized,
was given an association response without 6, 9 and 12 Mbit/s ([frlg_link.md](frlg_link.md), The
advertised rate set); a missing Pia type 2 Join Response gives the same symptom.

## 什么有效

在实机硬件上，在两个卡带上，主机服务于游戏机提供的每项活动：双向神秘礼物、作为主机交换和加入方、整个联合房间，包括全链路战斗、新闻神奇、有线电视俱乐部斗兽场和来访的战斗塔训练家。

通过礼物链接的两个解释器，游戏机还运行发送给它的代码：它的内存读取和写入，它的ROM映射到它运行的构建的命名函数，它自己的函数用八个参数调用，以及由它自己的`CreateMon`构建的主机选择的宝可梦，并留在玩家的队伍中。 RNG是端到端封闭的；每次有针对性的异色遭遇需要按 A 键。

来宾到包装器的边界被解码（[游戏机上的代码](frlg_rom.md#where-the-boundary-stands)）：来宾的一个存储通过区域的支持是字节精确和常量值的，植入的指针的消费者从中读取他们的目标
`main` 在静态地址处的自身数据以及系统调用存储到组件中的数据将作为计数和 GBA 地址读回，每个地址都会进行边界检查。包装器自己的扫描管道被解码到其第一阶段（[包装器自己的扫描管道](frlg_rom.md#the-wrappers-own-scan-pipeline)）：扫描结果、消耗循环和父节点候选列表都是固定形状和有界的，并且单个长度路径（站名，最多 `0x40`）被夹在其调用者处。
## 相关页面

|页 |内容 |
|---|---|
| [链接协议](frlg_link.md) | RFU链路层、座位屏障、联合房间、聊天、链路战斗和有线电视俱乐部斗兽场|
| [神秘礼物](frlg_gift.md) |礼物会议、创作礼物、神奇新闻、来访培训师以及阻塞的无线通信路径 |
| [游戏机上的代码](frlg_rom.md) |神秘事件虚拟机、本机 ARM 有效负载以及读取和写入实时保存 |
| [ROM图](frlg_rom_map.md) |如何测量地址、四个功能表、物种表和法语 Easy Chat 词汇 |
| [随机数生成器](frlg_rng.md) |阅读和预测`gRngValue`，以及瞄准遭遇战的场存根|
| [叶绿](frlg_leafgreen.md) |第二个墨盒共享什么、测量的偏移图以及作为仪器的英国构造 |
| [主机实现](frlg_host.md) |交换和神秘礼物主机的组件边界|
## 两个墨盒

叶绿以分段恒定偏移量运行相同的代码；测量的对和边界位于[叶绿](frlg_leafgreen.md)上。切勿预测跨越无括号边界的地址。
## 贯穿所有内容的规则

- 分解的链接顺序是证据；其地址需要在墨盒上测量。   `pokeldn/frlg/rom/rom_map.py`记录了每个地址是如何获得的。
- 在发送之前，栏在独角兽（`buffer_script.emulate`、`emulate_repeating`，两个模拟控制台）下离线运行。一个出现故障或永不返回的 1，将神秘礼物菜单挂在无路可走的地方；永远循环的字段存根会冻结整个世界。
