import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from handlers.base_handler import BaseHandler


def escape_markdown_v2(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))


class SupportHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler=None):
        app.add_handler(CallbackQueryHandler(cls.callback, pattern="^support$"))

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        monobank_number = escape_markdown_v2("1234 5678 9012 3456")
        monobank_name = escape_markdown_v2("Іван Іванов")
        privat_number = escape_markdown_v2("9876 5432 1098 7654")
        privat_name = escape_markdown_v2("Петро Петров")

        text = (
            "💸 *Реквізити для підтримки:*\n\n"
            f"• *Monobank:* `{monobank_number}`\n"
            f"  Отримувач: {monobank_name}\n"
            f"• *Privat24:* `{privat_number}`\n"
            f"  Отримувач: {privat_name}\n\n"
            "Дякуємо за вашу підтримку\\! ❤️"
        )

        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await context.bot.delete_message(
                chat_id=update.callback_query.message.chat_id,
                message_id=update.callback_query.message.message_id
            )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
