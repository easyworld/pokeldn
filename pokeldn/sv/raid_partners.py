"""The NPC trainers a Tera Raid seats in the slots no player holds (docs/sv_raid.md, Partners): their
table, the trainers a partner seed draws from the pool the host's unlock stage picks, and a seed that
draws the trainers asked for."""

import os
from dataclasses import dataclass

from pokeldn.sv import raid_encounter

# The RaidPoint's u32 at 0x3e0 is the host's raid unlock stage, the game's progress less one: 0 Tera
# Raids unlocked (one and two stars) to 4 six stars, the highest difficulty flag set [0xe2826c]. 5 drew broken partners on a retail Scarlet and
# crashed its battle later.
STAGES = raid_encounter.PROGRESS[1:]
SIX_STARS = len(STAGES) - 1
# The partners a pokeldn raid seats with one console: our player and the console hold the other two
# of the four slots. Each further console takes one (`slots`).
HOSTED = 2

TRAINERS = ("Austin", "Ava", "Logan", "Hailey", "Evan", "Charlotte", "Kylie", "Hunter", "Gianna",
            "Eli", "Henry", "Chase", "Claire", "Brooklyn", "Zoe", "Samantha", "Dylan", "Luke")


@dataclass(frozen=True)
class Partner:
    trainer: str
    species: int        # National Dex number
    name: str
    level: int          # Serebii's: a partner's beside a Lv 20, 50 or 100 host Pokemon (`level_for`)
    ability: str
    moves: tuple
    tera: str           # Henry's is drawn ("Random")
    rank: int = 0       # 1 the partners raiders favour, 2 the next tier, 0 the rest
    why: str = ""       # why raiders want this partner, in a few words; "" for most
    detail: str = ""    # `why` at more length


