from bot import MyBot
import os
from os.path import join, dirname
from dotenv import load_dotenv
from cogs.utils.helpcommand import PaginatedHelpCommand

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


bot = MyBot('/', help_command=PaginatedHelpCommand())

extensions = [
    'cogs.manager',
    'cogs.webhook',
    'cogs.admin',
]


for extension in extensions:
    bot.load_extension(extension)


bot.run(os.environ.get('TOKEN'))
