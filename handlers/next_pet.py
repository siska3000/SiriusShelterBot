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


def is_image_url_valid(url):
    try:
        response = requests.get(url)
        return response.status_code == 200 and 'image' in response.headers['Content-Type']
    except requests.exceptions.RequestException as e:
        print(f"Помилка при перевірці URL: {e}")
        return False


def escape_markdown_v2(text: str) -> str:
    # Екранує спецсимволи MarkdownV2
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))


class NextPetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('next', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("sirius_key (2).json", scope)
        client = gspread.authorize(creds)

        spreadsheet = client.open_by_key("1bwx4LsiH2IFAxvQlZG3skYQSt_zti1yrynRfXlhwlPg")
        worksheet = spreadsheet.sheet1
        df = get_as_dataframe(worksheet, evaluate_formulas=True).dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])

        required_columns = ['Name', 'Age', 'PhotoURL', 'MyStory', 'Size', 'SkillsAndCharacter', 'Species']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"У таблиці відсутні обов'язкові стовпці: {', '.join(missing_columns)}.",
            )
            return

        species_filter = context.user_data.get('species', 'all')

        if species_filter == 'all':
            df_filtered = df
        elif species_filter == 'Кіт':
            df_filtered = df[df['Species'] == 'Кіт']
        elif species_filter == 'Пес':
            df_filtered = df[df['Species'] == 'Пес']
        else:
            df_filtered = pd.DataFrame()

        if df_filtered.empty:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Немає доступних тварин цього виду.",
            )
            return

        current_index = context.user_data.get("pet_index", -1)  # стартуємо з -1, бо next буде 0
        next_index = (current_index + 1) % len(df_filtered)
        context.user_data["pet_index"] = next_index

        pet = df_filtered.iloc[next_index]

        pet_name = pet['Name']
        pet_story = pet['MyStory']
        pet_age = pet['Age']

        pet_size = pet['Size'] if not pd.isna(pet['Size']) else 'Невідомо'
        pet_skills_character = pet['SkillsAndCharacter'] if not pd.isna(
            pet['SkillsAndCharacter']) else 'Немає інформації'
        pet_image_url = pet['PhotoURL']

        if not is_image_url_valid(pet_image_url):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Неможливо завантажити зображення для цієї тварини.",
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
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )

            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image,
                caption=caption,
                parse_mode='MarkdownV2',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except requests.exceptions.RequestException as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Помилка при скачуванні зображення: {e}",
            )
