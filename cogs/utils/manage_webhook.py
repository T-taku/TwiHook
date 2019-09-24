import re
import base64
import discord
from aiohttp.web_exceptions import HTTPBadRequest
import asyncio
import uuid
from cogs.utils.colours import deepskyblue, red
from cogs.utils.database import TwitterUser, Subscription


def get_on_off(num):
    return 'ON' if num else 'OFF'


def inversion(num):
    return 1 if not num else 0


back_emoji = '\N{LEFTWARDS BLACK ARROW}'
finish_emoji = '\N{BLACK SQUARE FOR STOP}'


operations = {
    back_emoji: '戻る',
    '0\N{combining enclosing keycap}': 'テキストの変更',
    '1\N{combining enclosing keycap}': '監視間隔の変更',
    '2\N{combining enclosing keycap}': 'リプライ,リツイートの設定',
    '3\N{combining enclosing keycap}': '削除',
    finish_emoji: '終了',
}


def tobase64(text):
    return base64.b64encode(text.encode('utf-8')).decode()


def frombase64(text):
    text = text.encode()
    return base64.b64decode(text).decode()


class UserPaginate:
    def __init__(self, ctx, message, webhook_data, user):
        self.bot = ctx.bot
        self.message = message
        self.loop = self.bot.loop
        self.ctx = ctx
        self.me = ctx.me
        self.channel = ctx.channel
        self.guild = ctx.guild
        self.author = ctx.author
        self.webhook_data = webhook_data
        self.embed = discord.Embed()
        self.user: TwitterUser = user

    def add_webhook_data(self):
        self.embed.add_field(name='テキスト', value=self.user.text)
        self.embed.add_field(name='監視間隔', value=f'{self.user.period}分')
        self.embed.add_field(name='有効か', value='はい' if self.user.state else 'いいえ')
        self.embed.add_field(name='オンオフ状態', value=f'ツイート {get_on_off(self.user.normal)}\n'
                                                      f'リプライ {get_on_off(self.user.reply)}\n'
                                                      f'リツイート {get_on_off(self.user.retweet)}')

    async def update(self):
        await self.message.edit(embed=self.embed)

    async def error(self, text):
        self.embed = discord.Embed(title='エラー', description=text, color=red)
        await self.update()
        await asyncio.sleep(5)

    async def success(self, text):
        self.embed = discord.Embed(title='成功', description=text, color=0x00ff00)
        await self.update()
        await asyncio.sleep(3)

    async def menu(self):
        while not self.loop.is_closed():
            try:
                self.embed = discord.Embed(title='検索監視の詳細')
                self.add_webhook_data()
                self.embed.add_field(name='操作', value='\n'.join([f'{i} {j}' for i, j in operations.items()]))
                await self.update()

                reaction, member = await self.bot.wait_for('reaction_add', check=lambda r, m:
                                                           str(r.emoji) in operations.keys() and m.id == self.author.id,
                                                           timeout=120)

                emoji = str(reaction.emoji)

                if emoji == back_emoji:
                    return True

                elif emoji == finish_emoji:
                    return False

                elif emoji == '0\N{combining enclosing keycap}':
                    func = self.change_text()

                elif emoji == '1\N{combining enclosing keycap}':
                    func = self.change_clock()

                elif emoji == '2\N{combining enclosing keycap}':
                    func = self.change_clock()

                elif emoji == '3\N{combining enclosing keycap}':
                    func = self.delete()

                else:
                    return False

                result = await func

                if not result:
                    return False

            except asyncio.TimeoutError:
                return False

    async def double_wait(self, emojis):
        event = asyncio.Event()

        async def reaction_wait():
            reaction, member = await self.bot.wait_for('reaction_add', check=lambda
                r, m: m.id == self.author.id and str(r.emoji) in [back_emoji, finish_emoji] + list(emojis.keys()),
                                                       timeout=30)
            return reaction, member

        async def message_wait():
            message = await self.bot.wait_for('message', check=lambda m:
            m.author.id == self.author.id, timeout=30)
            return message

        reaction_task = self.bot.loop.create_task(reaction_wait())
        message_task = self.bot.loop.create_task(message_wait())

        def reaction_done(*args, **kwargs):
            message_task.cancel()
            event.set()

        def message_done(*args, **kwargs):
            reaction_task.cancel()
            event.set()

        reaction_task.add_done_callback(reaction_done)
        message_task.add_done_callback(message_done)

        await event.wait()
        reaction, member = None, None
        message = None

        if not reaction_task.cancelled():
            reaction, member = reaction_task.result()
        if not message_task.cancelled():
            message = message_task.result()

        return reaction, member, message

    async def change_text(self):
        self.embed = discord.Embed(title='テキストの変更', description='使用したいテキストのリアクションを押すか、入力してください。',
                                   color=deepskyblue)
        emojis = {
            '0\N{combining enclosing keycap}': '{{UserName}} : {{CreatedAt}} : {{LinkToTweet}}',
            '1\N{combining enclosing keycap}': '{{CreatedAt}} : {{LinkToTweet}}',
        }
        if self.user.text:
            emojis['2\N{combining enclosing keycap}'] = frombase64(self.user.text)

        for key, value in emojis.items():
            self.embed.add_field(name=key, value=value)

        reaction, member, message = await self.double_wait(emojis)

        if reaction:
            emoji = str(reaction.emoji)
            if emoji == back_emoji:
                return True
            elif emoji == finish_emoji:
                return False

            if emoji in emojis.keys():
                await self.user.update(text=tobase64(emojis[emoji])).apply()
                await self.success('変更完了しました。')
                return True

        elif message:
            await self.user.update(text=tobase64(message.content))
            await self.success('変更完了しました。')
            return True

    async def change_clock(self):
        self.embed = discord.Embed(title='時間の変更', description='投稿確認間隔を変更します。好きな投稿確認間隔のリアクションを押してください\n'
                                                              '0\N{combining enclosing keycap} 10分\n'
                                                              '1\N{combining enclosing keycap} 5分\n'
                                                              '2\N{combining enclosing keycap} 1分',
                                   color=deepskyblue)
        reactions = [back_emoji, finish_emoji,
                     '0\N{combining enclosing keycap}',
                     '1\N{combining enclosing keycap}',
                     '2\N{combining enclosing keycap}']

        reaction, member = await self.bot.wait_for('reaction_add', check=lambda
            r, m: m.id == self.author.id and str(r.emoji) in reactions,
                                                   timeout=30)

        emoji = str(reaction.emoji)
        if emoji == back_emoji:
            return True
        elif emoji == finish_emoji:
            return False
        if emoji == '0\N{combining enclosing keycap}':
            period = 10
        elif emoji == '1\N{combining enclosing keycap}':
            period = 5
        else:
            period = 1

        subscription = await Subscription.query.where(Subscription.id == self.webhook_data.discord_user_id).gino.first()
        if period in [1, 5]:
            if not subscription.max == 0:
                await self.error('サブスクリプションがされていません。`subscription` コマンドでサブスクリプションの確認をしてください。')
                return True
            if subscription.residue == 0:
                await self.error('サブスクリプション個数の上限に達しました。`subscription` コマンドでサブスクリプションの確認をしてください。')
                return True
            if not subscription.is_special and period == 1:
                await self.error('プラン上の問題からサブスクリプションできませんでした。`subscription` コマンドでサブスクリプションの確認をしてください。')
                return True

            await subscription.update(residue=subscription.residue - 1).apply()
            await self.user.update(period=period).apply()
        else:
            if not subscription.max != 0 and not subscription.max == subscription.residue:
                await subscription.update(residue=subscription.residue + 1).apply()

            await self.user.update(period=10).apply()

        await self.success('完了しました')

        return True

    async def change_setting(self):
        lists = {
            '0\N{combining enclosing keycap}': f' ツイート {get_on_off(self.user.normal)}',
            '1\N{combining enclosing keycap}': f' リプライ {get_on_off(self.user.reply)}',
            '2\N{combining enclosing keycap}': f' リツイート {get_on_off(self.user.retweet)}',
        }
        embed = discord.Embed(title='変更したい番号のリアクションをクリックして下しあ。')
        for key, value in lists.items():
            embed.add_field(name=key, value=value)

        reaction, member = await self.bot.wait_for('reaction_add',
                                                   check=lambda _r, m: str(_r.emoji) in
                                                                       [back_emoji, finish_emoji]
                                                                       + list(lists.keys()) and
                                                                       m.id == self.author.id and
                                                                       _r.message.id == self.message.id,
                                                   timeout=120)

        emoji = str(reaction.emoji)
        if emoji == back_emoji:
            return True
        elif emoji == finish_emoji:
            return False

        if emoji == '0\N{combining enclosing keycap}':
            await self.user.update(normal=inversion(self.user.normal)).apply()
        elif emoji == '1\N{combining enclosing keycap}':
            await self.user.update(reply=inversion(self.user.reply)).apply()
        elif emoji == '2\N{combining enclosing keycap}':
            await self.user.update(retweet=inversion(self.user.retweet)).apply()

        return await self.change_setting()

    async def delete(self):
        await self.user.delete()
        await self.success('削除終了しました。')
        return False
