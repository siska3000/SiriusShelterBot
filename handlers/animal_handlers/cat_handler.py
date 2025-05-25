import logging
import os
import re
import sqlite3  # Added

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler
from handlers.givefamily_handler import GiveFamilyHandler

logger = logging.getLogger(__name__)  # Added logger instance

DB_NAME = 'sirius.db'  # Added


def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))


def truncate_text(text: str, max_length: int) -> str:
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text


class CatHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('cat', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info("CatHandler callback triggered")

        try:
            conn = sqlite3.connect(DB_NAME)
            # Fetch all necessary columns
            query = "SELECT Name, Age, Gender, Size, SkillsAndCharacter, MyStory, PhotoURL, Species, ProfileURL FROM animals"
            df = pd.read_sql_query(query, conn)
            conn.close()
        except sqlite3.Error as e:
            logging.error(f"Помилка при читанні з бази даних SQLite: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Помилка завантаження даних з бази."
            )
            return
        except Exception as e:
            logging.error(f"Неочікувана помилка при завантаженні даних: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Неочікувана помилка завантаження даних."
            )
            return

        required_columns_db = ['Name', 'Age', 'PhotoURL', 'MyStory', 'Species',
                               'ProfileURL']  # Size, SkillsAndCharacter are handled with .get()
        missing_columns = [col for col in required_columns_db if col not in df.columns]

        if missing_columns:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"У базі даних відсутні необхідні стовпці: {', '.join(missing_columns)}. Будь ласка, перевірте дані.",
            )
            return

        df = df.dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])
        df_cats = df[df['Species'] == 'Кіт']  # for species name

        if df_cats.empty:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Наразі немає доступних котів для показу.",
            )
            return

        random_pet = df_cats.sample(n=1).iloc[0]

        pet_name = random_pet['Name']
        pet_age = random_pet['Age']
        pet_story_original = random_pet['MyStory']
        pet_size = random_pet.get('Size', 'Розмір не вказано.')
        pet_skills_character = random_pet.get('SkillsAndCharacter', 'Навички та характер не описано.')
        pet_profile_url = random_pet.get('ProfileURL', 'Немає посилання профілю')

        # Use PhotoURL directly as it's stored like 'photos/filename.jpg'
        pet_photo_path = random_pet['PhotoURL']

        logging.info(f"Шлях до фото: {pet_photo_path}")
        logging.info(f"Файл існує? {os.path.isfile(pet_photo_path)}")

        # --- Зберігаємо дані тваринки для GiveFamilyHandler ---
        context.user_data['current_pet_name'] = str(pet_name) if pd.notna(pet_name) else 'Невідоме ім\'я'
        context.user_data['current_pet_age'] = str(pet_age) if pd.notna(pet_age) else 'Невідомий вік'
        context.user_data['current_pet_url'] = pet_profile_url

        caption_parts = [
            f"Ім'я: {escape_markdown_v2(pet_name)}",
            f"Вік: {escape_markdown_v2(pet_age)}",
            f"Розмір: {escape_markdown_v2(pet_size)}",
            f"Навички та характер: {escape_markdown_v2(pet_skills_character)}",
        ]

        base_caption_text = "\n".join(caption_parts) + "\n\nМоя історія:\n>"
        max_story_length = 1024 - len(base_caption_text) - 50

        pet_story_escaped = escape_markdown_v2(pet_story_original)
        truncated_story = truncate_text(pet_story_escaped, max_story_length)
        caption = base_caption_text + truncated_story

        if len(caption) > 1024:  # Final check
            caption = truncate_text(caption, 1024)

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
            try:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )
            except Exception as e:
                logging.info(f"Не вдалося видалити повідомлення (CatHandler): {e}")

        try:
            with open(pet_photo_path, 'rb') as image_file:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=image_file,
                    caption=caption,
                    parse_mode='MarkdownV2',
                    reply_markup=reply_markup
                )
        except FileNotFoundError:  # Should be caught earlier, but as a safeguard
            logging.error(f"Файл з фото не знайдено під час відправки: {pet_photo_path}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"На жаль, фото для {escape_markdown_v2(pet_name)} не вдалося відправити\\. Спробуйте іншу тваринку\\.",
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logging.error(f"Несподівана помилка при відправці фото в CatHandler: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
            )
