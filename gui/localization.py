"""Chinese presentation, independent of protocol IDs and cartridge strings.

Terminology: https://github.com/kwsch/PKHeX/blob/master/PKHeX.WinForms/Resources/text/lang_zh-Hans.txt
"""
import atexit
import functools
import re

from pokeldn.pokemon import BuilderError, Service
from gui.zh_hans import LABELS, SPECIES

_SPECIES = re.compile(r"(?<![\w])(" + "|".join(re.escape(s) for s in sorted(SPECIES, key=len, reverse=True)) + r")(?![\w])")


def names(value: str) -> str:
    return _SPECIES.sub(lambda m: SPECIES[m[0]], value)


def translate(value: str) -> str:
    """Only presentation strings use this; option keys and user-entered values stay unchanged."""
    if value in LABELS:
        return LABELS[value]
    # Compound descriptions append a shared reminder; translate each part without changing its meaning.
    for suffix in (" Turns off any game boost that is on.",):
        if value.endswith(suffix):
            return translate(value[:-len(suffix)]) + "会关闭正在运行的游戏增强功能。"
    from pokeldn.frlg.gift import builder as frlg
    if value.endswith(frlg.MOM_STEPS):
        return translate(value[:-len(frlg.MOM_STEPS)]) + "保存增强功能后，发送一次“由妈妈恢复增强功能”。每次重启后，与真新镇家中的妈妈对话恢复；接收其他神奇卡片后需重新发送此礼物。"
    outfit = re.fullmatch(r"Puts the (.+) in the wardrobe", value)
    if outfit:
        return "在衣柜中添加" + translate(outfit[1]) + "。"
    invalid_gift = re.fullmatch(r"Invalid gift file: (.+)", value, re.S)
    if invalid_gift:
        return "礼物文件无效：" + translate(invalid_gift[1])
    name_error = re.fullmatch(r"Names: (.+)", value, re.S)
    if name_error:
        return "名称错误：" + translate(name_error[1])
    for prefix, target in (("PKHeX could not read it (", "PKHeX 无法读取（"),
                           ("PKHeX finds it not legal (", "PKHeX 判定其不合法（")):
        if value.startswith(prefix) and value.endswith(")"):
            return target + translate(value[len(prefix):-1]) + "）"
    patterns = (
        (r"(\d+) of its moves are not legal\.", r"有 \1 个招式不合法。"),
        (r"The level goes from (\d+) to 100: a Pokemon never loses levels\.", r"等级必须在 \1 到 100 之间，宝可梦等级不能降低。"),
        (r"This form of (.+) is not in that game\.", r"该游戏中不存在 \1 的此形态。"),
        (r"(.+) is not in that game\.", r"该游戏中不存在 \1。"),
        (r"[Tt]he lister asks for level (\d+) to (\d+)\.?", r"挂牌方要求等级在 \1 到 \2 之间。"),
        (r"[Tt]he lister asks for (.+?)\.?", r"挂牌方想要 \1。"),
        (r"Windows did not give pokeldn permission to change (.+)", r"Windows 未授予 pokeldn 修改 \1 的权限。"),
        (r"unknown button (.+)", r"未知按键：\1"),
        (r"(.+) must be a number of milliseconds from (\d+) to (\d+)", r"\1 必须为 \2 到 \3 毫秒之间的数值"),
        (r"(.+) must be \[x, y\], each from -1 to 1", r"\1 必须为 [x, y]，每个值介于 -1 和 1 之间"),
        (r"(.+) must be a list", r"\1 必须为列表"),
        (r"repeats nest deeper than (\d+)", r"重复步骤的嵌套超过 \1 层"),
        (r"(.+) must be an object", r"\1 必须为对象"),
        (r"(.+) must have exactly one of press, wait, repeat", r"\1 必须且只能包含 press、wait、repeat 中的一项"),
        (r"(.+): unknown field (.+)", r"\1：未知字段 \2"),
        (r"(.+) must be text", r"\1 必须为文本"),
        (r"(.+): repeat must be a whole number from 1 to 10000", r"\1：重复次数必须为 1 到 10000 的整数"),
        (r"(.+): press must be a button name or a list of them", r"\1：press 必须为按键名称或按键名称列表"),
        (r"not a macro file: (.+)", r"不是有效的宏文件：\1"),
        (r"the macro is longer than the board's (\d+) steps", r"宏超过开发板的 \1 步限制"),
        (r"no (POKELDN-PAD) found: is the board powered and running the controller firmware\?", r"未找到 \1，请检查开发板是否已通电并运行手柄固件。"),
        (r"no answer from the controller board on (.+)", r"\1 上的手柄开发板未响应"),
        (r"the board refused the request \((.+)\)", r"开发板拒绝了请求（\1）"),
        (r"the board did not answer (.+) within (\d+) s", r"开发板未在 \2 秒内响应 \1"),
        (r"A raid gives at most (\d+) rewards\.", r"一场团体战最多可设置 \1 项奖励。"),
        (r"Choose an item for reward (\d+)\.", r"请为第 \1 项奖励选择道具。"),
        (r"Reward (\d+) needs a quantity from 1 to 999\.", r"第 \1 项奖励的数量必须为 1 到 999。"),
        (r"pokeldn cannot write to (.+)\.", r"pokeldn 无法写入 \1。"),
        (r"the download is (\d+) bytes", r"下载文件大小为 \1 字节"),
        (r"the archive holds no (.+)", r"压缩包中缺少 \1"),
        (r"SHA256SUMS does not list (.+)", r"SHA256SUMS 中未列出 \1"),
        (r"(.+) does not match its SHA-256 in SHA256SUMS", r"\1 与 SHA256SUMS 中的 SHA-256 校验和不一致"),
        (r"PKHeX has no transfer route \((.+)\)\.", r"PKHeX 没有可用的传送路径（\1）。"),
        (r"(.+) already has (\d+) Pokemon queued\.", r"\1 的队列中已有 \2 只宝可梦。"),
        (r"Their Pokemon was refused: (.+)", r"对方的宝可梦被拒绝：\1"),
        (r"Your partner's app refused your Pokemon: (.+)", r"对方的应用拒绝了你的宝可梦：\1"),
        (r"Adds ([\d,]+) to the player's money, up to ([\d,]+)", r"为玩家增加 \1 金钱，上限为 \2"),
        (r"Sword and Shield have no item above (\d+)\.", r"剑／盾不存在编号大于 \1 的物品。"),
        (r"Sword and Shield have no item (\d+)\.", r"剑／盾不存在编号为 \1 的物品。"),
        (r"Unknown gift kind (.+)\.", r"未知礼物类别：\1。"),
        (r"Unknown outfit (.+)\.", r"未知服装：\1。"),
        (r"A card carries (\d+) pieces of clothing at most; pick fewer outfits\.", r"每张卡片最多携带 \1 件服装，请减少所选服装。"),
        (r"Mystery Gift files do not support game (.+)\.", r"神秘礼物文件不支持游戏 \1。"),
        (r"Duplicate gift field (.+)\.", r"礼物字段重复：\1。"),
        (r"Expected gift fields: (.+)\.", r"需要以下礼物字段：\1。"),
        (r"This gift is for (.+), not (.+)\.", r"此礼物适用于 \1，当前游戏为 \2。"),
        (r"Gift component (.+) failed its SHA-256 check\.", r"礼物组件 \1 未通过 SHA-256 校验。"),
        (r"A (.+) file holds a (.+) gift, not (.+)\.", r"\1 文件用于保存 \2 礼物，当前礼物属于 \3。"),
        (r"(\d+) bytes are not a Pokemon of this game\.", r"这 \1 字节的数据不是此游戏的宝可梦。"),
        (r"Expected (.+), received (.+)\.", r"需要 \1 格式，实际收到 \2。"),
        (r"Unsupported edit (.+)\.", r"不支持的修改：\1。"),
        (r"No Gen 3 event is named (.+)\.", r"没有名为 \1 的第三世代活动。"),
        (r"PKHeX made an illegal (.+): (.+)", r"PKHeX 生成的 \1 不合法：\2"),
        (r"Line (\d+): (.+)", r"第 \1 行：\2"),
        (r"It would hang the console: (.+)", r"此代码会导致游戏机无响应：\1"),
        (r"Assembling needs the GNU Arm assembler: install it with (.+)", r"汇编需要 GNU Arm 汇编器，请使用以下方式安装：\1"),
        (r"(\d+) bytes; returned 1 after (\d+) frames? \((\d+) instructions\) and answers (0x[0-9A-F]+)\.",
         r"\1 字节；在 \2 帧后返回 1（执行 \3 条指令），回复值为 \4。"),
        (r"(\d+) bytes; returned 1 after (\d+) frames? \((\d+) instructions\) and sends back (\d+) bytes\.",
         r"\1 字节；在 \2 帧后返回 1（执行 \3 条指令），返回 \4 字节。"),
        (r"Build the Pokemon to offer for trade (\d+) first\.", r"请先生成第 \1 次交换的宝可梦。"),
        (r"The Pokemon for trade (\d+) is not legal\.", r"第 \1 次交换的宝可梦不合法。"),
        (r"(.+) must be an integer\.", r"\1 必须是整数。"),
        (r"A nickname is at most (\d+) characters in this game\.", r"此游戏的昵称最多为 \1 个字符。"),
        (r"(.+) cannot be lower than level (\d+) in this game\.", r"此游戏中的 \1 等级不能低于 \2。"),
        (r"(.+) cannot be shiny in this game\.", r"此游戏中的 \1 不能为异色。"),
        (r"No legal (.+) with these choices\. (.+)", r"无法按这些选项生成合法的 \1。\2"),
        (r"(.+) is not in this game\.", r"此游戏中不存在 \1。"),
        (r"(.+) cannot have (.+)\.", r"\1 无法拥有 \2。"),
        (r"(.+) cannot be held in this game\.", r"此游戏中无法携带 \1。"),
        (r"EVs add up to (\d+); at most (\d+)\.", r"努力值总和为 \1，最多为 \2。"),
        (r"(Overworld and battles|Overworld only|Battles only) run up to x(\d+) all the time", r"\1 始终以最高 \2 倍速运行"),
        (r"(Overworld and battles|Overworld only|Battles only) run up to x(\d+) while (.+) is held", r"按住 \3 时，\1 以最高 \2 倍速运行"),
        (r"The game runs x(\d+) slower while (.+) is held, to hit the frame", r"按住 \2 时，游戏减速至 1/\1，以便对准帧"),
        (r"Walk through walls, trees and water while (.+) is held; people still block the way", r"按住 \1 可穿过墙壁、树木和水面；人物仍会挡路"),
        (r"(.+) both draw in the top-right corner: pick one\.", r"\1 均在右上角显示，请选择一个。"),
        (r"Gives (.+), level (\d+)(.*)", r"赠送 \1，等级 \2\3"),
        (r"Gives (.+), a level the game rolls(.*)", r"赠送 \1，等级由游戏随机决定\2"),
        (r"Gives a (.+) egg", r"赠送 \1 的蛋"),
        (r"Gives (.+?)(?: x(\d+))?", r"赠送 \1 ×\2"),
        (r"Starts a battle with a wild (.+), level (\d+)", r"开始野生对战：\1，等级 \2"),
        (r"Holding (.+)", r"携带 \1"),
        (r"Adds (\d+) Battle Points", r"增加 \1 对战点数"),
        (r"Card id (\d+): a console takes the same id again", r"卡片 ID \1：游戏机可重复接收相同 ID"),
        (r"Card id (\d+): a console takes it once", r"卡片 ID \1：只能领取一次"),
        (r"Card id (\d+): a console takes it again", r"卡片 ID \1：允许重复领取"),
        (r"Card id (\d+): a console takes it once for its date, at most ten such cards a day", r"卡片 ID \1：每个日期可领取一次，每天最多十张此类卡片"),
        (r"Original trainer (.+)", r"原始训练家：\1"),
        (r"Puts (\d+) pieces? of clothing in the wardrobe; the player gets the version for their own character", r"向衣柜添加 \1 件服装，玩家收到对应自身角色的版本"),
        (r"Built for (.+)", r"目标版本：\1"),
        (r"News “(.*)”", r"新闻“\1”"),
        (r"Says “(.*)”", r"显示“\1”"),
    )
    for pattern, replacement in patterns:
        if re.fullmatch(pattern, value, re.S):
            result = re.sub(pattern, replacement, value, flags=re.S)
            for fragment in ("Overworld and battles", "Overworld only", "Battles only"):
                result = result.replace(fragment, LABELS[fragment])
            # These strings embed literal user or trainer text, so keep their values intact.
            if pattern.startswith(("News", "Says", "Original trainer")):
                return result
            return names(result).replace(", shiny", "，异色").replace(", can Gigantamax", "，允许超极巨化").replace(" (an egg)", "（蛋）")
    return names(value)