# (species, name, ability, moves, Tera type) per trainer in draw order, by the pool's level, as
# Serebii's Tera Raid Battle partners page lists them, but for the Tera types of Dylan's Haxorus and
# Luke's Clodsire, which it leaves out: Dragon and Ground, as a retail console showed them.
# Dylan and Luke are not in the level-16 pool.
POOLS = {
    16: (
        (58, "Growlithe", "Intimidate", ("Ember", "Leer", "Bite"), "Fire"),
        (418, "Buizel", "Swift Swim", ("Aqua Jet", "Bite", "Water Gun"), "Water"),
        (672, "Skiddo", "Sap Sipper", ("Tackle", "Vine Whip", "Growth"), "Grass"),
        (81, "Magnemite", "Magnet Pull", ("Thunder Shock", "Thunder Wave", "Swift"), "Electric"),
        (819, "Skwovet", "Cheek Pouch", ("Tackle", "Defense Curl", "Rollout"), "Normal"),
        (397, "Staravia", "Intimidate", ("Wing Attack", "Quick Attack", "Growl"), "Flying"),
        (739, "Crabrawler", "Hyper Cutter", ("Rock Smash", "Bubble Beam", "Work Up"), "Grass"),
        (425, "Drifloon", "Aftermath", ("Gust", "Hex", "Payback"), "Ghost"),
        (434, "Stunky", "Stench", ("Bite", "Acid Spray", "Screech"), "Dark"),
        (281, "Kirlia", "Synchronize", ("Confusion", "Calm Mind", "Disarming Voice"), "Psychic"),
        (624, "Pawniard", "Defiant", ("Metal Claw", "Scratch", "Scary Face"), "Random"),
        (702, "Dedenne", "Cheek Pouch", ("Draining Kiss", "Parabolic Charge", "Charm"), "Fairy"),
        (402, "Kricketune", "Swarm", ("Bug Bite", "Sing", "Aerial Ace"), "Fairy"),
        (744, "Rockruff", "Keen Eye", ("Rock Throw", "Bite", "Leer"), "Rock"),
        (551, "Sandile", "Intimidate", ("Sand Tomb", "Scary Face", "Bite"), "Ground"),
        (361, "Snorunt", "Inner Focus", ("Powder Snow", "Ice Shard", "Bite"), "Ice"),
    ),
    40: (
        (323, "Camerupt", "Magma Armor", ("Flame Wheel", "Bulldoze", "Yawn"), "Fire"),
        (419, "Floatzel", "Swift Swim", ("Water Pulse", "Aqua Jet", "Growl"), "Water"),
        (673, "Gogoat", "Sap Sipper", ("Horn Leech", "Facade", "Growth"), "Grass"),
        (82, "Magneton", "Magnet Pull", ("Metal Sound", "Shock Wave", "Tri Attack"), "Electric"),
        (820, "Greedent", "Cheek Pouch", ("Facade", "Bite", "Tail Whip"), "Normal"),
        (334, "Altaria", "Natural Cure", ("Aerial Ace", "Dragon Breath", "Feather Dance"), "Flying"),
        (57, "Primeape", "Vital Spirit", ("Low Kick", "Rage Fist", "Leer"), "Grass"),
        (426, "Drifblim", "Aftermath", ("Hex", "Air Slash", "Will-O-Wisp"), "Ghost"),
        (215, "Sneasel", "Inner Focus", ("Thief", "Ice Shard", "Leer"), "Ice"),
        (97, "Hypno", "Insomnia", ("Zen Headbutt", "Fire Punch", "Thunder Punch"), "Psychic"),
        (437, "Bronzong", "Levitate", ("Gyro Ball", "Psybeam", "Metal Sound"), "Random"),
        (700, "Sylveon", "Cute Charm", ("Fairy Wind", "Quick Attack", "Charm"), "Fairy"),
        (123, "Scyther", "Swarm", ("Fury Cutter", "Aerial Ace", "Leer"), "Fairy"),
        (745, "Lycanroc", "Keen Eye", ("Rock Tomb", "Accelerock", "Leer"), "Rock"),
        (844, "Sandaconda", "Sand Spit", ("Bulldoze", "Sand Attack", "Poison Tail"), "Ground"),
        (362, "Glalie", "Inner Focus", ("Ice Fang", "Bite", "Scary Face"), "Ice"),
        (148, "Dragonair", "Shed Skin", ("Dragon Breath", "Safeguard", "Slam"), "Dragon"),
        (454, "Toxicroak", "Anticipation", ("Venoshock", "Low Kick", "Poison Sting"), "Poison"),
    ),
    80: (
        (59, "Arcanine", "Intimidate", ("Flamethrower", "Bite", "Leer"), "Fire"),
        (748, "Toxapex", "Merciless", ("Surf", "Poison Jab", "Chilling Water"), "Water"),
        (930, "Arboliva", "Seed Sower", ("Energy Ball", "Safeguard", "Earth Power"), "Grass"),
        (939, "Bellibolt", "Electromorphosis", ("Discharge", "Mud Shot", "Light Screen"), "Electric"),
        (982, "Dudunsparce", "Serene Grace", ("Hyper Drill", "Glare", "Drill Run"), "Normal"),
        (398, "Staraptor", "Intimidate", ("Brave Bird", "Facade", "Feather Dance"), "Flying"),
        (128, "Tauros", "Intimidate", ("Raging Bull", "Work Up", "Assurance"), "Grass"),
        (426, "Drifblim", "Aftermath", ("Shadow Ball", "Air Slash", "Will-O-Wisp"), "Ghost"),
        (197, "Umbreon", "Synchronize", ("Dark Pulse", "Thunder Wave", "Psychic"), "Dark"),
        (282, "Gardevoir", "Synchronize", ("Psyshock", "Dazzling Gleam", "Life Dew"), "Psychic"),
        (823, "Corviknight", "Pressure", ("Iron Head", "Drill Peck", "Scary Face"), "Random"),
        (700, "Sylveon", "Pixilate", ("Moonblast", "Quick Attack", "Charm"), "Fairy"),
        (214, "Heracross", "Swarm", ("Megahorn", "Brick Break", "Bulk Up"), "Bug"),
        (934, "Garganacl", "Purifying Salt", ("Rock Slide", "Rock Tomb", "Heavy Slam"), "Rock"),
        (750, "Mudsdale", "Own Tempo", ("High Horsepower", "Rock Smash", "Low Kick"), "Ground"),
        (461, "Weavile", "Pressure", ("Night Slash", "Ice Punch", "Leer"), "Ice"),
        (612, "Haxorus", "Rivalry", ("Dragon Claw", "Facade", "Scary Face"), "Dragon"),
        (980, "Clodsire", "Poison Point", ("Poison Jab", "Stomping Tantrum", "Toxic"), "Ground"),
    ),
}
# The level Serebii gives each stage's pool, which names the pool here. A partner is built at four
# fifths of the host Pokemon's level whatever the pool (`level_for`), so these are a Lv 20, 50 or 100
# host's partners.
LEVELS = (16, 16, 40, 80, 80)

