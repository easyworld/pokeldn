---
title: Legends Z-A
nav_order: 10
has_children: false
---

# 传说 Z-A

宝可梦传奇：Z-A（游戏 ID `0100f43008c44000`）是一款原生 Switch 游戏，Pia 静态链接到 `main`。其数据包头是版本 16，即 `pokeldn.ldn.crypto` 为 GBA 应用程序编写的数据包头。
## 转储

基础应用程序 `v0` (4.3 GB)，更新 `0100f43008c44800` `v393216` (2.1 GB)，Mega Dimension DLC
`0100f43008c45002`。

| NCA |编号 |集装箱偏移|部分键 |
|---|---|---|---|
|计划（更新）| `4a70b3ff963bfe412681185cea68bf55` | `0x2085d0` | `b9de1a0334576634f8fdafdd703f7f9a` |
|控制| `3e7ba1cd223145fa4f299a8f4cafd4cb` | `0xbd0` | `a8cb59338ce785237048d52452eb6adf` |

程序 NCA 在第 0 节中具有 exeFS，在第 1 节中具有 BKTR RomFS。exeFS 保存 `main`（33,970,422 字节）、`main.npdm`（1,700）、`rtld`（8,550）和 `sdk` (6,247,676)，无 `subsdk0`。解压后，`main`为文本`0..0x3163f70`，rodata来自`0x3164000`，数据来自`0x3bc2000`；该页面上的地址是该图像的偏移量。 Control RomFS数据位于NCA `+0x14c00`，节计数器`0000000000000005`； `control.nacp` 给出了显示版本 2.0.2 和 `+0x30b0` 处的八个本地通信 ID，全部为 `0100f43008c44000`。
## 无线层

|价值| |哪里 |
|---|---|---|
| LDN 密码 | `BM7cXkadR9ugiXdHiurkiyhrQwcR3rMgCM5BF47dranKXWAGpGEA9z3ncXRnPjCX` |罗数据 `0x33391fc`，数据 `0x3eeda1f` |
| Pia游戏键| `p3bwdaSsywFXUkDu` |数据 `0x3eeda0e` |

