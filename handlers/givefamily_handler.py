import re
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from telegram.error import BadRequest
import gspread
from oauth2client.service_account import ServiceAccountCredentials
# from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError

from handlers.base_handler import BaseHandler

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
                EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_email)],
                PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cls.get_phone)],
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
        query = update.callback_query
        await query.answer()

        try:
            if query.message:
                await query.message.delete()
        except Exception as e:
            logger.warning(f"Couldn't delete message: {e}")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📝 Введіть, будь ласка, ваш емейл:"
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
            raise

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
                    rows=1000,
                    cols=20
                )
                logger.info(f"Created new worksheet: {GiveFamilyHandler.WORKSHEET_NAME}")

            return True
        except gspread.exceptions.APIError as e:
            if 'PERMISSION_DENIED' in str(e):
                error_msg = (
                    "🔒 Помилка доступу до Google Таблиці\n\n"
                    f"Будь ласка, надайте доступ для облікового запису:\n"
                    f"{GiveFamilyHandler.SERVICE_ACCOUNT_EMAIL}\n\n"
                    f"1. Відкрийте таблицю: {GiveFamilyHandler.SHEET_LINK}\n"
                    f"2. Натисніть 'Налаштування доступу'\n"
                    f"3. Додайте вищевказаний email з правами редактора"
                )
                logger.error(error_msg)
                raise PermissionError(error_msg)
            raise
        except Exception as e:
            logger.error(f"Sheet access verification failed: {e}")
            raise

    @staticmethod
    def _append_to_sheet(data: list):
        try:
            client = GiveFamilyHandler._get_google_sheet_client()
            spreadsheet = client.open_by_key(GiveFamilyHandler.SPREADSHEET_ID)

            try:
                worksheet = spreadsheet.worksheet(GiveFamilyHandler.WORKSHEET_NAME)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=GiveFamilyHandler.WORKSHEET_NAME,
                    rows=1000,
                    cols=20
                )

            worksheet.append_row(data)
            logger.info(f"Successfully wrote data to sheet: {data}")
            return True
        except Exception as e:
            logger.error(f"Failed to write to sheet: {e}")
            raise

    @staticmethod
    async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
        email = update.message.text.strip()

        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            await update.message.reply_text("❌ Ви ввели невірний email. Спробуйте ще раз:")
            return EMAIL

        context.user_data['email'] = email
        await update.message.reply_text("📞 Введіть ваш номер телефону (наприклад, +380XXXXXXXXX або 0XXXXXXXXX):")
        return PHONE

    @staticmethod
    async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
        phone = update.message.text.strip()

        if not re.match(r"^(?:\+380|380|0)\d{9}$", phone):
            await update.message.reply_text(
                "❌ Невірний формат номеру. Приклад: +380XXXXXXXXX або 0XXXXXXXXX. Спробуйте ще раз:")
            return PHONE

        # Normalize phone number
        if phone.startswith('0'):
            phone = '+38' + phone
        elif phone.startswith('380'):
            phone = '+' + phone

        context.user_data['phone'] = phone
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

        data = [
            context.user_data.get('email', 'N/A'),
            context.user_data.get('phone', 'N/A'),
            context.user_data.get('first_name', 'N/A'),
            context.user_data.get('last_name', 'N/A'),
            context.user_data.get('comment', 'N/A'),
        ]

        try:
            # Verify access before attempting to write
            GiveFamilyHandler._verify_sheet_access()

            # Write data
            GiveFamilyHandler._append_to_sheet(data)

            summary = (
                f"✅ Дані успішно збережено!\n\n"
                f"📋 Переглянути таблицю:\n"
                f"{GiveFamilyHandler.SHEET_LINK}\n\n"
                f"📧 Емейл: {data[0]}\n"
                f"📞 Телефон: {data[1]}\n"
                f"👤 Ім'я: {data[2]}\n"
                f"👥 Прізвище: {data[3]}\n"
                f"💬 Коментар: {data[4]}"
            )
            await update.message.reply_text(summary)

        except PermissionError as e:
            await update.message.reply_text(str(e))
        except Exception as e:
            logger.error(f"Failed to save data: {e}")
            await update.message.reply_text(
                "❌ Помилка збереження даних. Будь ласка, спробуйте пізніше."
            )

        # Clear conversation data
        context.user_data.clear()
        return ConversationHandler.END
