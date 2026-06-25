from tortoise import Model, fields


class GiveawayWinner(Model):
    id = fields.IntField(pk=True)
    giveaway_callback_value = fields.TextField()
    user_id = fields.BigIntField()
    username = fields.TextField(null=True)
    first_name = fields.TextField(null=True)
    last_name = fields.TextField(null=True)
    place = fields.IntField()
    is_reserve = fields.BooleanField(default=False)
    selected_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        unique_together = ("giveaway_callback_value", "user_id")

    async def add_winner(
        self,
        giveaway_callback_value: str,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        place: int,
        is_reserve: bool = False,
    ):
        await self.create(
            giveaway_callback_value=giveaway_callback_value,
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            place=place,
            is_reserve=is_reserve,
        )

    async def get_winners(self, giveaway_callback_value: str) -> list[dict]:
        return await self.filter(
            giveaway_callback_value=giveaway_callback_value,
        ).all().order_by("is_reserve", "place").values(
            "user_id",
            "username",
            "first_name",
            "last_name",
            "place",
            "is_reserve",
        )

    async def delete_winners(self, giveaway_callback_value: str):
        await self.filter(giveaway_callback_value=giveaway_callback_value).delete()
