import asyncio
import base64
import datetime

import aiohttp
import discord

from cogs.utils.database import *
from cogs.utils.twitter import get_client

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
        for _user in await NewUser.query.gino.all():
            user = await TwitterUser.query.where(TwitterUser.uuid == _user.uuid).gino.first()
            if not user:
                continue
            auth = await Auth.query.where(Auth.id == user.discord_user_id).gino.first()
            twitter = get_client(token=auth.token, secret=auth.secret)
            loop.create_task(check_twitter(user, twitter))
            await _user.delete()


async def wait_new_day():
    now = datetime.datetime.now()
    new_day = datetime.datetime(year=now.year, month=now.month, day=now.day) + datetime.timedelta(days=1)
    print(new_day.timestamp() - now.timestamp())
    await asyncio.sleep(new_day.timestamp() - now.timestamp())
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
        try:
            twitter_user: TwitterUser = await TwitterUser.query.where(TwitterUser.webhook_id == webhook.id) \
                .where(TwitterUser.id == twitter_user.id) \
                .where(TwitterUser.state == 1).gino.first()
            if not twitter_user:
                break

            if last_id:
                params['since_id'] = last_id

            if not twitter_user.reply:
                params['exclude_replies'] = 'true'
            else:
                params['exclude_replies'] = 'false'

            r = await twitter.request('GET', 'statuses/user_timeline.json', params=params)
            for tweet in r[::-1]:
                if tweet['retweeted']:
                    if not twitter_user.retweet:
                        continue
                else:
                    if not twitter_user.normal:
                        continue

                if not twitter_user.text:
                    loop.create_task(send_webhook(webhook_url, 'テキストが設定されていないため、表示することができませんでした。'
                                                               '管理人は設定をお願いします。'))
                    print(f'webhook {webhook.id} is failed')
                    continue

                text = replace_ifttt(twitter_user.text, tweet)
                loop.create_task(send_webhook(webhook_url, text))
            params['count'] = 20
            if r:
                last_id = r[0]['id']
        except Exception:
            import traceback
            traceback.print_exc()


async def check_search(search: Search, twitter):
    last_id = None
    q = search.text
    webhook = await Webhook.query.where(Webhook.id == search.webhook_id).gino.first()
    webhook_url = 'https://discordapp.com/api/webhooks/{0.id}/{0.token}'.format(webhook)
    params = {'q': q,
              'lang': 'ja',
              'result_type': 'recent',
              'count': 40,
              }
    r = await twitter.request('GET', 'search/tweets.json', params=params)
    if r:
        last_id = r[0]['id']
    while not loop.is_closed():
        await asyncio.sleep(search.period)
        try:
            search = await Search.query.where(Search.uuid == search.uuid).gino.first()
            if not search:
                break

            if last_id:
                params['since_id'] = last_id

            r = await twitter.request('GET', 'search/tweets.json', params=params)

            for tweet in r[::-1]:
                text = get_tweet_link(tweet)
                loop.create_task(send_webhook(webhook_url, text))

            if r:
                last_id = r[0]['id']


        except Exception:
            import traceback
            traceback.print_exc()


async def main():
    await db.set_bind('postgresql://localhost/twihook')
    await db.gino.create_all()
    for _user in await NewUser.query.gino.all():
        await _user.delete()

    twitter_users = await TwitterUser.query.gino.all()
    for user in twitter_users:
        auth = await Auth.query.where(Auth.id == user.discord_user_id).gino.first()
        twitter = get_client(token=auth.token, secret=auth.secret)
        loop.create_task(check_twitter(user, twitter))
    searches = await Search.query.gino.all()
    for s in searches:
        auth = await Auth.query.where(Auth.id == s.discord_user_id).gino.first()
        twitter = get_client(token=auth.token, secret=auth.secret)
        loop.create_task(check_search(s, twitter))

    loop.create_task(check_new_user())
    loop.create_task(wait_new_day())

    await event.wait()
    loop.stop()
    loop.close()


if __name__ == '__main__':
    loop.run_until_complete(main())
