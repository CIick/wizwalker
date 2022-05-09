from wizwalker.memory.memory_object import PropertyClass


class PlayDeck(PropertyClass):
    async def deck_to_save(self) -> list["PlaySpellData"]:
        spell_data = []
        for addr in await self.read_shared_vector(72):
            spell_data.append(PlaySpellData(self.memory_reader, addr))

        return spell_data

    async def graveyard_to_save(self) -> list["PlaySpellData"]:
        spell_data = []
        for addr in await self.read_shared_vector(96):
            spell_data.append(PlaySpellData(self.memory_reader, addr))

        return spell_data


class PlaySpellData(PropertyClass):
    async def template_id(self) -> int:
        return await self.read_value_from_offset(72, "unsigned int")

    async def enchantment(self) -> int:
        return await self.read_value_from_offset(76, "unsigned int")
