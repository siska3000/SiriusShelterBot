import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class AdminSecretPanelHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('admin_secret_panel', cls.callback)
        button_handler.register_callback('show_applications', cls.callback)
        button_handler.register_callback('menu', cls.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        # Перевіряємо, чи є користувач адміністратором
        if not BaseHandler.is_admin(user_id):
            logger.warning(f"Non-admin user {user_id} tried to access admin panel.")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="У вас немає прав для доступу до цієї панелі. ⛔️"
            )
            return

        logger.info(f"Admin user {user_id} accessed admin panel.")

        # Текст повідомлення для адмін-панелі
        message_text = "Вітаємо в Адмін-панелі! Оберіть дію:"

        # Кнопки для адміністративних функцій
        keyboard = [
            # Приклади адмін-функцій. Замініть їх на реальні, коли будете їх реалізовувати
            [InlineKeyboardButton('Показати список анкет 📝', callback_data='show_applications'),
             InlineKeyboardButton('Керувати тваринами 🐾', callback_data='manage_pets')],
            [InlineKeyboardButton('У головне меню', callback_data='menu')],  # Кнопка повернення в основне меню
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Видалення попереднього повідомлення (кнопки з головного меню)
        if update.callback_query:
            try:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )
            except Exception as e:
                logger.warning(f"Failed to delete previous message in AdminSecretPanelHandler: {e}")

        # Надсилаємо повідомлення з адмін-панеллю
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message_text,
            reply_markup=reply_markup
        )