class DisplayService(Service):
    def _ask(self, request):
        try:
            reply = super()._ask(request)
        except BuilderError as exc:
            raise BuilderError(translate(str(exc))) from exc
        for found in reply.get("sets", ()):
            for key in ("errors", "notes"):
                found[key] = [translate(line) for line in found.get(key, ())]
        if "encounter" in reply:
            reply["encounter"] = translate(reply["encounter"])
        for route in reply.get("games", {}).values():
            route["reason"] = translate(route.get("reason", ""))
        return reply


SERVICE = DisplayService(display_language="zh-Hans")
atexit.register(SERVICE.close)


@functools.cache
def game_terms(game: str) -> dict[str, str]:
    """Remote GTS metadata carries names rather than IDs; pair PKHeX names using their original IDs."""
    from pokeldn.pokemon import SERVICE as english
    result = {}
    for kind in ("moves", "items", "balls", "natures", "abilities"):
        localized = {n["id"]: n["name"] for n in SERVICE.names(game, kind)}
        result.update((n["name"], localized[n["id"]]) for n in english.names(game, kind)
                      if n["id"] in localized)
    return result


def summary(info: dict) -> str:
    parts = [f"{info['species']}-{info['form']}" if info.get("form") else info["species"], f"等级 {info['level']}"]
    if info.get("shiny"):
        parts.append("异色")
    if info.get("nickname") and info["nickname"].lower() != info["species"].lower():
        parts.append(f"“{info['nickname']}”")
    parts += [info.get("nature", ""), info.get("ability", ""), info.get("ball", "")]
    if info.get("held_item"):
        parts.append(f"携带 {info['held_item']}")
    return " · ".join(p for p in parts if p)


