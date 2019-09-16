from discord.ext import commands


class NoAuthenticated(commands.CheckFailure):
    pass


class CannotPaginate(Exception):
    pass
