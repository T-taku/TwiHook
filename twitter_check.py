from cogs.utils.database import *
from cogs.utils.twitter import get_client
import asyncio
import aiohttp
import discord
import datetime
import base64
import os
loop = asyncio.get_event_loop()
event = asyncio.Event()


def frombase64(text):
    text = text.encode()
    return base64.b64decode(text).decode()


def get_tweet_link(tweet):
    return f'https://twitter.com/{tweet["user"]["screen_name"]}/status/{tweet["id"]}'


def replace_ifttt(text, tweet):
    replaces = {
        '{{UserName}}': tweet['user']['name'],
        '{{ScreenName}}': tweet['user']['screen_name'],
        '{{Text}}': tweet['text'],
        '{{LinkToTweet}}': get_tweet_link(tweet),
        '{{CreatedAt}}': tweet['created_at']
    }
    text = frombase64(text)
    for key, value in replaces.items():
        text = text.replace(key, value)

    return text


async def check_new_user():
    while not loop.is_closed():
        await asyncio.sleep(60)
        with open('waiting.txt') as f:
            for line in f.read().split('\n'):
                webhook_id, twitter_id = line.split()
                user = await TwitterUser.query.where(TwitterUser.id == twitter_id)\
                    .where(TwitterUser.webhook_id == webhook_id).gino.first()
                auth = await Auth.query.where(Auth.id == user.discord_user_id).gino.first()
                twitter = get_client(token=auth.token, secret=auth.secret)
                loop.create_task(check_twitter(user, twitter))
        os.remove('waiting.txt')


async def wait_new_day():
    now_stamp = datetime.datetime.now().timestamp()
    new_day = datetime.datetime.today().timestamp() + 86400
    await asyncio.sleep(new_day - now_stamp)
    event.set()


async def send_webhook(webhook_url, text):
    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(webhook_url, adapter=discord.AsyncWebhookAdapter(session))
            await webhook.send(content=text)
    except Exception:
        pass


async def check_twitter(twitter_user: TwitterUser, twitter):
    webhook = await Webhook.query.where(Webhook.id == twitter_user.webhook_id).gino.first()
    webhook_url = 'https://discordapp.com/api/webhooks/{0.id}/{0.token}'.format(webhook)
    params = {'user_id': int(twitter_user.id), 'count': 20, 'exclude_replies': 'false'}
    r = await twitter.request('GET', 'statuses/user_timeline.json', params=params)
    if r:
        last_id = r[0]['id']
    else:
        last_id = None
        params['count'] = 1
    while not loop.is_closed():
        await asyncio.sleep(twitter_user.period * 60)
        if last_id:
            params['since_id'] = last_id
        try:
            r = await twitter.request('GET', 'statuses/user_timeline.json', params=params)
        except Exception:
            raise
        for tweet in r[::-1]:
            if tweet['retweeted']:
                continue
            text = replace_ifttt(twitter_user.text, tweet)
            loop.create_task(send_webhook(webhook_url, text))

        last_id = r[0]['id']
        params['count'] = 20


async def main():
    await db.set_bind('postgresql://localhost/twihook')
    await db.gino.create_all()
    twitter_users = await TwitterUser.query.gino.all()
    for user in twitter_users:
        auth = await Auth.query.where(Auth.id == user.discord_user_id).gino.first()
        twitter = get_client(token=auth.token, secret=auth.secret)
        loop.create_task(check_twitter(user, twitter))

    await event.wait()
    loop.stop()
    loop.close()


if __name__ == '__main__':
    loop.run_until_complete(main())
