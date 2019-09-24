import aiohttp
import discord
from discord.ext import commands
import asyncio
import uuid
from cogs.utils.auth import AuthManager
from cogs.utils.checks import is_authenticated
from cogs.utils.colours import red
from cogs.utils.database import Webhook as DBWebhook, TwitterUser
from cogs.utils.manage import Manager


class Webhook(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @commands.group()
    @is_authenticated()
    async def webhook(self, ctx):
        """`help webhook`コマンドからサブコマンドをご覧ください。"""
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=discord.Embed(title='エラー', description='このコマンドにはサブコマンドが必要です。', color=red))

    @webhook.command()
    async def new(self, ctx, webhook_url):
        """Webhookのurlを登録します。"""
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(webhook_url, adapter=discord.AsyncWebhookAdapter(session))
            if await DBWebhook.query.where(DBWebhook.id == str(webhook.id))\
                    .where(DBWebhook.token == webhook.token)\
                    .where(DBWebhook.discord_user_id == str(ctx.author.id)).gino.first():
                await ctx.send('そのWebhookはすでに登録されています。登録情報を変更・追加したい場合は`webhook manage`コマンドを使用してください。')
                return
            await DBWebhook.create(id=str(webhook.id), token=webhook.token, discord_user_id=str(ctx.author.id),
                                   uuid=str(uuid.uuid4()))
            await ctx.send(f'作成が完了しました。`webhook manage {webhook.id}`で登録情報の変更をお願いします。')

    @webhook.command()
    async def manage(self, ctx, webhook_id):
        """登録されたWebhookに紐つけるtwitterユーザーなどを設定します。"""
        db_webhook = await DBWebhook.query.where(DBWebhook.discord_user_id == str(ctx.author.id)).where(DBWebhook.id == webhook_id).gino.first()

        if not db_webhook:
            await ctx.send(embed=discord.Embed(title='無効なidです。', color=red))
            return

        if db_webhook.discord_user_id != str(ctx.author.id):
            await ctx.send(embed=discord.Embed(title='無効なidです。', color=red))
            return
        auth = await self.bot.auth.get_client(ctx)

        manager = Manager(self.bot, ctx, db_webhook,
                          'https://discordapp.com/api/webhooks/{0.id}/{0.token}'.format(db_webhook),
                          auth)

        r = await manager.main_menu()
        if r:
            message = ctx.message
            message.content = f'{ctx.prefix}webhook list'
            context = await self.bot.get_context(message)
            await self.bot.invoke(context)

    @webhook.command()
    async def list(self, ctx):
        """あなたが追加したWebHookの一覧を表示します。"""
        db_webhook = await DBWebhook.query.where(DBWebhook.discord_user_id == str(ctx.author.id)).gino.all()
        embed = discord.Embed(title='あなたが登録したwebhook一覧')
        async with aiohttp.ClientSession() as session:
            for hook in db_webhook:
                webhook = discord.Webhook.from_url(
                    'https://discordapp.com/api/webhooks/{0.id}/{0.token}'.format(hook),
                    adapter=discord.AsyncWebhookAdapter(session))
                channel = self.bot.get_channel(webhook.channel_id)
                guild = self.bot.get_guild(webhook.guild_id)

                if channel:
                    channel_name = channel.name
                else:
                    channel_name = '不明'

                if guild:
                    guild_name = guild.name
                else:
                    guild_name = '不明'

                embed.add_field(name=f'id: {hook.id}',
                                value=f'ギルド: {guild_name}\n'
                                f'チャンネル: {channel_name}\n')

        await ctx.send(embed=embed)

    @webhook.command()
    async def delete(self, ctx, webhook_id):
        webhook = await DBWebhook.query.where(DBWebhook.id == webhook_id) \
            .where(DBWebhook.discord_user_id == str(ctx.author.id)).gino.first()
        if not webhook:
            await ctx.send(embed=discord.Embed(title='エラー', description='そのidのWebhookは登録されていません。', color=red))
            return

        twitter_users = await TwitterUser.query.where(TwitterUser.webhook_id == webhook.id)\
            .where(TwitterUser.discord_user_id == str(ctx.author.id)).gino.all()

        for user in twitter_users:
            await user.delete()

        await webhook.delete()
        await ctx.send('削除が完了しました。')


def setup(bot):
    return bot.add_cog(Webhook(bot))
