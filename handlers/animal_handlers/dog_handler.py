import logging
import os
import re
import sqlite3

import pandas as pd
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler
from handlers.givefamily_handler import GiveFamilyHandler

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)  # Added logger instance

DB_NAME = 'sirius.db'  # Added
MAX_CAPTION_LENGTH = 1024  # ✅ ДОДАНО — ліміт Telegram на caption


def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))


# ✅ ДОДАНО — функція, яка обрізає caption до 1024 символів
def build_caption(pet_name, pet_age, pet_gender, pet_size, pet_skills, pet_story):
    def esc(text):
        return escape_markdown_v2(text if pd.notna(text) else 'Невідомо')

    base_caption = (
        f"*Ім'я:* {esc(pet_name)}\n"
        f"*Вік:* {esc(pet_age)}\n"
        f"*Гендер:* {esc(pet_gender)}\n"
        f"*Розмір:* {esc(pet_size)}\n"
        f"*Навички:* {esc(pet_skills)}\n\n"
        f"*Моя Історія:*\n>"
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


class DogHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('allpets', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.info("AllpetHandler callback triggered")

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

        required_columns_db = ['Name', 'Age', 'PhotoURL', 'MyStory', 'Species']
        missing_columns = [col for col in required_columns_db if col not in df.columns]

        if missing_columns:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"У базі даних відсутні необхідні стовпці: {', '.join(missing_columns)}. Будь ласка, перевірте дані.",
            )
            return

        df = df.dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])
        if df.empty:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Наразі немає доступних тварин для показу.",
            )
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
        pet = df_filtered.sample(1).iloc[0]

        pet_name = pet['Name']
        pet_gender = pet['Gender']
        pet_age = pet['Age']
        pet_story = pet['MyStory']
        pet_size = pet.get('Size', 'Невідомо')
        pet_skills = pet.get('SkillsAndCharacter', 'Немає інформації')
        pet_photo_path = pet['PhotoURL']
        pet_profile_url = pet.get('ProfileURL', 'Немає посилання профілю')

        logging.info(f"Шлях до фото: {pet_photo_path}")
        logging.info(f"Файл існує? {os.path.isfile(pet_photo_path)}")

        # --- Зберігаємо дані тваринки для GiveFamilyHandler ---
        context.user_data['current_pet_name'] = str(pet_name) if pd.notna(pet_name) else 'Невідоме ім\'я'
        context.user_data['current_pet_age'] = str(pet_age) if pd.notna(pet_age) else 'Невідомий вік'
        context.user_data['current_pet_url'] = pet_profile_url
        context.user_data['species'] = 'Пес'

        caption = build_caption(pet_name, pet_age, pet_gender, pet_size, pet_skills,
                                pet_story)  # 🔧 ЗМІНЕНО: використовуємо функцію
        logging.info(f"Caption length: {len(caption)}")  # ✅ ДОДАНО: діагностика довжини caption

        keyboard = [
            [
                InlineKeyboardButton('<<', callback_data='prev'),  # Calls PrevPetHandler -> NextPetHandler.show_pet
                InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                InlineKeyboardButton('>>', callback_data='next')  # Calls NextPetHandler.callback
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
                logging.info(f"Не вдалося видалити повідомлення (AllpetHandler): {e}")

        try:
            with open(pet_photo_path, 'rb') as image_file:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=image_file,
                    caption=caption,
                    parse_mode='MarkdownV2',
                    reply_markup=reply_markup
                )

        except telegram.error.TimedOut as e:
            logging.error(f"Несподівана помилка в AllpetHandler.callback при відправці фото: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Зачекайте хвилинку"
            )

        except Exception as e:
            logging.error(f"Несподівана помилка в AllpetHandler.callback при відправці фото: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Зачекайте секунду"
            )
            # Якщо фото не вдалося відправити - відправляємо текстовий варіант
            text_message = (
                f"Не вдалося завантажити фото для {escape_markdown_v2(pet_name)}, але ось інформація:\n\n"
                f"{caption.replace('>', '')}\n\n"
                f"[Посилання на профіль]({pet_profile_url})" if pd.notna(pet_profile_url) else ""
            )

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text_message,
                parse_mode='MarkdownV2',
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )
