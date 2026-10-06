---
title: Let's Go Pikachu and Eevee
nav_order: 7
has_children: true
---

# 我们走吧！ 皮卡丘和伊布

在宝可梦 Let's Go 皮卡丘 和 Let's Go 伊布 (2018) 中，Pia 静态链接到 `main` (269
RTTI 中的 `nn::pia` 类）和游戏的 C++ 代码位于其上，通过 `gflnet3`（一年后剑和盾使用的中间件）提供协议缓冲区消息。

静态读取为Let's Go皮卡丘1.0.2（`010003f003a34000`，更新NSP `v131072`，SDK 5.4.151.0）；硬件测量是针对法语 Let's Go 皮卡丘和 Let's Go 伊布进行的。 Let's Go 伊布使用皮卡丘的本地通信 ID，因此两个角色在伊布不变的情况下进行交换。

本地交换和战斗要求双方玩家提供链接码：固定十个中依次排列三个宝可梦，分两行显示：皮卡丘、伊布、妙蛙种子、小火龙、杰尼龟； 波波、绿毛虫、小拉达、胖丁、地鼠。该代码设置广告的场景ID（[会话页面](lgpe_session.md#the-link-code)）；托管和加入都可以在任何代码下工作。
## 相关页面

|页 |内容 |
|---|---|
| [Let's Go 墨盒和会话](lgpe_session.md) |标题是由什么构建的，LDN 密码和 Pia 游戏密钥、Pia 标头版本 3、会话密钥、真实会话运行时的站和克隆协议、启动游戏自身消息的门以及交换 | 的四个游戏消息
## 什么有效

`bin/lgpe_join.py` 加入游戏机的会话，并且 `bin/lgpe_host.py` 主持游戏机加入的一个会话。一个席位承载一个又一个交换：每次交换正常保存后，交换调度程序从状态 7 返回到状态 1，除非保存报告链路结束 (`0x886908`)，并且保存在新通道 (`0x8375a4`) 上重新创建队伍提议对象（[会话页面](lgpe_session.md#the-trade-dispatcher)）。两个发射器都会记录一列记录，每个记录都放在座位上。游戏不检查收到的盒子结构的任何字段：一个异色等级 100 的冒名顶替者百变怪，每个 IV 中有 31 个，每个 AV 中有 200 个，在摘要屏幕上读回。 Clone Protocol的接管交换经过游戏的`0x11b080`门，Reliable Protocol携带identity、offer、commit和kind 4（下一次交换的选择）； `pokeldn.lgpe.pb7`读写提供232字节盒结构和类4进位。

三项排队交易在两个角色的一个席位上完成。每个完成的条目都保存为一个校验和的 260 字节文件，并且主机在游戏机离开后以代码 0 退出。创下的记录
`pokeldn.pokemon`（选择的级别、性别、性质、球、IV 和 AV）由 `bin/lgpe_host.py
--fresh-pid` 提供，在接收摘要屏幕上显示这些字段。

当玩家按下返回键时，游戏机离开座位。 `bin/lgpe_join.py --leave-after SECONDS` 在其第一个应答交换步骤之后很长时间内运行相同的出口，并且 `bin/lgpe_host.py` 应答游戏机的返回（[A 加入方离开](lgpe_session.md#a-joiner-leaving)）。
`tests/test_lgpe_host_commit.py` 将主机的提交阶段固定在脚本游戏机上：错误的提交使游戏机处于确认屏幕上，并设置了保存的交换锁定（在计算的游戏时间的十分钟内没有交易），然后是致命错误屏幕。
## 未解决

> 本节已随上游更新，以下内容暂保留英文。

- How counted play time relates to wall time, so how long the lock lasts on a clock: the rate of
  the gated call `0x13c944` and whether the frame period stays at 33.3 ms are unread. Trying Link
  Trade at play time P + 9 and P + 11 minutes after an aborted commit, against a stopwatch, measures
  both.
- What leaves a console's clone protocol silent on the host's `0xa1` on clone type 4, while its radio
  acknowledges every frame, after a host answers its withdrawn vote with A 2. `0x51c110`
  drops such a message silently in `0x522a60` while the sender's bit is in the `+0xc0` mask, and
  earlier at the destination check, the per-sender count filter or a length check; the message's own
  bytes (destination `0x0002`, count 69 after a highest earlier host count of 63) pass the first two
  for in-order delivery. What held the silence is unknown; the capture shows no
  severity-4 error (`0x4d8a80`, result 2 and the fatal error screen). An `0xa1` repeated until
  answered separates a pending mask (a later copy answered) from a message that never reaches the
  clone protocol (none answered); a sniffing board records what arrived independently of the host.
- Which process the trade dispatcher's child is, and whether the sync save's commit channel at
  `seq+0xb8` is released after an aborted commit.
- Whether the dispatcher's modes 1 and 2 are link battles. The reading rests on the scene they build;
  a capture of a link battle's session, with the mode word `+0x8c`, settles it.
