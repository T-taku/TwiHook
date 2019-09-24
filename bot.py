from discord.ext import commands
from cogs.utils.database import db
from cogs.utils.auth import AuthManager
from cogs.utils.error import NoAuthenticated, CannotPaginate
from cogs.utils.colours import red
import traceback
import discord
import asyncio


class MyBot(commands.Bot):
    def __init__(self, command_prefix, **options):
        super().__init__(command_prefix, **options)
        self.db = db
        self.auth = AuthManager(self, self.db)
        self.loop.create_task(self.db_setup())
        self.loop.create_task(self.route_presence())

    async def on_command_error(self, context, exception: Exception):
        if isinstance(exception, NoAuthenticated):
            embed = discord.Embed(title='登録が必要です', description='`register`コマンドを使用して登録を行ってください。', color=red)
            await context.send(embed=embed)
        elif isinstance(exception, CannotPaginate):
            await context.send(f'エラー {exception}')
        else:
            await context.send(f'エラー {exception}')
        traceback.print_exc()

    async def db_setup(self):
        await self.db.set_bind('postgresql://localhost/twihook')
        await self.db.gino.create_all()

    async def route_presence(self):
        await self.wait_until_ready()
        while not self.is_closed():
            await self.change_presence(activity=discord.Game(name='TwiHook - Twitter to Discord'))
            await asyncio.sleep(5)
            await self.change_presence(activity=discord.Game(name='Help -> /help'))
            await asyncio.sleep(5)

