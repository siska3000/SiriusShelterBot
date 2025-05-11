from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


from handlers.base_handler import BaseHandler


class MonobankHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        # Реєструємо тільки callback без створення нового CallbackQueryHandler
        button_handler.register_callback('menu', cls.callback)
        button_handler.register_callback('mono', cls.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton('У головне меню', callback_data='menu')],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await context.bot.delete_message(
                chat_id=update.callback_query.message.chat_id,
                message_id=update.callback_query.message.message_id
            )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Реквізити:\n`4441 1111 0000 0000`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
