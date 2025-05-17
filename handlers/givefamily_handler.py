import logging
import re

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from handlers.base_handler import BaseHandler

# from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError

# States
EMAIL, PHONE, FIRST_NAME, LAST_NAME, COMMENT = range(5)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class GiveFamilyHandler(BaseHandler):
    # Google Sheets config
    CREDENTIALS_FILE = "sirius_key (2).json"
    SPREADSHEET_ID = "1jjIDk58RjKF8SeNrm0a3Ijt8zpLa9pT2wej4053MXZk"  # Direct spreadsheet ID
    WORKSHEET_NAME = "Лист1"
    SHEET_LINK = "https://docs.google.com/spreadsheets/d/1jjIDk58RjKF8SeNrm0a3Ijt8zpLa9pT2wej4053MXZk/edit?usp=sharing"
    SERVICE_ACCOUNT_EMAIL = "sheltersirius@sirius-459511.iam.gserviceaccount.com"  # From your credentials file

    @classmethod
    def register(cls, app, button):
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(cls.start_conversation, pattern='^givefamily$')
            ],
            states={
                EMAIL: [MessageHandler(filters.TEXT & ~filters.CONTACT, cls.get_email)],
                PHONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_phone),
                    MessageHandler(filters.CONTACT, cls.get_phone)
                ],
                FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_first_name)],
                LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_last_name)],
                COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_comment)],
            },
            fallbacks=[],  # Можливо, варто додати fallbacks для скасування розмови
            allow_reentry=True,
        )
        app.add_handler(conv_handler)
        logger.info("GiveFamilyHandler registered.")

    @staticmethod
    async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📝 Щоб подарувати сім'ю тваринці, заповніть, будь ласка, коротку анкету.\nВведіть ваш емейл:"
        )
        return EMAIL

    @staticmethod
    def _get_google_sheet_client():
        try:
            scope = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                GiveFamilyHandler.CREDENTIALS_FILE,
                scope
            )
            logger.info(f"Authenticating with service account: {creds.service_account_email}")
            return gspread.authorize(creds)
        except Exception as e:
            logger.error(f"Google Sheets authentication error: {e}")
            raise  # Прокидаємо виняток далі для обробки в get_comment

    @staticmethod
    def _verify_sheet_access():
        """Verify access to the specific spreadsheet"""
        try:
            client = GiveFamilyHandler._get_google_sheet_client()

            # Try to open the spreadsheet directly by ID
            spreadsheet = client.open_by_key(GiveFamilyHandler.SPREADSHEET_ID)

            # Verify worksheet exists or create it
            try:
                worksheet = spreadsheet.worksheet(GiveFamilyHandler.WORKSHEET_NAME)
                logger.info(f"Found worksheet: {GiveFamilyHandler.WORKSHEET_NAME}")
            except gspread.exceptions.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=GiveFamilyHandler.WORKSHEET_NAME,
                    rows=1000,  # Можливо, варто зробити більше рядків
                    cols=20  # Можливо, варто зробити більше стовпців
                )
                logger.info(f"Created new worksheet: {GiveFamilyHandler.WORKSHEET_NAME}")

            # Можна також перевірити наявність очікуваних заголовків стовпців тут

            return True
        except gspread.exceptions.APIError as e:
            if 'PERMISSION_DENIED' in str(e):
                error_msg = (
                    "🔒 Помилка доступу до Google Таблиці\n\n"
                    f"Будь ласка, надайте доступ для облікового запису:\n"
                    f"{GiveFamilyHandler.SERVICE_ACCOUNT_EMAIL}\n\n"
                    f"1. Відкрийте таблицю: {GiveFamilyHandler.SHEET_LINK}\n"
                    f"2. Натисніть 'Налаштування доступу' (Share)\n"
                    f"3. Додайте вищевказаний email з правами редактора (Editor)"
                )
                logger.error(error_msg)
                raise PermissionError(error_msg)  # Прокидаємо PermissionError
            raise  # Прокидаємо інші APIError
        except Exception as e:
            logger.error(f"Sheet access verification failed: {e}")
            raise  # Прокидаємо інші винятки

    @staticmethod
    def _append_to_sheet(context: ContextTypes.DEFAULT_TYPE,
                         user_data_list: list):  # Приймаємо context та список даних користувача
        """Appends application data including pet URL and application ID to the Google Sheet."""
        try:
            client = GiveFamilyHandler._get_google_sheet_client()
            spreadsheet = client.open_by_key(GiveFamilyHandler.SPREADSHEET_ID)

            try:
                worksheet = spreadsheet.worksheet(GiveFamilyHandler.WORKSHEET_NAME)
            except gspread.exceptions.WorksheetNotFound:
                logger.warning(f"Worksheet '{GiveFamilyHandler.WORKSHEET_NAME}' not found, attempting to create.")
                worksheet = spreadsheet.add_worksheet(
                    title=GiveFamilyHandler.WORKSHEET_NAME,
                    rows=1000,
                    cols=20
                )

            all_rows = worksheet.get_all_values()
            next_application_id = len(all_rows) + 1

            # Отримуємо ProfileURL тваринки зі збережених даних користувача
            pet_profile_url = context.user_data.get('current_pet_url', 'N/A')

            # Формуємо повний рядок даних для запису
            # Порядок: ID анкети, ProfileURL тваринки, email, phone, first_name, last_name, comment
            # **ПЕРЕВІРТЕ ПОРЯДОК СТОВПЦІВ У ВАШІЙ GOOGLE ТАБЛИЦІ!**
            full_data_row = [
                next_application_id,  # 1. ID анкети
                pet_profile_url,  # 2. ProfileURL тваринки
                *user_data_list
                # 3-7. Розпаковуємо список з даними користувача (email, phone, first_name, last_name, comment)
            ]

            worksheet.append_row(full_data_row)  # Записуємо повний рядок
            logger.info(f"Successfully wrote data to sheet: {full_data_row}")
            return True
        except Exception as e:
            logger.error(f"Failed to write to sheet: {e}")
            raise  # Прокидаємо виняток далі для обробки в get_comment

    @staticmethod
    async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
        email = update.message.text.strip()

        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            await update.message.reply_text("❌ Ви ввели невірний email. Спробуйте ще раз:")
            return EMAIL

        context.user_data['email'] = email
        # Використовуємо клавіатуру для запиту контакту
        keyboard = [
            [KeyboardButton('Поділитися номером телефону', request_contact=True)]  # Український текст
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True,
                                           resize_keyboard=True)  # resize_keyboard для кращого вигляду

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📞 Введіть ваш номер телефону або натисніть кнопку 'Поділитися номером телефону':",
            # Змінено текст під кнопку
            reply_markup=reply_markup
        )

        return PHONE

    @staticmethod
    async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Перевіряємо, чи це контакт
        if update.message.contact:
            phone = update.message.contact.phone_number
            # Після надсилання контакту, прибираємо клавіатуру
            reply_markup = ReplyKeyboardRemove()
            await update.message.reply_text("Дякую! Номер отримано.",
                                            reply_markup=reply_markup)  # Додано повідомлення про отримання номеру
        else:
            phone = update.message.text.strip()
            # Тут можна додати більш строгу валідацію формату номеру телефону, якщо не використовується кнопка

        # Проста перевірка наявності номеру
        if not phone:
            await update.message.reply_text(
                "❌ Будь ласка, введіть номер телефону або надішліть контакт за допомогою кнопки.")
            return PHONE

        context.user_data['phone'] = phone
        # Прибираємо клавіатуру, якщо номер введено текстом (на випадок, якщо користувач не натиснув кнопку)
        # Або це вже зроблено, якщо номер відправлено контактом
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=update.message.message_id  # Видаляємо повідомлення з клавіатурою запиту контакту
            )
            # Або відправляємо нове повідомлення без клавіатури
        except Exception:
            pass

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

        # Збираємо дані користувача в список
        user_data_list = [
            context.user_data.get('email', 'N/A'),
            context.user_data.get('phone', 'N/A'),
            context.user_data.get('first_name', 'N/A'),
            context.user_data.get('last_name', 'N/A'),
            context.user_data.get('comment', 'N/A'),
        ]

        # Отримуємо URL тваринки, збережений раніше
        pet_profile_url = context.user_data.get('current_pet_url', 'N/A')

        try:
            GiveFamilyHandler._append_to_sheet(context, user_data_list)

            # Формуємо summary для користувача (можна додати URL тваринки)
            summary = (
                f"✅ Ваша анкета успішно надіслана!\n\n"
                f"🔗 Посилання на тваринку: {pet_profile_url}\n"  # Додано URL тваринки
                f"📧 Емейл: {user_data_list[0]}\n"
                f"📞 Телефон: {user_data_list[1]}\n"
                f"👤 Ім'я: {user_data_list[2]}\n"
                f"👥 Прізвище: {user_data_list[3]}\n"
                f"💬 Коментар: {user_data_list[4]}\n\n"
                f"Дякуємо за ваш інтерес до наших підопічних! Ми зв'яжемося з вами найближчим часом."
            # Фінальне повідомлення
            )
            await update.message.reply_text(summary)

        except PermissionError as e:
            # Обробка помилки доступу до таблиці
            await update.message.reply_text(str(e))
        except Exception as e:
            # Обробка інших помилок запису
            logger.error(f"Failed to save data to sheet in get_comment: {e}")
            await update.message.reply_text(
                "❌ Помилка збереження даних анкети. Будь ласка, спробуйте пізніше або зв'яжіться з нами іншим способом."
            )

        # Clear conversation data
        context.user_data.clear()
        return ConversationHandler.END
