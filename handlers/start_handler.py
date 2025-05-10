from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

from handlers.manager_handler import ManagerHandler
from handlers.base_handler import BaseHandler
from handlers.support_handler import SupportHandler


class StartHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        app.add_handler(CommandHandler('start', cls.callback))
        button_handler.register_callback('support', SupportHandler.callback)
        button_handler.register_callback('FAQ', ManagerHandler.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton('Переглянути тварин 🐶', callback_data='watchpet')],
            [
                InlineKeyboardButton('Підтримати нас 💵❤️', callback_data='support'),
                InlineKeyboardButton("Зв'язатися з нами ☎️", callback_data='FAQ')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Вітаю! Я телеграм-бот притулку для тварин Сіріус 😊",
            reply_markup=reply_markup
        )

