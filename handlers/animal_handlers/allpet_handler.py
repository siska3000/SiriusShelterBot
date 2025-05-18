import logging
import re
from io import BytesIO

import gspread
import pandas as pd  # Переконайтесь, що pandas імпортовано
import requests
from gspread_dataframe import get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler
from handlers.givefamily_handler import GiveFamilyHandler

logger = logging.getLogger(__name__)


def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))  # Додано str() на випадок, якщо дані не текстові


class AllpetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('allpets', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

        # 1. Авторизація через JSON-файл ключа
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("sirius_key (2).json", scope)
        client = gspread.authorize(creds)

        try:
            spreadsheet = client.open_by_key("1bwx4LsiH2IFAxvQlZG3skYQSt_zti1yrynRfXlhwlPg")
            worksheet = spreadsheet.sheet1  # або назва аркуша: spreadsheet.worksheet("Назва аркуша")
        except Exception as e:
            logger.error(f"Помилка доступу до Google Sheets в AllpetHandler: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="На жаль, виникла проблема з доступом до даних тварин. Спробуйте пізніше.",
            )
            return

        # Додаємо ProfileURL, Name, Age до обов'язкових стовпців для перевірки та читання
        required_columns_for_df = [
            'Name',
            'Age',
            'PhotoURL',
            'MyStory',
            'Size',
            'SkillsAndCharacter',
            'Species',
            'ProfileURL'
        ]
        # Вибираємо тільки ці стовпці та видаляємо рядки, де ключові поля (Name, Age, PhotoURL, MyStory) порожні
        df = get_as_dataframe(worksheet, evaluate_formulas=True)  # Читаємо всю таблицю спочатку

        # Перевірка наявності необхідних стовпців
        missing_columns = [col for col in required_columns_for_df if col not in df.columns]

        if missing_columns:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"У таблиці відсутні необхідні стовпці: {', '.join(missing_columns)}. Будь ласка, додайте їх.",
            )
            return

        # Фільтруємо та видаляємо рядки з відсутніми ключовими даними після перевірки стовпців
        df = df.dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])

        if df.empty:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Наразі немає доступних тварин для показу.",
            )
            return

        # Вибір випадкової тварини
        random_pet = df.sample(n=1).iloc[0]
        pet_name = random_pet['Name']
        pet_age = random_pet['Age']
        pet_size = random_pet['Size']
        pet_skills_character = random_pet['SkillsAndCharacter']
        pet_story = random_pet['MyStory']
        pet_image_url = random_pet['PhotoURL']
        pet_profile_url = random_pet.get('ProfileURL', 'N/A')  # Отримуємо ProfileURL

        # --- Зберігаємо дані тваринки для GiveFamilyHandler ---
        context.user_data['current_pet_name'] = str(pet_name) if pd.notna(pet_name) else 'Невідоме ім\'я'
        context.user_data['current_pet_age'] = str(pet_age) if pd.notna(pet_age) else 'Невідомий вік'
        context.user_data['current_pet_url'] = pet_profile_url

        if pd.isna(pet_story):
            pet_story = "Історія не доступна."
        if pd.isna(pet_size):
            pet_size = "Розмір не вказано."
        if pd.isna(pet_skills_character):
            pet_skills_character = "Навички та характер не описано."

        # Скачування зображення
        try:
            image_response = requests.get(pet_image_url)
            image_response.raise_for_status()

            image = BytesIO(image_response.content)
            image.name = 'pet_image.jpg'

            # Екрануємо текст для MarkdownV2
            caption = (
                f"Ім'я: {escape_markdown_v2(pet_name)}\n"
                f"Вік: {escape_markdown_v2(pet_age)}\n"
                f"Розмір: {escape_markdown_v2(pet_size)}\n"
                f"Навички та характер: {escape_markdown_v2(pet_skills_character)}\n\n"
                f"Моя історія:\n>{escape_markdown_v2(pet_story)}"
            )

            keyboard = [
                [
                    InlineKeyboardButton('<<', callback_data='prev'),
                    InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                    InlineKeyboardButton('>>', callback_data='next')
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

        except requests.exceptions.RequestException as e:
            logger.error(f"Помилка при скачуванні зображення або відправці фото: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"На жаль, виникла помилка при завантаженні фото тваринки або відправці повідомлення. Спробуйте пізніше.",
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred in AllpetHandler.callback: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Виникла неочікувана помилка. Будь ласка, спробуйте пізніше.",
            )
