import json
import logging
import re
import pandas as pd
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler
from handlers.givefamily_handler import GiveFamilyHandler

logger = logging.getLogger(__name__)


def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))


class NextPetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('next', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        current_index = context.user_data.get('pet_index', -1)
        context.user_data['pet_index'] = current_index + 1
        await NextPetHandler.show_pet(update, context)

    @staticmethod
    async def show_pet(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            with open('google_sheet_data_updated.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
        except Exception as e:
            logging.error(f"Помилка при читанні JSON: {e}")
            await update.message.reply_text("Помилка завантаження даних.")
            return

        species = context.user_data.get('species', 'all')
        df_filtered = df[df['Species'] == species] if species != 'all' else df
        df_filtered = df_filtered.dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])

        if df_filtered.empty:
            await update.message.reply_text("Немає доступних тварин цього виду.")
            return

        index = context.user_data.get('pet_index', 0) % len(df_filtered)
        context.user_data['pet_index'] = index

        pet = df_filtered.iloc[index]

        pet_name = pet['Name']
        pet_age = pet['Age']
        pet_story = pet['MyStory']
        pet_size = pet.get('Size', 'Невідомо')
        pet_skills = pet.get('SkillsAndCharacter', 'Немає інформації')
        pet_photo_path = pet['PhotoURL']
        pet_profile_url = pet.get('ProfileURL', 'Немає посилання профілю')

        # --- Зберігаємо дані тваринки для GiveFamilyHandler ---
        context.user_data['current_pet_name'] = str(pet_name) if pd.notna(pet_name) else 'Невідоме ім\'я'
        context.user_data['current_pet_age'] = str(pet_age) if pd.notna(pet_age) else 'Невідомий вік'
        context.user_data['current_pet_url'] = pet_profile_url

        caption = (
            f"Ім'я: {escape_markdown_v2(pet_name)}\n"
            f"Вік: {escape_markdown_v2(pet_age)}\n"
            f"Розмір: {escape_markdown_v2(pet_size)}\n"
            f"Навички: {escape_markdown_v2(pet_skills)}\n\n"
            f"Історія:\n> {escape_markdown_v2(pet_story)}"
        )

        keyboard = [
            [
                InlineKeyboardButton('<<', callback_data='prev'),
                InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                InlineKeyboardButton('>>', callback_data='next')
            ],
            [InlineKeyboardButton('У головне меню', callback_data='menu')],
        ]

        try:
            with open(pet_photo_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo,
                    caption=caption,
                    parse_mode='MarkdownV2',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except FileNotFoundError:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Файл з фото не знайдено: {pet_photo_path}",
            )
