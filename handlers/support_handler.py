from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.bank_handlers import PrivatbankHandler
from handlers.bank_handlers.monobank_handler import MonobankHandler
from handlers.base_handler import BaseHandler


class SupportHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('support', cls.callback)
        button_handler.register_callback('mono', MonobankHandler.callback)
        button_handler.register_callback('privat', PrivatbankHandler.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton('Monobank', callback_data='mono')],
            [InlineKeyboardButton('Privat24', callback_data='privat')],
            [InlineKeyboardButton("Pumb", callback_data='pumb')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Виберіть будь ласка ваш банк яким збираєтесь оплачувати",
            reply_markup=reply_markup
        )
