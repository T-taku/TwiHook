import re
import base64
import discord
from aiohttp.web_exceptions import HTTPBadRequest
import asyncio
import uuid
from cogs.utils.colours import deepskyblue, red
from cogs.utils.database import TwitterUser, Subscription, NewUser, Search, NewSearch
from .error import CannotPaginate
import itertools

from .manage_search import SearchPaginate
from .manage_webhook import UserPaginate

back_emoji = '\N{LEFTWARDS BLACK ARROW}'
finish_emoji = '\N{BLACK SQUARE FOR STOP}'

twitter_compile = re.compile(r'twitter\.com/(?P<username>[a-zA-Z0-9_\-.]{3,15})')
keys = ['0\N{combining enclosing keycap}', '1\N{combining enclosing keycap}', '2\N{combining enclosing keycap}']
all_keys = ['0\N{combining enclosing keycap}',
            '1\N{combining enclosing keycap}',
            '2\N{combining enclosing keycap}',
            '3\N{combining enclosing keycap}']
all_emojis = [
    back_emoji,
    '0\N{combining enclosing keycap}',
    '1\N{combining enclosing keycap}',
    '2\N{combining enclosing keycap}',
    '3\N{combining enclosing keycap}',
    finish_emoji,
    ]


def is_int(string):
    try:
        int(string)
    except ValueError:
        return False
    else:
        return True


def tobase64(text):
    return base64.b64encode(text.encode('utf-8')).decode()


def frombase64(text):
    text = text.encode()
    return base64.b64decode(text).decode()


