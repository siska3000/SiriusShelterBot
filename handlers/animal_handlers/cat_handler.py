from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


from handlers.base_handler import BaseHandler


class CatHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        # Реєструємо тільки callback без створення нового CallbackQueryHandler
        button_handler.register_callback('cat', cls.callback)
        button_handler.register_callback('menu', cls.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton('Всі тварини 😺🐶', callback_data='allpets')],
            [
                InlineKeyboardButton('Коти 😺', callback_data='cat'),
                InlineKeyboardButton('Собаки 🐶', callback_data='dog')
             ],
            # [InlineKeyboardButton('Фільтри', callback_data='filter')],
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
            text="Для початку оберіть вид улюбленця",
            reply_markup=reply_markup
        )
