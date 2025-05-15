import re
from io import BytesIO

import gspread
import pandas as pd
import requests
from gspread_dataframe import get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler
from handlers.givefamily_handler import GiveFamilyHandler


def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)


class DogHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('dog', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("sirius_key (2).json", scope)
        client = gspread.authorize(creds)

        spreadsheet = client.open_by_key("1bwx4LsiH2IFAxvQlZG3skYQSt_zti1yrynRfXlhwlPg")
        worksheet = spreadsheet.sheet1

        df1 = get_as_dataframe(worksheet, evaluate_formulas=True)

        print("Стовпці таблиці:", df1.columns)

        required_columns = ['Name', 'Age', 'PhotoURL', 'MyStory', 'Species', 'Size', 'SkillsAndCharacter']
        missing_columns = [col for col in required_columns if col not in df1.columns]
        if missing_columns:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"У таблиці відсутні необхідні стовпці: {', '.join(missing_columns)}.",
            )
            return

        df = df1[df1['Species'] == 'Пес']

        random_pet = df.sample(n=1).iloc[0]
        pet_name = random_pet['Name']
        pet_age = random_pet['Age']
        pet_size = random_pet['Size']
        pet_skills_character = random_pet['SkillsAndCharacter']
        pet_story = random_pet['MyStory']
        pet_image_url = random_pet['PhotoURL']

        if pd.isna(pet_story):
            pet_story = "Історія не доступна."
        if pd.isna(pet_size):
            pet_size = "Невідомо"
        if pd.isna(pet_skills_character):
            pet_skills_character = "Не вказано"

        try:
            image_response = requests.get(pet_image_url)
            image_response.raise_for_status()

            image = BytesIO(image_response.content)
            image.name = 'pet_image.jpg'

            caption = (
                f"Ім'я: {escape_markdown_v2(str(pet_name))}\n"
                f"Вік: {escape_markdown_v2(str(pet_age))}\n"
                f"Розмір: {escape_markdown_v2(str(pet_size))}\n"
                f"Навички та характер: {escape_markdown_v2(str(pet_skills_character))}\n\n"
                f"Моя історія:\n> {escape_markdown_v2(str(pet_story))}"
            )

            keyboard = [
                [
                    InlineKeyboardButton('<<', callback_data='prev'),
                    InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                    InlineKeyboardButton('>>', callback_data='next')
                ],
                [InlineKeyboardButton('У головне меню', callback_data='menu')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if update.callback_query and update.callback_query.data != 'givefamily':
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )

            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image,
                caption=caption,
                parse_mode='MarkdownV2',
                reply_markup=reply_markup
            )

        except requests.exceptions.RequestException as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Помилка при скачуванні зображення: {e}",
            )
