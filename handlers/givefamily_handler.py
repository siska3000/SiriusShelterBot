import logging
import re
import sqlite3
from datetime import datetime

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, \
    InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from handlers.base_handler import BaseHandler

EMAIL, PHONE, FIRST_NAME, LAST_NAME, COMMENT = range(5)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class GiveFamilyHandler(BaseHandler):
    # Database config
    DB_NAME = "sirius.db"

    @staticmethod
    def initialize_application_db():
        """Creates the 'applications' table in the database if it doesn't exist."""
        conn = None
        try:
            conn = sqlite3.connect(GiveFamilyHandler.DB_NAME)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pet_profile_url TEXT,
                    email TEXT,
                    phone TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    comment TEXT
                )
            ''')
            conn.commit()
            logger.info("Successfully initialized/verified 'applications' table in the database.")
        except sqlite3.Error as e:
            logger.error(f"Error initializing 'applications' table: {e}")
        finally:
            if conn:
                conn.close()

    @classmethod
    def register(cls, app, button):
        cls.initialize_application_db()

        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(cls.start_conversation, pattern='^givefamily$')
            ],
            states={
                EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.CONTACT, cls.get_email)],
                PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_phone),
                    MessageHandler(filters.CONTACT, cls.get_phone)
                ],
                FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_first_name)],
                LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_last_name)],
                COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_comment)],
            },
            fallbacks=[],
            allow_reentry=True,
        )
        app.add_handler(conv_handler)
        logger.info("GiveFamilyHandler registered.")

    @staticmethod
    async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Ensure previous message is deleted if it's a callback from a photo message
        if update.callback_query:
            try:
                # Attempt to delete the message with the photo and inline keyboard
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )
                logger.info("Previous message deleted before starting givefamily conversation.")
            except Exception as e:
                logger.info(f"Could not delete previous message: {e}")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📝 Щоб подарувати сім'ю тваринці, заповніть, будь ласка, коротку анкету.\nВведіть ваш емейл:"
        )
        return EMAIL

    @staticmethod
    def _save_application_to_db(context: ContextTypes.DEFAULT_TYPE, user_data_list: list):
        conn = None
        try:
            conn = sqlite3.connect(GiveFamilyHandler.DB_NAME)
            c = conn.cursor()

            current_timestamp = datetime.now().isoformat()
            pet_profile_url = context.user_data.get('current_pet_url', 'N/A')

            email, phone, first_name, last_name, comment_text = user_data_list

            c.execute('''
                INSERT INTO applications (timestamp, pet_profile_url, email, phone, first_name, last_name, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (current_timestamp, pet_profile_url, email, phone, first_name, last_name, comment_text))
            conn.commit()
            logger.info(f"Successfully wrote application data to SQLite DB for pet URL: {pet_profile_url}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to write application to SQLite DB: {e}")
            raise
        finally:
            if conn:
                conn.close()

    @staticmethod
    async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
        email = update.message.text.strip()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            await update.message.reply_text("❌ Ви ввели невірний email. Спробуйте ще раз:")
            return EMAIL
        context.user_data['email'] = email
        keyboard = [
            [KeyboardButton('Поділитися номером телефону', request_contact=True)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📞 Введіть ваш номер телефону або натисніть кнопку 'Поділитися номером телефону':",
            reply_markup=reply_markup
        )
        return PHONE

    @staticmethod
    async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.contact:
            phone_number = update.message.contact.phone_number
            await update.message.reply_text("Дякую! Номер отримано.", reply_markup=ReplyKeyboardRemove())
        else:
            phone_number = update.message.text.strip()
            if not re.match(r"^\+?[0-9\s\-\(\)]{7,20}$", phone_number):  # Example regex
                await update.message.reply_text(
                    "❌ Номер телефону виглядає невірно. Будь ласка, спробуйте ще раз, наприклад: +380XXXXXXXXX або 0XXXXXXXXX."
                )
                return PHONE
            await update.message.reply_text("Дякую! Номер отримано.", reply_markup=ReplyKeyboardRemove())

        if not phone_number:
            await update.message.reply_text(
                "❌ Будь ласка, введіть номер телефону або надішліть контакт за допомогою кнопки.")
            return PHONE

        context.user_data['phone'] = phone_number
        await update.message.reply_text("👤 Введіть ваше ім'я:")
        return FIRST_NAME

    @staticmethod
    async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        first_name = update.message.text.strip()
        context.user_data['first_name'] = first_name if first_name else "N/A"
        await update.message.reply_text("👥 Введіть ваше прізвище:")
        return LAST_NAME

    @staticmethod
    async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        last_name = update.message.text.strip()
        context.user_data['last_name'] = last_name if last_name else "N/A"
        await update.message.reply_text("💬 Залиште коментар (або напишіть 'пропустити', якщо коментаря немає):")
        return COMMENT

    @staticmethod
    async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
        comment = update.message.text.strip()
        context.user_data['comment'] = comment if comment.lower() not in ['пропустити', 'skip'] else "N/A"

        user_data_list = [
            context.user_data.get('email', 'N/A'),
            context.user_data.get('phone', 'N/A'),
            context.user_data.get('first_name', 'N/A'),
            context.user_data.get('last_name', 'N/A'),
            context.user_data.get('comment', 'N/A'),
        ]

        pet_name = context.user_data.get('current_pet_name', 'Невідоме ім\'я')
        pet_age = context.user_data.get('current_pet_age', 'Невідомий вік')

        try:
            GiveFamilyHandler._save_application_to_db(context, user_data_list)

            summary = (
                f"✅ Ваша анкета успішно надіслана до нашої бази даних!\n\n"
                f"🐶 Тваринка: {pet_name}, {pet_age}\n"
                f"📧 Емейл: {user_data_list[0]}\n"
                f"📞 Телефон: {user_data_list[1]}\n"
                f"👤 Ім'я: {user_data_list[2]}\n"
                f"👥 Прізвище: {user_data_list[3]}\n"
                f"💬 Коментар: {user_data_list[4]}\n\n"
                f"Дякуємо за ваш інтерес до наших хвостиків! Ми зв'яжемося з вами найближчим часом."
            )

            keyboard = [
                [InlineKeyboardButton('У головне меню', callback_data='menu')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(summary, reply_markup=reply_markup)

        except PermissionError as e:
            await update.message.reply_text(str(e))
        except Exception as e:
            logger.error(f"Failed to save data to sheet in get_comment: {e}")
            await update.message.reply_text(
                "❌ Помилка збереження даних анкети. Будь ласка, спробуйте пізніше або зв'яжіться з нами іншим способом."
            )

        context.user_data.clear()
        return ConversationHandler.END
