from discord.ext import commands
from .error import NoAuthenticated


def is_authenticated():
    async def check(ctx):
        if await ctx.bot.auth.is_authenticated(ctx):
            return True
        raise NoAuthenticated()

    return commands.check(check)
