from discord.ext import commands
from .utils import colours, checks
import discord
from cogs.utils.database import *


class Meta(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['dash', 'board'])
    @checks.is_authenticated()
    async def dashboard(self, ctx):
        """登録されているWebhookなどの現在の状況を表示します。"""
        webhook = await Webhook.query.where(Webhook.discord_user_id == str(ctx.author.id)).gino.all()
        subsc = Subscription.query.where(Subscription.id == str(ctx.author.id)).gino.first()
        is_subsc = 'はい' if subsc else 'いいえ'
        embed = discord.Embed(title=f'{ctx.author.name}さんの情報',
                              description=f'登録Webhook数: {len(webhook)}\nサブスクリプションの有無: {is_subsc}',
                              color=colours.deepskyblue)
        await ctx.send(embed=embed)


def setup(bot):
    return bot.add_cog(Meta(bot))
