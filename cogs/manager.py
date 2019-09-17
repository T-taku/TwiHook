from discord.ext import commands


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


def setup(bot):
    return bot.add_cog(Manager(bot))
