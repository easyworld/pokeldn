"""What the app offers per game: each tool is an entry point, the tested flags it always gets, the
fields a user fills in, and what to press on 游戏机上都需要输入。 Fixed arguments may carry {received}
(the Received folder), {stamp} (the run's time) and {src_var} (a fresh random id)."""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Field:
    flag: str | tuple[str, ...]   # "" is positional; a tuple passes the same value to each flag
    label: str
    kind: str = "text"            # text number choice switch pokemon file builder multi linkcode code (eight
                                  # digits), or a PKHeX name list: species move item ball
    help: str = ""
    default: str | bool = ""
    choices: tuple[tuple[str, str], ...] = ()
    required: bool = False
    group: str = ""               # fields sharing a group render on one card
    invert: bool = False          # a switch that passes its flag when turned off
    unset: tuple[str, ...] = ()   # arguments passed when the field is left empty
    exts: tuple[str, ...] = ()
    when: tuple[str, str] = ()    # (flag, value): the field applies only while that field has that value
    unless: str = ""             # hide and omit the field while this source field has a value
    template: str = ""            # the value is passed as template.format(value), e.g. "ball={}"
    limits: tuple[tuple[str, int, str], ...] = ()   # (NAME, highest, why) for NAME=VALUE text
    choice_help: tuple[tuple[str, str], ...] = ()
    queue: int = 1                # a pokemon field: how many trades one session can carry
    more: str = ""                # a pokemon field: the flag for the second and later offers
    count: str = ""               # a pokemon field: the flag that carries how many there are
    hidden: bool = False          # applied with its default, set on the Advanced tab instead of Basic
    shiny: bool = False           # a switch that makes the species field's Pokemon shiny, for its sprite

    @property
    def key(self) -> str:
        if isinstance(self.flag, tuple):
            return self.flag[0]
        if self.template:
            return f"{self.flag} {self.template}"
        return self.flag or f"#{self.label}"


@dataclass(frozen=True)
class Tool:
    key: str
    name: str
    script: str
    summary: str
    steps: tuple[str, ...]
    fields: tuple[Field, ...] = ()
    fixed: tuple[str, ...] = ()
    doc: str = ""
    unavailable: str = ""         # why the tool cannot run yet; it is shown greyed out


@dataclass(frozen=True)
class Game:
    key: str
    name: str
    short: str
    doc: str
    tools: tuple[Tool, ...]


VERSIONS = (("firered", '火红'), ("leafgreen", '叶绿'))
LANGUAGES = (("english", '英语'), ("french", '法语'), ("german", '德语'),
             ("italian", '意大利语'), ("spanish", '西班牙语'), ("japanese", '日语'))
CHANNELS = (("1", "1"), ("6", "6"), ("11", "11"))
FRESH_PID = Field("--fresh-pid", '每次运行使用新 PID', "switch", default=True, hidden=True,
                  help='为交换的宝可梦生成新的 PID 和加密常量，使已领取过的存档可以再次接收。活动宝可梦等必须保留 PID 的文件，请关闭此选项。')
CHANNEL_HELP = 'pokeldn 创建的网络所使用的无线信道。'
CODE_HELP = '与玩家在游戏机上输入的密码一致。'


def host_seconds(default: str, extra: str = "") -> Field:
    return Field("--seconds", '时间限制（秒）', "number", default=default, hidden=True,
                 help=" ".join(p for p in ('点击“开始”后主机运行的时长，到时自动关闭。请为队列中的每次交换预留时间。', extra) if p))


def join_seconds(default: str) -> Field:
    return Field("--hold", '时间限制（秒）', "number", default=default, hidden=True,
                 help='加入游戏机后保持连接的时长，到时自动离开。')


QUEUE = 6   # a party's worth


def offer(flag: str = "", required: bool = True, help: str = "", queue: int = 1, more: str = "",
          count: str = "") -> Field:
    return Field(flag, '用于交换的宝可梦', "pokemon", required=required,
                 help=help or '选择种类，由 PKHeX 生成适用于此游戏的合法宝可梦。',
                 queue=queue, more=more, count=count)