class Manager:
    def __init__(self, bot, ctx, webhook_data, webhook_url):
        self.bot = bot
        self.ctx = ctx
        self.me = ctx.me
        self.channel = ctx.channel
        self.guild = ctx.guild
        self.author = ctx.author
        self.webhook_data = webhook_data
        self.webhook_url = webhook_url
        self.embed = None
        self.message = None
        self.state = None
        self.twitter = None

        if ctx.guild is not None:
            self.permissions = self.channel.permissions_for(ctx.guild.me)
        else:
            self.permissions = self.channel.permissions_for(ctx.bot.user)

        if not self.permissions.embed_links:
            raise CannotPaginate('embedを表示する権限がないため、ヘルプコマンドを表示することができません。')

        if not self.permissions.send_messages:
            raise CannotPaginate('Botはメッセージを送信できません。')

        if not self.permissions.add_reactions:
            raise CannotPaginate('リアクションを追加する権限がないため、ヘルプコマンドを表示することができません。')

        if not self.permissions.read_message_history:
            raise CannotPaginate('メッセージ履歴を読む権限がないため、ヘルプコマンドを表示することができません。')

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

    def get_webhook_url(self):
        return 'https://discordapp.com/api/webhooks/{0.id}/{0.token}'.format(self.webhook_data)

    def get_twitter_users(self):
        return TwitterUser.query.where(TwitterUser.webhook_id == str(self.webhook_data.id))\
            .where(TwitterUser.discord_user_id == str(self.author.id)).gino.all()

    def get_search(self):
        return Search.query.where(Search.webhook_id == str(self.webhook_data.id))\
                .where(Search.discord_user_id == str(self.author.id)).gino.all()

    async def get_screen_name(self, twitter_id):
        r = await self.twitter.request('GET', 'users/show.json', params={'user_id': int(twitter_id)})
        return r["screen_name"]

    async def get_user_count(self):
        twitter_users = await self.get_twitter_users()
        return len(twitter_users)

    async def get_search_count(self):
        return len(await self.get_search())

    async def add_reactions(self, reactions):
        for reaction in reactions:
            await self.message.add_reaction(reaction)

    async def update(self):
        if self.message is not None:
            await self.message.edit(embed=self.embed)

    async def wait_for_message(self):
        message = await self.bot.wait_for('message', check=lambda
            m: m.author.id == self.author.id and m.channel.id == self.channel.id,
                                          timeout=30)

        return message

    async def error(self, text):
        self.embed = discord.Embed(title='エラー', description=text, color=red)
        await self.update()
        await asyncio.sleep(5)

    async def success(self, text):
        self.embed = discord.Embed(title='成功', description=text, color=0x00ff00)
        await self.update()
        await asyncio.sleep(3)

    async def get_main_embed(self):
        users = await self.get_twitter_users()
        tf = []
        operations = {
            back_emoji: 'Webhook一覧へ',
        }
        for key, value in itertools.zip_longest(keys, users):
            if not value:
                text = '新しいユーザーを作成する'
                tf.append(False)
            else:
                username = await self.get_screen_name(value.id)
                text = f'@{username}を編集する'
            operations[key] = text
            tf.append(True)

        search = await self.get_search()
        if search:
            operations['3\N{combining enclosing keycap}'] = f'検索監視を編集する'
            tf.append(True)
        else:
            operations['3\N{combining enclosing keycap}'] = f'検索監視を作成する'
            tf.append(False)

        main_embed = discord.Embed(title=f'Webhook id:{self.webhook_data.id} を編集',
                                   description='Webhookを編集します。リアクションをクリックしてください',
                                   color=deepskyblue)
        return main_embed, tf

    async def main_menu(self):
        embed, tf = await self.get_main_embed()
        self.message = await self.ctx.send(embed=embed)
        await self.add_reactions(all_emojis)
        try:
            while True:
                result = True
                self.embed, tf = await self.get_main_embed()
                await self.update()
                reaction, member = await self.bot.wait_for('reaction_add',
                                                           check=lambda r, m:
                                                           str(r.emoji) in all_emojis and m.id == self.author.id,
                                                           timeout=120)
                emoji = str(reaction.emoji)
                if emoji == back_emoji:
                    return True
                elif emoji == finish_emoji:
                    result = False

                if tf[all_emojis.index(emoji)]:
                    if all_emojis.index(emoji) == 3:
                        result = await SearchPaginate(self.ctx, self.message,
                                                      self.webhook_data, (await self.get_search())).menu()
                    else:
                        result = await UserPaginate(self.ctx, self.message,
                                                    self.webhook_data,
                                                    (await self.get_twitter_users())[all_emojis.index(emoji)]).menu()
                elif not tf[all_emojis.index(emoji)]:
                    if all_emojis.index(emoji) == 3:
                        result = await self.new_search()
                    else:
                        result = await self.new_hook()

                if not result:
                    await self.end()
                    return False

        except asyncio.TimeoutError:
            return False

    async def new_search(self):
        self.embed = discord.Embed(title='新しい検索監視の作成',
                                   description='新しい検索監視に使用するクエリを送信してください',
                                   color=deepskyblue)
        await self.update()

        reaction, member, message = await self.double_wait([back_emoji, finish_emoji])

        if reaction:
            emoji = str(reaction.emoji)
            if emoji == back_emoji:
                return True
            elif emoji == finish_emoji:
                return False
        _uuid = str(uuid.uuid4())
        await Search.create(query=tobase64(message.content), webhook_id=self.webhook_data.id,
                            discord_user_id=str(self.author.id), uuid=_uuid)
        await NewSearch.create(uuid=_uuid)
        await self.success('作成完了しました')
        return True

    async def new_hook(self):

        if await self.get_user_count() == 3:
            await self.error('３個以上のtwitterアカウントを紐つけることはできません。')
            return True

        self.embed = discord.Embed(title='新しいフックの作成',
                                   description='新しいフックに紐つけるtwitterのユーザー名(`@なし`)もしくはユーザーへのurlを送信してください',
                                   color=deepskyblue)
        await self.update()

        reaction, member, message = await self.double_wait([back_emoji, finish_emoji])

        if reaction:
            emoji = str(reaction.emoji)
            if emoji == back_emoji:
                return True
            elif emoji == finish_emoji:
                return False

        match = re.search(twitter_compile, message.content)
        if match:
            username = match.group('username')
        else:
            username = message.content

        twitter = await self.bot.auth.get_client(self.ctx)

        try:
            r = await twitter.request('GET', 'users/show.json', params={'screen_name': username})
        except HTTPBadRequest:
            await self.error('無効なユーザー名もしくは鍵・凍結されたアカウントです。')
            return True

        await self.success('アカウント名{}をフックに追加します。'.format(r['screen_name']))

        _uuid = str(uuid.uuid4())

        await TwitterUser.create(id=r['id_str'], webhook_id=self.webhook_data.id, period=10,
                                 discord_user_id=str(self.author.id), uuid=_uuid)

        await NewUser.create(uuid=_uuid)
        return True

    async def end(self):
        await self.message.delete()
