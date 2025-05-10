from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler


class SocialMediaHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        # Реєструємо тільки callback без створення нового CallbackQueryHandler
        button_handler.register_callback('socmed', cls.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton('У головне меню', callback_data='menu')],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Ось наші соц мережі і наші контактні дані"
                 "\n[Інстаграм](https://www.instagram.com/sirius.shelter/)"
                 "\n[Фейсбук](https://www.facebook.com/Shelter.SIRIUS)"
                 "\n[Твітер](https://twitter.com/)"
                 "\n[Ютуб](https://www.youtube.com/@sheltersirius569)"
                 "\n[Тікток](https://www.tiktok.com/@sirius.shelter)"
                 "\nНаш телефон [\+380931934069]"
                 "\nНаша поштова адреса [dogcat\.sirius@gmail\.com]",
            parse_mode='MarkdownV2',
            reply_markup=reply_markup
        )