def gift_description(game, state, name):
    """Keep gift payloads unchanged; FRLG species IDs are different from the national dex."""
    from pokeldn.app.gift_builder import module
    if game != "frlg" or state.get("kind", "card") != "card":
        when, lines = module(game).describe(state, name)
        return translate(when), [translate(line) for line in lines]
    from pokeldn.frlg.gift.builder import GIVERS
    giver = next((g for g in GIVERS if g[0] == state.get("giver")), GIVERS[0])
    when = f"在{translate(giver[2])}与{translate(giver[1])}对话时生效。"
    if giver[0] != "deliveryman":
        when += "该人物持有礼物时不显示卡片。"
    lines = []
    for step in state.get("steps", ()):
        action = step.get("type")
        if action in ("pokemon", "battle"):
            verb = "赠送" if action == "pokemon" else "开始野生对战："
            lines.append(f"{verb} {name('species', step.get('species'))}，等级 {step.get('level') or 5}")
        elif action == "egg":
            lines.append(f"赠送 {name('species', step.get('species'))} 的蛋")
        elif action == "item":
            lines.append(f"赠送 {name('item', step.get('item'))} ×{step.get('quantity') or 1}")
        else:
            text = str(step.get("text") or "").splitlines()
            lines.append(f"显示“{text[0] if text else ''}”")
    card = state.get("card", {})
    lines.append("每次对话均可领取，直到接收其他礼物" if giver[0] != "deliveryman" else
                 "允许重复领取" if card.get("repeatable") else "每个存档只能领取一次")
    if card.get("shareable"):
        lines.append("玩家可以分享卡片")
    return when, lines


