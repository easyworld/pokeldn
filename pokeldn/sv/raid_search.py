"""Search a range of raid seeds for the bosses that match a filter, ranked by a stat score or the
rewards wanted: the app's raid finder (docs/sv_raid.md, Finding a seed)."""

import bisect
from dataclasses import dataclass
import heapq
from itertools import product

from pokeldn.sv import raid_encounter as encounter, raid_event, raid_scan

# The PKHeX helper scans tens of millions of seeds a second (pokeldn.sv.raid_scan); without it, Python.
FAST = raid_scan.available()
MAX_COUNT = 1 << 32                   # seeds in each context: every seed
PYTHON_WORK = 1_000_000               # without the helper, seeds times contexts
DEFAULT_COUNT = 100_000_000 if FAST else 100_000
MAX_RESULTS = 100
# The boss's scale each size mark filter wants: 0 for the Mini mark, 255 for the Jumbo mark.
SIZE_MARKS = {"either": (0, 0xFF), "mini": (0,), "jumbo": (0xFF,)}
SCORE_LIMIT = 1 << 31                 # every score is under it: the helper's rank holds it beside the seed
# (label, score, lowest first). Stats are HP Atk Def Spe SpA SpD. "rewards" scores the rewards wanted
# instead, in their order (ranked_rewards).
OBJECTIVES = {
    "overall": ("Lowest overall bulk", lambda s: s[0] * (s[2] + s[5]), True),
    "physical": ("Lowest physical bulk", lambda s: s[0] * s[2], True),
    "special": ("Lowest special bulk", lambda s: s[0] * s[5], True),
    "offense": ("Weakest offense", lambda s: max(s[1], s[4]), True),
    "hardest": ("Highest total stats", sum, False),
    "rewards": ("Most desired rewards", None, False),
}


@dataclass(frozen=True)
class Found:
    seed: int
    context: dict
    stars: int
    boss: dict
    score: int
    rewards: tuple = ()           # [(item, quantity)], drawn when the search wants rewards

    @property
    def is_shiny(self):
        b = self.boss
        return (b["trainer_id"] ^ b["secret_id"] ^ (b["pid"] >> 16) ^ (b["pid"] & 0xFFFF)) < 16


def contexts(version="any", map_name="any", progress="any", content="any", event=None, group="any"):
    """-> the raid contexts a search covers; "any" widens a dimension. A black crystal ignores the
    story progress, so it is searched once. With an event, the contexts are its dens' (`group` one
    of them): Paldea, and one progress per stage, since the progresses of a stage draw alike."""
    if event is not None:
        return _event_contexts(event, version, progress, group)
    for value, choices in ((version, encounter.VERSIONS), (map_name, encounter.MAPS),
                           (progress, encounter.PROGRESS), (content, encounter.CONTENTS)):
        if value != "any" and value not in choices:
            raise ValueError(f"{value!r} is not one of {choices}")
    pick = lambda value, choices: choices if value == "any" else (value,)
    out = []
    for v, m, c in product(pick(version, encounter.VERSIONS), pick(map_name, encounter.MAPS),
                           pick(content, encounter.CONTENTS)):
        stages = ("6star",) if c == "black" else pick(progress, encounter.PROGRESS)
        out += [{"version": v, "map_name": m, "progress": p, "content": c} for p in stages]
    return out


def _event_contexts(event, version, progress, group):
    out = []
    for v in raid_event.versions(event):
        if version not in ("any", v):
            continue
        for den in raid_event.dens(event, v):
            if str(group) not in ("any", str(den.group)):
                continue
            stages = {}
            for p in raid_event.progresses(event, v, den.group):
                if progress in ("any", p):
                    stages.setdefault(raid_event.STAGES[p], p)
            out += [{"version": v, "map_name": "paldea", "progress": p, "content": den.content,
                     "event": event, "group": den.group, "den": den.label} for p in stages.values()]
    return out


def generate(seed, context):
    """-> the Raid the seed gives in a context as `contexts` makes it, an event's when it names one."""
    if "event" in context:
        return raid_event.generate(context["event"], seed, context["version"], context["progress"],
                                   context["group"])
    return encounter.generate(seed, context["version"], context["map_name"], context["progress"],
                              context["content"])


