from typing import List

from wizwalker.memory.memory_object import Primitive, PropertyClass, DynamicMemoryObject


class CombatEvent(PropertyClass):

    async def read_base_address(self) -> int:
        raise NotImplementedError()

    async def event_type(self) -> int:
        return await self.read_value_from_offset(72, Primitive.int32)

    async def write_event_type(self, event_type: int):
        await self.write_value_to_offset(72, event_type, Primitive.int32)

    async def source_subcircle(self) -> int:
        return await self.read_value_from_offset(76, Primitive.int32)

    async def write_source_subcircle(self, source_subcircle: int):
        await self.write_value_to_offset(76, source_subcircle, Primitive.int32)

    async def target_subcircle(self) -> int:
        return await self.read_value_from_offset(80, Primitive.int32)

    async def write_target_subcircle(self, target_subcircle: int):
        await self.write_value_to_offset(80, target_subcircle, Primitive.int32)

    async def effect_param(self) -> int:
        return await self.read_value_from_offset(84, Primitive.int32)

    async def write_effect_param(self, effect_param: int):
        await self.write_value_to_offset(84, effect_param, Primitive.int32)

    async def effect_type(self) -> int:
        return await self.read_value_from_offset(88, Primitive.int32)

    async def write_effect_type(self, effect_type: int):
        await self.write_value_to_offset(88, effect_type, Primitive.int32)

    async def effect_value(self) -> int:
        return await self.read_value_from_offset(96, Primitive.int32)

    async def write_effect_value(self, effect_value: int):
        await self.write_value_to_offset(96, effect_value, Primitive.int32)

    async def success_flag(self) -> bool:
        return await self.read_value_from_offset(100, Primitive.bool)

    async def write_success_flag(self, success_flag: bool):
        await self.write_value_to_offset(100, success_flag, Primitive.bool)

    async def damage_or_heal(self) -> int:
        return await self.read_value_from_offset(104, Primitive.int32)

    async def write_damage_or_heal(self, damage_or_heal: int):
        await self.write_value_to_offset(104, damage_or_heal, Primitive.int32)

    async def secondary_value(self) -> int:
        return await self.read_value_from_offset(108, Primitive.int32)

    async def write_secondary_value(self, secondary_value: int):
        await self.write_value_to_offset(108, secondary_value, Primitive.int32)

    async def critical_flag(self) -> bool:
        return await self.read_value_from_offset(116, Primitive.bool)

    async def write_critical_flag(self, critical_flag: bool):
        await self.write_value_to_offset(116, critical_flag, Primitive.bool)

    async def school(self) -> int:
        return await self.read_value_from_offset(120, Primitive.int32)

    async def write_school(self, school: int):
        await self.write_value_to_offset(120, school, Primitive.int32)

    async def caster_name(self) -> str:
        return await self.read_string_from_offset(128)

    async def write_caster_name(self, caster_name: str):
        await self.write_string_to_offset(128, caster_name)

    async def target_name(self) -> str:
        return await self.read_string_from_offset(160)

    async def write_target_name(self, target_name: str):
        await self.write_string_to_offset(160, target_name)

    async def pip_info_1(self) -> int:
        return await self.read_value_from_offset(192, Primitive.int32)

    async def write_pip_info_1(self, pip_info_1: int):
        await self.write_value_to_offset(192, pip_info_1, Primitive.int32)

    async def pip_flag_1(self) -> bool:
        return await self.read_value_from_offset(196, Primitive.bool)

    async def write_pip_flag_1(self, pip_flag_1: bool):
        await self.write_value_to_offset(196, pip_flag_1, Primitive.bool)

    async def pip_info_2(self) -> int:
        return await self.read_value_from_offset(200, Primitive.int32)

    async def write_pip_info_2(self, pip_info_2: int):
        await self.write_value_to_offset(200, pip_info_2, Primitive.int32)

    async def pip_flag_2(self) -> bool:
        return await self.read_value_from_offset(204, Primitive.bool)

    async def write_pip_flag_2(self, pip_flag_2: bool):
        await self.write_value_to_offset(204, pip_flag_2, Primitive.bool)


class DynamicCombatEvent(DynamicMemoryObject, CombatEvent):
    pass
