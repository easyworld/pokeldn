---
title: Tera Raids
parent: Scarlet and Violet
nav_order: 1
---

# Tera Raids

A local Tera Raid is a Scarlet/Violet session of up to four stations on LDN scene 7. The host runs
the lobby, then sends every participant one bootstrap message holding the four players' Pokemon, the
boss and its RaidPoint, and each console fights the battle on its own. `bin/sv_host.py --raid-seed`
hosts a raid a retail console joins, `bin/sv_join.py --raid-pokemon` joins one a console hosts; in
both, the program's player leaves as the battle begins and its Pokemon fights on as the console's
AI partner. Addresses are offsets into the decompressed `main` of Scarlet 4.0.0, the version the
retail Scarlet measured here runs; Violet 4.0.0 has the same code at the same offsets
([docs/sv.md](sv.md)).

## Hosting

The host advertises scene 7, four participants and Link Code 4970. The console joins from
X, Poke Portal, Tera Raid Battle, offline search. `--raid-seed` with the four context flags picks the
raid ([The seed](#the-seed)), `--raid-pokemon` is the party record our player brings (PKHeX checks
it), and `--raid-reward ITEM:QUANTITY`, repeated, replaces the seed's rewards with rows of items the
Scarlet/Violet bag holds (the PKHeX helper's `bag` list: every pouch but the key items, unreleased
items out). `--raid-partner TRAINER`, up to once for each slot the consoles leave empty (two with
one console, one with two), seats those NPC partners in slot order, and
`--raid-partner-progress STAGE` picks the stage they come from ([Partners](#partners)). The app's
Tera Raid (Host) tool carries the flags below.

    --channel 1 --scene-id 7 --max-participants 4 --code 4970 --scarlet-response --session-flags 0
    --session-packet-id 1 --no-session-ack --join-seq 0 --update-seq 0 --update-delay 0.02
    --rtt-probe --clock --net-stations 4 --record-delay 0.1 --record-spacing 0.003
    --host-player-id 00000000000000010000000000000000

In raid mode the host differs from a trade host in what it addresses and when:

| | a raid host |
|---|---|
| mesh-addressed messages (RTT, 0x80, 0x81), the Session station lists | to the subnet broadcast, not the console's address (unicast over ldn_mitm, which carries no broadcast to a peer) |
| Net 0x11 | one sequence, repeated until the 0x12 |
| the station list's console entry | the player the console's join request named; with a placeholder player the console is seated and absent from the lobby |
| the station list | resent every 2 s until the console's type 6 |
| the opening | only after that type 6: the eleven first bulk acks, the 0x81 port 5 open and an RTT request in one packet; the 0x81 port 1 open, the channel table and the port-2 type 6; the identity 20 ms later, one record every 3 ms |
| the port-2 type 3 | answered with two type 9s: the host's station with code 0, the console's with code 1 |

The opening's 0x7C, 0x81 port 5 and 0x80 port 2 messages repeat every 0.25 s until acknowledged,
and every ack the host sends declares the lowest unacknowledged sequence of the stream.

### Several consoles

`--raid-players N` (1 to 3, the app's "Consoles joining") seats up to three consoles in one lobby,
each at the lowest free station index, 1 to 3. The consoles share the lobby and the start;
from the first turn each one fights its own battle, with its own NPC partners, and gets its own
rewards ([Which station runs the server](#which-station-runs-the-server)). The host keeps one set of streams per console, as for
a single one, with that console's index wherever a single console's raid has 1:

| | the console at index *k* |
|---|---|
| join response | station index and join order *k* |
| station list | every seated station, ours first; each new seat and each departure from the lobby sends the list to every seated console under the next sequence, resent until each one's type 6 |
| Net 0x11 | our station, then the seated consoles by index, then the joiner; each change of seats goes to every seated console under its next sequence |
| destination bitmap | `1 << k` under three destination bits |
| bulk ack | entry *k* |
| opening | 0x81 ports *k* and 4 + *k*, the ports the console sends on |
| port-2 type 6 | ours and the members already seated, in join order, with their codes and count |
| port-2 type 9s | ours under code 0, each seated member's under its code, the console's last under code *k*; each seated member receives the console's |
| bootstrap | its Pokemon in slot *k*; an empty slot for a free seat |

A join that finds every seat taken, or comes after the start, is left unanswered, and a console with
no free seat gets no Net 0x11. The host drops every packet whose header and footer do not name its
own variable id, and every reliable message whose bitmap lacks station 0: consoles in one lobby
address each other through the same broadcast.

A port-2 slot keeps its members at slot `+0x170` as a u8 code and a u64 station id;
`0x138d208` returns a station's code, 0xfd for a non-member. A retail host's type-3 handler
`0x1981e94` takes the lowest code 0 to 7 that no member holds and no queued type 9 names
(`0x279c9a0`), then broadcasts one type 9 per member with its own code and one for the joiner. The
receiver `0x18b68fc` appends a `(code, id)` it has not listed, never changing a listed member's code;
for its own id it raises a member-joined event for every other member, and the code becomes its
own. The type 6 (`0x12fbf8c`, composer `0xe457cc`, to the joining station only) carries the members'
ids at `+0xa0`, their codes at `+0xc0`, the count at `+0xc4` and the closed byte at `+0xc5`; its
receiver `0x279b9c4` replays a type 9 for each member.

The lobby's participants are the port-2 members: the Lua lobby (chunk `be21e654`, receiver
`0.15829`; a `0.N` here is the chunk's main function's prototype N, counted from 0) files every
message under its sender's code, and under 253 a sender with no code. Each console sends its state
0x18 and its Pokemon to the others on entering the lobby, and a station receiving a 0x18 answers
with its own Ready state and Pokemon; the consoles of one lobby exchange their Pokemon among
themselves.

The reliable header's receive check (`0x6f0410`..`0x6f0430`) tests the receiver's own bit,
`index & 31` of word `index >> 5` (bit 0 station 0), for any destination count from 1 to 23. A
retail sender writes three, the station capacity 4 (`0x44dfcb0`) less one (`0x6e71c4`), whatever
the number of stations.

The host hands the network to the lowest index still on it, as for one console; the other consoles
draw the is-migrating Net 0x11 and NetStartHostMigration with no Session type 7. The is-migrating
0x11 to each console ranks every seated station (a rank is who hosts next) and goes to the others only
after the next host's type 8; NetStartHostMigration goes out once every console has answered its 0x11
with 0x12, and no plain Net 0x11 follows. The run ends once every console has left the network or each
handover has run out.

What decides whether the consoles stay in one battle:

| condition | code |
|---|---|
| a console that sees another leave keeps it only once it is migrating: `[net+0x249]` set by an is-migrating 0x11, or `[net+0x1c0]` set by NetStartHostMigration; otherwise it drops it from its session and resets its Net station | station-left handler `0x69d08c`, `0x69d174` |
| a Net 0x11 with a newer sequence drops every station marked as gone | `0x69e008`, `0x6b5074` |
| the next host waits up to 8000 ms for every Net station to reach state 2 (seen on its new network), then drops those still in state 1, sends Net 0x11, waits for every 0x12 and sends the Session type 5 | NetHostMigrationJob `0x6a9cd4`, `0x6aa2a8`; `0x6d44f0` |
| the other console waits 10000 ms for that type 5, then fails | `0x6dc024`, `0x6dc124` |
| the type 7's last u16 at most the next host's applied list sequence | `0x6d9164` |

Two emulated Scarlets handed over this way formed one session on the next host's network (type 5
answered with type 6, no error on either screen) and fought on with an NPC in the free seat.

A Pia host sends the new Net 0x11 to every station on each change of LDN participants: `0x69c310`
compares the previous and current connection status, `0x69c79c` increments the one counter
`[NetProtocol+0x60]` and sends every slot to each station but its own, rankings in ascending IPv4
order (`0x6a05ec`). On LDN a joiner's 0x11 receiver `0x69db14` creates no station from its entries
(`0x6a2fac` returns 0): it stores the host's address and ids, copies rankings onto stations it already
has and answers 0x12. A joiner's stations come from the LDN node list (`nn::ldn::GetNetworkInfo`,
`0x6b43a8`), port 12345.

The type-5 receiver `0x6d7f8c` creates each newly listed station in `0x6d840c` only when its IPv4
and port are in that node list (`0x6a8320`); otherwise it sends no type 6 and resets its applied
sequence to 0xffff (`0x6d81a4`), so a later copy of the same list is evaluated again.

Session type 9 (`0x6d4ef0`), from a joiner to the host, `09 | its constant id | count | count
constant ids`, names the stations it has not heard from (`0x6d4a60`) and repeats every 3000 ms. The
host's receiver `0x6d940c` hands a single named station to the kick job (`0x6dc878`) and resends the
station list to every station.

After a console's join a raid host sends packet id 0, or the seated console drops what follows a
higher id
([docs/pia.md](pia.md#version-11-what-a-receiver-drops-scarlet-400)): a station list resent under
packet id 1 after a packet with id 87 left the first console of a two-console lobby on its old list
(retail and emulated), and the second showed "Communicating..." until it reported the first silent.
Sent the later lists under packet id 0, two emulated consoles and two retail Scarlets listed each
other and fought one raid, in sync after the host left.

A random player id of the form `10 00` and fourteen random bytes drew no type 6 from a retail
console; the anonymous id `00000000000000010000000000000000` (`pia_connect.DEFAULT_PLAYER_ID`) seated
it.

## The lobby

A raid message is a game message on 0x80 port 0: a u16 handler key, a kind byte, a step byte
([The trade](sv.md#the-trade)), then the game serializer's header and a payload.

| bytes | field |
|---|---|
| 0 | handler key, u16 |
| 2 | kind, step: one u16 message id (0x012f the bootstrap, 0x0193 the battle begins) |
| 4 | a counter, u16, per sender, incremented on every send by `0xa583fc`: a retail host's lobby runs 0x0105 to 0x010e, a guest's 1, 2, 3... |
| 6 | compression, u32: 0 none, 2 LZ4 |
| 10 | the payload's plain size, u32 |
| 14 | a network-object id, u16, zero unless the sender's `0x14ede48` finds one |
| 16 | two bytes of padding the constructor never writes (stale heap in retail messages) |
| 18 | the payload |

| key | kind | what |
|---|---|---|
| 0x3380 | 0x2c | the raid's descriptor: species (DevID), form, stars, Tera type, gender, the encounter's record number |
| 0x3380 | 0x2d | a participant's state: 0x00 not ready, 0x01 ready, 0x0c the host's start, 0x0d a guest's answer to it, 0x18 entering the lobby, 0x1e the host refusing a late station (`0.30822`) |
| 0x3380 | 0x2e | a participant's Pokemon, its encrypted 344-byte party record |
| 0x3380 | 0x2f | the battle bootstrap |
| 0x3380 | 0x30 | the lobby timer, in seconds left (0x91 downwards) |
| 0x0132 | 0x6e, 0x73 | a console loading the battle, then loaded |
| 0x3480 | 0x93 | the battle begins |
| 0x007b | 0x13 | the battle-start messages a host sends after 0x3480 |

A retail guest sends 0x18 and its Pokemon on entering the lobby and 0x01 when its player presses
Ready: in seven retail raids four guests sent 0x01, 1.9 to 3.6 s after their Pokemon, and three sent
none before the host's start at 5.39 s; all seven answered the start with 0x0d and fought.

The header is message object `+0x40..+0x4f`. The receive path `0x18bec54` copies the id, the
counter and the object id back into the object and compares none of them; it does not check the LZ4
return value, and uses the plain size only as the output capacity.

A battle-start frame on key 0x007b is a 12-byte port address (three u32), a u32 length and a
payload whose first 32 bytes are a header struct copied verbatim by `0x1227714`: u32 type at 0x00,
u64 at 0x08 and 0x10, u8 at 0x18 and 0x19, and padding at 0x04 and 0x1a..0x1f. Message 15 carries
`05 05` at 0x18 then padding `07 26 5a 00 00 00`; message 16 (type 0x46, builder `0x2898350`)
carries `ceaf29` in the padding its builder never writes. The readers `0xf5a2fc` (+0, +8, +0x10,
+0x18, which accepts 5 or the receiver's own index) and the type switch `0xe10088` (0x46 handler
`0x2897afc`) read no padding. `0x14ab234` drops a frame unless one of the receiver's ports
registered its address: message 15 is addressed (0x2713, 1, 2), messages 16 to 20 (0x2713, 3, 5),
where 0x2713 is a runtime u32 at `+0x40` of an object whose writer is untraced.
An emulated Scarlet 4.0.0 given messages 13, 15 and 16 with that padding zeroed acknowledged every
battle-start message on its first send and began the battle with the host's Pokemon, as with the
retail bytes.
An emulated Scarlet 4.0.0 took the keep branch `0x14ab210` 13 ms after the host sent messages 15
and 16: `0x14ab234` matched a battle-start frame's address and `0x14ab298` stored it.

The battle reads message 16 by its type. The reader `0xe0fd68` pops a frame and, when the header's
u64 at +0x08 is 0, switches on the type at +0x00 (`0xe10088`): type 0x46 calls `0x2897afc` with
`[reader+0x48]` as its only argument, and `0x2897afc` stores 1 at its `+0x71`. That argument is the
per-frame update `0x289358c`'s own object: `0xfa4bb4` builds it with the initialiser `0x28950c8`
(`+0x40` the battle state machine, here `sm`; `+0x48` the stepped object `[sm+0xa8]`, `+0x50` the reader
`[sm+0xb0]`), stores it at `[sm+0x148]` (`0xfa4c18`) and assigns it to `reader+0x48` (`0x2892ab4`
at `0xfa4c68`). The state `0x28932a4` calls the update with `[sm+0x148]` (`0x28932d0`). The update
reads `+0x71`: while the byte is 0 it pumps
the reader (`0xe0f014`) and calls `0xfc363c([+0x48], 0)`; while it is 1 it stops pumping and calls
`0xfc363c([+0x48], 1)` each frame, and `0x28935b8` clears the byte when that returns true. With 1,
`0xfc363c` takes an item from the source at `+0xa8` and hands it to the sinks at `+0xa0` and `+0xb8`
while the sink at `[+0xb8]+0xa0` is empty. The sink holds a deque (map `+0x60`, start `+0x98`,
size `+0xa0`) and steps each element's vf `+0x68` every frame (`0xfc38dc`). The update's result is
unused (`0x28932d4`) and nothing on this path writes the state machine's state at `+0x68`.
An emulated Scarlet 4.0.0 popped on the type-0x46 branch a frame carrying a marker the host wrote into
message 16's padding (`46000000 d16a1616`, `0500 161616161616`): the frame was message 16. The pop
came after the network had gone down, after the Error 7 dialog and before the first command menu,
on the update's own pump (return addresses `0x28935d0`, then `0x28932d4`).

In 4.0.0 no decision reads the padding. The receive path loads the serializer header's last two
bytes (`0x18bec98`) and stores them at `+0x4e` (`0x18bece4`) with no comparison; of the 49 message
classes, only the serializers `0x290b150` and `0x14c7904` load `+0x4e`, to write the header out. The
battle-start readers `0xe0fd68`, `0xe106a4`, `0xf5a2fc`, `0xf5a810` and `0xf5bc10` read the 32-byte
header at +0x00, +0x08, +0x10, +0x18 and +0x19; `0xf5a454` and `0xf5ae40` copy all 32 bytes into a
frame `0xf5bb4c` re-sends, and compare none. The transport copies (`0x14ab150`, `0x14ab234`,
`0x16a319c`) compare only the 12-byte address.

The channel table a raid host announces on 0x7C port 1 holds six keys, zlib-compressed: a Link
Trade's four (`0x007b`, `0x0132`, `0x0232`, `0x0332`) and `0x3380`, `0x3480`. A retail guest
announces them as two messages: the four, then the raid's two 0.79 s later. Port 2 carries a type 6
from the host: the type 7's session block under kind 5 and capacity 4, then a list of four slots
with the host's station id in the first (`port2.build_session`).

`pokeldn.sv.raid.RaidHost` releases the host's messages to one console in order, each at its time
from the port-2 answer and after the console's previous step; `pokeldn.sv.raid.RaidGroup` holds what
the consoles of one lobby share. With one console that readies within 5 s the sequence numbers are a
retail host's:

| seq | message | released by |
|---|---|---|
| 1 | descriptor (zlib, INITIALIZED) | the console's own lobby Pokemon (0x2e) |
| 2, 3 | state 0x18, our Pokemon | |
| 4, 5, 6 | timer 0x91, 0x90, 0x8f | 0.73, 1.76, 2.75 s |
| 7 | state 0x01 | 3.19 s |
| 8, 9 | timer 0x8e, 0x8d | 3.76, 4.79 s |
| | the timer, each time it drops | one step a second from 0.73 s after the first console's answer |
| 10 | state 0x0c, the start | 5.39 s, once `--raid-players` consoles are seated and every one has sent 0x01, or once the timer has sent 0 |
| | Net 0x50, property state 7 | the console's state 0x0d |
| | Session station list, the next sequence | the console's Net 0x51 |
| 11, 12 | the bootstrap, two fragments | the console's type 6 for it |
| 13 | loaded, `0x320173` | the console's 0x6e or 0x73 |
| 14 | the battle begins, `0x803493` | the console's 0x73 |
| 15 to 20 | the battle-start messages | the console's 0x93; then 0, 0.10, 0.12, 0.16, 0.18 s |

The timer is the seconds left before the host's lobby deadline: a retail host opens a 180 s lobby
and sends the value once a second (`0.27104`), so the 0x91 of the table came 35 s after it opened.
Our timer starts at 180 at the first console's answer; a console that joins a running lobby
receives it at its current value. A console's 0x00 or 0x18 withdraws its 0x01; its Pokemon does
not, since a ready console resends it to each newcomer.

In the game's code a guest answers 0x0c with 0x0d at once, with no Ready check, and a guest whose
timer reaches 0 waits for the bootstrap (`Raid_Start_Ready`, `0.27137`): only the host starts a
battle. A guest that holds the bootstrap without having readied ends its lobby before the timer
(`0.27104`) and goes to the battle the same way. A retail host readies on its player's first choice
and sends 0x0c on the second (`0.27095`). `Raid_Start_Ready` turns the menu's first three items off
(`f6277C172(false)`) on entry, on host and guest alike; on a host it turns the first, the one that
starts, and the menu back on while every other member is ready, and off again when one is not: its
player can start only once every guest is ready. Whether `f6277C172(false)` hides an item or greys
it out is unresolved. At timer 0 it breaks the lobby up when no member is ready and starts
otherwise. `Raid_Start_Go` (`0.27140`) resends 0x0c until every member has answered 0x0d, then sends
the bootstrap, slot *k* the Pokemon of the member with code *k*; ours waits for every console's 0x0d
too, and starts once every console is ready or at timer 0 whoever is ready.

A gated message leaves 50 ms after its milestone; the Net 0x50 and the station list repeat every
0.5 s until answered, and the raid messages every 0.5 s until acknowledged. A retail console once
answered the bootstrap with 0x73 and no 0x6e, so message 13 waits for either.

Five seconds after the last console's message 20 the host hands the console its network as a leaving retail host does
([docs/sv.md](sv.md#leaving)): Session type 7 naming the console, every second until its type 8;
Net 0x11 in its is-migrating form, every 0.5 s until its 0x12; NetStartHostMigration `01400000`
every 0.3 s until the console leaves the network or 4 s pass. A host that destroyed its network 5 s
after message 20 instead drew 2318-0006 on the console's screen at the battle's opening in one of
four retail raids, the battle going on offline after it.

The Net 0x50 is the trade host's property body (`NET_PROPERTY_BODY`) with sequence 1, the network
id, byte 27 set to 7 and the host's 132 application bytes at +38, zlib-compressed under message flags
0x31. Sent uncompressed under 0x31, it drew no 0x51.

## The battle bootstrap

Message 0x2f carries a 0xaa0-byte record, LZ4-compressed (the block format alone, `pokeldn.sv.lz4`):

| offset | size | what |
|---|---|---|
| 0x000 | 4 x 0x158 | the four participants' party records, encrypted, the host's in slot 0 |
| 0x560 | 0x158 | the boss's party record |
| 0x6b8 | 0x3e8 | the RaidPoint |

The serializer `0xe327fc` writes the five records from the message object's `+0x440`, `+0x448`,
`+0x450`, `+0x458` and `+0x50` through `0xe329b4` (0x158 bytes each), then four quadwords from
`+0x58` and 0x3c8 bytes from `+0x78`. The object (0x460 bytes) is made by `0x18bb4fc`, typed by
`0x18bb5f8`; `0x1592b7c` writes the serializer header and picks the compression, `0x1592dac` and
`0x1592e80` run LZ4 (`0x71d940`). The RaidPoint is copied whole: `0x1bae670` calls `0x1bae760`, which
takes it through the reflected-field getter `0x1baff98` (the pointer at `+8`, or a zeroed 0x3c8-byte
singleton) into `+0x78` by `0x1bb0018`.

An empty participant slot holds species 0 at level 1, nicknamed `Egg`, Tera types 19, language 2,
current HP 11 and stats 11/5/5/5/5/5, the same record in every retail bootstrap; a bootstrap with
all-zero empty slots crashed a retail console as its battle began. The guest's slot 1 is the record
from its lobby message 0x2e. A retail host split the message at 1395 bytes, the second fragment
zlib-compressed.

The RaidPoint, offsets from its start:

| offset | size | what |
|---|---|---|
| 0x000 | 24 | the point's name, ASCII, `RaidPoint_` and a suffix (`RaidPoint_POKELDN_0` is accepted) |
| 0x018 | u32 | 0x40 (one retail black point held `0x458F9952`; 0x40 is accepted) |
| 0x020 | 4 x u32 | stars, the crystal (0 standard, 1 black; [2 and 3 for an event](#event-raids)), the record's `captureRate` (1; an event's 0 or 2), its `captureLv` |
| 0x030 | 7 x u32 | the record's `raidTimeData`: active (a bool), `gameLimit`, `clientLimit`, `commandLimit`, `pokeReviveTime`, `aiIntervalTime`, `aiIntervalRand`; `raid_point` writes an active record's, zero for an inactive one |
| 0x04c | 37 x u32 | the boss's action profile: HP coefficient, the shield's nine values, six extra actions (action, timing, value, move), the double action's three values |
| 0x0e4 | 45 x 16 | reward rows: item, quantity, a rare-item flag, subject |
| 0x3b4 | u8 | 0 in a retail standard point, 1 in a retail black one |
| 0x3b8 | 7 x u32 | stars, species (DevID), form, gender, level, 0, Tera type |
| 0x3d8 | u64 | `randSeed`, the partner seed ([Partners](#partners)) and the battle's random seed ([The battle's random numbers](#the-battles-random-numbers)): nonzero in retail points; `raid_point` writes the one it is given, 0 by default |
| 0x3e0 | u32 | `raidNpcGroupID`, the host's raid unlock stage, which picks the partner pool ([Partners](#partners)): 4 in every retail point seen; `raid_point` writes the stage of the raid's progress unless given one |

In the raid tables every six-star record's `raidTimeData` is active with `gameLimit` 450 and
`commandLimit` 60, every one-star record's inactive with `gameLimit` 300, and the rest zero; a retail
black point (record 6045) carried 1, 450, 0, 60, a retail three-star point (record 3019) an inactive bool byte with three stale bytes after it, then zeros.
Bytes 0x3b5..0x3b7, 0x3d4..0x3d7 and 0x3e4..0x3e7 held stale bytes in both retail points.

The action profile is the record's `bossDesc` in the game's raid tables, in that order; the
actions are 0 none, 1 reset the boss's stat changes, 2 reset the players', 3 a move, 4 drain the
Tera orb, and the timings 0 none, 1 time, 2 HP. An action's value is the share of the boss's HP or
of the time left that brings it, and the shield's first two values are the HP and time shares that
raise it, either one; Serebii's scripted actions for the seven-star Kingambit of August 2026 read
the same from its record. HP coefficients run 500, 500, 800, 1200, 2000 and 2500 for one to six
stars.

A retail point's reward rows are the seed's fixed rows, then its lottery draws, then the host's
bonus rows: three under subject 4 and one under subject 5. A fixed row's subject is the reward
table's `SubjectType` (0 every player, 1 the host, 2 the guests, 3 once); the game's enum
`RaidRewardItemSubjectType` has no 4 or 5. In both retail points the subject-4 rows were the seed's
lottery drawn three more times on the same generator, and the subject-5 row the boss's Tera Shard
with the count `RaidGemItemRewardBoost` gives its difficulty (0, 0, 2, 5, 10, 12 and 0 for one to
seven stars; 2 at three stars, 12 at six). The meal-power table reader `0xef885c` reads one raid
field, `AddRewardSlots`. A row's third word was 1 on a Bottle Cap lottery row and 0 elsewhere.

An emulated Scarlet 4.0.0 guest sent one row under each subject 0 to 5 listed subjects 0, 2, 3 and 5
on its reward screen and left out 1 and 4. With a meal's Raid Power: Ghost Lv. 1 active it left out
subject 4 against a Steel Tera boss and listed it against a Ghost Tera boss; sent three subject-4
rows there, it listed the first only. Sent four subject-4 rows against the Ghost Tera boss, it listed
the first two with the power at level 2 and the first three at level 3.

An active meal power is held in memory as u32 kind, u32 type, u32 level and an f32 of seconds left,
1800 when eaten and counting down in the field. The level 2 and 3 checks above, and the one below,
wrote the level and type words of a Jambon-Beurre's Raid Power: Ghost Lv. 1 record.

On a black-crystal point (seed `09F3E337`, Kingambit with Tera type Fairy) with a Raid Power: Fairy
Lv. 3, the same guest listed 18 of the point's 19 rows: every subject-0 row, the subject-2 row, the
three subject-4 rows and the subject-5 Fairy Tera Shard x12; it left out the subject-1 row. The one
row carrying the rare-item flag, the subject-4 Bottle Cap, came first on the screen; the others kept
the point's order. The point was `raid_point`'s with only the action profile replaced (HP coefficient
100, the rest zero) so that a single guest could win; its stars, crystal, `raidTimeData` and rows
were the seed's.

Scarlet 4.0.0's Lua reward filter, `C07C34FC3B976E5A7.F316609DEA110601D`
(lines 78707 to 78765 as its bytecode records them), keeps subject 0 for every player, 1 for the host, 2 for a guest
and 3 when its once-reward eligibility argument is true. It keeps the first N subject-4 rows,
where N is the highest level of an active Raid Power matching the boss's Tera type. Meal kind 5
is Raid Power; type 18 matches every Tera type. Subject 5 requires item 2481, the Glimmering Charm,
in the receiving player's inventory. The row counter advances for every subject-4 row.
Executing the unchanged Lua function with native environment getters supplied by a test harness
kept zero, one, two and three subject-4 rows at levels 0 to 3, for both host and guest, with and
without the charm. Mismatched types kept zero; multiple matching powers used the highest level.

A host matching retail reward construction preserves each fixed row's subject and each row's
rare-item flag, writes ordinary lottery rows under subject 0, then appends three continued
lottery draws under subject 4. It appends the difficulty's Tera Shard boost under subject 5
when its quantity is positive. Each receiver applies its own meal and charm eligibility.

The timer initializer `C2D7F486425487755.F0C64BA9B6853E61A` (lines 79486 to 79513 as its bytecode records them)
uses supplied time fields when `raidTimeData.active` is true. With it false, a group battle uses
game limit 300, command limit 60, client limit 0, revive time 30, AI interval 17 and AI interval
randomness 6. Executing its unchanged Lua function with the six-star table data yielded
450, 60, 0, 0, 0 and 0 respectively; a zeroed RaidPoint yielded the defaults.
Both functions are in Lua chunk `be21e65463b9a98f`, SHA-256
`c1a4f4e2625912cf0b739a642a79ba3357df0557a544b92da22a6cb139de2815`.

`raid_point` builds the seed's rows as a retail host does: each fixed row's table subject, the
lottery table's rare flag, three more lottery draws under subject 4 and the difficulty's Tera Shard
boost under subject 5. For seeds 7B741233 (three stars) and 09F3E337 (black) its 45 rows equal the
retail points' bytes. A retail Scarlet guest holding the Glimmering Charm, sent seed 7B741233's
rows, listed Ice Tera Shard x1 and x2: the subject-5 row, and not the host's subject-1 x1 row.
Chosen rewards go under subject 0 with no bonus rows, so a guest receives
every one. A retail console awarded a row rewritten to Quick Ball x500, with the other
rows cleared and one bonus row left, as written.

## Partners

Every console fills the participant slots no lobby member holds with the same NPC trainers, drawn
from two RaidPoint words the Lua calls `randSeed` (u64 at 0x3d8) and `raidNpcGroupID` (u32 at 0x3e0)
(`0.4453`). The natives behind their getters read +0x3b8 (`0x1be5ac0`) and +0x3c0 (`0x1be5c20`) of
the 0x3c8-byte struct that follows the RaidPoint's first 0x20 bytes. The guest's bootstrap handler
reads both (`0.15829`); a retail host draws a new `randSeed` at each start and writes both
(`Raid_Start_Go`, `0.27140`). The u64 seeds xoroshiro128+ whole (native `0x17ebec0`), with
`0x82A2B175229D6A5B` as the second word. The console draws three trainers (`0.7804`), each
`next_int(n)` over the n trainers still in the pool (masked to the bits of n − 1, redrawing values
of n or more) and taken out of the pool, so in the full pool the bounds run 18, 17, 16. The empty
slots take the draws in slot order (`0.4455`): one empty slot takes the first, wherever it sits.

The u32 at 0x3e0 picks the pool, the data table field `difficulty_0`*N+1* (`0.7797`), its trainers
and their Pokemon (the table below): 0 and 1 the first 16 trainers, 2 all 18, 3 and 4 all 18. A
partner's Pokemon is built at level int(0.8 × the level of the Pokemon in battle slot 0, the
host's), not its preset's (`0.4455`, `0.4901`), so Serebii's levels 16, 40 and 80 are those of Lv
20, 50 and 100 hosts. In a pokeldn raid slot 0 holds `--raid-pokemon`. Retail Scarlets showed Eli's
Gardevoir at Lv 80 beside a Lv 100 one and at Lv 29 beside a Lv 37 one, whatever their own Pokemon's
levels (100 and 84), and the first stages' Eli's Kirlia and Charlotte's Staravia at Lv 80 beside a
Lv 100 one, past their pool's 16. At 5 a retail Scarlet's partners were Pikachu named after the boss
and its battle crashed later, so `raid_point` refuses a stage past 4.

A retail host writes its raid unlock stage at 0x3e0: `raidNpcGroupID` comes from native `0xe2826c`
(Lua binding `0x193a560`, `0.2895`), which reads four save flags through the flag getter `0xeb1cf4`
and returns the highest set, no other flag counting:

| flag key | name (PKHeX) | stage |
|---|---|---|
| none set | | 0 |
| `0xEC95D8EF` | `FSYS_RAID_DIFFICTLTY3_RELEASE` (`KUnlockedRaidDifficulty3`) | 1 |
| `0xA9428DFE` | `FSYS_RAID_DIFFICTLTY4_RELEASE` (`KUnlockedRaidDifficulty4`) | 2 |
| `0x9535F471` | `FSYS_RAID_DIFFICTLTY5_RELEASE` (`KUnlockedRaidDifficulty5`) | 3 |
| `0x6E7F8220` | `FSYS_RAID_DIFFICTLTY6_RELEASE` (`KUnlockedRaidDifficulty6`) | 4 |

Executed under unicorn with a mocked flag store, all 16 flag combinations return this mapping. The
Tera Raid unlock flag (`0x27025EBF`) is not read, so 0 is a save with one- and two-star raids or
none. The stage is the story progress less one (`raid_encounter.PROGRESS` from `tera`), and the
seven-star events share stage 4. The pool of stage 2 (Serebii's level 40) comes with four stars, one
stage after the "3 Star Raids Unlocked" heading Serebii gives it.

One den gives different partners on different attempts. A retail console ignored party records in
bootstrap slots no lobby station held: it still drew two partners. The bootstrap goes out after the
host's start, so a guest that leaves the lobby before it never holds the RaidPoint.

`pokeldn.sv.raid_partners` holds the table and the draw. `bin/sv_host.py` writes the stage of
`--raid-progress`, six stars for a black crystal or a seven-star event raid, or the one
`--raid-partner-progress` names, and draws a new partner seed for each run. With `--raid-partner` it
draws seeds until the first draws are those trainers in that order: 306 seeds on average for two of
eighteen, about a millisecond. Its log names the seed, the partners it seats and their level, four
fifths of `--raid-pokemon`'s (`raid_partners.level_for`). Our player and each console joining
(`--raid-players`) hold a slot, so a pokeldn raid seats two partners with one console, one with two
and none with three (`raid_partners.slots`); more `--raid-partner` than that are refused before the
radio. The host takes the seed's first draws to fill the empty slots left to right; a console that
misses the start leaves one more empty slot, which a further draw fills. Two retail Scarlets joining
`--raid-players 2 --raid-partner Eli` showed Eli's Gardevoir in the one empty slot, the fourth.

The pool, in draw-index order, from Serebii's Tera Raid Battle partners page:

| # | trainer | 0x3e0 0, 1 | 2 | 3, 4 |
|---|---|---|---|---|
| 0 | Austin | Growlithe | Camerupt | Arcanine |
| 1 | Ava | Buizel | Floatzel | Toxapex |
| 2 | Logan | Skiddo | Gogoat | Arboliva |
| 3 | Hailey | Magnemite | Magneton | Bellibolt |
| 4 | Evan | Skwovet | Greedent | Dudunsparce |
| 5 | Charlotte | Staravia | Altaria | Staraptor |
| 6 | Kylie | Crabrawler | Primeape | Tauros |
| 7 | Hunter | Drifloon | Drifblim | Drifblim |
| 8 | Gianna | Stunky | Sneasel | Umbreon |
| 9 | Eli | Kirlia | Hypno | Gardevoir |
| 10 | Henry | Pawniard | Bronzong | Corviknight |
| 11 | Chase | Dedenne | Sylveon | Sylveon |
| 12 | Claire | Kricketune | Scyther | Heracross |
| 13 | Brooklyn | Rockruff | Lycanroc | Garganacl |
| 14 | Zoe | Sandile | Sandaconda | Mudsdale |
| 15 | Samantha | Snorunt | Glalie | Weavile |
| 16 | Dylan | | Dragonair | Haxorus |
| 17 | Luke | | Toxicroak | Clodsire |

A retail Scarlet joining `bin/sv_host.py` (two empty slots) showed, with these two words in the
RaidPoint:

| 0x3d8 | 0x3e0 | partners |
|---|---|---|
| 0 | 2 | Samantha (Glalie), Zoe (Sandaconda) |
| 0x12345678deadbeef | 2 | Henry (Bronzong), Ava (Floatzel) |
| 0x26 | 2 | Ava (Floatzel), Logan (Gogoat) |
| 0 | 0, 1 | Chase (Dedenne), Samantha (Snorunt) |
| 0 | 3, 4 | Samantha (Weavile), Zoe (Mudsdale) |
| 0xaf05b3d1838735c0 | 4 | Eli (Gardevoir), Ava (Toxapex) |

### Favoured partners

Raiders rate ten partners of the stage 3 and 4 pool (Serebii's level 80) above the rest.
`raid_partners.RECOMMENDED` holds them, and the app's card for each ends on why and a star: gold for
the four raiders favour, silver for the next tier.

| rank | trainer | Pokemon | why |
|---|---|---|---|
| gold | Eli | Gardevoir | Life Dew heals the whole team; seven-star solo guides ask for it, often with Bellibolt. |
| gold | Hailey | Bellibolt | Light Screen, when she sets it, cuts the boss's special damage; Discharge can paralyze. |
| gold | Logan | Arboliva | Safeguard keeps status conditions off the team; Grassy Terrain heals each turn and also powers a boss's Grass moves. |
| gold | Charlotte | Staraptor | Intimidate on every respawn and Feather Dance cut the boss's physical Attack. |
| silver | Austin | Arcanine | Intimidate on every respawn; Leer lowers the boss's Defense. |
| silver | Kylie | Tauros | Intimidate on every respawn; Raging Bull breaks the boss's screens. |
| silver | Hunter | Drifblim | Will-O-Wisp burns the boss, halving its physical damage. |
| silver | Gianna | Umbreon | Thunder Wave paralysis can give a free turn, by chance. |
| silver | Evan | Dudunsparce | Glare paralyzes at 100% accuracy, except a boss with an Electric Tera type. |
| silver | Samantha | Weavile | Leer lowers the boss's Defense before its shield; Ice Punch can freeze. |

Intimidate raises the Attack of a Defiant or Competitive boss, such as Annihilape, on every respawn.
The earlier stages' pools have no Life Dew, Light Screen or Safeguard. The partners' moves changed
with The Teal Mask update; the sets above are Serebii's, which the sources describe.

Sources, read 2026-10-11: Amiibo Doctor's Tera Raid NPC Partners Tier List (June 2025); Game8's
seven-star event guides (Skeledirge, Goodra, Dragonite); Smogon's seven-star raid threads
(Porygon2, Glimmora, Annihilape and others).

## The seed

A raid is drawn from a 32-bit seed and the console's state: version, region (Paldea, Kitakami,
Blueberry, table prefixes `""`, `su1_`, `su2_`), story progress and the crystal. xoroshiro128+
starts from the seed and the constant `0x82A2B175229D6A5B` (`0xe29340`); its first draw, a hundred
values, picks a standard crystal's stars against the story stage's bounds (a black crystal has six),
the second picks the encounter by rate within that star level and version. `0xe29404` builds the
table name with `%sdifficulty_%02d` and passes the record to `0x1eab5e4`, which reads its
`raidEnemyInfo`; `0x2935b68` walks all three prefixes and six levels. A fresh xoroshiro from the
same seed then draws the boss: EC (the low half of the seed plus `0x229D6A5B`, so a boss record
gives its seed back), a fake trainer id, PID, flawless IVs, IVs, ability, gender,
nature (Toxtricity's from its form's list), height, weight and scale, as PKHeX's
`Encounter9RNG.GenerateData` does; the Tera type and the reward lottery each take another fresh
generator.

`pokeldn.sv.raid_encounter` implements it over `pokeldn/sv/data/raid_base.json`, built by
`scripts/gen_sv_raid_data.py` from Tera-Finder's encounter lists and reward tables, PKHeX's personal
table and the eighteen `raid_enemy_XX_array` tables of the game's RomFS
(`arc/worlddataraidraid_gem_item_reward_boostdata.bin.trpak`, FlatBuffers with their own `.bfbs`
schemas). Over 12600 seeds in every context its bosses equal PKHeX.Core 26.8.26's field for field,
including six Paldea encounters (records 5094 to 5099) whose retail table gives Tera rule 0 (the
species' own types), which PKHeX holds as rule 1 (any type). The crystal builder `0xe26ff0` reads
`gemType` and draws any of 18 for both 0 and 1 (`cmp w9, #2` at `0xe27414`, redrawing until the
value is under 18), as PKHeX does; the generic converter `0x160e108` treats 0 as the species' types
but is not on the raid's path. A boss record
built from seed `BD13FB43` (Violet, Paldea, four stars) equals a retail bootstrap's byte for byte;
one from `7B741233` (Scarlet, Paldea, five stars) equals a French retail Scarlet's but for the
nickname and language: a retail host writes its own language and that language's species name
(`Embrylex`, 3), the generator English (2). The console shows the boss under its own language's
name either way.

Species in the raid tables are the game's DevID: the National Dex number up to 916, the game's own
order from 917 (Tinkatink 957 is 1000), as `gen9.internal_index`. The descriptor and the RaidPoint
carry the DevID too: a retail Scarlet shown a descriptor and RaidPoint with species 1000 listed
and fought Tinkatink.
A black-crystal record holds a battle level of 90 with effort values (for example 128 Defense and
128 Special Defense) and a capture level of 75; a standard record's two levels agree and its effort
values are zero. The bootstrap's boss record and the RaidPoint summary carry the battle level and
the effort values, the RaidPoint's `+0x2c` the capture level: a black boss built from `09F3E337`
(Scarlet, Paldea) equals a French retail Scarlet's but for the nickname and language.

## Event raids

A Poke Portal News delivery holds five files: `raid_enemy_array`, `fixed_reward_item_array`,
`lottery_reward_item_array` and `raid_priority_array`, FlatBuffers with the base tables' layout, and
`event_raid_identifier`, a u32 that repeats the priority table's `VersionNo` (`20221202`). From 1.3.0 a
delivery carries each again under the patch it is for (`_1_3_0`, `_2_0_0`, `_3_0_0`), the older copy
dummied out; the newest is read. A `raid_enemy_array` record is a standard one's, with
`RomVer` (0 both versions, 1 Scarlet, 2 Violet), `DeliveryGroupID`, `Difficulty` as the stars (7 a
seven-star raid), `CaptureRate` (0 never caught, 1, 2 caught once) and its own reward table names, and
its `BossPokePara` fixes what a standard boss draws:

| field | an event record |
|---|---|
| `Sex` | 0 drawn; 1 male, 2 female, and the gender draw is skipped |
| `Seikaku` | 0 drawn; the nature plus 1, no draw |
| `TalentType` | 1: `TalentVnum` flawless IVs; 2: `TalentValue`'s six IVs, no draws |
| `RareType` | 0 drawn; 1 never: a PID shiny against the fake trainer has bit 28 flipped; 2 always: its high half is rewritten to a shiny xor of 0 |
| `ScaleType` | 0 two draws; 1 to 5 one draw in 0-15, 16-47, 48-207, 208-239, 240-255; 6 `ScaleValue` |
| `Item`, `EffortValue` | the boss's held item and battle EVs (a seven-star Pikachu holds a Light Ball) |

A record's `TimeDesc` is its `raidTimeData`, and the RaidPoint carries it at 0x030: every seven-star
record's is active, `gameLimit` 450 to 900 and `commandLimit` 60, as are five five-star records'
(`gameLimit` 320 to 450); the other 420 records' are inactive (gallery of 2026-09-06).

A den belongs to a delivery group, 1 to 10; `raid_priority_array` counts the dens of each. xoroshiro
from the seed draws the hundred-sided roll a standard crystal's stars take and drops it, then a value
under the total rate of the group's records that are the console's version and of a star level the
story stage allows, and takes the record whose span holds it, in table order [PKHeX
`EncounterDist9.GetIsPossibleSlot`]:

| progress | stage | stars drawn |
|---|---|---|
| beginning, Tera Raids | 0 | 1, 2 |
| 3-star | 1 | 1 to 3 |
| 4-star | 2 | 1 to 4 |
| 5-star, 6-star | 3 | 3 to 7 |

A record of rate 0 is never drawn. The boss and its Tera type are drawn as a standard raid's with
the record's fixed fields; the rewards are the record's fixed table, then the lottery's draws from
the delivery's own tables, a seven-star raid's count as a six-star one's. A lottery slot with a rate
and no item weighs in the total and gives nothing, as does a row of quantity 0. The lottery tables of
Gimmighoul's first 2023 round in Scarlet are malformed so, every slot empty or of quantity 0, and its
raids give their fixed rows only.

`pokeldn.sv.raid_event` reads a delivery folder (an [EventsGallery](https://github.com/projectpokemon/EventsGallery)
event, or its `Files`) and generates the `Raid` the host stages:

    ./.venv/bin/python bin/sv_host.py ... --raid-pokemon FILE --raid-seed 52E6B438 \
        --raid-event "EventsGallery/Released/Gen 9/SV/Raid Events/002 Charizard the Unrivaled" \
        --raid-version scarlet --raid-progress 6star [--raid-event-group 1] [--raid-catch-normal]

The RaidPoint carries the record's capture rate and, as the crystal, the save's raid content: 2 an
event, 3 a seven-star event (Tera-Finder `RaidContent`).

An emulated Scarlet 4.0.0 guest fought both. Eevee Spotlight (20221125) at seed `00000002`,
beginning progress, crystal 2: a one-star Eevee, caught, its reward screen listing the seed's rows in
order. Charizard the Unrivaled (20221202) at seed `00000001`, six-star progress, crystal 3 and
`raidTimeData` 1, 600, 0, 60: the boss named "Charizard the Unrivaled", its timer bar losing about a
tenth of its length a minute, a 600 s limit where the console's own is 300 s.
A retail Scarlet over the ESP32 board fought the same two raids: the one-star Eevee won, its catch
offered and the seed's rewards given; Charizard the Unrivaled shown as seven stars, its timer bar
shrinking slowly. It also fought a standard black raid (seed `00000004`, Pincurchin) whose RaidPoint
carried the record's `raidTimeData` 1, 450, 0, 60.

The app's Tera Raid (Host) tool picks the event from its own copy of the gallery, which it downloads
and updates, and narrows the raid's version, progress and crystal to what the event spawns
([Raid events](gui.md#raid-events)). The crystals offered come from `raid_event.dens`: a delivery
group with dens in the priority table and a record in that version; Walking Wake's spotlight offers
Scarlet its group 1 and Violet its group 2.

A capture rate of 2 is a catch once per save: every seven-star record has it, and so do the five-star
Walking Wake and Iron Leaves of each spotlight round, Dialga and Palkia's spotlight and the shiny
Rayquaza. The save keeps the record numbers caught, eight bytes each, the number and a captured flag
(block `0x8B14392F`; from 2.0.1 the defeated flags are `0xA4BA4848`'s, PKHeX `RaidSevenStar9`), and a
rerun repeats its number (Walking Wake is 2023022801 in all seven rounds), so a catch in one round
closes the others. The
shiny Treasures of Ruin spotlights' records have 0: never caught. The host's summary names the rule
(`caught once per save`, `cannot be caught`).

A console checks that list by the record number of the lobby descriptor (0x2c). A retail Violet
that had caught Mighty Mewtwo (2023090101), shown the host's descriptor of it, said "you won't be able to
catch the Tera Pokemon" in the lobby, with the RaidPoint's capture rate written 1 or 2 alike, as no
RaidPoint is sent before the battle. Against Magikarp the Unrivaled (2026071701), which its save had
caught, the same console:

| descriptor's record number | RaidPoint's capture rate | the lobby | after the win |
|---|---|---|---|
| 2026071701, the record's | 2 | won't be able to catch | no catch |
| 2026071701 | 1 | won't be able to catch | no catch |
| 2026071799, a stand-in | 1 | no warning | caught |
| 2026071799, again | 1 | no warning | caught |

A record number the save lists as caught blocks the catch after the win whatever capture rate the
RaidPoint carries (the second row). A catch under capture rate 1 does not add the stand-in to the
list (the fourth row). `--raid-catch-normal` serves a catch-once record as a normal catch: the
RaidPoint's capture rate 1, and in the descriptor a stand-in record number, the record's date with
the suffix 99 (`raid_event.stand_in`: 2026071799). No delivery has that suffix (every one's is at
most 14). The summary says `served as a normal catch of record 2026071799`. A never-caught record
stays 0.

The stand-in is in the descriptor alone: the boss record and the RaidPoint but its capture rate are
the event's, byte for byte, and no PK9 field holds a record number. PKHeX.Core 26.8.26's raid
encounters (`EncounterDist9`, `EncounterMight9`) have none either, only their delivery group, so a
catch's legality cannot depend on it. Every catch-once record of the gallery but Kingambit's second
round (newer than that release), in each version it spawns in, at three seeds each and Magikarp at
`000FD5D7`, 331 raids: the boss record the host sends, given a test trainer as PKHeX's own conversion
of the encounter gives it, equals PKHeX's catch of that raid from that seed and is legal. A seven-star catch
is legal only with the Mightiest Mark (`RibbonMarkMightiest`), which the console gives it: the
Magikarp the console caught under 2026071799 has it.

A fixed reward row's subject 3 (`Only Once` in `Encounters.txt`: a seven-star raid's TM and Ability
Patch) is a separate rule; `raid_point` writes the table's subject and each console's reward
filter applies it.
An event boss can be any species, so the personal entries, move PP and names past the raid bosses'
come from `pokeldn/sv/data/species.json` (`scripts/gen_sv_species_data.py`, the PKHeX revision of
`raid_base.json`).

Against EventsGallery's 153 delivery folders (2026-09-06): every table decodes as its JSON; the
distribution and seven-star encounters pkNX's ripper makes of them equal PKHeX.Core 26.8.26's 174 and
55, all of them (Kingambit's second round is newer than that release, `000 Base Data` the game's own
placeholder); 20 080 bosses, forty seeds for every event, version, stage and group, equal PKHeX's
`GenerateSeed32` field for field, PKHeX allowing each record at its stage; and
`scripts/check_sv_raid_events.py` finds every delivery's 537 encounters, and raids drawn from them,
agree with its `Encounters.txt`, Gimmighoul's malformed round aside. Each of PKHeX's 229 encounters
at seeds `00000001`, `12345678`, `9ABCDEF0`, `DEADBEEF`, `52E6B438` and `0000F00D` gives the
encryption constant, IVs, ability number, gender, nature, height, weight and scale that
`boss_fields` draws for the gallery's record of it.

## Finding a seed

The app's raid seed field shows the boss and rewards the seed gives in the tool's context, and Find
a raid searches seeds from a first one, typed or picked at random, in every context the filters
leave (`pokeldn.sv.raid_search`) for a species, star level, Tera type, nature, gender, shininess,
size mark and IV ranges. It ranks the results by a score of the boss's stats (HP times the sum of
its defenses, either defense alone, its better attacking stat, or its total) or by the rewards
wanted (Most desired rewards, below). One result per species is kept unless a species is chosen.

### Size marks

PKHeX allows the Mini mark on a Pokemon that has been in Scarlet or Violet at scale 0 and the Jumbo
mark at scale 255 (`MarkRules.IsMarkAllowedMini`, `IsMarkAllowedJumbo`). The finder's Size mark
eligibility wants the boss's scale at 0 (Mini mark), 255 (Jumbo mark) or either (Any mark). The
scale is drawn after the height and weight (`boss_fields`):

| scale rule | scale | chance of 0 or of 255 |
|---|---|---|
| two draws (rule 0), every standard and black crystal boss | `next_int(0x81) + next_int(0x80)` | 1 in 16 512 each |
| an event band from 0 (rule 1) or from 240 (rule 5) | `next_int(16) + low` | 1 in 16 for the end it touches |
| an event's own value (rule 6) | the record's `scale` | always or never |

`raid_search.size_marks` names the marks an event's bosses of the chosen crystal, stars and species
can take, and the finder greys out the others.

### Wanted rewards

Its Rewards section, folded until opened, wants rewards: rows of an item and the least quantity a
raid must give of it, the raid's quantities of an item summed and two rows of one item added up.
A result then shows its rewards. Folded, the rows stay and the search ignores them. The items and
quantities offered are those the raids searched can give (`raid_search.reward_choices`): for every
encounter a context draws (its star levels at that progress, in that version, or an event's den),
narrowed to the stars, species and Tera type chosen, its fixed rows plus any number of its lottery's
draws of an item up to the most a raid draws (exactly as many as it draws when the lottery holds
nothing else), each Tera type the boss can take naming its shards and the species its material.
Every Paldea, Kitakami and Blueberry context at once lists 343 items in about a second, so the list
is made off the page. The search skips an encounter that cannot give what is wanted, then draws a
seed's rewards before its boss.

Most desired rewards ranks the results by the rewards wanted, in their order: more of the first item
wins, then more of the second, each row's least still a minimum. A raid's total of an item counts as
a digit, its place among the totals the raids searched can give, from the least up
(`raid_search.ranked_rewards`): a black crystal gives a material 8 to 30 by twos, 12 places. The
leading items' digits make one score under 2^31, which the helper keeps beside the seed in a 64-bit
rank; the items after those only want their least. Five items fit in every raid known (an event's
Exp. Candy L has 59 totals, the most of any item), and a black crystal ranks four herbas, patches or
caps and four materials.

### The helper's scan

The PKHeX helper scans the seeds over every core (`services/pkhex/RaidScan.cs`, packed and sent by
`pokeldn.sv.raid_scan`, in a helper process of its own): a seed's encounter, its boss up to the
scale, the score, every filter and the rewards, the work of `select`, `boss_fields`, `rewards` and
`tera_type` on the context's tables. It names a context's best seeds (or each species' best), and
`search` makes their raids with the plain Python code, so the results, their order and the ties
between seeds and contexts are the Python scan's (`tests/test_sv_raid.py` compares both).

The scan turns most seeds away after their encounter. Each encounter row's best rank is worked out
once per request: its flawless IVs at 31 wherever they can fall, its other IVs the best the IV filter
lets through, the best of its natures, and ranked by rewards the most the row gives of each item. A
seed whose row cannot beat the ranks kept so far stops there; one that passes is checked again after
its flawless IVs and after all its IVs, against the best any nature makes of them (a nature changes
a stat by a tenth, and every score grows with each stat). Ranked by rewards, the rewards are drawn
first, a draw looks only at the lottery rows that give a wanted item, and the draws stop once those
left cannot bring the first item to the kept ranks' first digit. Each request carries the ranks the
earlier ones kept (each species' with one boss per species), and only a search's first request
carries a context's tables, which the helper keeps by their digest.

A request holds 16 777 216 seeds, then as many as the helper scans in about a quarter of a second, up
to 268 435 456. A search covers up to 4 294 967 296 seeds in each context, in as many contexts as
chosen (`most_seeds`); the finder offers a hundred million, and Every seed searches all of them.
Stop at the first match answers the first raid that matches, whatever its score, instead of the best
ones (`stop_at_first`): the earliest seed of the first context that has one, the contexts searched
one after the other. Without the helper (a source checkout that has not built it), Python scans
about 22 000 seeds a second, up to a million seed and context pairs, and the finder offers 100 000.

Measured on an Apple M4 (10 cores), the helper warm:

| search | time |
|---|---|
| 10 000 000 seeds of one context (Scarlet, Paldea, 6-star, standard) | 0.02 s, 0.03 s wanting a shiny |
| 10 000 000 seeds in each of the 42 contexts | 0.51 s |
| 100 000 000 seeds in each of the 42 contexts, the finder's default | 5.2 s |
| every seed of one context | 6.1 s |
| every seed of the 42 contexts | 4 min 3 s |
| every seed of Scarlet's Paldea black crystal, two Bitter Herba Mystica then two Ability Patches ranked, one boss per species | 20.9 s |
| every seed of that crystal, wanting the Jumbo mark | 3.3 s |

## The battle between consoles

Measured between two emulated Scarlet 4.0.0, one hosting a 4-star crystal and one joining from the
Poke Portal, two NPC partners in the free seats. The hosting console stays in the session for the
whole battle. Every battle message is a battle-start frame on key 0x007b addressed (0x2713, x, y), its
32-byte header's type at +0x00, a u64 step counter at +0x08, a u64 round at +0x10, then 5 and a
battler or station byte at +0x18 and +0x19:

| type | from | size | what |
|---|---|---|---|
| 0x01, 0x05, 0x11, 0x15, 0x25, 0x29, 0x47, 0x49 | the host, address (0x2713, 1, 2) | 50 to 20626 | a step; each guest answers type + 1 under the same counters |
| 0x02, 0x12, 0x16, 0x26, 0x2a, 0x48, 0x4a | every station, address (0x2713, 3, 5) or (0x2713, 2, 2) | 50 | the answer to a step |
| 0x06 | a station for its own battler; the host for its own, for each NPC's and again for the guest's | 250 | one battler's command; +0x19 is the battler slot (0 host, 2 the guest, 3 and 4 the NPCs) |
| 0x15 | the host, one per acting battler, the boss included | 20626 | the round: five 0x70-byte action blocks (slots 0 host, 1 boss, 2 guest, 3 and 4 NPCs) at +0x20, a byte per slot counting the actions in its block at +0x250 ([Actions](#actions)), the server command queue's length at +0x258 and the queue from +0x25c; 123 to 802 bytes deflated |
| 0x46 | the host, 62 times at the start | 54 | |
| 0x51 | the host | 86 | |

In about 4 minutes the joiner's two directions carried 475 reliable messages on 0x80 port 0, 27979
bytes on the wire, at most 80 in one second one way. Only the host sends the NPCs' commands and the type-0x15 records.

The battle is server and client. The host's builder `0x113c8a0` (type 0x15 at `0x113c908`) copies the
action blocks, runs the round (`0x113e3d0`) and appends the server command queue it produced; the
host's AI makes the NPCs' commands, and the boss's action reaches a guest only inside a 0x15. A guest
plays the queue, and for types 0x13, 0x15, 0x17, 0x19, 0x1f, 0x23, 0x25 and 0x4d it rebuilds the body
from the host's action blocks with the same builder and compares size and bytes (`0xf5cfa4`); a
mismatch goes to `0xf5bfd4`, the receive-timeout handler. A station that hosts a battle has to produce
the queue Scarlet's own engine produces from the same state.

### Which station runs the server

The battle server is the first entry of the port-2 member list, the list every console builds from
the lobby host's Session type 6 (members at `+0xa0`, codes `+0xc0`, count `+0xc4`; composer
`0xe457cc`) and type-9 receiver `0x18b68fc`; `pokeldn.sv.port2.build_session` puts the host first.

| step | code |
|---|---|
| the raid start `0.4455` (Lua) sets the server slot to 0: `setup:f4891D27C(0)` | `0x182ca10` -> `0x2d36398`, setup `+0x94` |
| for member i it maps i to slot 0, 2, 3, 4, stores the member's code at `+0x99+slot` and, for its own code, the slot at `+0x90` | `0x1ccd15c` walks the member vector at port-2 `+0x170`; `0x2d363a0`, `0x130ea2c` |
| `0x2a1cd74` copies setup `+0x94` to `net+0x58` and `+0x90` to `net+0x5c`, once, at battle start | from `0x18915c4` |
| a console is the server when `!setup.710 && slot == net+0x58` | net vf `+0x78` = `0x2a1d994`; config `+0x2c` via `0xfa363c`, kept at server `+0x490` |
| the 0x15 checker is installed only on a console that is not the server | `0xfb0ee8` |
| a receive timeout or a failed check calls net vf `+0x70` = `0x2a1d920`; in a raid it sets `net+0xca` and `0x18e217c` sets `net+0x58` to the console's own slot (`net+0xf0`, written once at `0x2a1cda8`) | `0xf5bfd4` |

Setup `+0x710` is set only by `0x7faed0`, from the Lua binding `f3AF42713` when builder field 22 is
true; the raid start never sets it. No message names the server: member order does. A console that
loses its link to the server makes itself the server for the rest of the battle, and every console
does so independently. When the lobby host listed first stops sending, each console fights its own
battle.

The member vector is append-only and has three writers, all through `0x18b65c8` -> `0x18b68fc`:
the session block of a type 6 or 7 (`0x18b566c`, entry `(block+0x98 code, block+0x90 host
station)`, appended first), the type-6 member replay (`0x279ba2c`) and the type 9 (`0x1954bac`). A
type 9 before any block is dropped (`0x18b65e4`). Entry 0 on every console is the host its first
block names. Measured on two emulated Scarlet 4.0.0:

| what the lobby host sent | what the consoles did |
|---|---|
| a type 6 whose block host is the receiving console's own station | sent no port-2 join, Error 7 |
| port-2 type 10 (`0a b9 02 <slot> b9 01 <u64 station>`, parser `0x279bbdc`, erase `0x194562c`) naming the block host, in the lobby | left the session |
| the same type 10 after the bootstrap | "The raid has been abandoned!" |
| the same type 10 once the console reported 320173 (loaded) | each fought alone with two NPC partners |
| a member code naming an empty bootstrap participant | the battle's loading aborted (2162-0001) |
| five members, the fifth (mapped to slot 0 by the Lua, which remaps only indexes 1 to 3) a console | the lobby listed no member; after the start and the bootstrap both consoles left before any battle frame |

Bootstrap participant k belongs to the member with code k. A console that fails over runs every
other battler by its own AI: the per-slot readers are built only for a console that was the server
at battle start (`0xfa52b0`, `0xfa5314`). Its own code is the code of the first vector entry with
its own station (`0xd5f3b4`), and the Lua's slot loop (`0.4455` @1206..@1248) has no break, so the
last matching entry sets the console's slot.

### The battle's random numbers

Every random draw of a round comes from one xoroshiro128+ object of 0x28 bytes (vtable `0x4500bd0`):

| offset | size | what |
|---|---|---|
| 0x00 | 8 | vtable |
| 0x08 | 2 x u64 | the state |
| 0x18 | u64 | the seed |
| 0x20 | u64 | the number of draws made |

The server's main module (0x378 bytes, constructor `0x12742d0`) holds it at `+0x10`; round code
reaches it as `[[x+0x10]+0x10]` (`0x11440e8`). The module's initialiser `0x127d824` sets the state
to the seed and `0x82A2B175229D6A5B`, the count to 0 (`0x127d9a8`), taking the seed from `+0x20` of
its parameter block. A guest's checker fills that word from the battle setup's `+0x718`
(`0x2891748`); the raid start `0.4455` (@1152..@1157) sets `+0x718` through the Lua binding
`fAF4A81E0` (setter `0x7faf1c`) to the RaidPoint's `randSeed`. The partner seed is also the battle
seed, and the station that writes the bootstrap chooses it. The per-slot modules a server builds
(`0x126ba88`, from `0xfa9f90`) are initialised with seed 0.

On an emulated Scarlet 4.0.0 fighting a raid hosted with `randSeed` `D64EB3974D89705E`, the
server's random held that seed and a state equal to it advanced seven steps, with a count of 7, at
a later round; that round drew four times.

A draw adds `s0 + s1` and steps the state; the count rises by one per call, not per redraw:

| function | draw |
|---|---|
| `0x11440f0(rand, n)` | a u64 below n: `s0 + s1` masked to the bits of n − 1, redrawn while n or more; n below 2 returns 0 and draws nothing |
| `0x114da8c(rand, p)` | `(s0 + s1) & 0x7f` redrawn while 100 or more; true when below p |

Many round functions inline the step instead of calling these.

### Actions

A round's action header is five 0x70-byte blocks, one per client slot, each up to seven 16-byte
actions (a u64 action word, then the actor's battler id as a u64), and at +0x230 a byte per slot
counting the actions in its block. The server decodes them in slot order into 0x8c-byte action
entries (`0x1145e40`, decoder `0x11461b4`). The action word's low four bits are the kind:

| kind | entry kind | fields of the word |
|---|---|---|
| 1 | 1, a move | bits 4..7 the target's battle position, 8..23 the move, bit 25 a flag |
| 2 | 2 | bits 4..19 and 20..27; the next u32 |
| 3 | 3, a switch | bits 4..7 the party index (the actor is that party member), 8..11, bit 12 |
| 4 | 6 | bits 4..11, 12..15 and 16..23 |
| 5 | 4 | bit 4 |
| 6 | 5 | bits 4..11 |
| 7, 10, 11 | 7, 8, 9 | none |
| 9 | 10 | bits 4..11 |
| 12 | 11 | bits 4..11; the next u32 |
| 13 | 14 | bits 4..7, 8..11, 12..15, 16..27, 32..43, 44..55, 56..59, 60..63 |

A word whose bits 0..3 are 3 and bit 12 is set is skipped, as are kinds 0, 8, 14 and 15. A recorded
player action `41 67 03 00 ...` is a move (kind 1) at target position 4, move 871 (Torch Song).

### The server command queue

A type-0x15 record's queue (+0x23c of the body, its length at +0x238) is a run of commands. A
command is a big-endian u16 id, then its arguments packed by the id's format as one big-endian bit
stream, padded at the front to whole bytes (writer `0x119bf58`, jump table `0x3c6aa7c`). The id to
format map is built from 208 rows of (u16 id, u8 format, u8 0) at `0x3c6abe4`, a later row for the
same id winning; ids run 0 to 205. Ids 0xce to 0xd4 are read by the reader `0xe515f0` itself (jump
table `0x3c6a90c`):

| id | body |
|---|---|
| 0xce | none: the end of the queue |
| 0xcf, 0xd2 | a group: a u8 byte count, then that many bytes |
| 0xd0 | a u8 count, at most 4, then that many bytes |
| 0xd1 | two bytes |
| 0xd3 | one byte |
| 0xd4 | none |

Format bytes and their argument widths in bits (`pokeldn.sv.battle.queue.FORMATS`):

| format | widths | format | widths |
|---|---|---|---|
| 0x00 | none | 0x57 | 32, 8, 8, 8, 8, 8, 8 |
| 0x01 | 8 | 0x62 | 32, 16 |
| 0x02 | 8, 8 | 0x63 | 8, 8, 32 |
| 0x04 | 5, 3, 8, 16 | 0x65 | 32, 16, 16, 16, 16 |
| 0x10, 0x20 | 32, 16, then eight of 32 | 0x66 | 8, then five of 32 |
| 0x11 | 16 | 0x67 | 32, then six of 16 |
| 0x12 | 8, 16 | 0x72 | 32, 32 |
| 0x14 | 5, 3, 5, 3 | 0x75 | 32, 8, 32, 32, 32 |
| 0x17 | seven of 16 | 0x83 | 32, 32, 32 |
| 0x1a | ten of 16 | 0x84 | 8, 32, 32, 32 |
| 0x21 | 32 | 0x85 | 8, 8, 32, 32, 32 |
| 0x22 | 8, 32 | 0x86 | six of 8 |
| 0x23 | 5, 5, 5, after one pad bit | 0x93 | 32, 8, 8 |
| 0x28 | eight of 32 | 0x96 | six of 32 |
| 0x29 | 32, then eight of 8 | 0xa3 | 32, 8, 16 |
| 0x42 | 5, 3 | 0xa4 | 32, 8, 8, 8 |
| 0x43 | 8, 8, 8 | 0xb3 | 32, 8, 32 |
| 0x45 | 16, 16, 16, 32, 16 | 0xc3 | 32, 32, 16 |
| 0x52 | 32, 8 | 0xc4 | 32, 32, 16, 16 |
| 0x53 | 8, 8, 16 | 0xd3 | 32, 16, 16 |
| | | 0xd4 | 32, 32, 16, 8 |

Every queue starts with command 0xb5. A round in which slot 2 used Hex (move 506) on the boss
carried `0x5a (3, 506, 212)`, `0x5b (3, 506)` and `0xc9 (3, 0, 506, 4, 0)`. Every queue recorded
from emulated Scarlet 4.0.0 servers and the type-0x15 records between two emulated consoles, 20 in
all, decodes to its last byte and encodes back to the same bytes (`tests/test_sv_battle_queue.py`).
The 0xcf groups seen so far are zero-filled.

### Reproducing a round

A round is replayed exactly under unicorn from an emulated console halted at the builder
`0x113c8a0` with type 0x15: memory comes from the GDB stub one page at a time as the replay first
touches it, the thread-local page behind `tpidrro_el0` is a stand-in whose `+0x1f8` names a fake
thread, and SVCs 0x10, 0x11, 0x12, 0x1a, 0x1b, 0x1d and 0x1e return 0. Eleven replayed rounds
equalled, byte for byte, the bodies the console then built itself; a round touched 159 to 353 pages.

`pokeldn.sv.battle` is a Python port of the server, one function per game function, keyed by its
offset from main. The builder `0x113c8a0` runs in Python for message kinds 1, 5, 17 and 21: the
round driver `0x113e3d0` with move selection, damage `0xf7c344`, fainting `0x1144df8` and end of
turn `0x114a094`, and the battle start `0x113dca8` with its send-out, item, ability and entry
handlers. Over 86 halted consoles (49 rounds, 5 battle starts) the port leaves the same body and
the same memory pages as the game's own code, with no call handed back to it. The heap it allocates
from is the SDK's `nn::mem::StandardAllocator` over a thread cache, ported with the cache's creation
and its TinyMT32 key (`0x525f448`). In the battle-state build steps `0x2891748`, `0x2892ac0`,
`0x2d381a4` and `0x2892dd4` every ported callee matches; the entries themselves and 244 of their
callees are still the game's code. `__cxa_guard_acquire` (`0x53c49a0`) returns 1 and sets byte 1
of the guard to 2 when neither byte 0 nor byte 1 is set.

A Hex round reads 16838 bytes it did not write: 1496 from the static image, 5372 from the
command-format map and 2926 from the server object (both made by `0x2d381a4`), 2414 from the
battlers and their Pokemon (made by `0x2892ac0`), 1756 from the main module family (made by
`0x2891748`), 2278 from the data tables (personal, growth, moves, flags and id-hash, each a u16 to
record map at +0x68 into a FlatBuffers file, held in function-local statics) and 576 from the
round's action blocks.

## Joining

`bin/sv_join.py --raid-pokemon FILE` joins a scene-7 network and takes part as a guest. The
console's player opens a crystal, chooses Challenge as a group and waits; the app's Tera Raid (Join)
tool runs it. `pokeldn.sv.raid.RaidGuest` and the joiner do, in order:

| step | the guest |
|---|---|
| Net | answers 0x11 and 0x50 under message flags 0x11 |
| Session | leaves the station list that comes with the join response unanswered, acknowledges its retransmission at least 1 s later, then every later list, and sends the clock request with byte 9 set |
| channels | splits the host's six-key table into the four and the raid's two, announces the four, joins port 2 0.24 s later and announces the raid's keys 0.79 s after the table; delays its 0x7C acks 0.25 s |
| identity | the standard record set (`pokeldn.sv.reference`) 0.44 s after the seat, record 1 under the trainer name |
| lobby | state 0x18 and its Pokemon 0.27 s after that; state 0x01 2 s later |
| start | state 0x0d once the host's state 0x0c arrives; a guest that sent 0x0d as its ready was acknowledged and never shown ready |
| battle | acknowledges the host's 0x3480 0x93, sends the Session type-3 leave every 0.5 s until the type 4 (four sends at most) and leaves the network; a retail Scarlet in the battle answered none of the four |

Against a retail host the guest appeared in the lobby under the trainer name, became ready and let
the host start; its Pokemon stayed in the battle.

## Unresolved

- Whether a listener of the GlueCode dispatcher `0x18beef4` reads `+0x4c` as a word (listeners
  register at run time; groups 1 to 3 are called at `0x18bf87c`), and which consumer drains the
  per-slot queues `0xe106a4` fills (`0x113d5e0` from `0xe107ac`). Message 16, with +0x08 zero,
  enters neither queue: the reader switches on it and `0xf5bc10` returns at `0xf5bc30`.
- What the source at `+0xa8` of the object `0xfc363c` steps holds, and which item message 16
  releases into the sink: the item `0xfc363c` returns through x8 at `0xfc36ac`, then its vtable's
  `+0x68`. The source is `[[sm+0x48]+0x128]` (`0xfa46d4`); what fills `[sm+0x48]` is untraced.
- What writes the 0x2713 word of the battle-start port address. The builders read it at `+0x40`
  of the object at the battle network object's `+0x110` (`0xfa7320`, `0xfa8628`, `0xfb1cf8`,
  `0x28949f4`); no instruction in the image materialises 0x2713. On an emulated Scarlet 4.0.0 guest that object (vtable `0x44ff6c8`,
  constructor `0x16b21f0`, which zeroes `+0x40`, destructor `0x2894604`) held the u32 pair
  `0x1527b, 7` at `+0x38` and 0x2713 at `+0x40` when the builders first read it at the join.
  Every raid hosted with it began its battle, on retail and emulated consoles.
- Whether the battle timer a guest runs on a six-star point is the point's `gameLimit` 450; the
  reward-screen check did not measure it.
- What the RaidPoint's byte 0x3b4 holds.
- Whether a retail console's reward screen follows the Lua filter for subjects 2 to 4; subjects 1
  and 5 are measured on a retail guest, the rest on an emulated one.
- Whether the five-star catch-once records go in the save's list as the seven-star ones do.
- Why a retail Violet that associated to the next host's network sent no Pia for 46 s, with the handover
  of an earlier host (is-migrating 0x11 to both at once).
