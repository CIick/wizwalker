from typing import List, Optional

from wizwalker.memory.memory_object import Primitive, PropertyClass, DynamicMemoryObject
from .combat_event import DynamicCombatEvent
from .spell_effect import DynamicSpellEffect


class CombatResolver(PropertyClass):
    async def read_base_address(self) -> int:
        raise NotImplementedError()

    async def event_handler_ptr(self) -> int:
        """
        Pointer to the event handler dispatched via vtable+0xA8.

        Notes:
            Offset 0x48 (72) — see EmitCombatEvent RE docs.
        """
        return await self.read_value_from_offset(72, Primitive.int64)

    async def event_list(self) -> List[DynamicCombatEvent]:
        """
        Read the combat event linked list (std::list<CombatEvent>).

        The event list sentinel is at resolver+0x50 (offset 80) and
        the count is at resolver+0x58 (offset 88). Events are cleared
        at the start of each round and the resolver is freed after
        combat ends — read while combat is active.

        Notes:
            Each list node is 0xF0 bytes: 0x10 (next/prev) + 0xE0 (event data).
            read_linked_list returns addresses pointing to node+0x10 (the event data).
        """
        events = []
        for addr in await self.read_linked_list(80):
            events.append(DynamicCombatEvent(self.hook_handler, addr))
        return events

    async def bool_global_effect(self) -> bool:
        return await self.read_value_from_offset(112, Primitive.bool)

    async def write_bool_global_effect(self, bool_global_effect: bool):
        await self.write_value_to_offset(112, bool_global_effect, Primitive.bool)

    async def global_effect(self) -> Optional[DynamicSpellEffect]:
        addr = await self.read_value_from_offset(120, Primitive.int64)

        if addr == 0:
            return None

        return DynamicSpellEffect(self.hook_handler, addr)

    async def battlefield_effects(self) -> List[DynamicSpellEffect]:
        effects = []
        for addr in await self.read_shared_vector(136):
            effects.append(DynamicSpellEffect(self.hook_handler, addr))

        return effects


class DynamicCombatResolver(DynamicMemoryObject, CombatResolver):
    pass
