import logging  # Додано логування
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

logger = logging.getLogger(__name__)  # Ініціалізація логера


def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))  # Додано str()


class CatHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('cat', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

        # 1. Авторизація через JSON-файл ключа
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("sirius_key (2).json", scope)
        client = gspread.authorize(creds)

        try:
            # 2. Підключення до таблиці по ключу
            spreadsheet = client.open_by_key("1bwx4LsiH2IFAxvQlZG3skYQSt_zti1yrynRfXlhwlPg")
            worksheet = spreadsheet.sheet1
        except Exception as e:
            logger.error(f"Помилка доступу до Google Sheets в CatHandler: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="На жаль, виникла проблема з доступом до даних тварин. Спробуйте пізніше.",
            )
            return

        # 3. Зчитування у pandas DataFrame
        df1 = get_as_dataframe(worksheet, evaluate_formulas=True)

        # Додаємо ProfileURL до обов'язкових стовпців для перевірки та читання
        required_columns = [
            'Name',
            'Age',
            'PhotoURL',
            'MyStory',
            'Species'
            'Size',
            'SkillsAndCharacter',
            'ProfileURL'
        ]
        missing_columns = [col for col in required_columns if col not in df1.columns]
        if missing_columns:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"У таблиці відсутні необхідні стовпці: {', '.join(missing_columns)}. Будь ласка, додайте їх.",
            )
            return

        # Фільтруємо за видом та видаляємо рядки з відсутніми ключовими даними
        df = df1[df1['Species'] == 'Кіт'].dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])

        if df.empty:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Наразі немає доступних котів для показу.",
            )
            return

        random_pet = df.sample(n=1).iloc[0]
        pet_name = random_pet['Name']
        pet_age = random_pet['Age']
        pet_size = random_pet['Size']
        pet_skills_character = random_pet['SkillsAndCharacter']
        pet_story = random_pet['MyStory']
        pet_image_url = random_pet['PhotoURL']
        pet_profile_url = random_pet.get('ProfileURL', 'N/A')  # або pet.get(...)

        # --- Зберігаємо дані тваринки для GiveFamilyHandler ---
        context.user_data['current_pet_name'] = str(pet_name) if pd.notna(pet_name) else 'Невідоме ім\'я'
        context.user_data['current_pet_age'] = str(pet_age) if pd.notna(pet_age) else 'Невідомий вік'
        context.user_data['current_pet_url'] = pet_profile_url

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
                f"Моя історія:\n>{escape_markdown_v2(str(pet_story))}"
            )

            keyboard = [
                [
                    InlineKeyboardButton('<<', callback_data='prev'),  # prev/next потребуватимуть фільтрації за видом
                    InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                    InlineKeyboardButton('>>', callback_data='next')  # prev/next потребуватимуть фільтрації за видом
                ],
                [InlineKeyboardButton('Назад', callback_data='watchpet')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if update.callback_query and update.callback_query.data != 'givefamily':
                try:
                    await context.bot.delete_message(
                        chat_id=update.callback_query.message.chat_id,
                        message_id=update.callback_query.message.message_id
                    )
                except Exception as e:
                    logger.error(f"Failed to delete message: {e}")

            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image,
                caption=caption,
                parse_mode='MarkdownV2',
                reply_markup=reply_markup
            )

            # Зберігаємо поточний фільтр виду тварини для prev/next
            context.user_data['species'] = 'Кіт'


        except requests.exceptions.RequestException as e:
            logger.error(f"Помилка при скачуванні зображення або відправці фото: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"На жаль, виникла помилка при завантаженні фото тваринки або відправці повідомлення. Спробуйте пізніше.",
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred in CatHandler.callback: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Виникла неочікувана помилка. Будь ласка, спробуйте пізніше.",
            )
