from discord.ext import commands
from .utils import colours, checks
import discord
import pkg_resources
from cogs.utils.database import *


class Meta(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['dash', 'board'])
    @checks.is_authenticated()
    async def dashboard(self, ctx):
        """登録されているWebhookなどの現在の状況を表示します。"""
        webhook = await Webhook.query.where(Webhook.discord_user_id == str(ctx.author.id)).gino.all()
        subsc = await Subscription.query.where(Subscription.id == str(ctx.author.id)).gino.first()
        is_subsc = 'はい' if subsc else 'いいえ'
        embed = discord.Embed(title=f'{ctx.author.name}さんの情報',
                              description=f'登録Webhook数: {len(webhook)}\nサブスクリプションの有無: {is_subsc}',
                              color=colours.deepskyblue)
        await ctx.send(embed=embed)

    @commands.command()
    async def info(self, ctx):
        """Botの詳細な情報を表示します。"""
        embed = discord.Embed(title=self.bot.user.name, color=colours.deepskyblue)
        owner = self.bot.get_user(212513828641046529)
        embed.set_author(name=str(owner), icon_url=owner.avatar_url)

        total_members = 0
        total_online = 0
        offline = discord.Status.offline
        for member in self.bot.get_all_members():
            total_members += 1
            if member.status is not offline:
                total_online += 1

        total_unique = len(self.bot.users)

        text = 0
        voice = 0
        guilds = 0
        for guild in self.bot.guilds:
            guilds += 1
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text += 1
                elif isinstance(channel, discord.VoiceChannel):
                    voice += 1

        embed.add_field(name='Members',
                        value=f'{total_members} total\n{total_unique} unique\n{total_online} unique online')
        embed.add_field(name='Channels', value=f'{text + voice} total\n{text} text\n{voice} voice')

        version = pkg_resources.get_distribution('discord.py').version
        embed.add_field(name='Guilds', value=str(guilds))

        embed.add_field(name='登録ユーザー', value=f'{len(await Auth.query.gino.all())}')
        embed.add_field(name='登録webhook', value=f'{len(await Webhook.query.gino.all())}')

        embed.set_footer(text=f'discord.py v{version}', icon_url='http://i.imgur.com/5BFecvA.png')

        await ctx.send(embed=embed)


def setup(bot):
    return bot.add_cog(Meta(bot))