def event_text(value: str) -> str:
    result = translate(value)
    # Event trainer names and campaign titles are retained; Pokemon names and attributes use Chinese.
    result = re.sub(r"\blevel (\d+)\b", r"等级 \1", result)
    result = re.sub(r"\b[Ss]hiny\b", "异色", result)
    result = re.sub(r"\b(\d+) Battle Points\b", r"\1 对战点数", result)
    result = re.sub(r"\b(\d+) pieces? of clothing\b", r"\1 件服装", result)
    for source, target in (("(Galar)", "（伽勒尔）"), ("Master Ball", "大师球"), (" (an egg)", "（蛋）"),
                           (" (Gmax)", "（超极巨化）"), ("can Gigantamax", "可超极巨化")):
        result = result.replace(source, target)
    result = re.sub(r"\(([^()]*)\)", lambda m: "（" + LABELS[m[1]] + "）" if m[1] in LABELS else m[0], result)
    months = {"Feb": "2", "March": "3", "April": "4"}
    result = re.sub(r"\((\d{4}) (Feb|March|April) International Competition ([JM])\)",
                    lambda m: f"（{m[1]} 年 {months[m[2]]} 月国际挑战赛 {m[3]}）", result)
    return result


def event_label(game: str, card: dict) -> str:
    """Name official item rewards by their record IDs, independent of the archive's English title."""
    if game == "swsh" and card["group"] == "Items":
        from pokeldn.swsh.events import item_pairs
        items = {item["id"]: item["name"] for item in SERVICE.names(game, "items")}
        return "，".join(f"{items.get(ident, f'道具 {ident}')} ×{quantity}"
                       for ident, quantity in item_pairs(card["record"]))
    return event_text(card["label"])