def queued(flag: str = "", help: str = "", **kw) -> Field:
    """An offer field whose session trades each entry in turn, on one seat."""
    help = help or '选择种类，由 PKHeX 生成适用于此游戏的合法宝可梦。'
    return offer(flag, help=f'{help}点击“添加交换”加入队列，同一会话将按顺序交换。',
                 queue=QUEUE, **kw)


ONLINE_CODE_HELP = ("与交换伙伴约定的八位密码，也需要在游戏机上输入。"
                    "留空可与此游戏中未设置密码的在线玩家匹配。")


def without(fixed: tuple[str, ...], flag: str) -> tuple[str, ...]:
    """`fixed` with `flag` and its value taken out."""
    out, skip = [], False
    for arg in fixed:
        if skip:
            skip = False
        elif arg == flag:
            skip = True
        else:
            out.append(arg)
    return tuple(out)


def online(host: Tool, steps: tuple[str, ...], code: Field) -> Tool:
    """The host tool trading a partner far away instead of a built offer (docs/online.md). `code`
    is the room both players enter, the console's own link code where the game has one."""
    kept = tuple(f for f in host.fields if f.kind != "pokemon" and f is not FRESH_PID
                 and f.flag not in ("--seconds", code.flag))
    return Tool(host.key.replace("-host", "-online"), "交换（在线）", host.script,
                "与远方玩家交换：双方分别为自己的游戏机创建本地交换，"
                "再通过互联网连接。",
                ("与交换伙伴约定密码，或留空匹配未设置密码的在线玩家。",
                 "启动后，等待日志显示“Trading with”和交换伙伴的名字。", *steps,
                 "对方提出交换后，会显示其宝可梦。双方确认后"
                 "开始交换。"),
                (code,) + kept + ((host_seconds("1800", "预留寻找交换伙伴及完成交换的时间。"),)
                                  if any(f.flag == "--seconds" for f in host.fields)
                                  or "--seconds" in host.fixed else ()),
                fixed=without(host.fixed, "--seconds") + ("--online",), doc="online.md")


FRLG_PATH = '宝可梦中心二楼 → 第三位接待员 → 直接大厅 → 交换中心'

FRLG = Game("frlg", '火红／叶绿', "FRLG", "frlg.md", (
    Tool("frlg-trade-host", '交换（主机）', "bin/frlg_trade_host.py",
         '创建直接大厅交换，游戏机加入 pokeldn 的组。',
         ('启动主机，等待日志出现“Hosting Direct Corner”。',
          f'{FRLG_PATH} → 加入组，然后选择 POKELDN。',
          '选择要交换的宝可梦并确认。',
          '若队列中有多只宝可梦，每次保存后再次交换；主机会提供下一只。',
          '最后一次保存后返回交换菜单，等待主机提示，再选择“取消”并确认“是”。'),
         (queued(count="--trades"),
          Field("--version", '版本', "choice", default="firered", choices=VERSIONS, group='游戏机',
                help='pokeldn 的训练家在连接中报告的游戏版本，也是生成宝可梦的目标版本。'),
          Field("--language", '训练家语言', "choice", default="english", choices=LANGUAGES, hidden=True,
                help='pokeldn 的训练家在连接中报告的语言。'),
          Field("--channel", '信道', "choice", default="11", choices=CHANNELS, help=CHANNEL_HELP, hidden=True)),
         fixed=("--live", "--phy", "auto", "--slot", "0", "--ot", "{ot}", "--id", "{tid}:{sid}",
                "--out", "{received}/frlg-{stamp}.pk3"),
         doc="frlg_link.md"),
    Tool("frlg-trade-join", '交换（加入）', "bin/frlg_trade_join.py",
         '加入由游戏机创建的交换组。',
         ('先启动加入端，它会扫描直到发现游戏机。',
          f'{FRLG_PATH} → 成为组长。',
          '看到 POKELDN 后接受连接，再选择宝可梦并确认。',
          '若队列中有多只宝可梦，每次保存后再次交换；加入端会提供下一只。'),
         (queued(count="--trades"),),
         fixed=("--live", "--phy", "auto", "--slot", "0", "--ot", "{ot}", "--id", "{tid}:{sid}",
                "--out", "{received}/frlg-{stamp}.pk3"),
         doc="frlg_link.md"),
    Tool("frlg-gift", '神秘礼物', "bin/frlg_mg_host.py",
         '通过神秘礼物发送宝可梦、道具和游戏增强功能，备份或恢复存档，或读取训练家 ID 与队伍能力。',
         ('标题画面 → 神秘礼物 → 神奇卡片 → 朋友。接收新闻时选择第二项“神奇新闻”。',
          '启动主机，看到 POKELDN 后选择它。',
          '游戏机询问是否替换卡片时，选择“是”。',
          '发送增强功能、备份或恢复存档、读取存档或运行自定义游戏机代码时，请保持应用运行直到会话日志显示结果。',
          '两次运行之间，请退出搜索画面。'),
         (Field(("--version", "--expect-console"), '版本', "choice", default="firered",
                choices=VERSIONS, group='游戏机',
                help='游戏机使用的卡带版本；版本不符时会在发送前拒绝连接。'),
          Field("--gift-file", '礼物', "builder"),
          Field("--language", '训练家语言', "choice", default="english", choices=LANGUAGES, hidden=True,
                help='pokeldn 的训练家在连接中报告的语言。'),
          Field("--channel", '信道', "choice", default="11", choices=CHANNELS, help=CHANNEL_HELP, hidden=True)),
         fixed=("--live", "--ot", "{ot}", "--id", "{tid}:{sid}", "--dump-file",
                "{received}/frlg-dump-{stamp}.bin"), doc="frlg_gift.md"),
))