两者都与 [NintendoClients wiki](https://github.com/kinnay/NintendoClients/wiki/Pia-Game-Keys) 匹配。
## 数据包头

头文件版本 16，维基表格中的 Pia 6.39 到 7.2。布局是
`pokeldn.ldn.crypto.PiaHeader`（29字节，魔法`32AB9864`，加密时带有`0x80`的版本字节；参见[Pia](pia.md)）。

    0x24fadbc   initializer: magic at object +0x08, 0x10 at +0x0c, memsets nonce +0x15 (8), tag +0x1d (16)
    0x24faefc   validator: magic, (version & 0x7f) == 0x10, (length - 0x1d) >> 6 below 0x71
    0x24fb1e0   receive path, branches on bit 7 of the version byte
    0x24fb4b0   send path, writes 0x10 back to +0x0c when it seals nothing
    0x24fb46c   padding-size setter: ORs into bits 4..7 of object +0x0d (wire byte 0x05)
 该对象将随机数和标记保留在其线路偏移上方 8 个字节，正如传说阿尔宙斯的版本 11 标头在 `pokeldn.ldn.pia6` 中所做的那样。
## 广告

本地搜索屏幕上的游戏机托管一个网络并通告 112 个字节：0x5C Pia 系统属性块和 20 个游戏字节。不随链接代码改变的字段：

|领域 |价值|
|---|---|
|本地通讯 ID | `0100f43008c44000` |
| LDN协议| 1 |
|广告版| 4 |
|场景 ID | 1 |
|应用版本| 6 |
|安全模式| 1 |
|接受政策 |全部 |
|参与者| 1/2 | 1/2
|系统/应用通讯版| 22 / 6 |
|玩家姓名 |一个字节，一个空格，UTF-8 |

SSID 和通道针对每个会话。游戏字节是 ASCII 格式的链接代码，NUL 填充为 16，然后其长度为小端 `u32`。布局和密码字段据说是阿尔宙斯的（[pla.md](pla.md)，广告中的链接代码）； Z-A的游戏密钥给出了面具`1068a742ac3a8787ab6066a161f5d5e1`。 `pokeldn.za.build_advertise_data(code)` 单独从代码中复制每个广告； `tests/test_za.py` 均引脚。
## 座位

搜索游戏机接受电台并立即说出 Pia：第一个数据报（109 字节）在 0.02 秒处。数据包在 `AES_ECB(game_key, ssid)` 下进行身份验证，网络 ID 为 `CRC32(ssid[1:16])`（已解密 32 个中的 32 个）。未得到答复，它通过协议 1 (Net) 从其变量 id 发送到目的地 0：

|留言 | |
|---|---|
| `01 11 ...`，118 字节 |连接状态，序列 ID 2 和 3，每秒两次 |
| `01 40 00 00` |一旦状态变为无人应答，开始主机迁移 |

连接状态是布局 `pokeldn.ldn.pia_connect.parse_net_conn_request` 读取：四个插槽，两个已填充，均位于端口 12345，主机 `169.254.x.1`，加入方 `169.254.x.2`。它在大约 14 秒（实测为 14.4 秒）后停止，但仍保持静止状态。

在模拟对（捕获 768 个数据包）中，开头是：

- 主机首先传输，109 字节，关联后 48 毫秒；方加入在 47 毫秒后回答了 45 个字节，然后是 125；
- 标头随机数是来自随机 64 位基数的每站计数器，每个发送的数据包 +1；
- 加入方的第一个数据包源为 0，目的地为 0，数据包 ID 为 0，无页脚，未压缩；它的第二个带有它自己的源ID，zstd-compressed；
- 主机的下一个数据包被寻址到该 ID 并携带两字节接收者页脚。

在后面没有 Pia 主机的网络上，LDN 连接成功的方加入会在 7.94 秒后干净地断开连接。计时器是网络连接截止时间，8000 毫秒：

    0x251b1bc   LdnProtocol vtable 0x3c8aef8 slot 0x1d8: mov w0, #0x1f40
    0x2513520   NetBackgroundProcessJob StartConnectNetwork: job+0xa0 = now + ticks_per_ms * 8000
    0x25141c4   the WaitConnected step 0x25140bc, while the host is unknown: deadline against now
    0x25143a0   expiry: result 0x647a, state byte +0x100 = 5, a 5000 ms deadline (slot 0x1e8),
                then StartDisconnectNetwork
 截止时间在 LDN 连接完成之前开始，因此等待时间比 8 秒少了 0.06 秒。 LdnProtocol 的定时槽 0x1b0 至 0x1f8 返回 6000、1000、500、10500、4500、8000、20000、5000、5000 和 10000 ms；仅识别 0x1d8 和 0x1e8。
## 会议，在实机上

发送参考加入方的会话加入的站立即被接纳。游戏机发送：

|从座位上|游戏机发送什么 |
|---|---|
| 0.02 秒 |网络连接状态，118字节|
| 0.05 秒 |会话加入响应，类型 2，37 字节，加入方的变量 id |
| 0.06 秒 |可靠（协议 10）、106 字节和两个广播可靠（协议 11）|
| 0.08 秒 |网络更新属性，类型 0x50，150 字节 |
| 0.5 秒起 | RTT 请求，大约每秒 3 个 |
| 1.12 秒，重复 |会话更新会话，类型5，185字节|

该连接需要通过网络确认：十个协议（`1:0 3:5 5:1 6:0 9:1 10:3 11:4 12:4 13:7 15:0`）、应用程序通信版本 6、标识令牌 `0x06` 然后为零，以及一个空格的 PlayerInfo 名称。列出 GBA 应用程序的六个协议和版本 0x58 的连接没有得到答复，游戏机在入座后 8.7 秒开始主机迁移。使用上述 10 种协议进行的加入，如果其游戏消息未得到答复，则会在主机迁移中结束，并在席位后 27 秒“找不到合作伙伴”。回答每个网络、会话、RTT 和可靠消息且没有游戏消息（`bin/za_join.py` 没有 `--game`）的方加入将零售搜索的席位保留 150 秒，直到它离开：游戏机每秒发送大约 32 个数据包，回答离开，然后显示“未找到合作伙伴”。

协议计数与主机不同的连接被类型 0 处理程序 `0x254a030`（`0x254a090`，针对 `0x256c9f0`）丢弃，没有应答也没有站；如果协议版本或应用程序版本错误，则返回 37 字节类型 2、结果 3 (`0x254a2e4`) 或 4 (`0x254a290`)。主机的 WaitMember 消耗 3000 ± 999 ms（随机 u64 被读取带符号）。到期后，加入方位于网络层而不是会话中，LeaveMeshWithHostMigration 会在 8000 毫秒内轮询下一个主机 (`0x255a520`)，然后发送 Net 0x11 序列 3 和 Net 0x40。列出十个协议中的九个的方加入不会从零售搜索中提取任何会话消息；第一个网络 0x40 在座位后 8.74 至 11.01 秒（预计 8.05 至 12.1 秒）出现，游戏机在新 SSID 下打开新网络，仍在搜索。上面的8.7就是这个路径。

相同的加入方没有发送 RTT 应答，因此在 1.16 秒处的类型 6 之后什么也没有被踢出（踢球）：会话类型 13 从 14.24 秒开始，其中 9 个间隔约 0.5 秒，然后从 19.31 秒开始每 0.5 秒 Net 0x11 序列 3，Net 0x40 每从23.31秒开始0.3秒，最后一个数据包在25.13秒，然后游戏机上“找不到伙伴”。 27 秒的结尾是这样的序列：一个加入方在 10 秒内不从其自己的变量 id 发送任何内容。
## 游戏自带的兑换

在 Pia 之上，游戏在 Reliable（协议 10）和 Broadcast Reliable（协议 11）上运行，子标头 `pokeldn.ldn.reliable` 进行解析。交换携带下面的应用程序有效负载（参考捕获中的 20 个不同的有效负载），每个都重新发送直到确认，除了站 ID 之外，来自两个站的相同集合。按消息 ID，按首次出现的顺序排列：

|编号 |字节|它携带什么|
|---|---|---|
| `1400` | 106 | 106电台身份、UTF-16 格式的玩家姓名 |
| `1403` | 9 |身份的校验和 (SyncDataSet)，如下 |
| `0100` | 1211 | 1211选择屏幕从中绘制的记录 |
| `0101` | 354 | 354提议：9字节头，344字节宝可梦记录，1个尾字节|
| `0102`，`0104` | 5 |步骤消息|
| `0200` | 5 |确认步骤，最后一个字节 3、6、0x0b、0x0e |

`pokeldn.za.reference` 传送身份、其后续、协议 11 开局和选择记录，从玩家为 `Player` 的模拟对记录； `bin/za_join.py` 和
`bin/za_host.py` 发送它们（`--game-dir` 命名另一组）。

标识是一个 `b9` 两个元组：一个 u32，然后是一个包含 0x5d 字节 `bc` blob 的单成员元组。 blob 是一个六成员元组：一个 u32、两个小整数、玩家姓名和一个 32 字节的零字段，然后是其余部分。

    1400 b902 82<u32> b901 bc5d b906 82<u32> 01 02 bc1a <name> bc20 <32 bytes> ...
 名称为 26 字节，UTF-16LE，NUL 填充：最多 12 个字符，位于协议 10 消息的偏移量 0x18 处（协议 11 站前缀后面的 0x1c）。有了记录的 `Player`，一台实机就向其交换伙伴显示了 `Player`。两个启动器都将 `--trainer-name`（默认 `POKELDN`）写入其中（`pokeldn.za.reference.named`）。

通道 0x14 承载游戏在站之间保持同步的键值存储（`gfa::network::p2p`，在 `0x7796a0` 构建；消息 id `0x1400 | index`）：1400 是 UpdateValue (`0xc1bdf4`)、1402 DeleteAllValues 和 1403同步数据集（`0xc4b1b4`）。身份的外层 u32
`0x2abe85e2` 是值的键，是 `0xdf1b30` 的常量。 1403 在按键排序的发送者值上携带 1 u32，`h = crc32(le32(fnv1a32(value) + h))` 来自 `h = 0`（`0xc4b270`，FNV-1a at
`0xc4b31c`，`0xc4b420` 处的标准 CRC-32）；对于身份，该值是 `bc5d` 之后的 0x5d 字节。仅当每个电台都匹配时（`0xb8c724`、`0xb8c660`），接收器才会重新计算它并继续前进。记录的 `Player` 标识给出了 `1403b9018269fb308f`，即记录的消息。使用过时的 1403 发送的重命名身份会在其搜索屏幕上留下一个实机：它发送其 1400 和 1403，但不会发送 0100。`pokeldn.za.reference.sync_message` 为发送的身份构建 1403。
### 交换命令

> 本节已随上游更新，以下内容暂保留英文。

The trade session setup `0xca2928` subscribes five command types (named by ctti strings) on the
session's command channel (session+0xc8). The id is `0x100 | index`, the type's position in the
channel's list at +0x60 (`0x96129c`, a `strcmp` walk). Each payload is a `b9` struct opening with a
u16 round.

| id | command | handler | payload as the handler reads it | what the handler does |
|---|---|---|---|---|
| `0100` | CommandReady | `0x2dc4c7c` | round, 1200 bytes | copies the 1200 bytes to session+0x604, sets session+0xf0 |
| `0101` | CommandSelectPokemon | `0xb2a44c` | round, 344-byte record, one byte | loads the record (The offered Pokemon); bit 0 of the byte clear makes it a pick |
| `0102` | CommandConfirmTrade | `0xc8dda0` | round | ignored when session+0x152 is above the round; else partner state +0x134 = 4 |
| `0103` | CommandCancelTrade | `0x2dc51ac` | round, u32 reason | +0xab4 = reason with 1 and 2 swapped, else 0; +0x152 = round; +0x150 += 1; then `0x2dc41f8` |
| `0104` | CommandFinalAgreement | `0x2dc52b4` | round | ignored when +0x152 is above the round or own state +0x130 is not 4 or 5; else partner state 5 |

The cancel sender `0x964a60` sends nothing while own state +0x130 is 2 or 5; otherwise it sends
round +0x150 + 1, sets +0x130 = 2, advances +0x150 and +0x152, and drops the partner's state from
3..5 to 2 (3 when the reason is 0). The handlers reject only a round strictly below +0x152, so a
stale ConfirmTrade or FinalAgreement is ignored after a cancel and a higher round is accepted.
SelectPokemon reads no round.

The session object (0xab8 bytes; `0xca2658`, built by `0xca2704`, vtable `0x3e3a6e8`) holds a
configuration at +0x40 (u16 0x201, low byte the channel), callables at +0x48 and +0x88, and a zeroed
+0x150..+0xab7, so both rounds start at 0 and a session's first `0102` and `0104` are `b90100`.
`0x964568` (own state 6; caller `0x9601dc` in the live trade path `0x95f8f4`) clears the own offer
+0x120 and partner PokemonParam +0x128, sets both states to 2, clears +0x118, +0x11a, +0xd0 and zeroes
+0x150/+0x152: the next trade on the seat starts at round 0, and an answer still at round 1 is
accepted. `pokeldn.za.host` resets its round with each trade.

| own state | written by | when |
|---|---|---|
| 5 | session update `0x95f600` (`0x95f680`) | own state 3 or 4, byte +0x148 set, timer +0x138 at least 1.5 s, partner state 4 or 5, `0x963710` true |
| 6 | delegate invoke `0xdfda8c`, filled at `0x964e78` | the exchange worker's state-6 delegate |
| 7 | `0x2dc4b94`, installed by `0x964f0c` | the worker's state-7 delegate; unreachable in 2.0.2 |

`0x9610a4` (caller `0x95fdbc`) runs at own state 5 or more when the worker at +0xd0 is absent or its
+9 is 0 or 0x10: it calls the callable at session+0x48 with (+0x118, +0x120, +0x128), builds the
exchange worker (`0x966af0`, 0xb0 bytes) into +0xd0 and gives it the state-6 and state-7 delegates
(`0x9649e0`, `0x964a20`), stored by `0x9655a4` at worker+0x20 and +0x60. The trade object is built by
`0xc8ad1c` (`adr` at `0xca2578`; constructor `0xc8ae70`, vtable `0x3d8a0d0`: +0x68 `0xdd07cc`, +0x78
`0x2a67168`, +0x80 `0xcbc68c`); the store making it the callable at session+0x48 is untraced.

The worker's start `0x965660` stores the host test `0x9157d0` at +0x14, clears +0x15, stores
`0x34f2b0(rng, 0x12c) + 2` (2..302) at +0x18, zeroes +0xc and +0x10, sets +9 to 1. Its update
`0x960c20` (one caller, `0x95f750`) switches on +9 through the table `0x33a360d`.
`0x962ac0(peer, step)` stores `0x100 | step` at peer+0x48 and sends it; a wait compares the
partner's step at +0x70, valid when +0x71 is set.

| +9 | handler | what it does | next |
|---|---|---|---|
| 1 | `0x960d20` | trade object vfunc +0x68; result 1: +0x15 = (+0x14 != 0), result 0: +0x15 = 1 (`0x960e50`, `0x960e90`), else +0x15 = 0; send step 3 | 2 |
| 2 | `0x960cc0` | wait for the partner's 3 | 3 |
| 3 | `0x960d64` | trade object vfunc +0x78; false: state 4, send step 6 | 5 |
| 5 | `0x960ce0` | wait for the partner's 6 | 6 |
| 6 | `0x960da0` | `0x9628e8`: trade object +0x40 = 1, then vfunc +0x80 (`0xcbc68c`, the handler update in What the trade writes into a received record) | 7 |
| 7 | `0x960c84` | wait for trade object +0x40 == 3; +0x15 set: send 0xb | 8, else 9 |
| 9 | `0x960c40` | count +0x18 down once per update, then send 0xb | 10 |
| 8, 10 | `0x960ca0` | wait for the partner's 0xb | 11 |
| 11 | `0x960db0` | trade object +0x40 = 4 (`0x961098`) | 12 |
| 12 | `0x960dc0` | wait for trade object +0x40 == 5 (`0x9626e4`), send 0xe | 13 |
| 13 | `0x960d00` | wait for the partner's 0xe | 14 |
| 14 | `0x960de8` | +0x10 == 0: the state-6 delegate (`0x963810`); else the state-7 delegate (`0x9a0b00`); then `0x9637b8` | 0x10 |

Own state 6 is the exchange completed, after both stations passed the `0200b901XX` steps 3, 6, 0x0b
and 0x0e. Handler 14 picks the state-7 delegate when the worker's error word +0x10 is non-zero, and
nothing in 2.0.2 writes a non-zero value there: its only stores zero it, in the constructor
`0x966ba4` (`0x966bcc`) and the start `0x965660` (`0x9656a0`). The worker's abort phase +0xc is read
by the session tick `0x95f6e4` (`0x95f738`): 1 asks the trade object to cancel (`0x9636f8` sets trade
object +0x44 = 1) and parks the worker at step 0xf; 2 waits for trade object +0x44 == 3, then sets
step 14 and phase 3 (`0x95f7e0`). No code stores 1, so the abort phase never starts and no path
through the worker reaches own state 7. A store through a computed address is not excluded; a write
breakpoint on worker+0x10 would settle it. A station whose +0x15 is clear waits the random 2..302
updates before its 0x0b. What `0xdd07cc` returns and how the stored halfword maps onto the `b901XX`
bytes are untraced.

A Z-A choosing Cancel on the trade prompt sends `0103b9020100` (round 1, reason 0) and, once its
player picks again, redraws the prompt with the host's earlier offer without a resend. Its next
confirmation is `0102b90101` and `0104b90101`. A host answering under round 0 is ignored (the
handlers reject a round below +0x152) and the console waits on "Communicating"; round 1 completes the
trade. `pokeldn.za.host`
takes the round from the console's own `0102`, `0103` and `0104`.

### 加入方对这些流的欠债

根据参考对和模拟主机的确认进行测量：

- 协议 10 指向主机的变量 id，协议 11 指向网格 id 0x0001；两者都在两字节收件人页脚中携带主机的变量 id；
- 每个游戏数据包均经过zstd压缩；
- 纯确认位于流的基础 0xfff0 和消息标志 0x40 上；推进序列的一个被读取为后面有一个洞的数据。应用程序数据不携带消息标志；
- 协议 11 上的确认为 74 字节：站的四个字节、一个流字节、四的计数，然后是下一个预期半字的四个条目和一个十六字节掩码，最后一个被缩短。   条目1是加入方的流；其他三个主机报告空闲底座0xfff0；
- 身份在 INIT 下消失，选择记录在其后，然后在新的序列下重复，每次相同的 1211 字节（测量：大约 0.5 秒后，然后大约每秒 4 个字节）；
- 子标头的接收者计数在协议 11 上为 3，在协议 10 上为 0；
- 在协议 11 上，子报头长度计算四字节站前缀后的 VOC，因此每个帧携带的字节数比其声明的多四个字节：开头是 `00000001` 和 `1402 b900`，身份是前缀和整个协议 10 身份，九字节消息是 `1403b9018269fb308f`，确认是前缀和四个完整字节18 字节条目。在其声明的长度处剪切的帧被丢弃（主机每秒重新发送其开头大约十次）；最后四个字节错误的主机会被确认，但会将主机保留在其搜索屏幕上。

LDN NodeInfo本地通信版本（0x40字节的+0x2E）在参考站上为6； 0 的处理方式相同。
### 踢球

一个主机踢了一个自己的变量 id 在 10 秒内没有获取任何数据包的电台，无论其播放器的屏幕如何：它到该电台的 RTT 停止，并且每 501 ms 重复一次会话类型 13（0x0d，其八字节常量 id 大尾数，长度为 10，原因字节为 1），由 `0x2551320` 组成
`0x25512b4`，其两个调用者`0x255bad4`和`0x255bd70`在
`nn::pia::session::KickoutManageJob`（`vfunc6` `0x255bda0`）。 0x0001只是一个目的地；没有人听到它发出的方加入。在捕捉到的踢腿事件中，它发生在座位后 18 至 25 秒。

    0x2547700   from SessionProtocol vfunc 10 (0x2547170), while the local station's byte +0x48 is 2
                and +0x1b0 is non-zero: for each station in state 2, reason 1 through 0x2547dd0 (map at
                session+0x1048) when now > last_heard(+0xb8) + ticks_per_ms * (s32)[+0x1b0]
    0x24f5f08   ticks per ms: GetSystemTickFrequency() / 1000, computed once
    0x25504c8   writes +0x1b0 on session+0x18, and +0x338 of the object 0x24f11f0 returns
    0x253d9d4   session start 0x253d4f0: max([setting+0x28c], 4000) to 0x25504c8
                (0x253d9cc ldr x0,[x20,#0x18]), [setting+0x290] to 0x257d12c just before
    0x199eb48   setting constructors store (+0x28c, +0x290) = (10000, 1000) as one u64; also
                0x199edf0, 0x199f07c, 0x199f2f8, 0x19a0494, 0x19a0a4c, and Pia's default 0x251a4c8
    0x255c990   one-shot table [0x3ee51d8][station id], read and cleared: also kicks with reason 1
    0x2548b60   drains the map into 0x255b4a0, which takes a slot in KickoutManageJob's 24-entry
                table and sends the first type 13; the job's update 0x255bc10 resends every 501 ms
    0x2567280   refreshes last-heard for each station whose bit (byte +0x30) is set in the mask
                0x2566740 builds from the received-data map, keyed by the header's source id
会话+0x18是`SessionProtocol`（0xd8e8字节，vtable `0x3c8db18`，协议类型0xd），由`0x253f284`在Session初始化中的`0x253cacc`为`0x253c880`，在session中也存储了framework+0xb8+0x30。
### 保活

该设置的 +0x290 是以毫秒为单位的发送静默限制（`0x257d12c` -> `0x256a238`；负数失败，并显示
0x10407，0变为1000）。 `SessionPacketWriter`（vtable `0x3c8da30`）vfunc 7 `0x2544004` 调用
`0x256a2d0` 与每个发送的站掩码 (`0x2568924`)：处于状态 2 的每个其他站，其 id 最多为 0x17 且字节 +0xa0 清除 (`0x25770d8`) 在发送时标记为 +0xb0，并且当 +0xb0 早于限制时进行标记（从不发送到包含）。标记站（`0x2568928`）得到一个额外的数据包（`0x256a89c(p, 0, 0)`）：一个协议为0的Pia消息，位0x10字节0xfd，端口0，标志0，空甲醛。因此，只要一秒钟没有任何信息发送到已就座的电台，就会向其发送一个数据包；没有对此进行任何捕获检查。字节+0xa0 标记一个站被踢出，只能由
来自 `0x255b4a0` 的 `0x2577094` 和非主机的排水 `0x2548b60`。
### 数据包 ID

数据包 ID 在每个发送方的两个计数器上运行：一个用于目的地 0x0001，一个用于每个其他目的地（0 和主机的变量 ID 共享它）。 `nn::pia::session::SessionPacketReader::vfunc11`
`0x2566920` 在任何协议之前进行检查：未知来源或不接受任何站点；否则，目标选择控制器（0x0001 为站+0x78，否则为站+0x50），并且 `0x2576ad0` 检查数据包 id（连线 0x0a）和大端随机数（连线 0x0d）：

    id == 0                                         accept, nothing recorded
    last id == 0                                    last id = id - 1
    last nonce == 0 and nonce != 0                  last nonce = nonce - 1
    (s16)(id - last id) < 1                         reject
    nonce != 0 and (s64)(nonce - last nonce) < 1    reject
    otherwise                                       last id = id, last nonce = nonce if non-zero
 被拒绝的数据包转到 `0x25655d8` 并被丢弃：重复的 id，或者前面有一个 0x8000 或更多。对于目标 0 具有单独计数器的方加入，每个 Net 0x51 都会被丢弃，直到它通过主机 id 计数器；主机重复其 Net 0x50 直到一个通过（大约 10 秒，测量）并且其更新序列 1 被延迟。 Net 0x51 处理程序 `0x2504100` 不读取标头字段：它反序列化 (`0x250f930`)，检查长度和类型 0x51 (`0x2504150`)，将源与其站进行匹配 (`0x250c60c`， `0x24fba00`) 并将消息 +4 处的站和确认序列传递到 `0x250daa8`。
### 其余的连接

- Net：连接状态0x11用0x12应答，更新属性0x50用0x51应答。
- 会话：类型 5 更新会话用 15 个字节进行应答：类型、站的 LDN 常量 id、作为大端 u32 的更新序列和 0x0001。 GBA 应用程序的答案（原始 MAC，无序列）使 Z-A 主机每两秒无限期地重复其更新。

接受更新序列 1 的主机在大约 50 毫秒后发送其选择记录（在座位后 1.2 和 1.25 秒，测量）并移动到其交换盒。
### 协议 10 上的交换

双方在选择记录后发送一个 354 字节的 `0101`（大约 2.5 秒后，测量）。提议的最后一个字节在电台主动发送的预览中为 1（每次光标在交换框上移动时，实机都会发送 1），而在玩家选择时为 0； a 主机 键位于该字节上，而不是计数上。以 1 发送的选秀被确认并视为无内容，并且伙伴等待与空槽的“通信”。

方加入用自己的答案回答主机的选择，并用 `0102b90100` 进行确认；主机确认相同，双方都发送 `0104b90100`（加入方的 `0102` 之后 1.5 秒的主机），加入方发送四个 `0200b901XX` 步，一次 03 和 06，在交换动画和交换工作人员随机等待之后发送 0b 和 0e（[交换命令](#the-trade-commands))。主机发送
`0000000202` 位于协议 11 上，并在其前缀下使用 `0201b901XX` 回答每个步骤。
`bin/za_join.py --trade-offer` 运行加入方。
## 提供的宝可梦

该提议的记录是第 8 代和第 9 代实体：四个 0x50 字节块按加密常量打乱，0x148 字节存储，0x158 带有队列尾部，校验和存储在主体上。 `pokeldn.gen9.decrypt`和`read`处理不变；样本提议为异色嗡蝠，等级44，完美IV，球22，能力151，动作542、103、403和162。来自三个参考会话的9条记录均读取版本52，语言10，见面地点200至212，见面日期在2025年10月，训练家ID 5071，秘密ID 14217，初训家“XS”，零身高和体重标量；仅当设置了当前处理程序时，处理程序的名称才显示为“Player”。

由 `pokeldn.gen9.build` 组成的由 344 个零字节组成的记录（或用
`pokeldn.za.pokemon.build_offer`)交易并保存：

|领域 |接收游戏做什么？
|---|---|
|昵称 0x58，昵称位 0x8F 位 7，IV 0x8C |保留，朱的布局|
|品种 0x08 |全国917以下，来自917第9代内部索引（`pokeldn.gen9.internal_index`、`national`）|
|移动 0x72，四个 u16 |保持发送状态（446、328、103、784 作为隐形岩石、沙墓、尖啸、破坏猛击到达）|
|水平|根据0x10的经验：1,000,000个大岩蛇，队伍等级字节为44到达100级|
|统计数据，当前 HP |根据物种重新计算；保留为零，则它们被填充 |
|自然、球、持有物品、光泽|保留 |
| 训练家 ID 12345，秘密 ID 54321 |显示为 993401，即 `54321 << 16 \| 12345` 的六位数字形式 |
|遇见地点 202 |狂野地带 18 |
|能力|未显示在摘要中 |

组成的冰伊布（经验125,000，语言3，遇见2025-10-16，规模128）显示等级50，起源法国，尺寸等级M。保存的记录已经在新的加密常量和PID下再次使用相同的`hi ^ lo`（`--fresh-pid`）进行交易。
### 内存中的记录

每个字段访问器都采用 `x0` 中记录的访问器对象：

|偏移|什么|
|---|---|
| +0x08 |指向 0x10 字节队列尾部的指针，对于存储的记录为 null |
| +0x10 |指向0x148字节内核的指针|
| +0x18 | 1.同时核心被加密|
| +0x19 |快速模式：1 在访问器调用之间保持核心解密 |
| +0x1c | `nn::os::LightEventType`，在清点服务员时发出释放信号 |
| +0x1e |自旋锁所有者字节，0x5f（空闲时）
| +0x1f |服务员计数|

    0xe5d810             16-bit word sum over the 0x140 bytes at core+8; checksum at core+6
    0xe5d8c0, 0xe5d940   crypt: seed = seed * 0x41c64e6d + 0x6073, XOR with seed >> 16, seeded by the
                         encryption constant at core+0 over core+8..+0x147, re-seeded over the tail
    0x3303ab0            block order: 32 rows of four bytes indexed by (EC >> 13) & 31, byte k for
                         block k; rows 0..23 are PKHeX's BlockPosition, rows 24..31 repeat 0..7
 访问器（141 个表引用位于 `0xe48000..0xe5d000` 中）锁定，当设置 +0x18 时解密，重新计算校验和，并在不匹配时将 4 放入 core+4 处的半字中；除非启用快速模式，否则将重写校验和并重新加密。 core+4 的位 2 是 Bad Egg 位，位于加密范围之外（`0xe485f0` 对其进行了测试）。发现它设置的吸气剂，A块中23个中的物种吸气剂`0xe49940`，从.bss中`0x3f7eda0`处的默认记录中读取，由`0xe5cdb4`在`0x3f7ed98`+2处用1初始化为零，语言（0xd5） `[0x3f0784()+0x378]` 和球 (0x124) 4. 串行器
`0xe47a20`（0x158字节）和`0xe47c60`（0x148）写入加密的、打乱的形式。
### main 2.0.2 读取和写入的字段

解密的、未洗牌的记录中的偏移量。代码未显示的名称是 PKHeX 的 (`PKM/PA9.cs`)。

|偏移|尺寸|吸气剂|二传手 |领域 |
|---|---|---|---|---|
| 0x00 | 4 |每个访问者 | `0xe514d0` |加密常数|
| 0x04 | 2 | `0xe485f0` | `0xe51698` |旗帜；位 2 坏蛋 |
| 0x06 | 2 |加载路径| `0xe48250` |校验和|
| 0x08 | 2 | `0xe49940` | `0xe52aa0` |品种：国行917以下，9代内部指数917以上|
| 0x0a | 2 | `0xe49b40` | `0xe52cc0` |持有物品 |
| 0x0c | 4 | `0xe49d50` | `0xe52ee0` | u32 | 训练家ID和秘密ID合一
| 0x10 | 4 | `0xe49f60` | `0xe53100` |经验;级别 = `0xe5ce70(species, form, exp)` |
| 0x14 | 2 | `0xe4a3c0` | `0xe535b0` |能力|
| 0x16 | 2 | `0xe4d7c0` 位 1，`0xe4d9d0` 位 2 | `0xe56ad0..0xe57130` |能力槽：位2隐藏，位1秒|
| 0x18 | 2 | `0xe4a5d0` | `0xe537d0` |标记|
| 0x1c | 4 | `0xe4dbe0` | `0xe57350` | PID|
| 0x20 | 1 | `0xe4d3a0` | `0xe56690` |自然 |
| 0x21 | 1 | `0xe4d5b0` | `0xe568b0` | stat 性质，stat 例程读取的内容 |
| 0x22 | 1 | `0xe4cd70` 位 0、`0xe4cf80` 位 1-2 | `0xe56030`，`0xe56250` |命运的邂逅，性别|
| 0x23 | 1 | `0xe5bcf0` | `0xe5bf00` | PKHeX 中的 IsAlpha（下）|
| 0x24 | 2 | `0xe4d190` | `0xe56470` |表格|
| 0x26..0x2b | 6 | `0xe4aa30..0xe4b480` | `0xe53c10..0xe546b0` |电动汽车 |
| 0x48，0x49 | 2 |无 | `0xe5a7e0`，`0xe5aa00` |身高和体重标量，仅书面 |
| 0x4a | 1 | `0xe512c0` | `0xe5ac20` |规模|
| 0x4b | 1 | `0xe5c120` | `0xe5c330` |等级奖励，PKHeX 中的 LevelBoost（下）|
| 0x58..0x71 | 26 | 26 `0xe4ddf0` | `0xe57570` |昵称，13 个 UTF-16 单位 |
| 0x72..0x79 | 8 | `0xe4b690(i)` | `0xe548d0(i)` |四步|
| 0x7a..0x7d | 4 | `0xe4b8b0(i)` | `0xe54b10(i)` |聚丙烯|
| 0x7e..0x81 | 4 | `0xe4bad0(i)` | `0xe54d50(i)` | PP UPS |
| 0x8a | 2 | `0xe48820` | `0xe51ec0` |当前HP |
| 0x8c | 4 | `0xe4bcf0..0xe4cb60` | `0xe54f90..0xe55e10` |六个 5 位 IV，从位 0、蛋位 30 开始，昵称为位 31 |
| 0x90 | 4 | `0xe48600` | `0xe516c0` |状态条件|
| 0x94..0x9f | 12 | 12 `0xe5cb00(i)` | `0xe5c550(i)` |每次移动标志 264..359 |
| 0xa8..0xc1 | 26 | 26 `0xe50840`，`0xe50a70` | `0xe5a190` |处理者姓名 |
| 0xc2 | 1 | `0xe50ca0` | `0xe5a3a0` |处理者的性别 |
| 0xc3 | 1 | `0xe50eb0` | `0xe5a5c0` |处理程序的语言 |
| 0xc4 | 1 | `0xe4f780`，如 `!= 0` | `0xe58a70` |当前处理程序 |
| 0xc6 | 2 | `0xe4f990` |无 |处理程序的 id（PKHeX 中的“未使用？”）|
| 0xc8 | 1 | `0xe4fdb0` | `0xe58eb0` |处理者的友谊；当 0xc4 为 1 时，`0xe4a170` 返回它，否则 0x112 |
| 0xc9..0xcd | 5 |无 | `0xe59910`、`0xe59b30`、`0xe59f70`、`0xe59d50`（u16 在 0xcc）|处理程序的内存，只写 |
| 0xce | 1 | `0xe4e2a0` | `0xe57780` |版本 |
| 0xd0 | 4 | `0xe5b280` | `0xe5b060` |形式论证 |
| 0xd4 | 1 |无 | `0xe5ae40` |附有丝带，仅写字|
| 0xd5 | 1 | `0xe4a7e0` | `0xe539f0` |语言 |
| 0xd6..0xf6 | 33 | 33 `0xe5cb00(i)` | `0xe5c550(i)` |每次移动标志 0..263 |
| 0xf8..0x111 | 26 | 26 `0xe4e4b0` | `0xe579a0` | 初训家姓名 |
| 0x112 | 1 | `0xe4fba0` | `0xe58c90` | 初训家的友谊 |
| 0x113..0x118 | 6 | `0xe590d0`、`0xe592e0`、`0xe594f0`、`0xe59700` | `0xe4ffc0`、`0xe501e0`、`0xe50400`、`0xe50620` | 初训家记忆：0x113、0x114、u16 at 0x116、0x118 |
| 0x11c..0x11e | 3 | `0xe4e910`、`0xe4eb20`、`0xe4ed30` | `0xe57bb0..0xe57ff0` |见面日期|
| 0x11f | 1 | `0xe5bae0` | `0xe5b8c0` |服从水平|
| 0x122 | 2 | `0xe4ef40` | `0xe58210` |见面地点 |
| 0x124 | 1 | `0xe4f150` | `0xe58430` |球 |
| 0x125 | 1 | `0xe4f360` 位 0-6、`0xe4f570` 位 7 | `0xe58650`，`0xe58860` |达到等级、初训家性别|
| 0x126 | 1 | `0xe5b6b0` | `0xe5b490` |超级训练位|
| 0x148 | 1 | `0xe49760` | `0xe518f0` |水平，躯干尾部|
| 0x14a..0x155 | 12 | 12 `0xe48a40` 和另外五个 | `0xe51ae0..0xe528b0` |最大生命值和五项统计数据 |
| 0x156 | 2 | `0xe48c20` | `0xe51cd0` |有符号的最大 HP 偏移量 |

访问器范围内的任何函数都不会触及这些字节，并且在每个游戏机制作的记录上全部为零：

    0x1a..0x1b  0x2c..0x47  0x4c..0x57  0x82..0x89  0xa0..0xa7  0xc5  0xcf  0xf7
    0x115  0x119..0x11b  0x120..0x121  0x127..0x147
 在朱的布局（由PA9.cs保存）中，他们保存了比赛统计数据，扑克牌，丝带和标记（0x2c..0x47），重新学习动作（0x82），战斗版本（0xcf），彩蛋日期和位置， HOME 追踪器 (0x127) 和 TM 记录 (0x12f)。 PA9.cs 将 0x4b..0x57 映射为 DLC TM 记录； main 只读 0x4b。

|字节|使用 |
|---|---|
| 0x4b |统计等级 = `level + [0x4b]`，上限为 200 (`0x10f558`) |
| 0x156（s16，在 PA9.cs 中未映射）| `0xe4163c`使用`max(1, maxhp + (s16)[0x156])`；加载路径永远不会写入它，因此组合值仍然存在 |
| 0x23 |模型描述符 `0x106a48` 在 +0x13 存储 `[0x23] != 0` (`0x106ba0`)，在 +0x12 旁边存储鸡蛋或坏蛋，并且缩放为 `(scale / 255) * 2 - 1`；唯一的二传手从 `0xe3f140` 调用。恰好在两个游戏机录制的 255 记录上排名第一 (罗丝雷朵 407, 冰伊布 471) |

0x4b 和 0x156 在每条游戏机制作的记录中均为零。
#### 每次移动标志

PA9.cs的加移动记录：360位，位k在0xd6 + k/8，k低于264，在0x94 + (k - 264)/8以上（朱的Tera类型在0x94/0x95是标志264..279 此处）。移动的索引是其在rodata `0x3303fb0`的340 u16移动ID中的位置，通过线性搜索`0xe669e0`找到（如果不存在则为-1；然后每个调用者都会跳过该标志）。 `0x631834` 设置一个标志，`0x673448` 清除 1，`0xe438e4` 清除数组，`0xe43068` 读取 1。大岩蛇，招式为 446, 328, 103, 784，旗号为 33 38 88 91 103 106 157 174 225 231 328 444 446 457 784。招式为 58, 103, 162, 247, 328, 403, 423、446、542、573 和 784 均在列表中。

`0xe343a0(species, form, move)` 读取个人条目的第 25 字段（vtable +0x36，通过
`0xe3cb88` 和 `0xe36850`)，为{u16 move, u8 level, u8解锁级别}的向量，并返回匹配的解锁级别或0。学习级别为1..100、253或254。在2.0.2表中：

|学习水平|解锁关卡|
|---|---|
| 1（4,803 条）| 10 | 10
| 3..100 (14,717) | 3..100 (14,717) |学习等级+3；例外情况 99 给出 100（六）和 102（一），33 给出 37（二）|
| 254、现种| 10 于 274 中的 266；其余的 19、20 或 22 |
| 253 | 253 192 年第 48 期第 10 期； 39、15、12、33、38 等其余 |

带有 vtable `0x3e28e58` 的 PokemonParam 包装器（321 个插槽，每个插槽都指向 +0x50 处的 PokemonParam）以三种方式使用它：

|槽 |功能|它是做什么的 |
|---|---|---|
| 135 | 135 `0x6a30b0` |列出解锁级别非零且等于其级别参数的移动 |
| 145 | 145 `0x631834` |设置移动标志，跳过移动 `0xe669e0` 未找到 |
| 150 | 150 `0x699308` |当解锁级别非零且级别（`0xe49760` 或来自存储记录的经验的 `0xe5ce70`）达到该级别时，true；否则标志|

旗帜可以解锁关卡规则无法解锁的动作；所有标志为零的记录仍然会解锁处于或低于其级别的每个学习集移动。 `0xe669e0` 的主叫方为 `0x631848`（置位）、`0x67345c`（清除）、`0x6993c8`（时隙 150）、`0xe4307c`（读）。位写入器 `0xe5c550` 仅由 `b` 从 `0x631864`（置位）和 `0x673478`（清零）输入；插槽 145（两个包装器 vtable 的 `0x63182c`、+0x488）有四个调用站点，因此游戏机以两种方式设置标志：

- `0x52fff0`、`0x824eb0` 和 `0x28eec70` 调用槽 135 并标记其列出的该级别的每个动作。
- `0x6568c4`，在构造例程`0x656060`（五个调用者）中，仅当包装槽+0x8b8（`0xdf5488`，`0x106ba0`，字节0x23 getter）为真时运行：它看起来按物种向上移动（插槽+0x1b0）和形式（插槽+0x1b8）在`0x657ae0`（来自GOT `0x3eca658` = `0x6137848`的地图，通过`0x511f90`;未找到源文件），检查它`0x41ea50`，通过槽+0x110（`0x6568a4`）写入移动槽0并标记它。

接收或加载的记录将其标志完整；接收路径上没有任何内容读取该数组。

摘要屏幕 `0x8d0610` 通过插槽 150 (`0x8d1a18`) 标记每一步“/plus_on”或“/plus_off”，在设置游戏标志 `flag_megaevo_disable` 时交换（`0x393b8`，命名标志读取，在
`0x8d1438`;密钥记录 `0x3db5548`，FNV-1a-64 哈希值 `0x5d0f3c74b46a0ff5`）。

控制台根据{解锁级别<=级别}创建的记录：

|记录|水平|旗帜|额外的标志 |未标记 |
|---|---|---|---|---|
| 嗡嗡714| 44 | 44等于| |举行542（解锁47级）|
| 青绵鸟 333 | 44 | 44等于| |举行297（解锁47级）|
| 哲尔尼亚斯 716 | 100 | 100等于| |持有 583（索引 214，不在其学习集中）|
| 大岩蛇 95 | 72 | 72 350 人失踪（254 级）| | |
| 罗丝雷朵 407 | 63 | 63 866 失踪（254 级）| 605（索引 227），字节 0x23 移动到插槽 0 | |
| 冰伊布 471 | 63 | 63等于| 247（索引 112），字节 0x23 移动到插槽 0 | |

冰伊布还携带伊布的 36、38、129、204 和 273（其自己的学习集中有 254 个条目）； 罗丝雷朵携带40，毒蔷薇（315）的253条目。
#### 能力

朱的u16位于0x14，槽位位于0x16。 GetAbility `0xe43bec` 返回低于 299 (0x12b) 的存储值，否则来自个人表的 `0xe5d368(species, form, bit 2 ? 2 : bit 1)`。 0x14的其他读取器只有类型获取器`0x99c84`和`0xa4354`（能力为121的物种493和能力为225的物种773从持有的物品`0xe5d528`、`0xe5d5a0`中获取类型）。创建例程
`0xe3eb34` 和 `0xbb8f04` 从 `0xe5d368` 写入。控制台制作的记录存储 5、30、38、81、151、187。

没有屏幕显示存储的能力。 `0xe43bec`仅由`b`从`0x288d894`输入，引擎组件的插槽42（`0x3d1a918`）（vtable地址点`0x3d1a7c8`，类型id `0xfb63b93a`，构造函数`0x2890cb8`);到原始吸气剂 `0xe4a3c0` 的所有其他路径都是类型吸气剂。七个 321 槽 PokemonParam 包装器 vtable（`0x3e28e58`、`0x3e29950`、`0x3e2a438`、`0x3e2af50`、
`0x3e2ba38`、`0x3e2c520`、`0x3e2d360`）制作插槽 42 `mov w0,wzr; ret`（`0x2d6fd88` 和三个副本）。战斗能力窗口`0x2d52468`（“BTL_STRID_STD_TokWin”，“tokusei”`0x31e3d5f`）读取槽42（`0x2d524f4`）。在模拟的 2.0.2 上，摘要页面没有命中 `0x288d894`、`0x2d52468`、
`0x2d6fd88`;狂野区战斗仅命中 `0x2d6fd88`，来自 `0xdc68c`。组件注册表
`0xd8a04`在handler+0x4c处缓存slot 42（`0x2ae8f4`，handler vtable `0x3d1b0a0`）；它的读者下落不明。
### 加载接收到的记录会检查什么

合作伙伴的 `0101` 达到 `0xb2a44c`，注册为 CommandSelectPokemon（`0xca33d8`，从 `0xca2928` 调用）。解串器 `0xb4e248` 需要具有三个成员 (`0xb4e33c`) 的标签 0xb9，将第一个读取为 u16 (`0xa91178`)，要求第二个是恰好为 0x158 字节的标签 0xbc (`0xb4e4b8`) 并将第三个保留在 struct+0x15a 处；出现任何错误时，不会调用处理程序 (`0xb4e1c8`)。处理程序分配 PokemonParam (`0x82713c`) 并加载 344 字节
`0x270994`：

1. `0xe47e94` 将 0x148 字节复制到核心，将 16 个字节复制到尾部，解密两者并比较校验和；不匹配会导致坏蛋位。它清除快速模式，因此通过重写校验和并重新加密来结束加载：错误的校验和会被纠正，并设置坏蛋位。
2. `0xe3f18c`：对于非零物种，`0x2901a4(species, form)` 在个人表（`0xe366b0`，键控 `species * 10000 + form` 的映射）中查找该对，并读取 FlatBuffers 字段 1 的字节（vtable +6，`0xe3bbfc`），不存在时为 0。零设置坏蛋位 (`0xe51698(acc, 1)`)。丢失的键会回退到map+0x80，即species-0条目，它没有字段1。
3. `0xe41750(pp, 1)` 将经验中的级别写入尾部，并重新计算最大 HP 和来自物种、形态、统计级别、IV、超级训练位、EV 和统计性质的五个统计数据。    当为 0 时，当前 HP 保持为 0，否则按最大 HP 增益增加。
4. `0xe42584` 用 PP ups 将从槽 0 开始计数的非零动作的 PP 钳位到最大值（`0xe6646c`）；除非设置了 `[0x3f0784()+0x380]` 或 `0xe483b4` 为真，否则将跳过鸡蛋或坏蛋（`0xe4c950`、`0xe485f0`）。
5. `0xb2a4a4` 使用 PokemonParam 调用 session+0x88 处的可调用对象，忽略其结果，将其移至 session+0x128 中，并在第三个成员的位 0 清零时将伙伴状态 +0x134 设置为 3（选择）。可调用始终为 `0xad2c68`，名称检查如下（`0xca20a4` 在 `0xca2520`、`0xca25d8` 处使用它构建配置；没有其他引用它）。

没有任何东西可以根据学习集、球、气象数据、教练 ID、能力或尾部水平来检查动作。组合记录仅因错误的校验和或个人表字段 1 为零而失败，两者都会造成坏蛋，而不是拒绝；被拒绝的名字被重写。校验和错误的记录被绘制为鸡蛋图标，级别 0，男性符号，在提议的昵称下，提供“交换它”；交易后，它以“蛋”的形式落入盒子中，摘要为空，游戏继续运行。
### 收到的宝可梦名称检查

`0xad2c68` 返回空记录（IsEmpty `0x13778`），否则运行 `0x89f250`（其他调用者
`0x89de34`）：它使用0x20000字节缓冲区（`0x912e10`）将`nn::ngc::ProfanityFilter`打开到全局`0x612d3d0`中，用`0x9138d4(str, len, language)`检查三个名称并最终确定（`0x912d80`）。

|名称 |语言通过|失败时|
|---|---|---|
|昵称，0x58 |记录的，0xd5 | `0x8a0370` 以该语言写入物种名称 (`0xe33ca0`) 并清除昵称位 (0x8c 位 31) |
| 初训家，0xf8 |记录的，0xd5 | `0x3d8a248[language]`，用 `0xe579a0` 编写 |
|处理程序的，0xa8 |处理程序的，0xc3 | `0x3d8a248[language]`，用 `0xe5a190` 编写 |

12 或更多的语言将表索引为 0。当 `[0x3f0784()]+0x380` 和 accessor+0x1a 均为 0 时，`0x8a0370` 不会为 Egg 或 Bad Egg（`0xe4c950`、`0xe485f0`）写入任何内容。替换表`0x3d8a248` 保存 12 个 UTF-16 字符串：0、1、6 `ゼット.`； 2 `Z`； 3 `Zed`； 4、7、11 `Zeta`； 5
`Zett`； 8 `제트.`; 9、10 `Z.`。

`0x9138d4` 在以下情况下名称失败：

- 其长度为0或第一个单元为0；
- 7 个单位或以上且任何单位位于 0x3041..0x3090、0x30a1..0x30fa、0x4e00..0x9fcc 或0xac00..0xd7a3（`0x3308840`、`0x33087b8` 的车道）；
- 语言为1..5、7或11，第一个0之前的任何单位都在0x4e00..0x9fa0中，而不是0x4edd；
- L（来自`0x444330`）为0、6或11以上；
- 过滤器的 vfunc +0x28，由 `0x913ad0` 调用为 `(&result, pattern, &str, 1)`，模式为 `0x339f650[L - 1]`，留下非零结果。

长度扫描 `0x913a80`（跳过 0x10 标记的运行）测量为 0 的字符串在没有过滤器的情况下通过，过滤器调用返回错误 (`0x913b08`) 也是如此。处理程序语言为 0 的空处理程序名称变为 `ゼット.`，空的初训家名称为记录语言的字符串；完成的交换会覆盖处理程序的名称。 PKLDN 和参考名称通过。

L，游戏的文本语言，是单例`0x6131800`的字节+0x14（GOT `0x3ec7800`；读取
`0x444330` 到 `0x410a20` 一次 +0x80 标记其已构建）。它被编号为记录的语言字节，并索引消息目录表`0x3e278b8`（步长0x18，`0x940dd8`）：0,1,6“jpn”，2“英语”，3“法语”，4“意大利语”，5“德语”，7“西班牙语”，8 “韩国”、9“Simp_Chinese”、10“Trad_Chinese”、11“拉丁美洲”、12“项目”。当加载程序 `0x410a30` 的语言参数为 0 (`0x410a68`) 时，它使用 L。

启动时 `0xaa1340` 在 +0x10 处存储由 `nn::oe::GetDesiredLanguage()` 组成的索引 `0x17d6368` (ja, en-US, fr, de, it, es, zh-Hans, ko, nl, pt, ru, zh-Hant, en-GB, fr-CA, es-419如0..14，否则15），而`0x741760`通过`0x330f728`，`1 2 3 5 4 7 9 8 2 2 2 10 2 3 11`（14以上的2）将其映射到L，因此引导值为1..5或7..11。设置者`0x17d62ec`是+0x14的编写者之一；它的其他调用者是语言选择视图（`0x2c204ac`）、带有培训师记录的+0x47的`0xbb9d30`，以及存储任何整数的脚本绑定`0x1673170`（`0x16734c0`）。

模式 `0x339f650[L - 1]` 是一组 `nn::ngc` 单词列表，因此接收游戏机的语言会选择它们，无论记录的语言是什么：

|左 |图案|列表 |
|---|---|---|
| 1 日语 | 0x13 |日语、美式英语和英式英语 |
| 2 英语 | 0x12 |美式英语和英式英语 |
| 3 法语 | 0x36 |美式和英式英语、加拿大法语、法语 |
| 4 意大利语 | 0x92 |美式和英式英语、意大利语 |
| 5 德语 | 0x52 |美式和英式英语、德语 |
| 6 | 0 |没有任何;这个名字已经失败了|
| 7 西班牙语, 11 拉丁美洲西班牙语 | 0x11a |美式和英式英语、拉丁美洲西班牙语、西班牙语 |
| 8 韩语 | 0x412 |美式和英式英语、韩语 |
| 9, 10 中文 | 0x8813 |日语、美式和英式英语、中文、台语 |
### 交换写入接收记录的内容

交换的第6步调用交换对象vfunc +0x80，`0xcbc68c`，它调用`0xcbc7fc`。除非
`0xcbc9e8` 返回 null（`0xcbc854`，跳过更新），它用 `0x882104` 填充玩家训练家记录中的结构（`0x505c30` 来自 GOT `0x3ec28d8` 的单例）：u32 +0x40 （训练家ID和秘密ID），性别+0x45，语言+0x47，13个单位的名字来自+0x50。它用`0x825358`包装伙伴的PokemonParam（交换对象+0x78）并调用包装槽167（`0xcbc888`，+0x538；
`0xcebfe0` 在两个包装器 vtable 中），对 `0xcebfe8` 的 thunk ：

- 初训家的性别（`0xe4f570`，0x125位7），u32 0x0c（`0xe49d50`）和姓名（`0xe510c0`）都匹配结构：0xc4 = 0 (`0xe58a70`)，调用`0xe3f900`，返回1；
- 否则0xc4 = 1，结构名称（`0xe5a190`），性别为0xc2（`0xe5a3a0`），语言为0xc3（`0xe5a5c0`），0为处理程序的内存0xc9、0xca、0xcb 和 u16 0xcc（`0xe59910`、`0xe59b30`、`0xe59f70`、`0xe59d50`）、 `0xe340ac(species, form)`到友情0xc8（`0xe58eb0`），调用`0xe3f900`，返回0。

接收到的宝可梦会以接收玩家为训导员，除非该玩家是其初训家。每个 setter 在仍标记为加密的记录 (+0x18) 上重新求和 (`0xe5d810`) 并在不匹配时设置坏蛋位 (`0xe58b60..0xe58b80`)；在坏蛋上，它写入 `0x3f7ef98` (`0xe58bcc`) 的接收器。
### 个人表

`0xe380c0` 从 `0x7961b0` 配置为“avalon/data”(`[[0x3f7f038]]`)的目录加载 `personal_array.bin`，就像 `waza_array.bin`、`tokusei_array.bin` 和 `growTable.bin` 一样：

| | |
|---|---|
| `/arc/data.trpfd` | 9,877,520 字节：238,546 个文件哈希值，13,181 个包 |
| `/arc/data.trpfs` | 4,753,821,072 字节，魔法 `ONEPACK` |
|名称哈希 | FNV-1a 64，基础 `0xcbf29ce484222645` (`0xe38438`) |
| `avalon/data/personal_array.bin` |哈希 `0x68ab38e2cf1281ed`，文件索引 97074 |
|它的包装| 169、`arc/avalondatatokusei_array.bin.trpak`、trpfs `+0x4bc1840`、131,488 字节、4 个文件 |
|它的条目 |压缩类型3，110,132字节，`OodleLZ_Decompress`解压384,260 `0x1a9c9e0` |

包含 1445 个表、1445 个不同键的 FlatBuffers 向量。字段 0 以物种开头并形成半字，由地图生成器 `0xe36170` 键入为 `species * 10000 + form`（地图+0x80 处的键 0）。物种运行 0..1010，全部存在，434 个条目的形式高于 0； 917 中的键是第 9 代内部索引。字段 1 是超过 364 个物种的 594 个（物种、形态）对中的 1，其他 851 个物种中不存在。这 594 个等于 PKHeX 的 `personal_za` 存在列表，最多 1010 个； PKHeX 的 1011..1016（14 对）没有条目，以坏蛋的形式到达。 Mega Dimension DLC 不附带个人表（其一个 PublicData NCA，101,376 字节，包含 692 字节 RomFS）。物种 95、333、407、471、707、714 和 716 以 0 型存在。

在拳击或交换路径上没有发现拒绝坏蛋的情况。 `0x962388` 盒子里只有一个宝可梦，既不是空的（IsEmpty `0x13778`）也不是鸡蛋或坏的（IsEgg `0x18e4c`），而是实时交换路径
`0x95f8f4` 直接通过 `0x961964` (`0x960000`) 装箱。在交易所上，egg 和 Bad Egg 测试仅跳过工作：PP 钳位 `0xe42584` 和统计重新计算 `0xe41750`（由
`0xc34b5c`）。
## 与实机的交换

零售 Z-A 在其 Link Switch 搜索中与 `bin/za_join.py` 进行交易并保留完整的记录。交换后，游戏机返回到同一个座位上的交换箱并可以再次交换：`0x964568` 将两个状态重置为 2，并将两个回合重置为 0（[交换命令](#the-trade-commands)）。

加入方重复执行 `--trade-offer`：第四步后 2.7 秒，它会预览下一条记录，并在第 0 轮游戏机的下一个选择中选择它。`bin/za_join.py` 和 `bin/za_host.py` 在 ldn_mitm 上按顺序交换记录队列（`tests/test_za_host.py` 是加入方一侧的脚本），加入方在一个席位上用零售 Z-A 主机交换了两张排队的记录。

游戏机的交换动画在第四步之后运行，并且不包含交换命令。零售Z-A加入`bin/za_host.py`，从第四步开始：动画在1.1秒开始，收到的宝可梦在26秒左右出现（手按，最多晚2秒），游戏机的下一个预览（`01 01`，354字节）在30.2秒到达，玩家在31.7左右控制s。游戏机在其间不发送协议 10 消息。在游戏机的主机阶段较晚形成的席位将被移交：第一个数据报迟到，没有更新序列 1，并且游戏机每秒重复会话类型 9 一次（在 wiki 编号中开始主机迁移，这将踢到 12，而 Z-A 使用 13），直到它重新启动其网络（测量：第一个数据报在与正常座位上的 0.1 秒关联后 1.4 秒，网络6.5 秒后重新启动）。零售朱的搜索在硬件上表现相同；双方均未追踪到任何代码。
## 托管

搜索游戏机还扫描并加入携带标题广告及其链接代码的网络。 `bin/za_host.py` 主机一台； `pokeldn.za.host` 针对模拟对的交换逐字节固定。

|从座位上|主机发送什么 |
|---|---|
| 0 秒，每 0.46 秒一次，直到应答 |网络连接状态 0x11：序列 2、四个插槽、12345 上的主机和加入方 |
|在会议上加入 |加入方 ID 的加入响应（类型 2，37 字节），更新会话（类型 5，序列 0）为 0x0001 |
|与它| INIT 下协议 10 上的标识；身份和 `1403b9018269fb308f` 捆绑在协议 11 上，前缀 `00000002` |
|与它|净更新属性 0x50，每 0.5 秒一次，直到 0x51 |
| 0.2 秒起 | RTT请求到0x0001，大约每秒3个；对每个加入方的回应
|确认更新 0 后 1.15 秒 |更新会话序列 1 |
|一旦更新 1 被确认 | 1211 字节选择记录两次，间隔 60 ms |
| 2.7 秒后 |预览 `0101` |

与GBA应用程序的主机不同：

- 更新会话中的主机站条目携带标识令牌`0x06`；
- 更新序列被写入两次，分别在+1和+21处；
- 属性更新在 GBA 应用程序写入 `01` 的场景 id 之后携带 `02`（CloseParticipation，如下）；
- 广播确认报告条目 1 中的加入方流，其他三个中的 0xfff0。

零售 Z-A 加入 `bin/za_host.py` 并进行交易（提议标记：[协议 10 上的交换](#the-trade-on-protocol-10)）。任何链接代码都适用于这两种角色（`--code`，使用 12345678 进行测试）。

主机在第四次交换步骤后保留会话，并在游戏机离开时关闭。 A 游戏机在交换后返回其盒子并与 B 一起离开且没有错误；主机在离开后关闭。 `--hold-after-trade` 选择定时关闭；总体 `--seconds` 限制仍然适用。交换保存后，在计时器上关闭网络的主机会在游戏机上绘制“错误号：6”。

托管席位依次交换重复的 `--trade-offer` 中的记录队列：在上一次交换的第四步之后预览下一条记录。当玩家退出时，游戏机就会离开。交换后回到盒子上，游戏机在光标下预览宝可梦，因此 `--offer-out` 只保留选择。
### 属性更新

Net update 属性（类型 0x50）由 `0x2502960` 构建（序列位于 NetProtocol+0x160，通过
`0x250f5d0`）并由 `0x250e414` 进行大端序列化。从 0x26 字节网络消息开始的偏移量：

|电线|尺寸|领域 |
|---|---|---|
| 0x04 | 4 |序列号，NetProtocol+0x160 |
| 0x08 | 8 |网络 ID、会话属性 +0x90 |
| 0x10 | 2 |参与者人数 (`0x25050dc`) |
| 0x12 | 2 |站槽，NetProtocol+0x1216 |
| 0x14 | 8 |会话属性值（`vfunc +0x10`）； LDN 属性将场景 ID NetworkInfo +0x0a 保留在 +0x98 |
| 0x1c | 1 |接受状态（`0x2505ec0`）|
| 0x1d | 1 |会话属性 `vfunc +0x80`，位 0 |
| 0x1e | 4 |系统属性大小(`0x24fe4dc`) |
| 0x22 | 4 |游戏数据大小（`vfunc +0x50`）|

一旦设置了主机地址（+0x1280）和站自己的地址（+0x1260），或者当+0x12d0非零时，`0x2505ec0`返回NetProtocol+0x340处的字节； else 0. 它的作者：

|作家 |价值|
|---|---|
|网络创建和自动连接作业（`0x2511b94`、`0x2511658`），第三个作业站点 `0x2515714` |设置会话属性字节 +0xa6 时为 1，清除时为 2 |
| `0x2515434`，来自作业字节+0xc0（由`0x2515220`存储）| 1 至 `0x250758c` (`NetFacade` vfunc 17)、2 至 `0x2507828` (vfunc 19) |
| 主机迁移 `0x250b060` |当字节为 1 时重新运行 1 路径，否则重新运行 2 路径 |
|设置器 `0x2500a9c` | 1 来自 `0x25fdc90` 和 `0x25fe1ec` |
|接收 0x50 (`0x25035bc`) 的站 |消息的字节； `0x2502e70` 将自己的 +0xa6 设置为 `byte != 2` |

LDN 会话属性将 +0xa6 设置为 `stationAcceptPolicy == 0`（NetworkInfo +0x62、`0x25234b8`）。 1表示全部接受； 2 表示标志已清除。

2 条路径，自上而下：

    0x1a25454   game task slot 13 (vtable 0x3c17cc0, constructor 0x1a25390): calls 0x253e744 only
                while the session's (u64, u16) at +0xe0/+0xe8 is non-zero and equals +0xf0/+0xf8,
                the host test 0x9157d0 makes; returns when 0x253da70 finds the state object at 1
    0x253e744   -> 0x253e780 -> 0x253e7bc (0x10408 while state +0xd0 reads 1 or byte +0x528 is 0)
                -> 0x2546fe8(0), close -> 0x255c118, OpenCloseParticipationJob (facade session+0x30
                at job+0xc8): OpenParticipation 0x255c264 calls facade index 17, CloseParticipation
                0x255c404 calls index 19 (0x255c484)
    0x25183bc   facade index 19 (Net, Local, Lan, Wan, Nplnd facades): operation 0xa via 0x2507828;
                index 17 (0x251826c): operation 9 via 0x250758c
    0x2515220   0x250758c passes 1, 0x2507828 passes 2; when [[job+0xe0]+0x344] is 1 and 0x2513c0c
                returns 0, stores it at job+0xc0 (0x25152c0), else fails with 0x10408
    0x2513c0c   stores it at LdnBackgroundProcessJob+0x9b (0x2513c6c, the only writer), schedules
                vfunc 37 0x2513ccc: LDN protocol index 23 when +0x9b is 1, else 24 (0x2513d1c)
    0x2515434   copies job+0xc0 into the accept state (0x2500a9c), builds the Net 0x50 (0x2502960)

`nn::ldn::SetStationAcceptPolicy` (PLT `0x3163b60`) 在 `LdnProtocol` 中有 3 个调用者：索引 23
`0x251f18c` 设置 0（全部接受），索引 24 `0x251f110` 设置 1（拒绝），索引 21 `0x251f208` 设置 3（白名单，在 `AddAcceptFilterEntry` 之后）。在 Pia 中，`0x255c484` 是对 Facade 索引 19 的唯一虚拟调用，`0x2513d1c` 是 LDN 协议上通过 0xc0 的唯一调用，因此游戏关闭参与，策略 1 遵循，仅当它是会话主机时。主机迁移调用
直接 `0x250758c` 和 `0x2507828`（`0x250b098`、`0x250b0f8`）。

使用“CloseSession”（哈希 `0x0dd344f64c81e84d`）从本地会话驱动程序（`0x19a7590`，地址点 `0x3c16dc8`）的索引 19、第二个驱动程序（`0x1a2ab10`）的索引 19 以及 CloseSession 步骤调用任务生成器 `0x1a228f0` `0x19d7a70` 和 `0x1a35710` 的随机匹配序列。网络管理器仅通过主机测试（`0x2a49218`，来自 `0x915630`、`0x2cb5238`、`0xae0eb8`）后面的请求达到驱动程序索引 19 (`0x199dec4`)。本地驱动程序的插槽 13 (`0x19a1310`) 运行序列 `0x19a1470`；它的 CloseSession 步骤将槽 13 的第四个参数的位 0 传递给 `0x19d7a70`，它在设置时构建任务，并在清除时命名“NoNeedToClose”。

一旦加入方被承认，在代码 00000000 下托管链接交换搜索的模拟游戏机就会运行槽 13，从 `0xc8a198` 调用，第四个参数为常量 1（`mov w3, #1` 在
`0xc8a194`）。大约 10 秒后，从 CloseSession 步骤进入任务生成器 `0x1a228f0`
`0x19d7a70`（返回地址 `0x19d7acc`），以及来自 CloseParticipation 的门面索引 19（返回地址 `0x255c490`），而加入方保持就座，交换箱打开。从盒子里出来后，两者都没有再到达。

在实机的链路交换搜索中，广告持有策略 0，其中 2 个节点位于座位上，Pia 玩家计数（广告数据 +0x16，`e1 01 01 00` 到 `e1 01 02 00`，唯一变化的字节）移动到 2，然后策略 1 在游戏机的一个网络之前进行广告0x50（150字节，序列1，接受状态`02`），对于坐席会话策略保持1。前面没有主机迁移，因此零售 `02` 是 CloseParticipation 的；哪个任务生成器启动它尚未解决。通过加入方板解密的四个就座会话进行测量：玩家在 0.07 至 0.59 秒计数 2，策略 1 在 0.09 至 0.64 秒网络 0x50 之前 2 至 48 毫秒首次公布。对于 2 名参与者中的 2 名，该政策不会拒绝容量所没有的任何内容。
## 离开

一个站通过两个 `nn::pia::session` 作业之一离开，每个作业都等待来自另一个站的答复。调度程序 `0x2547490` 读取的会话类型（表 `0x336a9b7`，类型 0 到 17）：

|类型 |尺寸|发件人 |留言 |
|---|---|---|---|
| 3 | 22 | 22 a 方加入 离开 |离开请求：类型，随机 u32，其常量 id（8，大端），其变量 id（2），地址类型 0，其 IPv4，端口 |
| 4 | 15 | 15主机 |离开响应：类型，随机 u32，从请求复制的离开者常量和变量 ID |
| 9 | 30|主机离开|开始主机迁移：类型、主机常量和变量 ID、0、主机 IPv4 和端口、下一个主机的常量和变量 ID、`00 01` |
| 10 | 10 21 | 21站名类型9 |它的确认：类型，它自己的常量和变量 ID，然后是主机的 |

`pokeldn.za` 构建全部四个（`build_leave_request`、`build_leave_response`、`build_migration_ack`）。
### A 加入方离开

`LeaveMeshJob::SendLeaveRequest`（`0x2557e54`）将类型3发送到主机并设置500毫秒的截止时间； `WaitLeaveResponse` (`0x2558098`) 在类型 4 上完成并在每个截止日期重新发送，总共发送四次（计数器 +0x9c，`0x25581e0` 处的 `cmp w8, #2; b.gt`），然后在没有发送的情况下完成。 `0x25474f8` 仅在 15 个字节处且仅当字节 5 至 14 是站自己的 id 时才采用类型 4（+0x1b8、+0x1c0）；它设置作业的字节+0x99。主机的类型 3 处理程序 `0x254c5ac`（22 或 34 字节，仅限主机）在 `0x254c740` 处写入类型 4 并删除站 (`0x2548500`)。

加入主机的零售 Z-A 不发送类型 4，发送了四个类型 3，间隔约 0.5 秒，并在第一个发送后 2.0 秒取消身份验证（三个出发时间分别为 1.99、2.02 和 2.03 秒）。
`bin/za_host.py` 用类型 4 回答每个类型 3； `bin/za_join.py` 在离开 `--hold` 或 `--hold-after-trade` 时发送自己的类型 3，并继续类型 4 或在第四次发送后。
### A 主机离开

> 本节已随上游更新，以下内容暂保留英文。

`LeaveMeshWithHostMigrationJob` names the next host (`CalcNextHost` `0x255a6fc`), then
`SendStartHostMigrationMessage` (`0x255a91c`) sends the type 9 once a second until a 5000 ms
deadline (`0x255a8c8`), after which the job fails with `0x6c0e`. `WaitStartHostMigrationAck`
(`0x255abb4`) completes as soon as byte +0xe0 is set. The type-10 reader `0x2550a64` takes a 21-byte
message only on the host, only when bytes 11 to 20 are the host's own ids, and sets +0xe0 through
`0x255a630` when bytes 1 to 10 are the named next host's.

With the type 9 unanswered, a retail Z-A hosting a trade whose player backed out sent five type 9 one
second apart, then Net 0x11 sequence 3 from source 0 every 0.5 s for about 4 s, then Net 0x40 for
about 2 s, and went silent 10.82 to 10.86 s after its first type 9 (four departures); its network
went down 11.26 s after it in the one traced on the board. In an emulated pair the joiner answered
the type 9 with a type 10 48 ms later, the host sent Net 0x11 sequence 3 and the joiner answered
`0112000000000003`; the host's network was gone 0.25 s after its type 9. The joiner's type 10 and
0x12 went out with header flags 2, destination 0, packet id 0 and no footer.

With the type 10 and the 0x12 sent at once, a retail host sent the 0x11 0.04 s after its type 9
and then Net 0x40 (`01 40 00 00`, source 0) every 0.3 s for 4.06 s while the joiner stayed on its
network; no second type 9 came.

The Net 0x11 is the leaving host's connection status in the migration form of
`NetDestroyNetworkJob` (`0x2516444`, flag at job+0xd8, set when the disconnecting station is host,
`0x2503c44`): `0x2501930` bumps the sequence (NetProtocol+0x15c) and byte 29, the is-migrating byte,
is 1 while the NetHostMigration state NetProtocol+0x12d0 is 1 (`0x250f084`). It asks every client
for a Net 0x12 of that sequence; a client stores the sequence, sets NetProtocol+0x308 and answers
(`0x2503164`, `0x25035c0`). The host waits up to 4000 ms for every 0x12, then sends the 0x40 every
300 ms for 4000 ms, or 2000 ms when the wait expired, until it is alone, and destroys its network
(`0x251693c`, `0x25169f8`).

The 0x40 starts the next host's work: `0x2503d44`, on a station that is not host, calls
NetHostMigration start `0x25099a4`, which picks the next host (`0x2505d10`) and runs
`NetHostMigrationJob` (`0x2509da0`). On LDN it leaves the old network (`0x2503b14`); the next host
opens a network (`0x2507050`) and waits 6000 ms for the remaining clients, dropping any that do not
come back (`0x250acf0`); a client waits 1000 ms and reconnects. Success clears NetProtocol+0x12d0
and stores result 1 or 2 (host) or 3 (client) at NetProtocol+0x12d4; failure stores 4 with error
`0xc406`.

A Link Trade ends at the handover. The type-9 handler `0x2550684` removes the leaving host's station
(`0x2548500`) before starting `ProcessHostMigrationJob`, which drops the session's station count
(session+0x110). The trade scene update `0x95f398` runs the trade only while that count is above 1
(`0x95f45c`) and otherwise ends it with reason 3 (`0x95f508`), the ending a partner's leave request
also reaches. In a two-station trade the leaver is the only partner, so the trade ends whatever the
migration does, and the leaving console destroys its network.

Leaving on that first 0x40, the joiner was off the network 0.09 s after the type 9 (no trade, the
player backing out of the box).

`bin/za_join.py` answers a type 9 naming it with the type 10, and the Net 0x11 after it with the
0x12, and leaves the network on the first Net 0x40 (or once the console has been silent for a
second).

## 神秘礼物

2.0.2版神秘礼物提供网络获取、密码获取、查看神秘礼物；没有本地无线路径。
## 未解决

> 本节已随上游更新，以下内容暂保留英文。

- Whether game code reaches facade index 19 other than through CloseParticipation. A hosted Link
  Trade search with one joiner reached it from CloseParticipation.
- Whether a shipped script calls the binding `0x1673170` that stores any integer into L, and what the
  language-select table `[x0+0x50]` holds (breakpoint `0x16734c0`, read at `0x2c204ac`).
- Whether an optional timed close (`--hold-after-trade`) can leave the console without an error
  while it is still seated. The default host waits for the console's departure ([Hosting](#hosting)).
  A leaving retail host sends the type 9 first ([A host leaving](#a-host-leaving)); the timed close
  in `bin/za_host.py` sends none.
- What a retail Z-A shows and keeps after its trade ends at a handover it receives: the partner-left
  message, and whether the network it recreates stays open for a new joiner (`0x961a40` onward).
- What a station does with a protocol-0 message, and the keepalive's header bytes (`04 00` by the
  header diff). A capture of a seated station the console has nothing else to send to.