# The partners raiders want, by the pool's level: their rank (1 favoured, 2 the next tier), why, and
# why at more length (docs/sv_raid.md, Favoured partners).
RECOMMENDED = {
    80: {"Austin": (2, "Intimidate on each respawn cuts Attack",
                    "Intimidate cuts the boss's Attack on every respawn; Leer lowers its Defense"),
         "Logan": (1, "Safeguard blocks status; terrain heals",
                   "Safeguard prevents status conditions; Grassy Terrain heals each turn but powers Grass "
                   "moves"),
         "Hailey": (1, "Light Screen cuts special damage; can paralyze",
                    "Light Screen, when she uses it, cuts the boss's special damage; Discharge can paralyze"),
         "Evan": (2, "100% accurate Glare paralysis buys turns",
                  "Glare paralyzes at 100% accuracy, except a boss with an Electric Tera type"),
         "Charlotte": (1, "Intimidate and Feather Dance cut Attack",
                       "Intimidate on every respawn and Feather Dance both cut the boss's physical Attack"),
         "Kylie": (2, "Intimidate cuts Attack; breaks screens",
                   "Intimidate cuts the boss's Attack on every respawn; Raging Bull breaks its screens"),
         "Hunter": (2, "Will-O-Wisp burn halves physical damage",
                    "Will-O-Wisp burns the boss, halving the damage its physical moves deal"),
         "Gianna": (2, "Thunder Wave paralysis buys free turns",
                    "Thunder Wave paralysis can give a free turn to set up, down to chance"),
         "Eli": (1, "Life Dew heals the whole team",
                 "Life Dew heals the whole team; seven-star solo guides ask for it, often with Bellibolt"),
         "Samantha": (2, "Leer cuts Defense; Ice Punch can freeze",
                      "Leer lowers the boss's Defense before its shield goes up; Ice Punch can freeze")},
}


def stage_of(progress, content="standard"):
    """-> the stage a host of this raid has unlocked: its progress's, or six stars for a black crystal
    or a seven-star event raid, which only a host with six stars unlocked finds."""
    if content in ("black", "might"):
        return SIX_STARS
    return max(0, raid_encounter.PROGRESS.index(progress) - 1)


def level_for(host_level):
    """-> the level partners take beside a host Pokemon of `host_level`: int(0.8 x it), whatever the
    stage (docs/sv_raid.md, Partners)."""
    return host_level * 4 // 5


def slots(consoles=1):
    """-> the slots partners fill in a pokeldn raid `consoles` consoles join: two with one, none
    with three."""
    return max(0, HOSTED + 1 - consoles)


def pool(stage):
    """-> the partners a stage draws among, in draw order."""
    level = LEVELS[stage]
    favoured = RECOMMENDED.get(level, {})
    return tuple(Partner(TRAINERS[i], species, name, level, ability, moves, tera,
                         *favoured.get(TRAINERS[i], (0, "", "")))
                 for i, (species, name, ability, moves, tera) in enumerate(POOLS[level]))


def draw(seed, stage, count=HOSTED):
    """-> the indices of the trainers filling `count` empty slots, left to right: xoroshiro128+ from
    the u64 seed, each draw over the trainers still in the pool, the one drawn taken out."""
    rand = raid_encounter.Xoroshiro(seed)
    left = list(range(len(POOLS[LEVELS[stage]])))
    return [left.pop(rand.next_int(len(left))) for _ in range(count)]


def trainer(name):
    """-> a trainer's index, its name in any case."""
    for index, known in enumerate(TRAINERS):
        if known.lower() == str(name).strip().lower():
            return index
    raise ValueError(f"no raid partner is named {name!r}; the trainers are {', '.join(TRAINERS)}")


def seed_for(stage, wanted=(), entropy=os.urandom):
    """-> a random partner seed whose first draws are the trainers `wanted`, in order: none leaves
    every partner to the draw, one fixes the first."""
    wanted = tuple(wanted)
    size = len(POOLS[LEVELS[stage]])
    if len(wanted) > HOSTED:
        raise ValueError(f"a pokeldn raid seats {HOSTED} partners, not {len(wanted)}")
    if len(set(wanted)) < len(wanted):
        raise ValueError("a trainer fills one slot at most")
    for index in wanted:
        if index >= size:
            raise ValueError(f"{TRAINERS[index]} is not among the level-{LEVELS[stage]} partners")
    while True:
        seed = int.from_bytes(entropy(8), "little")
        if tuple(draw(seed, stage, len(wanted))) == wanted:
            return seed