LGPE_STEPS = 'X → 通信 → 本地通信 → 交换，输入相同的连接密码并搜索。'

LGPE = Game("lgpe", "Let's Go! 皮卡丘／伊布", "LGPE", "lgpe.md", (
    Tool("lgpe-host", '交换（主机）', "bin/lgpe_host.py",
         '使用连接密码创建交换，由游戏机加入。',
         ('先启动主机。', LGPE_STEPS, '选择宝可梦并确认。'),
         (queued("--offer", more="--next-offer"),
          Field("--code", '连接密码', "linkcode", required=True,
                help='玩家在游戏机上选择的三只宝可梦，顺序必须一致。'),
          FRESH_PID,
          host_seconds("1200", '到时若正在交换，会先完成该次交换。')),
         fixed=("--first", "echo", "--trainer-name", "{ot}", "--our-trainer", "{tid}:{sid}",
                "--received", "{received}/lgpe-{stamp}.pb7"), doc="lgpe.md"),
    Tool("lgpe-join", '交换（加入）', "bin/lgpe_join.py",
         '加入游戏机的交换搜索。',
         ('启动加入端，最多扫描五分钟。', LGPE_STEPS,
          '看到 POKELDN 后选择宝可梦并确认。队列中的宝可梦将依次提供，每次交换一只。'),
         (queued("--offer"), FRESH_PID),
         fixed=("--channels", "1,6,11", "--dwell", "2.5", "--connect", "--connect-seconds", "1800",
                "--ack-peer-clock", "--ack-re-announce", "--facts", "lgpe_net_facts.json",
                "--trainer-name", "{ot}", "--our-trainer", "{tid}:{sid}",
                "--received", "{received}/lgpe-{stamp}.pb7"),
         doc="lgpe_session.md"),
))