def summary_text(value: str) -> str:
    """Display a stored or remote summary without translating the player's nickname."""
    parts = []
    for part in value.split(" · "):
        if part.startswith(("'", "“")) and part.endswith(("'", "”")):
            parts.append(part)
        elif part.startswith("holding "):
            parts.append("携带 " + translate(part.removeprefix("holding ")))
        else:
            parts.append(event_text(part))
    return " · ".join(parts)


def translate_app_log(line: str) -> str:
    """Translate app-authored log messages for display, preserving diagnostic output and identifiers."""
    if not line.startswith("[app] "):
        return line
    message = line[6:]
    exact = {
        "This firmware uses a different radio protocol. Flash the board.": "此固件使用不同的无线通信协议，请刷写开发板。",
        "Stopping: the entry point leaves the network and closes the board.": "正在停止：程序将退出网络并关闭开发板连接。",
    }
    if message in exact:
        return "[app] " + exact[message]
    patterns = (
        (r"Checking (.+); the board may restart\.", r"正在检查 \1；开发板可能会重启。"),
        (r"Sessions now use (.+)\.", r"会话现在使用 \1。"),
        (r"Flashing (.+)\.", r"正在刷写 \1。"),
        (r"Exited with code (-?\d+)\.", r"程序已退出，退出码为 \1。"),
        (r"Could not open (.+): (.+)", r"无法打开 \1：\2"),
        (r"(.+) runs the controller firmware\.", r"\1 正在运行手柄固件。"),
        (r"No pokeldn firmware answered on (.+) \((.+)\)\.", r"\1 上的 pokeldn 固件未响应（\2）。"),
        (r"The chip on (.+) is an (.+)\.", r"\1 上的芯片为 \2。"),
        (r"Could not read the chip type on (.+) \((.+)\)\.", r"无法读取 \1 上的芯片类型（\2）。"),
        (r"(.+), protocol (\d+), chip revision (\d+), MAC (.+)", r"\1，协议 \2，芯片修订版本 \3，MAC \4"),
        (r"Downloading (.+) from (.+)\.", r"正在从 \2 下载 \1。"),
        (r"Firmware for (.+): (.+)", r"适用于 \1 的固件：\2"),
        (r"(.+) does not match the release's SHA256SUMS; nothing was written", r"\1 与发布版本的 SHA256SUMS 不一致；未写入任何文件。"),
        (r"(.+) is not supported\. Use an ESP32, ESP32-S3, ESP32-C3 or ESP32-C6\.", r"不支持 \1。请使用 ESP32、ESP32-S3、ESP32-C3 或 ESP32-C6。"),
        (r"Missing firmware for (.+): (.+)", r"缺少适用于 \1 的固件：\2"),
        (r"Merged firmware does not match (.+): (.+)", r"合并固件与 \1 不匹配：\2"),
        (r"Invalid merged firmware: (.+)", r"合并固件无效：\1"),
        (r"Firmware checksum does not match: (.+)", r"固件校验和不匹配：\1"),
    )
    for pattern, replacement in patterns:
        if re.fullmatch(pattern, message, re.S):
            return "[app] " + re.sub(pattern, replacement, message, flags=re.S)
    return "[app] " + LABELS.get(message, message)
