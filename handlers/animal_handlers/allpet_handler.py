import json
import logging
import os
import re

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler
from handlers.givefamily_handler import GiveFamilyHandler

# Очищення попередніх обробників логів
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# Екранування MarkdownV2
def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))


# Скорочення тексту
def truncate_text(text: str, max_length: int) -> str:
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text


class AllpetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('allpets', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info("AllpetHandler callback triggered")

        try:
            # Читання з локального JSON-файлу
            with open('google_sheet_data_updated.json', 'r', encoding='utf-8') as f:
                data = json.load(f)

            df = pd.DataFrame(data)

            required_columns = ['Name', 'Age', 'PhotoURL', 'MyStory', 'Size', 'SkillsAndCharacter', 'Species',
                                'ProfileURL']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"У таблиці відсутні необхідні стовпці: {', '.join(missing_columns)}. Будь ласка, додайте їх.",
                )
                return

            df = df.dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])
            if df.empty:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Наразі немає доступних тварин для показу.",
                )
                return

            random_pet = df.sample(n=1).iloc[0]
            pet_name = random_pet['Name']
            pet_age = random_pet['Age']
            pet_story_original = random_pet['MyStory']
            pet_size = random_pet.get('Size', 'Розмір не вказано.')
            pet_skills_character = random_pet.get('SkillsAndCharacter', 'Навички та характер не описано.')
            pet_profile_url = random_pet.get('ProfileURL', 'Немає посилання профілю')

            # Обробка шляху до фото
            BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            pet_photo_path = os.path.join(BASE_DIR, random_pet['PhotoURL'])

            logging.info(f"Шлях до фото: {pet_photo_path}")
            logging.info(f"Файл існує? {os.path.isfile(pet_photo_path)}")

            # --- Зберігаємо дані тваринки для GiveFamilyHandler ---
            context.user_data['current_pet_name'] = str(pet_name) if pd.notna(pet_name) else 'Невідоме ім\'я'
            context.user_data['current_pet_age'] = str(pet_age) if pd.notna(pet_age) else 'Невідомий вік'
            context.user_data['current_pet_url'] = pet_profile_url

            if not os.path.isfile(pet_photo_path):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Фото для тварини '{pet_name}' не знайдено локально.",
                )
                return

            caption_parts = [
                f"Ім'я: {escape_markdown_v2(pet_name)}",
                f"Вік: {escape_markdown_v2(pet_age)}",
                f"Розмір: {escape_markdown_v2(pet_size)}",
                f"Навички та характер: {escape_markdown_v2(pet_skills_character)}",
            ]

            base_caption_text = "\n".join(caption_parts) + "\n\nМоя історія:\n> "
            max_story_length = 1024 - len(base_caption_text) - 50

            pet_story_escaped = escape_markdown_v2(pet_story_original)
            truncated_story = truncate_text(pet_story_escaped, max_story_length)
            caption = base_caption_text + truncated_story

            if len(caption) > 1024:
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
                    logging.error(f"Не вдалося видалити повідомлення: {e}")

            with open(pet_photo_path, 'rb') as image_file:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=image_file,
                    caption=caption,
                    parse_mode='MarkdownV2',
                    reply_markup=reply_markup
                )

        except Exception as e:
            logging.error(f"Несподівана помилка в AllpetHandler.callback: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Сталася непередбачувана помилка. Спробуйте пізніше.",
            )
