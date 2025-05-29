import logging
import re
import sqlite3

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler
from handlers.givefamily_handler import GiveFamilyHandler

logger = logging.getLogger(__name__)

DB_NAME = 'sirius.db'


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
            conn = sqlite3.connect(DB_NAME)
            # Fetch all necessary columns, matching those in parse.py and used by the handler
            query = "SELECT Name, Age, Gender, Size, SkillsAndCharacter, MyStory, PhotoURL, Species, ProfileURL FROM animals"
            df = pd.read_sql_query(query, conn)
            conn.close()
        except sqlite3.Error as e:
            logging.error(f"Помилка при читанні з бази даних SQLite: {e}")
            if update.callback_query:
                await update.callback_query.message.reply_text("Помилка завантаження даних з бази.")
            # Fallback for non-callback updates, though less common for this handler
            elif update.message:
                await update.message.reply_text("Помилка завантаження даних з бази.")
            return
        except Exception as e:
            logging.error(f"Неочікувана помилка при завантаженні даних: {e}")
            if update.callback_query:
                await update.callback_query.message.reply_text("Неочікувана помилка завантаження даних.")
            elif update.message:
                await update.message.reply_text("Неочікувана помилка завантаження даних.")
            return

        species = context.user_data.get('species', 'all')
        df_filtered = df[df['Species'] == species] if species != 'all' else df
        # Ensure essential data for display is present
        df_filtered = df_filtered.dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])

        if df_filtered.empty:
            message_text = "Немає доступних тварин цього виду."
            if update.callback_query:
                # It's better to edit the message if it's a callback to avoid multiple messages
                await update.callback_query.edit_message_text(text=message_text)
            elif update.message:
                await update.message.reply_text(message_text)
            return

        index = context.user_data.get('pet_index', 0) % len(df_filtered)
        context.user_data['pet_index'] = index

        pet = df_filtered.iloc[index]

        pet_name = pet['Name']
        pet_gender = pet['Gender']
        pet_age = pet['Age']
        pet_story = pet['MyStory']
        pet_size = pet.get('Size', 'Невідомо')
        pet_skills = pet.get('SkillsAndCharacter', 'Немає інформації')
        pet_photo_path = pet['PhotoURL']  # Assumes PhotoURL is like 'photos/image.jpg'
        pet_profile_url = pet.get('ProfileURL', 'Немає посилання профілю')

        # --- Зберігаємо дані тваринки для GiveFamilyHandler ---
        context.user_data['current_pet_name'] = str(pet_name) if pd.notna(pet_name) else 'Невідоме ім\'я'
        context.user_data['current_pet_age'] = str(pet_age) if pd.notna(pet_age) else 'Невідомий вік'
        context.user_data['current_pet_url'] = pet_profile_url

        caption = (
            f"Ім'я: {escape_markdown_v2(pet_name)}\n"
            f"Вік: {escape_markdown_v2(pet_age)}\n"
            f"Гендер: {escape_markdown_v2(pet_gender)}\n"
            f"Розмір: {escape_markdown_v2(pet_size)}\n"
            f"Навички: {escape_markdown_v2(pet_skills)}\n\n"
            f"Моя Історія:\n>{escape_markdown_v2(
                pet_story if pet_story else 'Ця тваринка надто скромна, щоб розповідати про себе 😺')}")

        keyboard = [
            [
                InlineKeyboardButton('<<', callback_data='prev'),
                InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                InlineKeyboardButton('>>', callback_data='next')
            ],
            [InlineKeyboardButton('У головне меню', callback_data='menu')],
        ]

        # Delete previous message if it was a callback query to avoid clutter
        if update.callback_query:
            try:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )
            except Exception as e:
                logging.info(f"Could not delete previous message (NextPetHandler): {e}")

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
            logging.error(f"Файл з фото не знайдено: {pet_photo_path}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"На жаль, фото для {escape_markdown_v2(pet_name)} не знайдено\\. Спробуйте іншу тваринку\\.",
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logging.error(f"Помилка при відправці фото: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Виникла помилка при показі тваринки. Спробуйте ще раз."
            )
