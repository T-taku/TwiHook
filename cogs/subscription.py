import re
import aiohttp
from bs4 import BeautifulSoup
from .utils import *
from .utils.database import Subscription
from discord.ext import commands
import discord
listen_channel = 627785620139409418

pixiv_compile = re.compile('https://www\.pixiv\.net/member\.php\?id=([0-9]+)')


class SubscriptionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=['subs'])
    @is_authenticated()
    async def subscription(self):
        """サブスクリプション についてのコマンドです。省略形はsubsです。詳しくはhelp subsにて。"""
        pass

    @subscription.command()
    async def setup(self, ctx, pixiv_user_url):
        """pixivのユーザーと紐つけます。あなたのプロフィールページ、\n
        例えば( https://www.pixiv.net/member.php?id=34313725 ) を入力してください。"""
        ctx.send = ctx.author.send
        subscription = await Subscription.query.where(Subscription.id == str(ctx.author.id)).gino.first()
        if subscription.pixiv_user_id:
            await ctx.send('すでに設定されているため変更できません。\nもし変更したい場合は公式サーバーから申請してください。')
            return
        if not re.search(pixiv_compile, pixiv_user_url):
            await ctx.send('ピクシブのユーザーのurlの形式と異なるようです。')
            return

        async with aiohttp.ClientSession() as session:
            r = await session.get(pixiv_user_url)
            soup = BeautifulSoup(await r.text())

        find = soup.find_all(class_='error-title')
        if not find:
            await ctx.send('アカウントが存在しません。')
            return
        name = soup.find('h1', class_='name').text
        msg = await ctx.send(f'ユーザーネーム {name} さんを紐つけます。\n'
                             f'嘘のユーザーを紐つけたことが発覚した場合、あなたとあなたがWebhookを登録しているサーバーではTwiHookが使用できなくなります。\n'
                             f'完了する場合、\N{OK HAND SIGN}のリアクションを押してください。')
        await msg.add_reaction("\N{OK HAND SIGN}")
        reaction, member = await self.bot.wait_for('reaction_add', check=lambda r,m:
                                                   str(r.emoji) == "\N{OK HAND SIGN}" and m.id == ctx.author.id and
                                                   r.message.id == msg.id,
                                                   timeout=120)
        await ctx.send('受け付けました。あなたのdiscord tokenは')
        await ctx.send(subscription.discord_token)
        await ctx.send('です。(コピペ可能)')
        await subscription.update(pixiv_user_id=re.search(pixiv_compile, pixiv_user_url).groups()[0]).apply()

    @subscription.command()
    async def connect(self, ctx, discord_token, pixiv_token):
        """サブスクリプションの認証をします。"""
        if not pixiv_token in self.bot.pixivs.keys():
            await ctx.send('pixivの方での認証がされていません。もしされていて、エラーが出る場合は公式サーバーからお取り合わせください。')
            return

        subscription = await Subscription.query.where(Subscription.discord_token == discord_token)\
            .where(Subscription.pixiv_token == pixiv_token).gino.first()
        if not subscription:
            await ctx.send('discord_tokenもしくはpixiv_tokenが間違っているか、紐つけされていません。')
            return
        if subscription.max:
            await ctx.send('すでにサブスクリプションの認証が終了しています。追加のhookの場合は自動で処理されます。')
            return

        num, course = self.bot.ixivs[pixiv_token]
        del self.bot.pixivs[pixiv_token]
        await subscription.update(residue=num, max=num, is_special=course).apply()
        await ctx.send('認証が完了しました。')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.channel.id == listen_channel or message.author.bot:
            return
        url, num, course = message.content.split()

        user_id = re.search(pixiv_compile, url).groups()[0]
        subscription = await Subscription.query.where(Subscription.pixiv_user_id == user_id).gino.first()
        if not subscription:
            await message.channel.send('エラーが発生しました: 不明なユーザーです')
            return

        await message.delete()

        user = self.bot.get_user(int(subscription.id))
        await message.channel.send(
            f"{str(user)} さん、登録ありがとうございます。\nあなたのpixiv token は、 {subscription.pixiv_token} です。\n"
            f"subs connectコマンドを使用し有効化させてください。ありがとうございます。"
            , delete_after=30)
        self.bot.pixivs[subscription.pixiv_token] = [int(num), int(course)]