SWSH = Game("swsh", '剑／盾', "SwSh", "swsh.md", (
    Tool("swsh-host", '交换（主机）', "bin/swsh_host.py", '创建连接交换，由游戏机加入。',
         ('启动主机，等待网络建立。',
          'YY 通讯 → 连接交换 → 本地通信；两条提示均按 A，然后在地图中等待。',
          '看到 POKELDN 后选择宝可梦并确认。',
          '队列中的宝可梦依次交换，每次一只；请再次从盒子中选择。'),
         (queued("--offer-file"), FRESH_PID,
          Field("--code", '连接密码', "code", help='八位数字。留空进行无密码交换。'),
          Field("--channel", '信道', "choice", default="6", choices=CHANNELS, help=CHANNEL_HELP, hidden=True),
          host_seconds("900")),
         fixed=("--player-name", "{ot}", "--trainer-name", "{ot}",
                "--trainer-tid", "{tid}", "--trainer-sid", "{sid}",
                "--received", "{received}/swsh-{stamp}.pk8"), doc="swsh_trade.md"),
    Tool("swsh-join", '交换（加入）', "bin/swsh_connect.py", '加入游戏机的连接交换搜索。',
         ('YY 通讯 → 连接交换 → 本地通信，不设置密码；两条提示均按 A 确认。',
          '游戏机搜索时启动加入端。',
          '交换画面出现 POKELDN 后，选择宝可梦并确认。',
          '队列中的宝可梦依次交换，每次一只；请再次从盒子中选择。'),
         (queued("--offer-file", required=False,
                 help='选择种类，由 PKHeX 生成合法宝可梦。留空则返还队伍中的第一只宝可梦，并将昵称改为 POKELDN。'),
          FRESH_PID,
          join_seconds("900")),
         fixed=("--preset", "trade", "--send-snapshot", "live",
                "--snapshot-name", "{ot}", "--snapshot-tid", "{tid}", "--snapshot-sid", "{sid}",
                "--save-offered", "{received}/swsh-{stamp}.pk8"),
         doc="swsh_trade.md"),
    Tool("swsh-gift", '神秘礼物', "bin/swsh_gift_host.py",
         '通过本地无线通信发送礼物：选择预设、官方活动或自行制作。',
         ('神秘礼物 → 接收礼物 → 通过本地无线通信接收。',
          '启动主机，卡片通常在几秒内出现；若未出现，请重新尝试。',
          '接收卡片后停止主机。'),
         (Field("--gift-file", '礼物', "builder"),
          Field("--seconds", '时间限制（秒）', "number", default="300", hidden=True,
                help='点击“开始”后卡片广播的时长。')),
         doc="swsh_gift.md"),
))

BDSP_ROOM = '宝可梦中心二楼 → 左侧接待员 → 选择普通的“是”（无密码，非群组选项）。'

BDSP = Game("bdsp", '晶灿钻石／明亮珍珠', "BDSP", "bdsp.md", (
    Tool("bdsp-host", '交换（主机）', "bin/bdsp_host.py",
         '创建联盟房间，由游戏机进入。',
         ('玩家进入房间前启动主机。',
          f'{BDSP_ROOM}等待 pokeldn 的角色出现。',
          'Y → 通信 → 交换宝可梦，接受问候，再选择并确认。'),
         (queued("--offer"),
          FRESH_PID,
          Field("--password", '房间密码', "code", help='八位数字。留空加入无密码房间。'),
          host_seconds("1500")),
         fixed=("--ldn-protocol", "1", "--complete-trade", "--save-theirs", "{received}/bdsp-{stamp}",
                "--language", "{language}", "--name", "{ot}", "--trainer", "{ot}:{tid}:{sid}"),
         doc="bdsp_trade.md"),
    Tool("bdsp-join", '交换（加入）', "bin/bdsp_connect.py",
         '以角色身份加入游戏机的联盟房间并交换。',
         (f'{BDSP_ROOM}在房间内等待，并远离墙壁。',
          '启动加入端，等待角色出现。',
          'Y → 通信 → 交换宝可梦，等待自动出现问候。',
          '两次运行之间，请离开并重新进入房间。'),
         (queued("--trade-template"),
          Field("--trade-nickname", '昵称', hidden=True,
                help='为所有交换的宝可梦设置昵称；留空保留生成时的昵称。'),
          FRESH_PID,
          join_seconds("600")),
         fixed=("--channels", "1,6,11", "--count", "9", "--connect", "5", "--join", "6",
                "--reliable-ack", "--reliable-sweep", "3", "--room-walk", "15", "--room-pattern", "fixed",
                "--room-walk-steps", "0", "--join-avatar", "0", "--answer-requests", "--state", "0",
                "--recruiting", "0", "--answer-talk", "--can-talk", "0", "--initiate-talk",
                "--initiate-delay", "3", "--after-approach", "0x06:0001000000", "--trade-reply",
                "--complete-trade", "--src-var", "{src_var}",
                "--trade-save-poke", "{received}/bdsp-{stamp}.pb8", "--language", "{language}",
                "--name", "{ot}", "--trade-name", "{ot}", "--trade-tid", "{tid}", "--trade-sid", "{sid}"),
         doc="bdsp_trade.md"),
))

