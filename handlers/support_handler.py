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
            [InlineKeyboardButton('Monobank', callback_data='mono'),
             InlineKeyboardButton('Privat24', callback_data='privat')],
            [InlineKeyboardButton('Назад', callback_data='support')],

        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await context.bot.delete_message(
                chat_id=update.callback_query.message.chat_id,
                message_id=update.callback_query.message.message_id
            )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Виберіть будь ласка ваш банк яким збираєтесь оплачувати",
            reply_markup=reply_markup
        )
