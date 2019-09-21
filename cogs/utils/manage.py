import re
import base64
import discord
from aiohttp.web_exceptions import HTTPBadRequest
import asyncio
import uuid
from cogs.utils.colours import deepskyblue, red
from cogs.utils.database import TwitterUser, Subscription, NewUser
from .error import CannotPaginate

twitter_compile = re.compile(r'twitter\.com/(?P<username>[a-zA-Z0-9_\-.]{3,15})')


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


count_operations = ['0\N{combining enclosing keycap}', '1\N{combining enclosing keycap}',
                    '2\N{combining enclosing keycap}', '3\N{combining enclosing keycap}',
                    '4\N{combining enclosing keycap}', '5\N{combining enclosing keycap}',
                    '6\N{combining enclosing keycap}', '7\N{combining enclosing keycap}',
                    '8\N{combining enclosing keycap}', '9\N{combining enclosing keycap}',
                    ]

main_operations = {
    '\N{SQUARED NEW}': '新しくフックを作成します。',
    '\N{REGIONAL INDICATOR SYMBOL LETTER D}': '作成したフックを削除します。',
    '\N{BLACK RIGHT-POINTING TRIANGLE WITH DOUBLE VERTICAL BAR}': '個々のフックを停止・開始します。',
    '\N{INPUT SYMBOL FOR LATIN SMALL LETTERS}': 'フックの文章を変更します。',
    '\N{LEVEL SLIDER}': 'リプライ,リツイートなどを表示するかの設定を行います。',
    '\N{INFORMATION SOURCE}': 'フックの情報を表示します。',
    '\N{CLOCK FACE ONE OCLOCK}': 'フックの読み込み間隔を変更します。5分もしくは1分に設定すると、サブスクリプションが発生します。',
    '\N{BLACK SQUARE FOR STOP}': '終了します',
}
error_operations = {
    '\N{LEFTWARDS BLACK ARROW}': '戻る',
}
new_hook_operations = {
    '\N{LEFTWARDS BLACK ARROW}': '戻る',
}
delete_hook_operations = {
    '\N{LEFTWARDS BLACK ARROW}': '戻る',
}
show_hook_operations = {
    '\N{LEFTWARDS BLACK ARROW}': '戻る',
}
change_clock_operations = {
    '\N{LEFTWARDS BLACK ARROW}': '戻る',
}
state_to_reactions = {
    'main': main_operations.keys(),
    'error': error_operations.keys(),
    'new_hook': new_hook_operations.keys(),
    'delete_hook': delete_hook_operations.keys(),
    'show_hook': show_hook_operations.keys(),
    'change_clock': change_clock_operations.keys(),
}


