import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

from handlers.base_handler import BaseHandler
from handlers.manager_handler import ManagerHandler
from handlers.pet_handler import PetHandler
from handlers.socialmedia_handler import SocialMediaHandler
from handlers.support_handler import SupportHandler

logger = logging.getLogger(__name__)


class StartHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        app.add_handler(CommandHandler('start', cls.callback))

        button_handler.register_callback('support', SupportHandler.callback)
        button_handler.register_callback('FAQ', ManagerHandler.callback)
        button_handler.register_callback('socmed', SocialMediaHandler.callback)
        button_handler.register_callback('watchpet', PetHandler.callback)
        button_handler.register_callback('menu', cls.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

        keyboard = [
            [InlineKeyboardButton('Переглянути тварин 🐶', callback_data='watchpet')],
            [
                InlineKeyboardButton('Підтримати нас 💵❤️', callback_data='support'),
                InlineKeyboardButton("Зв'язатися з нами ☎️", callback_data='FAQ'),
            ],
            [InlineKeyboardButton("Наші соціальні мережі 📢", callback_data='socmed')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            try:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )
            except Exception as e:
                logger.warning(f"Failed to delete previous message in start_handler: {e}")

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Вітаю! Я телеграм-бот притулку для тварин Сіріус 😊",
            reply_markup=reply_markup
        )
