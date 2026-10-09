from typing import Dict

from wizwalker.memory.memory_object import Primitive, PropertyClass, DynamicMemoryObject


# Layout of a resolver event (class CombatResult, 0xE0 bytes; list node = 0x10 + 0xE0).
# Serialized properties come from the type dump (r806919, unchanged since r794561):
#   +0x48 m_resultType  +0x4C m_participantSubCircle  +0x50 m_effectType (kSpellEffects)
#   +0x54 m_effectAmount  +0x58 m_spellTemplateID  +0x5C m_spellBaseOverrideTemplateID
#   +0x60 m_targetSubCircle  +0xC0 m_durationModifier (float)  +0xC4 m_petCasted
#   +0xC8 m_petCastedTarget  +0xCC m_cloaked
# Non-serialized members (names are descriptive guesses, not from the dump):
#   +0x64 bool, +0x68 damage-school hash, +0x6C int, +0x74 bool, +0x78 school hash,
#   +0x80 std::string (caster / locale key), +0xA0 std::string (target / sound file)
#
# NOTE: before 2026-10 the accessors below were named by guess and several were
# wrong (target_subcircle read +0x50, effect_type read +0x58, ...). The old
# names/offsets are preserved only through ``legacy_v1_dict`` so capture format
# v1 stays reproducible.
class CombatEvent(PropertyClass):

    async def read_base_address(self) -> int:
        raise NotImplementedError()

    async def result_type(self) -> int:
        """CombatResult::kResultType"""
        return await self.read_value_from_offset(0x48, Primitive.int32)

    # kept: same offset/meaning as before
    async def event_type(self) -> int:
        return await self.result_type()

    async def participant_subcircle(self) -> int:
        return await self.read_value_from_offset(0x4C, Primitive.int32)

    async def source_subcircle(self) -> int:
        """Alias of participant_subcircle (offset unchanged)."""
        return await self.participant_subcircle()

    async def spell_effect_type(self) -> int:
        """SpellEffect::kSpellEffects of the effect that produced this result."""
        return await self.read_value_from_offset(0x50, Primitive.int32)

    async def effect_amount(self) -> int:
        return await self.read_value_from_offset(0x54, Primitive.int32)

    async def spell_template_id(self) -> int:
        return await self.read_value_from_offset(0x58, Primitive.uint32)

    async def spell_base_override_template_id(self) -> int:
        return await self.read_value_from_offset(0x5C, Primitive.uint32)

    async def target_subcircle(self) -> int:
        """m_targetSubCircle (+0x60). Previously this method read +0x50 (the effect type)."""
        return await self.read_value_from_offset(0x60, Primitive.int32)

    async def success_flag(self) -> bool:
        return await self.read_value_from_offset(0x64, Primitive.bool)

    async def damage_school(self) -> int:
        """Damage-school hash (+0x68, not serialized). Formerly ``damage_or_heal``."""
        return await self.read_value_from_offset(0x68, Primitive.int32)

    async def secondary_value(self) -> int:
        return await self.read_value_from_offset(0x6C, Primitive.int32)

    async def critical_flag(self) -> bool:
        return await self.read_value_from_offset(0x74, Primitive.bool)

    async def school(self) -> int:
        return await self.read_value_from_offset(0x78, Primitive.int32)

    async def caster_name(self) -> str:
        return await self.read_string_from_offset(0x80)

    async def target_name(self) -> str:
        return await self.read_string_from_offset(0xA0)

    async def duration_modifier(self) -> float:
        return await self.read_value_from_offset(0xC0, Primitive.float32)

    async def pet_casted(self) -> bool:
        return await self.read_value_from_offset(0xC4, Primitive.bool)

    async def pet_casted_target(self) -> int:
        return await self.read_value_from_offset(0xC8, Primitive.int32)

    async def cloaked(self) -> bool:
        return await self.read_value_from_offset(0xCC, Primitive.bool)

    async def to_dict(self) -> Dict:
        """Correctly named fields (capture format v2)."""
        return {
            "result_type": await self.result_type(),
            "participant_subcircle": await self.participant_subcircle(),
            "effect_type": await self.spell_effect_type(),
            "effect_amount": await self.effect_amount(),
            "spell_template_id": await self.spell_template_id(),
            "spell_base_override_template_id": await self.spell_base_override_template_id(),
            "target_subcircle": await self.target_subcircle(),
            "success_flag": await self.success_flag(),
            "damage_school": await self.damage_school(),
            "secondary_value": await self.secondary_value(),
            "critical_flag": await self.critical_flag(),
            "school": await self.school(),
            "caster_name": await self.caster_name(),
            "target_name": await self.target_name(),
            "duration_modifier": await self.duration_modifier(),
            "pet_casted": await self.pet_casted(),
            "pet_casted_target": await self.pet_casted_target(),
            "cloaked": await self.cloaked(),
        }

    async def legacy_v1_dict(self) -> Dict:
        """The historical (mislabelled) capture v1 keys, byte-for-byte as before."""
        return {
            "event_type": await self.read_value_from_offset(0x48, Primitive.int32),
            "source_subcircle": await self.read_value_from_offset(0x4C, Primitive.int32),
            "target_subcircle": await self.read_value_from_offset(0x50, Primitive.int32),
            "effect_param": await self.read_value_from_offset(0x54, Primitive.int32),
            "effect_type": await self.read_value_from_offset(0x58, Primitive.int32),
            "effect_value": await self.read_value_from_offset(0x60, Primitive.int32),
            "success_flag": await self.read_value_from_offset(0x64, Primitive.bool),
            "damage_or_heal": await self.read_value_from_offset(0x68, Primitive.int32),
            "secondary_value": await self.read_value_from_offset(0x6C, Primitive.int32),
            "critical_flag": await self.read_value_from_offset(0x74, Primitive.bool),
            "school": await self.read_value_from_offset(0x78, Primitive.int32),
            "caster_name": await self.read_string_from_offset(0x80),
            "target_name": await self.read_string_from_offset(0xA0),
            "pip_info_1": await self.read_value_from_offset(0xC0, Primitive.int32),
            "pip_flag_1": await self.read_value_from_offset(0xC4, Primitive.bool),
            "pip_info_2": await self.read_value_from_offset(0xC8, Primitive.int32),
            "pip_flag_2": await self.read_value_from_offset(0xCC, Primitive.bool),
        }


class DynamicCombatEvent(DynamicMemoryObject, CombatEvent):
    pass
