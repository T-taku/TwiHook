from discord.ext import commands
from .error import NoAuthenticated
from .database import Subscription
import uuid


def is_authenticated():
    async def check(ctx):
        if await ctx.bot.auth.is_authenticated(ctx):
            s = await Subscription.query.where(id=str(ctx.author.id)).gino.first()
            if not s:
                await Subscription.create(id=str(ctx.author.id),
                                          discord_token=str(uuid.uuid4()).replace('-', ''),
                                          pixiv_token=str(uuid.uuid4()).replace('-', ''))
            return True
        raise NoAuthenticated()

    return commands.check(check)