class WebhookManager:
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
        self.back = self.main_menu
        self.twitter = None

        self.pages = {
            ('main', '\N{SQUARED NEW}'): self.new_hook,
            ('main', '\N{REGIONAL INDICATOR SYMBOL LETTER D}'): self.delete_hook,
            ('main', '\N{BLACK RIGHT-POINTING TRIANGLE WITH DOUBLE VERTICAL BAR}'): self.stop_hook,
            ('main', '\N{INPUT SYMBOL FOR LATIN SMALL LETTERS}'): self.change_hook,
            ('main', '\N{LEVEL SLIDER}'): self.change_tweet_setting,
            ('main', '\N{INFORMATION SOURCE}'): self.show_hook,
            ('main', '\N{CLOCK FACE ONE OCLOCK}'): self.change_clock,
        }

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

    def add_embed_operation(self, operations):
        if self.embed:
            self.embed.add_field(name='操作', value='\n'.join([f'{i} {o}' for i, o in operations.items()]), inline=False)

    def get_webhook_url(self):
        return 'https://discordapp.com/api/webhooks/{0.id}/{0.token}'.format(self.webhook_data)

    def update_state(self, state):
        self.state = state

    def get_twitter_users(self):
        return TwitterUser.query.where(TwitterUser.webhook_id == str(self.webhook_data.id))\
            .where(TwitterUser.discord_user_id == str(self.author.id)).gino.all()

    def move_page(self, reaction):
        emoji = str(reaction.emoji)
        if emoji == '\N{LEFTWARDS BLACK ARROW}':
            if self.back:
                return self.back()
        if emoji == '\N{BLACK SQUARE FOR STOP}':
            return self.end()

        coroutine = self.pages[(self.state, emoji)]

        return coroutine()

    async def get_screen_name(self, twitter_id):
        r = await self.twitter.request('GET', 'users/show.json', params={'user_id': int(twitter_id)})
        return r["screen_name"]

    async def get_period(self):
        twitter_users = await self.get_twitter_users()
        if twitter_users:
            return twitter_users[0].period
        return 10

    async def get_user_count(self):
        twitter_users = await self.get_twitter_users()
        return len(twitter_users)

    async def add_reactions(self, reactions):
        for reaction in reactions:
            await self.message.add_reaction(reaction)

    async def update(self):
        if self.message is not None:
            await self.message.edit(embed=self.embed)

    async def trash_my_reactions(self):
        await self.refresh()
        gather = asyncio.gather(*[reaction.remove(self.me) for reaction in self.message.reactions])
        self.bot.loop.run_until_complete(gather)

    async def refresh(self):
        self.message = await self.channel.fetch_message(self.message.id)

    async def join(self):
        self.twitter = await self.bot.auth.get_client(self.ctx)
        if self.message is None:
            self.message = await self.channel.send(embed=self.embed)

    async def wait_for_move(self):
        """リアクションをつけ、選ばせ、リアクションを消す"""
        reactions = state_to_reactions[self.state]
        await self.add_reactions(reactions)
        await self.refresh()

        reaction, member = await self.bot.wait_for('reaction_add', check=lambda r, m: str(
            r.emoji) in reactions and m.id == self.author.id and r.message.id == self.message.id,
                                                   timeout=120)
        await self.trash_my_reactions()

        await self.move_page(reaction)

    async def wait_for_message(self):
        message = await self.bot.wait_for('message', check=lambda
            m: m.author.id == self.author.id and m.channel.id == self.channel.id,
                                          timeout=30)

        return message

    async def main_menu(self):
        self.update_state('main')
        is_subsc = "はい" if (await self.get_period()) in [1, 5] else "いいえ"

        description = f"""サブスクリプションしている: {is_subsc}\n"""
        self.embed = discord.Embed(title='Webhookの詳細', description=description, color=deepskyblue)
        self.embed.add_field(name='連携済みtwitterユーザー数', value=str(await self.get_user_count()), inline=False)
        self.embed.add_field(name='チェック間隔', value=f'{await self.get_period()}分', inline=False)
        self.add_embed_operation(main_operations)

        await self.update()
        await self.join()
        await self.wait_for_move()

    async def error(self, message, back=None):
        self.update_state('error')

        self.embed = discord.Embed(title='エラー', description=message, color=red)

        await self.update()
        self.add_embed_operation(error_operations)

        await self.refresh()

        self.back = back or self.main_menu

        await self.wait_for_move()
        return

    async def new_hook(self):
        self.update_state('new_hook')

        if await self.get_user_count() == 3:
            await self.error('３個以上のtwitterアカウントを紐つけることはできません。')
            return

        self.embed = discord.Embed(title='新しいフックの作成',
                                   description='新しいフックに紐つけるtwitterのユーザー名(`@なし`)もしくはユーザーへのurlを送信してください',
                                   color=deepskyblue)
        await self.update()
        await self.refresh()

        message = await self.wait_for_message()
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
            return
        self.embed.add_field(name='アカウント確認成功', value='アカウント名{}をフックに追加します。'.format(r['screen_name']), inline=False)
        self.add_embed_operation(new_hook_operations)
        await self.update()
        await TwitterUser.create(id=r['id_str'], webhook_id=self.webhook_data.id, period=await self.get_period(),
                                 discord_user_id=str(self.author.id), uuid=str(uuid.uuid4()))
        await NewUser.create(webhook_id=self.webhook_data.id, twitter_id=r['id_str'], uuid=str(uuid.uuid4()))

        await self.wait_for_move()

    async def delete_hook(self):
        self.update_state('delete_hook')
        self.back = self.main_menu
        if not await self.get_user_count():
            await self.error('twitterアカウントが紐ついていません。')
            return

        self.embed = discord.Embed(title='フックの削除', description='削除したいフックの数字のリアクションをクリックしてください。',
                                   color=deepskyblue)
        value = ''

        twitter_users = await self.get_twitter_users()
        using_emojis = {'\N{LEFTWARDS BLACK ARROW}': '戻る'}
        for user, emoji in zip(twitter_users, count_operations):
            using_emojis[emoji] = user
            value += f'{emoji} : @{await self.get_screen_name(user.id)}\n'
        self.embed.add_field(name='ユーザー一覧', value=value, inline=False)
        await self.update()
        await self.add_reactions(using_emojis.keys())
        reaction, member = await self.bot.wait_for('reaction_add',
                                                   check=lambda _r, m: str(_r.emoji) in using_emojis.keys() and
                                                                       m.id == self.author.id and
                                                                       _r.message.id == self.message.id,
                                                   timeout=30)
        if str(reaction.emoji) == '\N{LEFTWARDS BLACK ARROW}':
            await self.move_page(reaction)
            return

        await using_emojis[str(reaction.emoji)].delete()
        await self.trash_my_reactions()

        await self.delete_hook()

    async def stop_hook(self):
        self.update_state('stop_hook')
        self.back = self.main_menu
        if not await self.get_user_count():
            await self.error('twitterアカウントが紐ついていません。')
            return

        self.embed = discord.Embed(title='フックの編集', description='停止・開始したいフックの数字のリアクションをクリックしてください。',
                                   color=deepskyblue)
        value = ''

        twitter_users = await self.get_twitter_users()
        using_emojis = {'\N{LEFTWARDS BLACK ARROW}': '戻る'}
        for user, emoji in zip(twitter_users, count_operations):
            using_emojis[emoji] = user
            state = '\N{BLACK RIGHT-POINTING TRIANGLE} : 運用中' if user.state \
                else '\N{DOUBLE VERTICAL BAR} : 停止中'
            value += f'{emoji} : @{await self.get_screen_name(user.id)} : {state}\n'
        self.embed.add_field(name='ユーザー一覧', value=value, inline=False)
        await self.update()
        await self.add_reactions(using_emojis.keys())
        reaction, member = await self.bot.wait_for('reaction_add',
                                                   check=lambda _r, m: str(_r.emoji) in using_emojis.keys() and
                                                                       m.id == self.author.id and
                                                                       _r.message.id == self.message.id,
                                                   timeout=30)
        if str(reaction.emoji) == '\N{LEFTWARDS BLACK ARROW}':
            await self.trash_my_reactions()
            await self.move_page(reaction)
            return

        if using_emojis[str(reaction.emoji)].state:
            await using_emojis[str(reaction.emoji)].update(state=0).apply()

        else:
            await using_emojis[str(reaction.emoji)].update(state=1).apply()

        await self.stop_hook()

    async def change_hook(self):
        self.update_state('change_hook')
        self.back = self.main_menu
        if not await self.get_user_count():
            await self.error('twitterアカウントが紐ついていません。')
            return

        self.embed = discord.Embed(title='フックの文章変更', description='変更したいフックの数字のリアクションをクリックしてください。',
                                   color=deepskyblue)
        value = ''

        twitter_users = await self.get_twitter_users()
        using_emojis = {'\N{LEFTWARDS BLACK ARROW}': '戻る'}
        for user, emoji in zip(twitter_users, count_operations):
            using_emojis[emoji] = user
            value += f'{emoji} : @{await self.get_screen_name(user.id)}\n'
        self.embed.add_field(name='ユーザー一覧', value=value, inline=False)
        await self.update()
        await self.add_reactions(using_emojis.keys())
        reaction, member = await self.bot.wait_for('reaction_add',
                                                   check=lambda _r, m: str(_r.emoji) in using_emojis.keys() and
                                                                    m.id == self.author.id and
                                                                    _r.message.id == self.message.id,
                                                   timeout=30)
        if str(reaction.emoji) == '\N{LEFTWARDS BLACK ARROW}':
            await self.trash_my_reactions()
            await self.move_page(reaction)
            return

        await self.change_text(using_emojis[str(reaction.emoji)])

        await self.change_hook()

    async def change_text(self, twitter_user: TwitterUser):
        await self.trash_my_reactions()
        self.embed = discord.Embed(title='文章変更', description='文章を入力するか、次に示す例もしくは現在のもののリアクションを押してください。',
                                   color=deepskyblue)
        examples = [
            '{{UserName}} : {{CreatedAt}} : {{LinkToTweet}}',
            '{{CreatedAt}} : {{LinkToTweet}}',
        ]
        if twitter_user.text:
            examples.append(frombase64(twitter_user.text))

        for i, e in enumerate(examples, start=0):
            self.embed.add_field(name=count_operations[i], value=e)

        await self.update()
        await self.refresh()
        await self.add_reactions(count_operations[:len(examples)])
        event = asyncio.Event()

        async def reaction_wait():
            reaction, member = await self.bot.wait_for('reaction_add', check=lambda
                r, m: m.id == self.author.id and str(r.emoji) in count_operations[:len(examples)], timeout=30)
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

        if reaction:
            text = examples[count_operations.index(str(reaction.emoji))]
        else:
            text = message.content
        await twitter_user.update(text=tobase64(text)).apply()
        self.embed.add_field(name='完了', value='適切に変更されました。', inline=False)
        await self.update()
        await self.trash_my_reactions()
        await asyncio.sleep(2)

    async def show_hook(self):
        self.update_state('show_hook')
        twitter_users = await self.get_twitter_users()
        self.embed = discord.Embed(title='ユーザー一覧', color=deepskyblue)
        for user in twitter_users:
            screen_name = await self.get_screen_name(user.id)
            value = f"""
            **テキスト**: `{frombase64(user.text)}`
            有効か: {'はい' if user.state else 'いいえ'}
            """
            self.embed.add_field(name=f'@{screen_name}', value=value)
        await self.update()

        await self.wait_for_move()

    async def change_clock(self):
        self.update_state('change_clock')
        self.embed = discord.Embed(title='時間の変更', description='投稿確認間隔を変更します。好きな投稿確認間隔のリアクションを押してください\n'
                                                              '0\N{combining enclosing keycap} 10分\n'
                                                              '1\N{combining enclosing keycap} 5分\n'
                                                              '2\N{combining enclosing keycap} 1分',
                                   color=deepskyblue)
        await self.update()
        reactions = {
            '\N{LEFTWARDS BLACK ARROW}': '戻る',
            '0\N{combining enclosing keycap}': 10,
            '1\N{combining enclosing keycap}': 5,
            '2\N{combining enclosing keycap}': 1,
        }

        await self.add_reactions(reactions.keys())
        reaction, member = await self.bot.wait_for('reaction_add', check=lambda
                                                   r, m: m.id == self.author.id and str(r.emoji) in reactions.keys(),
                                                   timeout=30)
        if reactions[str(reaction.emoji)] == '戻る':
            await self.trash_my_reactions()
            await self.move_page(reaction)
            return

        subscription = await Subscription.query.where(Subscription.id == self.webhook_data.discord_user_id).gino.first()
        if reactions[str(reaction.emoji)] in [1]:
            if not subscription:
                await self.error('サブスクリプションがされていません。`subscription` コマンドでサブスクリプションの確認をしてください。')
                return
            if subscription.residue == 0:
                await self.error('サブスクリプション個数の上限に達しました。`subscription` コマンドでサブスクリプションの確認をしてください。')
                return
            if not subscription.is_special and reactions[str(reaction.emoji)] == 1:
                await self.error('プラン上の問題からサブスクリプションできませんでした。`subscription` コマンドでサブスクリプションの確認をしてください。')
                return
            if subscription:
                await subscription.update(residue=subscription.residue-1).apply()
            for user in await self.get_twitter_users():
                await user.update(period=reactions[str(reaction.emoji)]).apply()
        else:
            if await self.get_period() in [1]:
                #  課金のとこで来たらここを[1, 5]に変更
                if subscription:
                    await subscription.update(residue=subscription.residue + 1).apply()

            for user in await self.get_twitter_users():
                await user.update(period=reactions[str(reaction.emoji)]).apply()

        self.embed.add_field(name='変更完了', value='正常に変更が完了しました。', inline=False)
        await self.update()
        await self.trash_my_reactions()
        await self.wait_for_move()

    async def change_tweet_setting(self):
        self.update_state('change_tweet_setting')

        if not await self.get_user_count():
            await self.error('twitterアカウントが紐ついていません。')
            return

        self.embed = discord.Embed(title='ツイートの設定変更', description='変更したいフックの数字のリアクションをクリックしてください。',
                                   color=deepskyblue)
        value = ''

        twitter_users = await self.get_twitter_users()
        using_emojis = {'\N{LEFTWARDS BLACK ARROW}': '戻る'}
        for user, emoji in zip(twitter_users, count_operations):
            using_emojis[emoji] = user
            value += f'{emoji} : @{await self.get_screen_name(user.id)}\n'
        self.embed.add_field(name='ユーザー一覧', value=value, inline=False)
        await self.update()
        await self.add_reactions(using_emojis.keys())
        reaction, member = await self.bot.wait_for('reaction_add',
                                                   check=lambda _r, m: str(_r.emoji) in using_emojis.keys() and
                                                                       m.id == self.author.id and
                                                                       _r.message.id == self.message.id,
                                                   timeout=30)
        if str(reaction.emoji) == '\N{LEFTWARDS BLACK ARROW}':
            await self.trash_my_reactions()
            await self.move_page(reaction)
            return

        await self.trash_my_reactions()
        await self.change_setting(using_emojis[str(reaction.emoji)])

    async def change_setting(self, twitter_user: TwitterUser):

        def get_on_off(num):
            return 'ON' if num else 'OFF'

        def inversion(num):
            return 1 if not num else 0

        using_emojis = {'\N{LEFTWARDS BLACK ARROW}': '戻る',
                        '0\N{combining enclosing keycap}': f' ツイート {get_on_off(twitter_user.normal)}',
                        '1\N{combining enclosing keycap}': f' リプライ {get_on_off(twitter_user.reply)}',
                        '2\N{combining enclosing keycap}': f' リツイート {get_on_off(twitter_user.retweet)}',
                        }

        self.embed = discord.Embed(title='現在の状態', description='\n'.join([k+v for k, v in using_emojis.items()])
                                                              + '\n変更したいリアクションを押してください')

        await self.update()
        await self.add_reactions(using_emojis.keys())
        reaction, member = await self.bot.wait_for('reaction_add',
                                                   check=lambda _r, m: str(_r.emoji) in using_emojis.keys() and
                                                                       m.id == self.author.id and
                                                                       _r.message.id == self.message.id,
                                                   timeout=30)
        if str(reaction.emoji) == '\N{LEFTWARDS BLACK ARROW}':
            await self.trash_my_reactions()
            return

        emoji = str(reaction.emoji)

        if emoji == '0\N{combining enclosing keycap}':
            await twitter_user.update(normal=inversion(twitter_user.normal))
        elif emoji == '1\N{combining enclosing keycap}':
            await twitter_user.update(reply=inversion(twitter_user.reply))
        elif emoji == '2\N{combining enclosing keycap}':
            await twitter_user.update(retweet=inversion(twitter_user.retweet))

        await self.change_setting(twitter_user)

    async def end(self):
        await self.message.delete()
