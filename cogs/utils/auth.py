import asyncio
from discord.ext import commands
from .twitter import *
from .database import Auth
from aiohttp.web_exceptions import HTTPBadRequest


class AuthManager:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    async def is_authenticated(self, ctx: commands.Context):
        auth = await self.get(ctx)

        if not auth:
            return False
        return True

    async def request_authenticated(self, ctx: commands.Context):
        twitter = get_client_not_oauth()
        request_token, request_token_secret, _ = await twitter.get_request_token()
        authorize_url = twitter.get_authorize_url(request_token)
        await ctx.author.send(f'{authorize_url} を開き、5分以内にpinコードをここに入力してください。')

        try:
            oauth_verifier = await self.bot.wait_for('message', check=lambda m: m.author.id == ctx.author.id, timeout=5 * 60)
        except asyncio.TimeoutError:
            return False

        try:
            oauth_token, oauth_token_secret, _ = await twitter.get_access_token(oauth_verifier.content)
        except HTTPBadRequest:
            await ctx.author.send('PINコードが間違っています。もう一度やり直してください。')
            return False

        twitter = get_client(oauth_token, oauth_token_secret)

        twitter_user = await twitter.request('GET', 'account/verify_credentials.json')
        twitter_userid = twitter_user['id_str']

        await Auth.create(id=str(ctx.author.id),
                          twitter_id=twitter_userid,
                          token=oauth_token,
                          secret=oauth_token_secret
                          )

        await ctx.author.send('登録が完了しました。')
        return True

    async def get(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        auth = await Auth.query.where(Auth.id == user_id).gino.first()

        return auth

    async def get_client(self, ctx: commands.Context):
        auth = await self.get(ctx)

        return get_client(auth.token, auth.secret)
