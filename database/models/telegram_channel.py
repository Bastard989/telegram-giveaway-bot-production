import math
import random
import string
from typing import List, Dict, Any

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from tortoise import Model, fields


class TelegramChannel(Model):
    id = fields.IntField(pk=True)
    channel_id = fields.BigIntField()
    group_id = fields.BigIntField(null=True)
    post_id = fields.BigIntField(null=True)
    owner_id = fields.BigIntField()
    give_callback_value = fields.TextField()
    channel_callback_value = fields.CharField(max_length=80, unique=True)
    name = fields.TextField()
    role = fields.TextField(default="condition")



    async def add_channel(
        self,
        owner_id: int,
        channel_id: int,
        give_callback_value: str,
        name: str,
        group_id: int = False,
        role: str = "condition",
    ):

        random_callback_value = ''.join(
            random.choices(
                string.ascii_letters + string.digits, k=60
            )
        )

        await self.create(
            owner_id=owner_id,
            group_id=group_id,
            channel_id=channel_id,
            give_callback_value=give_callback_value,
            channel_callback_value=random_callback_value,
            name=name,
            role=role,
        )


    async def add_post_id(self, callback_value: str, post_id: int):
        await self.filter(give_callback_value=callback_value).update(post_id=post_id)


    async def delete_channel(self, channel_callback_value: str = False, give_callback_value: str = False):

        if channel_callback_value:
            await self.filter(channel_callback_value=channel_callback_value).delete()

        else:
            await self.filter(give_callback_value=give_callback_value).all().delete()


    async def exists_channel(
        self,
        channel_id: int,
        give_callback_value: str | bool = False,
        role: str | bool = False,
    ) -> bool:
        query = self.filter(channel_id=channel_id)
        if give_callback_value:
            query = query.filter(give_callback_value=give_callback_value)
        if role:
            query = query.filter(role=role)

        return await query.exists()


    async def get_channel_id(self, channel_callback_value: str) -> list[dict[str, Any]] | dict[str, Any]:
        return await self.filter(channel_callback_value=channel_callback_value).all().values('channel_id')


    async def get_channel_data(
        self,
        channel_callback_value: str = False,
        owner_id: int = False,
        give_callback_value: str = False,
        role: str = False,
    ):
        if channel_callback_value:
            query = self.filter(channel_callback_value=channel_callback_value)
            return await query.all().values(
                'channel_id',
                'name',
                'post_id',
                'group_id',
                'role',
                'channel_callback_value',
            )

        else:
            query = self.all()
            if owner_id:
                query = query.filter(owner_id=owner_id)
            if give_callback_value:
                query = query.filter(give_callback_value=give_callback_value)
            if role:
                query = query.filter(role=role)

            return await query.values(
                'channel_id',
                'name',
                'post_id',
                'group_id',
                'role',
                'channel_callback_value',
            )


    async def get_keyboard(
        self,
        owner_id: int = False,
        give_callback_value: str = False,
        role: str = False,
    ) -> InlineKeyboardMarkup | bool:
        query = self.all()
        if owner_id:
            query = query.filter(owner_id=owner_id)
        if give_callback_value:
            query = query.filter(give_callback_value=give_callback_value)
        if role:
            query = query.filter(role=role)

        channels_data = await query.values('name', 'channel_callback_value', 'role')


        if channels_data:
            markup = InlineKeyboardMarkup()

            for channel in channels_data:
                role_label = "Публикация" if channel["role"] == "publish" else "Подписка"
                markup.add(InlineKeyboardButton(
                    f"{role_label}: {channel['name']}",
                    callback_data=channel['channel_callback_value']
                ))


            return markup

        else:
            return False


    async def get_publish_channel(self, give_callback_value: str) -> dict | bool:
        data = await self.filter(
            give_callback_value=give_callback_value,
            role="publish",
        ).all().values("channel_id", "name", "post_id", "group_id")

        return data[0] if data else False
