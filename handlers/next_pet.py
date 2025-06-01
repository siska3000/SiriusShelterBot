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
MAX_CAPTION_LENGTH = 1024  # ✅ ДОДАНО — ліміт Telegram на caption


def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))


# ✅ ДОДАНО — функція, яка обрізає caption до 1024 символів
def build_caption(pet_name, pet_age, pet_gender, pet_size, pet_skills, pet_story):
    def esc(text):
        return escape_markdown_v2(text if pd.notna(text) else 'Невідомо')

    base_caption = (
        f"Ім'я: {esc(pet_name)}\n"
        f"Вік: {esc(pet_age)}\n"
        f"Гендер: {esc(pet_gender)}\n"
        f"Розмір: {esc(pet_size)}\n"
        f"Навички: {esc(pet_skills)}\n\n"
        f"Моя Історія:\n>"
    )

    remaining_length = MAX_CAPTION_LENGTH - len(base_caption)

    story_text = pet_story
    if story_text:
        # Обрізати сирий текст до ліміту, з запасом під три крапки
        if len(story_text) > remaining_length:
            story_text = story_text[:remaining_length - 3] + "..."
    else:
        story_text = 'Ця тваринка надто скромна, щоб розповідати про себе 😺'

    escaped_story = escape_markdown_v2(story_text)

    return base_caption + escaped_story


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
            query = "SELECT Name, Age, Gender, Size, SkillsAndCharacter, MyStory, PhotoURL, Species, ProfileURL FROM animals"
            df = pd.read_sql_query(query, conn)
            conn.close()
        except sqlite3.Error as e:
            logging.error(f"Помилка при читанні з бази даних SQLite: {e}")
            if update.callback_query:
                await update.callback_query.message.reply_text("Помилка завантаження даних з бази.")
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
        df_filtered = df_filtered.dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])

        if df_filtered.empty:
            message_text = "Немає доступних тварин цього виду."
            if update.callback_query:
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
        pet_photo_path = pet['PhotoURL']
        pet_profile_url = pet.get('ProfileURL', 'Немає посилання профілю')

        context.user_data['current_pet_name'] = str(pet_name) if pd.notna(pet_name) else 'Невідоме ім\'я'
        context.user_data['current_pet_age'] = str(pet_age) if pd.notna(pet_age) else 'Невідомий вік'
        context.user_data['current_pet_url'] = pet_profile_url

        caption = build_caption(pet_name, pet_age, pet_gender, pet_size, pet_skills,
                                pet_story)  # 🔧 ЗМІНЕНО: використовуємо функцію
        logging.info(f"Caption length: {len(caption)}")  # ✅ ДОДАНО: діагностика довжини caption

        keyboard = [
            [
                InlineKeyboardButton('<<', callback_data='prev'),
                InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                InlineKeyboardButton('>>', callback_data='next')
            ],
            [InlineKeyboardButton('У головне меню', callback_data='menu')],
        ]

        if update.callback_query:
            try:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )
            except Exception as e:
                logging.info(f"Could not delete previous message (NextPetHandler): {e}")
        logging.info(f"Ім'я тварини: {pet_name}")
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
            text_message = (
                f"Не вдалося завантажити фото для {escape_markdown_v2(pet_name)}, але ось інформація:\n\n"
                f"{caption}\n\n"
                f"[Посилання на профіль]({pet_profile_url})" if pd.notna(pet_profile_url) else ""
            )

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text_message,
                parse_mode='MarkdownV2',
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )
