import re
from io import BytesIO

import gspread
import pandas as pd
import requests
from gspread_dataframe import get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging # Додано логування

from handlers.base_handler import BaseHandler
from handlers.givefamily_handler import GiveFamilyHandler

logger = logging.getLogger(__name__) # Ініціалізація логера


def is_image_url_valid(url):
    try:
        # Додано timeout та перевірку status_code та content-type
        response = requests.head(url, timeout=5) # Використовуємо HEAD запит, він швидший
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        return 'image' in response.headers.get('Content-Type', '').lower()
    except requests.exceptions.RequestException as e:
        logger.error(f"Помилка при перевірці URL зображення: {e}")
        return False


def escape_markdown_v2(text: str) -> str:
    # Екранує спецсимволи MarkdownV2
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text)) # Додано str()


class PrevPetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('prev', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("sirius_key (2).json", scope)
        client = gspread.authorize(creds)

        try:
            spreadsheet = client.open_by_key("1bwx4LsiH2IFAxvQlZG3skYQSt_zti1yrynRfXlhwlPg")
            worksheet = spreadsheet.sheet1
        except Exception as e:
             logger.error(f"Помилка доступу до Google Sheets в PrevPetHandler: {e}")
             await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="На жаль, виникла проблема з доступом до даних тварин. Спробуйте пізніше.",
            )
             return

        df_full = get_as_dataframe(worksheet, evaluate_formulas=True)

        # Додаємо ProfileURL до обов'язкових стовпців для перевірки та читання
        required_columns = ['Name', 'Age', 'PhotoURL', 'MyStory', 'Size', 'SkillsAndCharacter', 'Species', 'ProfileURL']
        missing_columns = [col for col in required_columns if col not in df_full.columns]
        if missing_columns:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"У таблиці відсутні обов'язкові стовпці: {', '.join(missing_columns)}. Будь ласка, додайте їх.",
            )
            return

        species_filter = context.user_data.get('species', 'all')

        if species_filter == 'all':
            df_filtered = df_full.dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])
        elif species_filter == 'Кіт':
            df_filtered = df_full[df_full['Species'] == 'Кіт'].dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])
        elif species_filter == 'Пес':
            df_filtered = df_full[df_full['Species'] == 'Пес'].dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])
        else:
            # Якщо species_filter невідомий, можливо, це помилка або скидання фільтра
            df_filtered = df_full.dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])
            context.user_data['species'] = 'all'# Скидаємо фільтр

        if df_filtered.empty:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Немає доступних тварин цього виду.",
            )
            return

        current_index = context.user_data.get("pet_index", 0)
        prev_index = (current_index - 1) % len(df_filtered)
        context.user_data["pet_index"] = prev_index

        pet = df_filtered.iloc[prev_index]

        pet_name = pet['Name']
        pet_story = pet['MyStory']
        pet_age = pet['Age']

        pet_size = pet['Size'] if pd.notna(pet['Size']) else 'Невідомо' # Використовуємо pd.notna
        pet_skills_character = pet['SkillsAndCharacter'] if pd.notna(pet['SkillsAndCharacter']) else 'Немає інформації' # Використовуємо pd.notna
        pet_image_url = pet['PhotoURL']
        pet_profile_url = pet.get('ProfileURL', 'N/A')  # або pet.get(...)

        print(f"DEBUG (File: {__file__}): Значення ProfileURL, прочитане з таблиці: {pet_profile_url}")
        context.user_data['current_pet_url'] = pet_profile_url
        print(
            f"DEBUG (File: {__file__}): Значення, збережене у context.user_data['current_pet_url']: {context.user_data.get('current_pet_url', 'КЛЮЧ current_pet_url НЕ ЗНАЙДЕНО')}")


        if not is_image_url_valid(pet_image_url):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Неможливо завантажити зображення для тварини '{pet_name}'.",
            )
            return


        try:
            image_response = requests.get(pet_image_url)
            image_response.raise_for_status()
            image = BytesIO(image_response.content)
            image.name = 'pet_image.jpg'

            caption = (
                f"Ім'я: {escape_markdown_v2(pet_name)}\n"
                f"Вік: {escape_markdown_v2(pet_age)}\n"
                f"Розмір: {escape_markdown_v2(pet_size)}\n"
                f"Навички та характер: {escape_markdown_v2(pet_skills_character)}\n\n"
                f"Моя історія:\n> {escape_markdown_v2(pet_story)}"
            )

            keyboard = [
                [
                    InlineKeyboardButton('<<', callback_data='prev'),
                    InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                    InlineKeyboardButton('>>', callback_data='next')
                ],
                [InlineKeyboardButton('У головне меню', callback_data='menu')],
            ]

            if update.callback_query:
                # Намагаємося видалити попереднє повідомлення
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
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Помилка при скачуванні зображення або відправці фото: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"На жаль, виникла помилка при завантаженні фото тварини або відправці повідомлення. Спробуйте пізніше.",
            )
        except Exception as e:
             logger.error(f"An unexpected error occurred in PrevPetHandler.callback: {e}")
             await context.bot.send_message(
                 chat_id=update.effective_chat.id,
                 text="Виникла неочікувана помилка. Будь ласка, спробуйте пізніше.",
            )