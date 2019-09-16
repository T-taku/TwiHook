from aioauth_client import TwitterClient
import os
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '../../.env')
load_dotenv(dotenv_path)


def get_client_not_oauth():
    twitter = TwitterClient(
        consumer_key=os.environ.get('TWITTER_KEY'),
        consumer_secret=os.environ.get('TWITTER_SECRET'),
    )
    return twitter


def get_client(token, secret):
    twitter = TwitterClient(
        consumer_key=os.environ.get('TWITTER_KEY'),
        consumer_secret=os.environ.get('TWITTER_SECRET'),
        oauth_token=token,
        oauth_token_secret=secret,
    )
    return twitter

