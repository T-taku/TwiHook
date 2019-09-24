from gino import Gino
db = Gino()


class Auth(db.Model):
    __tablename__ = 'auth'

    id = db.Column(db.String(80), primary_key=True)
    twitter_id = db.Column(db.String(80))
    token = db.Column(db.String(100))
    secret = db.Column(db.String(100))


class Webhook(db.Model):
    __tablename__ = 'webhook'
    id = db.Column(db.String(100))
    token = db.Column(db.String(100))
    discord_user_id = db.Column(db.String(100))
    uuid = db.Column(db.String(100), primary_key=True)


class TwitterUser(db.Model):
    __tablename__ = 'twitter'
    id = db.Column(db.String(100))
    webhook_id = db.Column(db.String(100))
    discord_user_id = db.Column(db.String(100))
    text = db.Column(db.String(20000), default='')
    period = db.Column(db.Integer, default=10)
    state = db.Column(db.Integer, default=1)
    normal = db.Column(db.Integer, default=1)
    reply = db.Column(db.Integer, default=0)
    retweet = db.Column(db.Integer, default=0)
    uuid = db.Column(db.String(100), primary_key=True)


class Search(db.Model):
    __tablename__ = 'twitter_search'
    query = db.Column(db.String(2000))
    webhook_id = db.Column(db.String(100))
    discord_user_id = db.Column(db.String(100))
    text = db.Column(db.String(20000), default='')
    period = db.Column(db.Integer, default=10)
    state = db.Column(db.Integer, default=1)
    uuid = db.Column(db.String(100), primary_key=True)


class Subscription(db.Model):
    __tablename__ = 'subscription'
    id = db.Column(db.String(80), primary_key=True)
    is_special = db.Column(db.Integer, default=0)
    residue = db.Column(db.Integer, default=0)
    max = db.Column(db.Integer, default=0)


class NewUser(db.Model):
    __tablename__ = 'newuser'
    uuid = db.Column(db.String(100), primary_key=True)


class NewSearch(db.Model):
    __tablename__ = 'newsearch'
    uuid = db.Column(db.String(100), primary_key=True)
