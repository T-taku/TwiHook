from discord.ext import commands
from .utils import colours, checks
import discord


class Manager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def register(self, ctx):
        """ユーザー登録用のコマンドです。twitter認証が必要となります。"""
        if not await self.bot.auth.is_authenticated(ctx):
            await self.bot.auth.request_authenticated(ctx)
        else:
            await ctx.send('すでに登録が完了しています。')

    @commands.command(aliases=['dash', 'board'])
    @checks.is_authenticated()
    async def dashboard(self, ctx):
        """登録されているWebhookなどの現在の状況を表示します。"""
        embed = discord.Embed(title=f'{ctx.author.name}さんの情報',
                              description='登録Webhook数: {}\nサブスクリプションの有無: {}',
                              color=colours.deepskyblue)
        await ctx.send(embed=embed)


def setup(bot):
    return bot.add_cog(Manager(bot))
