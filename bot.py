from discord.ext import commands
from cogs.utils.database import db
from cogs.utils.auth import AuthManager
from cogs.utils.error import NoAuthenticated, CannotPaginate
from cogs.utils.colours import red
import discord


class MyBot(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.db = db
        self.auth: AuthManager = AuthManager(self, self.db)
        self.loop.create_task(self.db_setup())

    async def on_command_error(self, context, exception):
        if isinstance(exception, NoAuthenticated):
            embed = discord.Embed(title='登録が必要です', description='`register`コマンドを使用して登録を行ってください。', color=red)
            await context.send(embed=embed)
        elif isinstance(exception, CannotPaginate):
            embed = discord.Embed(title='エラー', description=exception.__context__, color=red)
            await context.send(embed=embed)
        else:
            raise exception

    async def db_setup(self):
        await self.db.set_bind('postgresql://localhost/twihook')
        await self.db.gino.create_all()