def _drawer(context):
    """-> seed -> (row, stars) in the context; an event's rows are gathered once, not per seed."""
    if "event" not in context:
        return lambda seed: encounter.select(seed, context["version"], context["map_name"],
                                             context["progress"], context["content"])
    rows = raid_event.candidates(context["event"], context["version"], context["progress"], context["group"])

    def draw(seed):
        row = raid_event.draw(rows, seed)
        return row, row["stars"]
    return draw


def _rows(context):
    """-> [(row, stars)] every encounter the context can draw."""
    if "event" in context:
        return [(r, r["stars"]) for r in raid_event.candidates(context["event"], context["version"],
                                                               context["progress"], context["group"])]
    content = context["content"]
    stars = {6} if content == "black" else {s for _, s in encounter.STAR_LOTTERY[context["progress"]]}
    return [(r, r["stars"]) for r in encounter.tables()["encounters"][f"{context['map_name']}_{content}"]
            if r["stars"] in stars and r["rate"] and r["rate_min"][context["version"]] >= 0]


def _reward_tables(context):
    """-> (fixed, lottery) tables a context's raids draw their rewards from; None the base game's."""
    event = context.get("event")
    return (event.fixed, event.lottery) if event is not None else (None, None)


def _gems(row):
    """-> the Tera types the boss of a row can have, which pick its Tera shards: the table's own, or
    any of 18 (encounter.tera_type)."""
    if row["tera"] >= 2:
        return {row["tera"] - 2}
    return set(range(len(encounter.TERA_TYPES)))


def _sums(amounts, counts):
    """-> every total of exactly k draws from `amounts`, k one of `counts`."""
    reach, out = {0}, {0} if 0 in counts else set()
    for k in range(1, max(counts, default=0) + 1):
        reach = {s + a for s in reach for a in amounts}
        if k in counts:
            out |= reach
    return out


def _reward_item(entry, material, gem):
    """-> the item a reward row gives: its own, or the boss's material or Tera shard."""
    return entry["item"] or {encounter.REWARD_MATERIAL: material,
                             encounter.REWARD_SHARD: encounter.TERA_SHARDS[gem]}.get(entry["category"], 0)


def _totals(row, stars, fixed, lottery, gem, items=None):
    """-> {item: every total of it a raid of the row gives with that Tera type}, of `items` alone
    when given: its fixed rows, plus any number of the lottery's draws of it up to the most a raid
    draws (all of them when the lottery holds nothing else)."""
    data = encounter.tables()
    material = int(data["material_items"].get(str(row["species"]), 0))
    item = lambda entry: _reward_item(entry, material, gem)
    fixed = data["fixed_rewards"] if fixed is None else fixed
    lottery = data["lottery_rewards"] if lottery is None else lottery
    given = {}
    for entry in fixed.get(row["fixed_rewards"], ()):
        if item(entry) and entry["amount"]:
            given[item(entry)] = given.get(item(entry), 0) + entry["amount"]
    draws = [(item(e), e["amount"]) for e in lottery.get(row["lottery_rewards"], ()) if e["probability"]]
    counts = set(encounter.REWARD_SLOTS[stars - 1]) if draws else {0}
    out = {}
    found = set(given) | {i for i, n in draws if i and n}
    for wanted in found if items is None else found & items:
        amounts = {n for i, n in draws if i == wanted and n}
        others = any(i != wanted or not n for i, n in draws)
        drawn = _sums(amounts, set(range(max(counts) + 1)) if others else counts)
        totals = {given.get(wanted, 0) + s for s in drawn} - {0}
        if totals:
            out[wanted] = totals
    return out


def reward_choices(scope, *, stars=None, species_id=None, tera_type=None, items=None):
    """-> {item: (every total of it, lowest first)} of the items the raids of `scope` can give,
    narrowed to a star level, species and Tera type as the search would be, and to a set of `items`."""
    out, seen = {}, {}
    shards = items is None or not items.isdisjoint(encounter.TERA_SHARDS)     # else one Tera type will do
    for context in scope:
        fixed, lottery = _reward_tables(context)
        for row, row_stars in _rows(context):
            if (stars is not None and row_stars != stars) or (species_id is not None
                                                              and row["species"] != species_id):
                continue
            gems = _gems(row) if tera_type is None else _gems(row) & {tera_type}
            for gem in gems if shards else sorted(gems)[:1]:
                key = (row["fixed_rewards"], row["lottery_rewards"], row["species"], row_stars, gem, id(fixed))
                if key not in seen:
                    seen[key] = _totals(row, row_stars, fixed, lottery, gem, items)
                for item, totals in seen[key].items():
                    out.setdefault(item, set()).update(totals)
    return {item: tuple(sorted(totals)) for item, totals in out.items()}


