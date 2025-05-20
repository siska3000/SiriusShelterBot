import os

from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN1_ID = os.getenv('ADMIN1_ID')
ADMIN2_ID = os.getenv('ADMIN2_ID')