PLA_STEPS = ('与祝庆村的交换 NPC 对话：交换 → 本地通信 → 确认提示。',
             '输入相同的八位密码，按 + 搜索。')
PLA_OFFER_HELP = '选择种类，由 PKHeX 生成合法宝可梦。留空则提供 pokeldn 的亚克诺姆。'

PLA = Game("pla", '传说 阿尔宙斯', "PLA", "pla.md", (
    Tool("pla-host", '交换（主机）', "bin/pla_host.py",
         '使用连接密码创建交换，由游戏机加入。',
         ('先启动主机。', *PLA_STEPS, '选择要提供的宝可梦并确认。',
          '保持主机运行直到交换完成。中断交换会导致一段时间内无法交换。'),
         (queued("--trade-box-record", required=False, help=PLA_OFFER_HELP),
          Field("--code", '连接密码', "code", default="00000000", help=CODE_HELP),
          FRESH_PID,
          host_seconds("900")),
         fixed=("--channel", "6", "--session-update", "--sustain", "--clock", "--data-exchange",
                "--game-channel", "--trade-box", "--player-name", "{ot}",
                "--offer-out", "{received}/pla-{stamp}.pa8"),
         doc="pla.md"),
    Tool("pla-join", '交换（加入）', "bin/pla_join.py",
         '搜索游戏机的交换连接并自动连接。',
         (*PLA_STEPS, '启动加入端。', '交换对象出现后，选择宝可梦并确认。'),
         (queued("--offer", required=False, help=PLA_OFFER_HELP),
          Field("--code", '连接密码', "code", default="00000000", help=CODE_HELP),
          FRESH_PID),
         fixed=("--player-name", "{ot}", "--offer-out", "{received}/pla-{stamp}.pa8"),
         doc="pla.md"),
))

SV_SEARCH = 'X → 宝可入口站 → 连接交换，在离线状态下搜索。'

SV = Game("sv", '朱／紫', "SV", "sv.md", (
    Tool("sv-host", '交换（主机）', "bin/sv_host.py",
         '创建交换，由正在搜索的游戏机加入。',
         ('先启动主机。', SV_SEARCH, '在交换画面选择宝可梦并确认。'),
         (queued("--trade-offer"),
          Field("--code", '连接密码', "code", help='留空创建无密码搜索。',
                unset=("--game-data",
                       "000000000000000000000000000000000000000000000000000000000000000000648cf400000000")),
          FRESH_PID),
         fixed=("--channel", "6", "--seconds", "900", "--host-player-id", "00000000000000010000000000000000",
                "--player-name", "POKELDN", "--rtt-probe", "--net-property", "--clock", "--net-stations", "4",
                "--scarlet-response", "--join-seq", "0", "--update-first-seq", "0", "--update-seq", "1",
                "--session-flags", "0x00", "--no-session-ack", "--update-delay", "2.03",
                "--host-player-name", " ", "--record-delay", "0.17",
                "--send-at", "0.06:0x7c:1:b90104b902b9027b0001b902b902320201b902b902320101b902b902320301",
                "--send-at", "0.06:0x81:1:0000000000f38800000000",
                "--send-at", "0.04:0x81:5:000500000ff00800000000",
                "--announce", "--announce-delay", "5.25",
                "--send-at", "6.00:0x7c:1:b90101b902b90280800001", "--offer-after-open", "2",
                "--trainer-name", "{ot}", "--offer-out", "{received}/sv-{stamp}.pk9"),
         doc="sv.md"),
    Tool("sv-join", '交换（加入）', "bin/sv_join.py",
         '加入游戏机的连接交换搜索。',
         (SV_SEARCH, '启动加入端。', '在交换画面选择宝可梦并确认。',
          '若游戏机持续拒绝连接，请退出并重新进入搜索画面。'),
         (queued("--trade-offer"),
          Field("--code", '连接密码', "code", help='留空加入无密码搜索。'),
          FRESH_PID),
         fixed=("--phy", "auto", "--seconds", "1500", "--hold", "900", "--channels", "1,6,11",
                "--dwell", "0.4", "--connect-timeout", "6", "--open-delay", "0.3", "--record-delay", "0.3",
                "--session-join", "--answer-migration", "--net-ack", "--ack-flags", "0x00",
                "--game-channel", "--announce-timeout", "20", "--rtt-delay", "0.3",
                "--trainer-name", "{ot}", "--offer-out", "{received}/sv-{stamp}.pk9"), doc="sv.md"),
))