def _scale_range(row):
    """-> the lowest and highest scale the row's boss can have (raid_encounter.boss_fields)."""
    rule = row.get("scale_type", encounter.SCALE_RANDOM)
    if rule == encounter.SCALE_VALUE:
        return row["scale"], row["scale"]
    if rule == encounter.SCALE_RANDOM:
        return 0, 0xFF
    span, low = encounter.SCALE_BANDS[rule]
    return low, low + span - 1


def size_marks(scope, *, stars=None, species_id=None):
    """-> the SIZE_MARKS a boss of `scope` can take, narrowed to a star level and species: all of
    them but where an event's band or own value rules a scale of 0 or 255 out."""
    ends = set()
    for context in scope:
        for row, row_stars in _rows(context):
            if (stars is None or row_stars == stars) and (species_id is None or row["species"] == species_id):
                low, high = _scale_range(row)
                ends |= {scale for scale in (0, 0xFF) if low <= scale <= high}
    return {mark for mark, scales in SIZE_MARKS.items() if ends & set(scales)}


def ranked_rewards(scope, rewards, *, stars=None, species_id=None, tera_type=None):
    """-> [(item, amounts)] the leading wanted items "Most desired rewards" ranks by, in their order,
    each with every total of it from its least up the raids searched give (reward_choices): a raid's
    total is a digit, its place among them, the first item the most significant, and as many items
    as one score under SCORE_LIMIT holds; those after only want their least. Five fit whatever they are
    in every raid known (an item has up to 59 totals, an event's Exp. Candy L), more mostly."""
    choices = reward_choices(scope, stars=stars, species_id=species_id, tera_type=tera_type, items=set(rewards))
    out, room = [], 1
    for item, least in rewards.items():
        amounts = tuple(n for n in ((0,) if least <= 0 else ()) + choices.get(item, ()) if n >= least) or (least,)
        if room * len(amounts) > SCORE_LIMIT:
            break
        room *= len(amounts)
        out.append((item, amounts))
    return out


def reward_score(rewards, ranked):
    """-> the "Most desired rewards" score of a raid's rewards [(item, quantity)]: the place of its
    total of each ranked item among that item's amounts, one digit each, larger better."""
    totals = {}
    for item, quantity in rewards:
        totals[item] = totals.get(item, 0) + quantity
    score = 0
    for item, amounts in ranked:
        score = score * len(amounts) + max(bisect.bisect_right(amounts, totals.get(item, 0)) - 1, 0)
    return score


def _can_give(row, stars, tables, wanted):
    """-> whether some raid of the row gives at least the wanted quantity of every wanted item."""
    best = {}
    for gem in _gems(row):
        for item, totals in _totals(row, stars, *tables, gem).items():
            best[item] = max(best.get(item, 0), max(totals))
    return all(best.get(item, 0) >= least for item, least in wanted.items())


def gives(rewards, wanted):
    """-> whether the rewards hold at least the wanted quantity of every wanted item."""
    totals = {}
    for item, quantity in rewards:
        totals[item] = totals.get(item, 0) + quantity
    return all(totals.get(item, 0) >= least for item, least in wanted.items())


def species(event=None):
    """-> [(species, name)] of every standard and black-crystal raid boss, or of an event's, by name."""
    names = encounter.tables()["species_names"]
    if event is not None:
        found = {r["species"] for r in event.rows if r["rate"]}
    else:
        found = {row["species"] for rows in encounter.tables()["encounters"].values() for row in rows}
    return sorted(((s, names[str(s)]) for s in found), key=lambda pair: pair[1].casefold())


