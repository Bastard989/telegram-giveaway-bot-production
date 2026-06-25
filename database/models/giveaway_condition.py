from tortoise import Model, fields


class GiveawayCondition(Model):
    id = fields.IntField(pk=True)
    giveaway_callback_value = fields.TextField()
    target_channel_id = fields.BigIntField()
    target_channel_name = fields.TextField(null=True)
    is_required = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        unique_together = ("giveaway_callback_value", "target_channel_id")

    async def add_condition(
        self,
        giveaway_callback_value: str,
        target_channel_id: int,
        target_channel_name: str,
    ) -> bool:
        if await self.filter(
            giveaway_callback_value=giveaway_callback_value,
            target_channel_id=target_channel_id,
        ).exists():
            return False

        await self.create(
            giveaway_callback_value=giveaway_callback_value,
            target_channel_id=target_channel_id,
            target_channel_name=target_channel_name,
        )
        return True

    async def get_conditions(self, giveaway_callback_value: str) -> list[dict]:
        return await self.filter(
            giveaway_callback_value=giveaway_callback_value,
            is_required=True,
        ).all().values("target_channel_id", "target_channel_name")

    async def delete_condition(self, giveaway_callback_value: str, target_channel_id: int):
        await self.filter(
            giveaway_callback_value=giveaway_callback_value,
            target_channel_id=target_channel_id,
        ).delete()

    async def delete_conditions(self, giveaway_callback_value: str):
        await self.filter(giveaway_callback_value=giveaway_callback_value).delete()
