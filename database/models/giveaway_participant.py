from tortoise import Model, fields


class GiveawayParticipant(Model):
    id = fields.IntField(pk=True)
    giveaway_callback_value = fields.TextField()
    user_id = fields.BigIntField()
    username = fields.TextField(null=True)
    first_name = fields.TextField(null=True)
    last_name = fields.TextField(null=True)
    subscription_checked = fields.BooleanField(default=False)
    captcha_passed = fields.BooleanField(default=False)
    joined_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        unique_together = ("giveaway_callback_value", "user_id")

    async def add_participant(
        self,
        giveaway_callback_value: str,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        subscription_checked: bool = True,
        captcha_passed: bool = False,
    ) -> bool:
        if await self.filter(
            giveaway_callback_value=giveaway_callback_value,
            user_id=user_id,
        ).exists():
            return False

        await self.create(
            giveaway_callback_value=giveaway_callback_value,
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            subscription_checked=subscription_checked,
            captcha_passed=captcha_passed,
        )
        return True

    async def exists_participant(self, giveaway_callback_value: str, user_id: int) -> bool:
        return await self.filter(
            giveaway_callback_value=giveaway_callback_value,
            user_id=user_id,
        ).exists()

    async def get_participants(self, giveaway_callback_value: str) -> list[dict]:
        return await self.filter(
            giveaway_callback_value=giveaway_callback_value,
        ).all().values("user_id", "username", "first_name", "last_name", "joined_at")

    async def count_participants(self, giveaway_callback_value: str) -> int:
        return await self.filter(giveaway_callback_value=giveaway_callback_value).count()

    async def delete_participants(self, giveaway_callback_value: str):
        await self.filter(giveaway_callback_value=giveaway_callback_value).delete()