def most_seeds(contexts):
    """-> the most seeds a search covers in each of `contexts` contexts: every seed of every one with
    the helper, a million over them all in Python."""
    return MAX_COUNT if FAST else min(MAX_COUNT, PYTHON_WORK // contexts)


def search(start, count, scope, objective="overall", *, stars=None, shiny=None, species_id=None,
           tera_type=None, nature=None, gender=None, ability=None, ivs=None, rewards=None, size_mark=None,
           one_per_species=False, limit=12, progress=None, cancelled=None, stop_at_first=False):
    """-> up to `limit` matches among seeds start..start+count-1 in every context of `scope`, best
    score first. `ivs` is six (low, high) ranges, HP Atk Def Spe SpA SpD; `rewards` {item: least
    quantity}, a raid's quantities of an item summed, and a match carries its rewards. `size_mark`, a
    key of SIZE_MARKS, wants a boss whose scale can take that mark.
    `stop_at_first` answers the first match alone, whatever its score: the earliest seed of the first
    context in `scope` that has one."""
    if objective not in OBJECTIVES:
        raise ValueError(f"no objective {objective!r}")
    if not scope or not 1 <= count <= most_seeds(len(scope)):
        raise ValueError(f"a search covers 1 to {most_seeds(len(scope) or 1):,} seeds in each context")
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"a search returns 1 to {MAX_RESULTS} results")
    _, score, lowest_first = OBJECTIVES[objective]
    best, by_species = [], {}
    total, done = count * len(scope), 0
    wanted = dict(rewards or {})
    ranked = []
    if objective == "rewards":
        if not wanted:
            raise ValueError("Most desired rewards ranks by the wanted rewards: want at least one.")
        ranked = ranked_rewards(scope, wanted, stars=stars, species_id=species_id, tera_type=tera_type)
    if size_mark is not None and size_mark not in SIZE_MARKS:
        raise ValueError(f"no size mark {size_mark!r}")
    filters = dict(stars=stars, shiny=shiny, species_id=species_id, tera_type=tera_type, nature=nature,
                   gender=gender, ability=ability, ivs=ivs, rewards=rewards, size_mark=size_mark)
    for index, context in enumerate(scope):
        draw = _drawer(context)
        tables = _reward_tables(context)
        able = {}                     # a row's id -> whether its raids can give what is wanted
        # The helper's scan names the few seeds this loop can keep; without it the loop takes them all.
        picked = raid_scan.offsets(
            start, count, context, objective, lowest_first, limit, one_per_species, cancelled=cancelled,
            progress=progress and (lambda n, base=index * count: progress(base + n, total)),
            stop_at_first=stop_at_first, amounts=[a for _, a in ranked], **filters) if FAST else None
        for offset in range(count) if picked is None else picked:
            if picked is None and cancelled and cancelled():
                return _ranked(best, by_species, one_per_species, limit)
            done = index * count + offset + 1
            if progress and picked is None and done % 5000 == 0:
                progress(done, total)
            seed = (start + offset) & 0xFFFFFFFF
            row, found_stars = draw(seed)
            if (stars is not None and found_stars != stars) or (
                    species_id is not None and row["species"] != species_id):
                continue
            given = ()
            if wanted:
                if id(row) not in able:
                    able[id(row)] = _can_give(row, found_stars, tables, wanted)
                if not able[id(row)]:
                    continue
                given = tuple(encounter.rewards(seed, row, found_stars, *tables))
                if not gives(given, wanted):
                    continue
            boss = encounter.boss_fields(seed, row)
            value = reward_score(given, ranked) if ranked else score(boss["stats"])
            found = Found(seed, context, found_stars, boss, value, given)
            if ((shiny is not None and found.is_shiny != shiny)
                    or (tera_type is not None and boss["tera_type_original"] != tera_type)
                    or (nature is not None and boss["nature"] != nature)
                    or (gender is not None and boss["gender"] != gender)
                    or (ability is not None and boss["ability"] != ability)
                    or (size_mark is not None and boss["scale"] not in SIZE_MARKS[size_mark])
                    or (ivs is not None and not all(lo <= iv <= hi for iv, (lo, hi)
                                                     in zip(boss["ivs"], ivs)))):
                continue
            if stop_at_first:
                return [found]
            # Larger is better on the heap; the earlier seed wins a tie.
            entry = (-found.score if lowest_first else found.score, -seed, done, found)
            if one_per_species:
                kept = by_species.get(boss["species"])
                if kept is None or entry[:2] > kept[:2]:
                    by_species[boss["species"]] = entry
            elif len(best) < limit:
                heapq.heappush(best, entry)
            elif entry[:2] > best[0][:2]:
                heapq.heapreplace(best, entry)
    if progress:
        progress(total, total)
    return _ranked(best, by_species, one_per_species, limit)


def _ranked(best, by_species, one_per_species, limit):
    entries = by_species.values() if one_per_species else best
    return [e[3] for e in sorted(entries, reverse=True)[:limit]]
