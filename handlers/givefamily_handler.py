import logging
import pathlib
import re
import sqlite3
import threading
import queue
import time
from datetime import datetime

from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
# ... (imports remain unchanged)

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
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def escape_markdown_v2(text: str) -> str:
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))


class GiveFamilyHandler(BaseHandler):
    BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()
    DB_NAME = str(BASE_DIR / "sirius.db")
    _job_queue = queue.Queue()
    _db_lock = threading.Lock()

    @staticmethod
    def _start_worker_thread():
        def worker():
            logger.info("[DB Worker] Thread started")
            with sqlite3.connect(GiveFamilyHandler.DB_NAME, timeout=30) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                cursor = conn.cursor()
                while True:
                    try:
                        user_data = GiveFamilyHandler._job_queue.get()
                        if user_data is None:
                            logger.info("[DB Worker] Exit signal received")
                            break
                        logger.info(f"[DB Worker] Processing job: {user_data}")
                        GiveFamilyHandler._do_write_to_db(user_data, conn, cursor)
                        GiveFamilyHandler._job_queue.task_done()
                        logger.info("[DB Worker] Job completed successfully")
                    except Exception as e:
                        logger.exception(f"[DB Worker] Critical error in worker thread: {e}")
                        time.sleep(1)

        thread = threading.Thread(target=worker, daemon=True, name="DBWorkerThread")
        thread.start()
        logger.info(f"[DB Worker] Thread started with ID: {thread.ident}")

    @staticmethod
    def initialize_application_db():
        logger.info(f"🗄️ DB Path: {GiveFamilyHandler.DB_NAME}")
        try:
            db_path = pathlib.Path(GiveFamilyHandler.DB_NAME)
            if not db_path.parent.exists():
                db_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(GiveFamilyHandler.DB_NAME) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
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
                c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                logger.info(f"✅ Existing tables: {c.fetchall()}")
        except Exception as e:
            logger.exception(f"❌ Failed to initialize DB: {e}")
            raise

    @classmethod
    def register(cls, app, button):
        logger.info("Initializing GiveFamilyHandler...")
        cls.initialize_application_db()
        time.sleep(0.5)  # Small delay to avoid lock conflicts
        cls._start_worker_thread()

        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(cls.start_conversation, pattern='^givefamily$')],
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
        logger.info("GiveFamilyHandler registered successfully")

    @staticmethod
    async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat_id
        await context.bot.send_message(chat_id=chat_id, text="📝 Введіть ваш емейл:")
        return EMAIL

    @staticmethod
    async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
        email = update.message.text.strip()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            await update.message.reply_text("❌ Невірний email. Спробуйте ще раз:")
            return EMAIL

        context.user_data['email'] = email
        keyboard = [[KeyboardButton('Поділитися номером телефону', request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("📞 Введіть номер або поділіться:", reply_markup=reply_markup)
        return PHONE

    @staticmethod
    async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.contact:
            phone_number = update.message.contact.phone_number
        else:
            phone_number = update.message.text.strip()
            if not re.match(r"^\+?[0-9\s\-\(\)]{7,20}$", phone_number):
                await update.message.reply_text("❌ Невірний формат телефону. Спробуйте ще раз.")
                return PHONE

        context.user_data['phone'] = phone_number
        await update.message.reply_text("👤 Введіть ім'я:", reply_markup=ReplyKeyboardRemove())
        return FIRST_NAME

    @staticmethod
    async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['first_name'] = update.message.text.strip()
        await update.message.reply_text("👥 Введіть прізвище:")
        return LAST_NAME

    @staticmethod
    async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['last_name'] = update.message.text.strip()
        keyboard = [["Пропустити"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("💬 Додайте коментар або натисніть 'Пропустити':", reply_markup=reply_markup)
        return COMMENT

    @staticmethod
    async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
        comment = update.message.text.strip()
        context.user_data['comment'] = "Немає коментаря" if comment.lower() == "пропустити" else comment

        user_data = {
            'email': context.user_data.get('email'),
            'phone': context.user_data.get('phone'),
            'first_name': context.user_data.get('first_name'),
            'last_name': context.user_data.get('last_name'),
            'comment': context.user_data.get('comment'),
            'pet_url': context.user_data.get('current_pet_url', 'https://dogcat.com.ua/pet/unknown'),
        }

        logger.info(f"[Main Thread] Queueing DB job: {user_data}")
        GiveFamilyHandler._job_queue.put(user_data)
        logger.info(f"[Main Thread] Queue size: {GiveFamilyHandler._job_queue.qsize()}")

        summary = (
            r"✅ *Анкета надіслана\!*" + "\n\n"
            f"📧 *Email:* {escape_markdown_v2(user_data['email'])}\n"
            f"📞 *Телефон:* {escape_markdown_v2(user_data['phone'])}\n"
            f"👤 *Ім'я:* {escape_markdown_v2(user_data['first_name'])}\n"
            f"👥 *Прізвище:* {escape_markdown_v2(user_data['last_name'])}\n"
            f"💬 *Коментар:* {escape_markdown_v2(user_data['comment'])}\n\n"
            r"Ми зв'яжемося з вами найближчим часом\."
        )

        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("У головне меню", callback_data="menu")]])
        await update.message.reply_text(summary, parse_mode="MarkdownV2", reply_markup=reply_markup)

        context.user_data.clear()
        return ConversationHandler.END

    @staticmethod
    def _do_write_to_db(user_data, conn, cursor):
        attempt = 0
        while attempt < 5:
            try:
                with GiveFamilyHandler._db_lock:
                    timestamp = datetime.now().isoformat()
                    cursor.execute('''
                        INSERT INTO applications (
                            timestamp, pet_profile_url, email, phone, first_name, last_name, comment
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        timestamp,
                        user_data.get('pet_url', 'N/A'),
                        user_data.get('email', 'N/A'),
                        user_data.get('phone', 'N/A'),
                        user_data.get('first_name', 'N/A'),
                        user_data.get('last_name', 'N/A'),
                        user_data.get('comment', 'N/A'),
                    ))
                    conn.commit()
                    logger.info(f"[DB Writer] Insert successful: {user_data.get('email')}")
                    return
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e):
                    attempt += 1
                    logger.warning(f"[DB Writer] DB locked, retrying ({attempt}/5)...")
                    time.sleep(0.5)
                else:
                    raise
        logger.error("[DB Writer] Failed to insert after 5 attempts")

