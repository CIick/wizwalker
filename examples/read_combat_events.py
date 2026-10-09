"""Capture a complete combat snapshot for replay by the combat simulator.

Produces a self-contained JSON file with:
  - Initial participant state (HP, school, full combat stats)
  - RNG seed for deterministic replay
  - Per-round spell selections and events
  - All spell template IDs resolved to names
  - Per-round HP tracking for verification

Usage:
  py read_combat_events.py <wad_path> <types_path>

Arguments:
  wad_path   - Path to Root.wad
  types_path - Path to types.json (generate with wiztype)

The script waits for combat, captures everything, and saves to
combat_snapshot.json when combat ends.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from wizwalker import ClientHandler
from wizwalker.memory.memory_objects.enums import DuelPhase

try:
    from katsuba import wad as katsuba_wad
    from katsuba.op import TypeList, SerializerOptions, Serializer, STATEFUL_FLAGS
except ImportError:
    print("ERROR: katsuba is required: pip install katsuba", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# School ID mapping (runtime hashes from GetSchoolHashFromName)
# ---------------------------------------------------------------------------
SCHOOL_NAMES = {
    0: "Any", 72777: "Ice", 78483: "Sun", 2330892: "Life", 2343174: "Fire",
    2448141: "Myth", 2504141: "Moon", 2625203: "Star", 78318724: "Death",
    83375795: "Storm", 663550619: "Gardening", 806477568: "CastleMagic",
    931528087: "WhirlyBurly", 1027491821: "Balance", 1429009101: "Shadow",
    1488274711: "Fishing", 1760873841: "Cantrips",
}

# ---------------------------------------------------------------------------
# CombatEvent event_type names — enum CombatResult::kResultType (r794561)
# Source: r794561_WizardDev.json hash 321241350
# ---------------------------------------------------------------------------
EVENT_NAMES = {
    0x00: "StartSpellCast",
    0x01: "StartSpellNoCast",
    0x02: "Focus",
    0x03: "Discard",
    0x04: "Flee",
    0x05: "HangingEffectAdded",
    0x06: "ProtectedHangingEffectAdded",
    0x07: "RemovingHangingEffect",
    0x08: "HangingEffectRemovedIncoming",
    0x09: "HangingEffectRemovedIncomingFast",
    0x0A: "HangingEffectRemovedIncomingDetonated",
    0x0B: "HangingEffectRemovedOutgoing",
    0x0C: "HangingEffectRemovedOutgoingFast",
    0x0D: "HangingEffectProcessed",
    0x0E: "HangingEffectRoundsModified",
    0x0F: "Bounce",
    0x10: "TakeDamage",
    0x11: "HealDamage",
    0x12: "TakeDamageOverTime",
    0x13: "HealDamageOverTime",
    0x14: "StealTake",
    0x15: "StealGive",
    0x16: "AbsorbDamage",
    0x17: "Miss",
    0x18: "Hit",
    0x19: "CriticalBlocked",
    0x1A: "CriticalHit",
    0x1B: "GlobalEffectProcessed",
    0x1C: "GlobalEffectAdded",
    0x1D: "GlobalEffectRemoved",
    0x1E: "PlayerDied",
    0x1F: "CreatureSummoned",
    0x20: "TeleportPlayer",
    0x21: "PipsModified",
    0x22: "PowerPipsModified",
    0x23: "ShadowPipsModified",
    0x24: "Stunned",
    0x25: "Unstunned",
    0x26: "Polymorphed",
    0x27: "UnPolymorphed",
    0x28: "Reshuffle",
    0x29: "SpellDone",
    0x2A: "ModifyHate",
    0x2B: "MindControlled",
    0x2C: "UnMindControlled",
    0x2D: "MindControlImmune",
    0x2E: "AddAura",
    0x2F: "RemoveAura",
    0x30: "BuffDebuff",
    0x31: "Resurrected",
    0x32: "DamageTypeChanged",
    0x33: "CloakedEffectAdded",
    0x34: "RevealCloakedEffect",
    0x35: "StunResist",
    0x36: "StunResistFailed",
    0x37: "StunImmune",
    0x38: "ArmorPierced",
    0x39: "AfterlifeEffectsProcessed",
    0x3A: "AfterlifeEffectsAdded",
    0x3B: "AfterlifeEffectsRemoved",
    0x3C: "EffectFailed",
    0x3D: "StartAOE",
    0x3E: "StopAOE",
    0x3F: "StartAOEAct",
    0x40: "StopAOEAct",
    0x41: "CombatTriggerListAdded",
    0x42: "CombatTriggerListRemoved",
    0x43: "AddShadowSpellEffect",
    0x44: "RemoveShadowSpellEffect",
    0x45: "ShadowSelfEffect",
    0x46: "UnShadowSelfEffect",
    0x47: "ChangeShadowSelfEffect",
    0x48: "AddBacklashResult",
    0x49: "RemoveBacklashResult",
    0x4A: "ModifyBacklash",
    0x4B: "AddIntercept",
    0x4C: "RemoveIntercept",
    0x4D: "TakeInterceptDamage",
    0x4E: "InterceptedDamage",
    0x4F: "InterceptedDamageThisRound",
    0x51: "IncreaseShadowCreatureLevel",
    0x52: "DecreaseShadowCreatureLevel",
    0x53: "SetShadowCreatureLevel",
    0x54: "RemoveShadowCreature",
    0x55: "ShadowCreatureAttack",
    0x56: "PostActionProcess",
    0x58: "CreatureSpawned",
    0x59: "CombatTriggerActivation",     # not in enum; confirmed via CE live analysis
    0x5A: "HangingEffectRemovedProtection",
    0x60: "pipConversionRefund",
    0x61: "planningPhasePipSync",
    0x62: "FirstPlayerSwitched",
    0x63: "Confused",
    0x64: "Unconfused",
    0x66: "Clued",
    0x67: "ClueImmune",
    0x6E: "AbsorbHeal",
    0x70: "PetCasted",
    0x71: "CastSigilSpell",
    0x72: "AddSpellToDeck",
    0x73: "SetTopTeam",
    0x74: "SetBottomTeam",
    0x75: "ClearTopTeam",
    0x76: "ClearBottomTeam",
    0x77: "StartBackRowCast",
    0x78: "StopBackRowCast",
    0x79: "SchoolPipsModified",
    0x7D: "ShadowCreatureEnd",
    0x7E: "None",
}


# ---------------------------------------------------------------------------
# WAD spell manifest loader
# ---------------------------------------------------------------------------
def load_spell_manifest(wad_path: Path, types_path: Path) -> tuple[dict[int, dict], "katsuba_wad.Archive"]:
    """Load template_id -> {name, path} from TemplateManifest.xml.

    Returns (lookup, archive) so the archive can be reused for lang files.
    """
    archive = katsuba_wad.Archive.mmap(str(wad_path))
    types = TypeList.open(str(types_path))
    opts = SerializerOptions()
    opts.flags = STATEFUL_FLAGS
    opts.shallow = False
    opts.skip_unknown_types = True
    ser = Serializer(opts, types)

    data = archive["TemplateManifest.xml"]
    if data.startswith(b"BINd"):
        data = data[4:]
    manifest = ser.deserialize(data)

    lookup = {}
    for entry in manifest.get("m_serializedTemplates"):
        tid = int(entry.get("m_id"))
        fname = entry.get("m_filename")
        if isinstance(fname, bytes):
            fname = fname.decode("utf-8", errors="replace")
        if not fname.startswith("Spells/"):
            continue
        name = fname.rsplit("/", 1)[-1]
        if name.endswith(".xml"):
            name = name[:-4]
        lookup[tid] = {"name": name, "path": fname}

    return lookup, archive


def load_lang_file(name: str) -> dict[str, str]:
    """Load a single Locale/en-US/<name>.lang file from the WAD archive.

    Lang file format (UTF-16, \\r\\n separated):
      Line 0: header "HEADER:<name>"
      Then groups of 3 lines: key, blank, value

    Cached per-name. Missing or undecodable files cache as {} so a single
    failed lookup does not retry every event.
    """
    if name in LANG_CACHE:
        return LANG_CACHE[name]
    if LANG_ARCHIVE is None:
        return {}

    path = f"Locale/en-US/{name}.lang"
    try:
        data = LANG_ARCHIVE[path]
    except (KeyError, Exception) as e:
        print(f"  [WARN] Could not load {path}: {e}")
        LANG_CACHE[name] = {}
        return LANG_CACHE[name]

    try:
        decoded = data.decode("utf-16")
    except UnicodeDecodeError:
        print(f"  [WARN] {path} decode error")
        LANG_CACHE[name] = {}
        return LANG_CACHE[name]

    file_lines = decoded.split("\r\n")
    _header, *lines = file_lines

    # keys at index 0, 3, 6, ... and values at index 2, 5, 8, ...
    LANG_CACHE[name] = dict(zip(lines[::3], lines[2::3]))
    return LANG_CACHE[name]


# Global lookups populated at startup
SPELL_MANIFEST: dict[int, dict] = {}
LANG_ARCHIVE = None
LANG_CACHE: dict[str, dict[str, str]] = {}


def spell_name(template_id: int) -> str:
    """Resolve a spell template ID to its name."""
    info = SPELL_MANIFEST.get(template_id)
    return info["name"] if info else str(template_id)


def school_name(school_id: int) -> str:
    return SCHOOL_NAMES.get(school_id, str(school_id))


# ---------------------------------------------------------------------------
# Participant stat capture
# ---------------------------------------------------------------------------
async def capture_participant(p) -> dict:
    """Capture all combat-relevant data from a CombatParticipant."""
    info = {
        "subcircle": await p.subcircle(),
        "is_player": await p.is_player(),
        "team": await p.team_id(),
        "school_id": await p.primary_magic_school_id(),
        "hp": await p.player_health(),
        "max_hp": await p.max_player_health(),
    }
    info["school_name"] = school_name(info["school_id"])

    # Entity display name
    info["name"] = f"s{info['subcircle']}"
    try:
        entity = await p.fetch_entity()
        if entity:
            dname = await entity.display_name()
            if not dname:
                dname = await entity.object_name()
            if dname:
                info["name"] = dname
    except Exception:
        pass

    # CombatParticipant runtime stats (used directly by CombatResolver)
    try:
        info["accuracy_bonus"] = await p.accuracy_bonus()
        info["stat_damage"] = await p.stat_damage()
        info["stat_resist"] = await p.stat_resist()
        info["stat_pierce"] = await p.stat_pierce()
        info["base_spell_damage"] = await p.base_spell_damage()
        info["mob_level"] = await p.mob_level()
    except Exception:
        pass

    # Full GameStats (players have this; mobs may not)
    try:
        gs = await p.game_stats()
        if gs:
            info["game_stats"] = {
                "reference_level": await gs.reference_level(),
                "school_id": await gs.school_id(),
                # Damage
                "dmg_bonus_percent_all": await gs.dmg_bonus_percent_all(),
                "dmg_bonus_flat_all": await gs.dmg_bonus_flat_all(),
                "dmg_bonus_percent": await gs.dmg_bonus_percent(),
                "dmg_bonus_flat": await gs.dmg_bonus_flat(),
                # Resist
                "dmg_reduce_percent_all": await gs.dmg_reduce_percent_all(),
                "dmg_reduce_flat_all": await gs.dmg_reduce_flat_all(),
                "dmg_reduce_percent": await gs.dmg_reduce_percent(),
                "dmg_reduce_flat": await gs.dmg_reduce_flat(),
                # Pierce
                "ap_bonus_percent_all": await gs.ap_bonus_percent_all(),
                "ap_bonus_percent": await gs.ap_bonus_percent(),
                # Accuracy
                "acc_bonus_percent_all": await gs.acc_bonus_percent_all(),
                "acc_bonus_percent": await gs.acc_bonus_percent(),
                # Critical / Block
                "critical_hit_rating_all": await gs.critical_hit_rating_all(),
                "block_rating_all": await gs.block_rating_all(),
                "critical_hit_percent_all": await gs.critical_hit_percent_all(),
                "block_percent_all": await gs.block_percent_all(),
                "critical_hit_rating_by_school": await gs.critical_hit_rating_by_school(),
                "block_rating_by_school": await gs.block_rating_by_school(),
                # Healing
                "heal_bonus_percent_all": await gs.heal_bonus_percent_all(),
                "heal_inc_bonus_percent_all": await gs.heal_inc_bonus_percent_all(),
                # Pips
                "power_pip_base": await gs.power_pip_base(),
                "power_pip_bonus_percent_all": await gs.power_pip_bonus_percent_all(),
                "pip_conversion_rating_all": await gs.pip_conversion_rating_all(),
                "pip_conversion_percent_all": await gs.pip_conversion_percent_all(),
                # Shadow
                "shadow_pip_max": await gs.shadow_pip_max(),
                "shadow_pip_rating": await gs.shadow_pip_rating(),
                "shadow_pip_bonus_percent": await gs.shadow_pip_bonus_percent(),
                # Other
                "stun_resistance_percent": await gs.stun_resistance_percent(),
            }
    except Exception:
        pass

    return info


# ---------------------------------------------------------------------------
# Event reading + action extraction
# ---------------------------------------------------------------------------
async def read_raw_events(duel) -> list[dict]:
    """Read all events from the resolver and return as plain dicts."""
    resolver = await duel.combat_resolver()
    if resolver is None:
        return []

    events = await resolver.event_list()
    result = []
    for evt in events:
        try:
            result.append({
                "event_type": await evt.event_type(),
                "source_subcircle": await evt.source_subcircle(),
                "target_subcircle": await evt.target_subcircle(),
                "effect_param": await evt.effect_param(),
                "effect_type": await evt.effect_type(),
                "effect_value": await evt.effect_value(),
                "success_flag": await evt.success_flag(),
                "damage_or_heal": await evt.damage_or_heal(),
                "secondary_value": await evt.secondary_value(),
                "critical_flag": await evt.critical_flag(),
                "school": await evt.school(),
                "caster_name": await evt.caster_name(),
                "target_name": await evt.target_name(),
                "pip_info_1": await evt.pip_info_1(),
                "pip_flag_1": await evt.pip_flag_1(),
                "pip_info_2": await evt.pip_info_2(),
                "pip_flag_2": await evt.pip_flag_2(),
            })
        except Exception as e:
            print(f"  [WARN] Error reading event: {e}")
    return result


def resolve_combat_message(key: str) -> str | None:
    """Resolve a locale key like "CombatMessages_00003473a" or
    "WizardBossFights_00000140" to display text.

    Splits on the first underscore: <LangFile>_<Code>. The lang file is
    loaded lazily from the WAD archive on first lookup and cached.
    """
    if not key or "_" not in key:
        return None
    name, code = key.split("_", 1)
    return load_lang_file(name).get(code)


def enrich_events(raw_events: list[dict], participants: dict) -> list[dict]:
    """Add resolved names to raw events."""
    enriched = []
    for e in raw_events:
        evt = dict(e)
        evt["event_name"] = EVENT_NAMES.get(e["event_type"], f"0x{e['event_type']:02X}")
        evt["spell_id"] = e["effect_type"]
        evt["spell_name"] = spell_name(e["effect_type"])
        evt["source_name"] = participants.get(e["source_subcircle"], {}).get("name", f"s{e['source_subcircle']}")
        evt["target_name_resolved"] = participants.get(e["target_subcircle"], {}).get("name", f"s{e['target_subcircle']}")

        # Auto-resolve school IDs in damage_or_heal field
        if e["damage_or_heal"] in SCHOOL_NAMES and e["damage_or_heal"] != 0:
            evt["damage_or_heal_school"] = school_name(e["damage_or_heal"])

        # CombatTriggerActivation (0x59): caster_name = locale key,
        # target_name = sound file path
        if e["event_type"] == 0x59:
            locale_key = e.get("caster_name", "")
            sound_file = e.get("target_name", "")
            if locale_key:
                evt["locale_key"] = locale_key
                text = resolve_combat_message(locale_key)
                if text:
                    evt["combat_message"] = text
            if sound_file:
                evt["sound_file"] = sound_file

        enriched.append(evt)
    return enriched


def extract_actions(events: list[dict],
                    enchantments: dict | None = None) -> list[dict]:
    """Extract per-participant spell selections from CastStart events.

    Each turn starts with StartSpellCast (0x00). If followed immediately by
    Miss (0x17), the participant fizzled or passed.

    Distinguishing fizzle vs intentional pass:
    - Fizzle: 0x17 event has a spell template ID in effect_type and
      effect_value matches the caster's pip cost (val > 0)
    - Pass: 0x17 event has no meaningful spell data (effect_type=0
      or the spell doesn't match StartSpellCast)

    Args:
        enchantments: {subcircle: {spell_template_id: enchant_template_id}}
    """
    if enchantments is None:
        enchantments = {}
    actions = []
    seen_casters = set()
    for i, evt in enumerate(events):
        if evt["event_type"] != 0x00:
            continue
        caster = evt["source_subcircle"]
        if caster in seen_casters:
            continue  # already recorded this caster's action
        seen_casters.add(caster)

        # Check if next event is Fizzle/Pass (0x17)
        fizzle_or_pass = False
        if i + 1 < len(events) and events[i + 1]["event_type"] == 0x17:
            fizzle_or_pass = True

        if fizzle_or_pass:
            # Distinguish fizzle from pass: if CastStart has a real spell
            # and the 0x17 event carries the same spell ID, it's a fizzle
            cast_spell = evt["effect_type"]
            fizzle_evt = events[i + 1]
            is_fizzle = (cast_spell != 0 and
                         fizzle_evt["effect_type"] == cast_spell)

            action = {
                "caster": caster,
                "caster_name": evt.get("source_name", f"s{caster}"),
                "action": "fizzle" if is_fizzle else "pass",
                "spell_id": cast_spell if is_fizzle else None,
                "spell_name": spell_name(cast_spell) if is_fizzle else None,
                "target": evt["target_subcircle"] if is_fizzle else None,
            }
            # Add enchantment info if the fizzled spell was enchanted
            if is_fizzle:
                ench_id = enchantments.get(caster, {}).get(cast_spell, 0)
                action["enchanted"] = ench_id != 0
                if ench_id:
                    action["enchant_id"] = ench_id
                    action["enchant_name"] = spell_name(ench_id)
            actions.append(action)
        else:
            sid = evt["effect_type"]
            # Find the actual target from SpellBegin (0x3D) for this caster
            target = evt["target_subcircle"]
            for subsequent in events[i:]:
                if subsequent["event_type"] == 0x3D and subsequent["source_subcircle"] == caster:
                    target = subsequent["target_subcircle"]
                    break

            ench_id = enchantments.get(caster, {}).get(sid, 0)
            action = {
                "caster": caster,
                "caster_name": evt.get("source_name", f"s{caster}"),
                "action": "cast",
                "spell_id": sid,
                "spell_name": spell_name(sid),
                "target": target,
                "enchanted": ench_id != 0,
            }
            if ench_id:
                action["enchant_id"] = ench_id
                action["enchant_name"] = spell_name(ench_id)
            actions.append(action)

    return actions


# ---------------------------------------------------------------------------
# HP snapshot
# ---------------------------------------------------------------------------
async def snapshot_hp(duel) -> dict:
    """Read current HP for all participants."""
    hp = {}
    try:
        for p in await duel.participant_list():
            sc = await p.subcircle()
            hp[sc] = await p.player_health()
    except Exception:
        pass
    return hp


# ---------------------------------------------------------------------------
# Enchantment snapshot
# ---------------------------------------------------------------------------
async def snapshot_enchantments(duel) -> dict:
    """Read enchantment data for each participant's spells in hand.

    Returns {subcircle: {spell_template_id: enchant_template_id}}.
    Only includes spells that have a non-zero enchantment.
    """
    result = {}
    try:
        for p in await duel.participant_list():
            sc = await p.subcircle()
            hand = await p.hand()
            if hand is None:
                hand = await p.saved_hand()
            if hand is None:
                continue
            enchants = {}
            for spell in await hand.spell_list():
                try:
                    tid = await spell.template_id()
                    ench = await spell.enchantment()
                    if ench != 0:
                        enchants[tid] = ench
                except Exception:
                    continue
            if enchants:
                result[sc] = enchants
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Human-readable event formatting (for console output)
# ---------------------------------------------------------------------------
def format_event(evt: dict) -> str:
    """Compact one-line format for console output."""
    ename = evt.get("event_name", f"0x{evt['event_type']:02X}")
    src = evt.get("source_name", f"s{evt['source_subcircle']}")
    tgt = evt.get("target_name_resolved", f"s{evt['target_subcircle']}")

    parts = [f"[{ename}]", f"{src} -> {tgt}"]

    fields = []
    sname = evt.get("spell_name", "")
    if sname and sname != str(evt.get("spell_id", "")):
        fields.append(f"spell={sname}")

    param = evt["effect_param"]
    if param != 0:
        fields.append(f"param={param}")

    val = evt["effect_value"]
    if val != 0:
        fields.append(f"val={val}")

    dmg = evt["damage_or_heal"]
    if dmg != 0:
        dmg_label = evt.get("damage_or_heal_school", str(dmg))
        fields.append(f"dmgHeal={dmg_label}")

    sec = evt["secondary_value"]
    if sec != 0:
        fields.append(f"sec={sec}")

    if evt["success_flag"]:
        fields.append("ok")
    if evt["critical_flag"]:
        fields.append("CRIT")

    if fields:
        parts.append(" ".join(fields))

    return "    " + " | ".join(parts)


def format_action(act: dict) -> str:
    ench_suffix = ""
    if act.get("enchanted"):
        ench_suffix = f" [enchanted: {act.get('enchant_name', act.get('enchant_id', '?'))}]"

    if act["action"] == "pass":
        return f"  {act['caster_name']} (s{act['caster']}): Pass"
    if act["action"] == "fizzle":
        return (f"  {act['caster_name']} (s{act['caster']}): "
                f"FIZZLE ({act['spell_name']} -> s{act['target']}){ench_suffix}")
    return (f"  {act['caster_name']} (s{act['caster']}): "
            f"{act['spell_name']} -> s{act['target']}{ench_suffix}")


# ---------------------------------------------------------------------------
# Main capture loop
# ---------------------------------------------------------------------------
async def main(wad_path: Path, types_path: Path):
    global SPELL_MANIFEST, LANG_ARCHIVE

    # Load spell manifest
    print("Loading spell manifest from TemplateManifest...")
    SPELL_MANIFEST, archive = load_spell_manifest(wad_path, types_path)
    print(f"  {len(SPELL_MANIFEST)} spells loaded.")

    # Stash WAD archive for lazy locale lookups (any <LangFile>_<Code> key
    # resolves by loading Locale/en-US/<LangFile>.lang on first hit).
    LANG_ARCHIVE = archive
    print()

    handler = ClientHandler()
    client = handler.get_new_clients()[0]

    try:
        print("Activating hooks...")
        await client.activate_hooks()
        print("Connected.\n")

        duel = client.duel
        fight_num = 0

        while True:
            # ---- Wait for combat ----
            print("Waiting for combat...")
            while True:
                try:
                    phase = await duel.duel_phase()
                    if phase not in (DuelPhase.ended,):
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            fight_num += 1
            print(f"Combat #{fight_num} detected!\n")

            # ---- Capture initial state ----
            print("Capturing initial state...")
            participant_list = {}
            try:
                for p in await duel.participant_list():
                    info = await capture_participant(p)
                    participant_list[info["subcircle"]] = info
                    role = "Player" if info["is_player"] else "Mob"
                    has_gs = "game_stats" in info
                    print(f"  s{info['subcircle']}: {info['name']} ({role}, "
                          f"{info['school_name']}, {info['hp']}/{info['max_hp']} HP"
                          f"{', stats=YES' if has_gs else ''})")
            except Exception as e:
                print(f"  [WARN] Error reading participants: {e}")

            rng_seed = None
            try:
                rng_seed = await duel.rng_seed()
                print(f"  RNG seed: {rng_seed}")
            except Exception:
                print("  [WARN] Could not read RNG seed")

            print()

            # Build spell manifest subset (only spells used in this fight)
            spells_seen = set()

            # ---- Per-round capture loop ----
            rounds = []
            last_round = -1
            last_phase = None
            round_captured = False

            while True:
                try:
                    phase = await duel.duel_phase()
                except Exception:
                    print("\nCombat ended (duel freed).")
                    break

                if phase == DuelPhase.ended:
                    # One last HP snapshot
                    if rounds:
                        rounds[-1]["hp_after"] = await snapshot_hp(duel)
                    print("\nCombat ended.")
                    break

                if phase in (DuelPhase.execution, DuelPhase.resolution):
                    try:
                        current_round = await duel.round_num()
                    except Exception:
                        await asyncio.sleep(0.2)
                        continue

                    if current_round != last_round:
                        round_captured = False
                        last_round = current_round

                    if not round_captured:
                        # Let events accumulate
                        await asyncio.sleep(0.5)

                        raw = await read_raw_events(duel)
                        if raw:
                            round_captured = True

                            # Check for new participants we haven't seen yet
                            # (NPCs can join mid-combat)
                            known = set(participant_list.keys())
                            seen_in_events = set()
                            for e in raw:
                                seen_in_events.add(e["source_subcircle"])
                                seen_in_events.add(e["target_subcircle"])
                            new_scs = seen_in_events - known
                            if new_scs:
                                print(f"  New participants detected: {new_scs}, re-reading...")
                                try:
                                    for p in await duel.participant_list():
                                        sc = await p.subcircle()
                                        if sc not in participant_list:
                                            info = await capture_participant(p)
                                            info["joined_round"] = current_round
                                            participant_list[info["subcircle"]] = info
                                            role = "Player" if info["is_player"] else "Mob"
                                            print(f"    s{sc}: {info['name']} ({role}, "
                                                  f"{info['school_name']}, "
                                                  f"{info['hp']}/{info['max_hp']} HP, "
                                                  f"joined R{current_round})")
                                except Exception as e:
                                    print(f"    [WARN] Error re-reading participants: {e}")

                            # Read enchantment state from participant hands
                            round_enchantments = await snapshot_enchantments(duel)

                            # Enrich with names
                            enriched = enrich_events(raw, participant_list)
                            actions = extract_actions(enriched, round_enchantments)

                            # Track spells seen
                            for evt in enriched:
                                sid = evt.get("spell_id", 0)
                                if sid and sid in SPELL_MANIFEST:
                                    spells_seen.add(sid)

                            # Track enchant spell IDs in manifest
                            for ench_map in round_enchantments.values():
                                for ench_id in ench_map.values():
                                    if ench_id in SPELL_MANIFEST:
                                        spells_seen.add(ench_id)

                            # Capture RNG seed for this round
                            round_seed = None
                            try:
                                round_seed = await duel.rng_seed()
                            except Exception:
                                pass

                            # HP snapshot
                            hp = await snapshot_hp(duel)

                            round_data = {
                                "round_num": current_round,
                                "rng_seed": round_seed,
                                "actions": actions,
                                "enchantments": round_enchantments,
                                "events": enriched,
                                "hp_after": hp,
                            }
                            rounds.append(round_data)

                            # Console output
                            print(f"Round {current_round}: {len(enriched)} events, "
                                  f"{len(actions)} actions")
                            for act in actions:
                                print(format_action(act))
                            for evt in enriched:
                                print(format_event(evt))
                                if evt["event_type"] == 0x59:
                                    msg = evt.get("combat_message", "")
                                    if msg:
                                        print(f"      ^ \"{msg}\"")
                            if hp:
                                hp_str = ", ".join(
                                    f"{participant_list.get(sc, {}).get('name', f's{sc}')}={h}hp"
                                    for sc, h in sorted(hp.items())
                                )
                                print(f"  HP: {hp_str}")
                            print()

                # During planning phase, re-read participants (HP may have changed
                # from damage-over-time or healing)
                if phase == DuelPhase.planning and last_phase != DuelPhase.planning:
                    if rounds:
                        hp = await snapshot_hp(duel)
                        if hp:
                            rounds[-1]["hp_after"] = hp

                last_phase = phase
                await asyncio.sleep(0.2)

            # ---- Build output ----
            # Spell manifest subset (only spells that appeared in this fight)
            manifest_subset = {}
            for sid in sorted(spells_seen):
                manifest_subset[str(sid)] = SPELL_MANIFEST[sid]

            snapshot = {
                "version": 1,
                "capture_time": datetime.now().isoformat(),
                "initial_state": {
                    "rng_seed": rng_seed,
                    "participants": {
                        str(sc): info for sc, info in sorted(participant_list.items())
                    },
                    "note": "Participants may include NPCs that joined mid-combat.",
                },
                "spell_manifest": manifest_subset,
                "rounds": rounds,
                "summary": {
                    "total_rounds": len(rounds),
                    "total_events": sum(len(r["events"]) for r in rounds),
                    "spells_used": sorted(
                        set(a["spell_name"] for r in rounds for a in r["actions"]
                            if a["spell_name"])
                    ),
                    "participants": [
                        f"s{sc}: {info['name']} ({info['school_name']})"
                        for sc, info in sorted(participant_list.items())
                    ],
                },
            }

            output_path = f"combat_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_path, "w") as f:
                json.dump(snapshot, f, indent=2, default=str)

            print(f"\nSnapshot saved: {output_path}")
            print(f"  {snapshot['summary']['total_rounds']} rounds, "
                  f"{snapshot['summary']['total_events']} events")
            print(f"  Participants: {snapshot['summary']['participants']}")
            print(f"  Spells used: {snapshot['summary']['spells_used']}")
            print()

    finally:
        print("\nClosing...")
        await handler.close()
        print("Done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Capture a complete combat snapshot for sim replay.",
        epilog=(
            "Root.wad: C:/ProgramData/KingsIsle Entertainment/Wizard101/"
            "Data/GameData/Root.wad\n"
            "types.json: pip install wiztype && wiztype --version 2 --indent 4"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("wad_path", type=Path, help="Path to Root.wad")
    parser.add_argument("types_path", type=Path, help="Path to types.json")
    args = parser.parse_args()

    if not args.wad_path.exists():
        parser.error(f"WAD not found: {args.wad_path}")
    if not args.types_path.exists():
        parser.error(f"Types not found: {args.types_path}")

    return args


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(wad_path=args.wad_path, types_path=args.types_path))