ZA = Game("za", '传说 Z-A', "PLZA", "za.md", (
    Tool("za-host", '交换（主机）', "bin/za_host.py",
         '创建交换，由正在搜索的游戏机加入。',
         ('先启动主机。',
          'X → 连接游玩 → 连接交换 → 附近的玩家，输入相同密码并搜索。',
          '在交换盒子中选择宝可梦，提出交换并确认。队列中的宝可梦依次交换，每次一只。',
          '最后一次交换后按 B 退出。'),
         (queued("--trade-offer"),
          Field("--code", '连接密码', "code", default="00000000", help=CODE_HELP),
          FRESH_PID,
          host_seconds("900")),
         fixed=("--trainer-name", "{ot}", "--offer-out", "{received}/za-{stamp}.pa9"), doc="za.md"),
    Tool("za-join", '交换（加入）', "bin/za_join.py",
         '加入游戏机的连接交换搜索。',
         ('连接交换 → 本地通信，使用连接密码搜索。',
          '启动加入端。建立连接时被拒绝属于正常现象，请保持运行。',
          '看到 POKELDN 后在交换盒子中选择并确认。队列中的宝可梦依次交换，每次一只。'),
         (queued("--trade-offer"),
          Field("--code", '连接密码', "code", default="00000000", help=CODE_HELP),
          FRESH_PID),
         fixed=("--channels", "1,6,11", "--dwell", "0.35", "--seconds", "1200", "--hold", "900",
                "--quiet-seat", "25", "--connect-timeout", "6", "--mac", "02:11:32:54:76:98", "--game",
                "--offer-delay", "4", "--trainer-name", "{ot}", "--offer-out", "{received}/za-{stamp}.pa9"),
         doc="za.md"),
))

def with_online(game: Game, steps: tuple[str, ...], code: Field | None = None) -> Game:
    """`game` with its online trade after its host tool; `code` replaces the host's own code field's
    help, or is a new field where the game has no code."""
    # The display name is localized; the key identifies the host role.
    host = next(t for t in game.tools if t.key.endswith("-host"))
    if code is None:
        code = next(f for f in host.fields if f.kind in ("code", "linkcode"))
        code = replace(code, help=ONLINE_CODE_HELP if code.kind == "code" else
                       "与交换伙伴选择相同的三只宝可梦，顺序也必须一致；在此处和"
                       "游戏机上都需要输入。")
    at = game.tools.index(host) + 1
    return replace(game, tools=game.tools[:at] + (online(host, steps, code),) + game.tools[at:])


GAMES = (
    with_online(FRLG, (f"{FRLG_PATH} → 加入组，然后选择 POKELDN。",
                       "对方的同行宝可梦显示在右侧：选择要送出的宝可梦，然后"
                       "确认。"),
                Field("--online-code", "连接密码", "code", help=ONLINE_CODE_HELP)),
    with_online(LGPE, (LGPE_STEPS, "选择宝可梦并确认。")),
    with_online(SWSH, ("Y-Comm → 连接交换，通过本地通信输入相同的连接密码；在"
                       "两条提示消息处按 A，然后在地图上等待。",
                       "看到 POKELDN 后选择要送出的宝可梦。")),
    with_online(BDSP, (f"{BDSP_ROOM} pokeldn 的角色将出现。",
                       "Y → 交流 → 交换宝可梦；接受问候，然后选择宝可梦。"),
                Field("--password", "连接密码", "code", help="与交换伙伴约定的八位密码，"
                      "也需要在联合房间的密码提示处输入。留空使用"
                      "无密码房间，匹配未设置密码的在线玩家。")),
    with_online(PLA, (*PLA_STEPS, "提出要交换的宝可梦并确认。")),
    with_online(SV, (SV_SEARCH, "在交换画面提出交换并确认。")),
    with_online(ZA, ("X → 连接游玩 → 连接交换 → 附近的玩家，输入相同密码并搜索。",
                     "在交换盒子中选择宝可梦，提出交换，然后确认。")),
)
