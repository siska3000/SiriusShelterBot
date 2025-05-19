import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class SocialMediaHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('socmed', cls.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

        message_text = "Ось тут ви можете знайти наші соціальні мережі:"

        social_media_buttons = [
            [
                InlineKeyboardButton("🌍 Наш Сайт", url="https://dogcat.com.ua/"),
                InlineKeyboardButton("📸 Instagram", url="https://www.instagram.com/sirius.shelter/")
            ],
            [
                InlineKeyboardButton("📘 Facebook", url="https://www.facebook.com/Shelter.SIRIUS"),
                InlineKeyboardButton("🎶 TikTok", url="https://www.tiktok.com/@sirius.shelter")
            ],
            # Рядок 3 - Twitter та YouTube менш пріоритетні або посилання застаріли
            # Якщо потрібні, розкоментуйте:
            # [
            #     InlineKeyboardButton("🐦 Twitter", url="https://twitter.com/"), # Перевірте посилання!
            #     InlineKeyboardButton("▶️ YouTube", url="https://www.youtube.com/@sheltersirius569") # Перевірте посилання!
            # ],
        ]

        menu_button = [
            [InlineKeyboardButton('У головне меню', callback_data='menu')]
        ]

        all_buttons = social_media_buttons + menu_button

        reply_markup = InlineKeyboardMarkup(all_buttons)

        if update.callback_query:
            try:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )
            except Exception as e:
                logger.warning(f"Failed to delete previous message: {e}")

        # Відправляємо повідомлення з текстом та інлайн кнопками
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message_text,
                reply_markup=reply_markup,
                # parse_mode='MarkdownV2'
            )

        except Exception as e:
            logger.error(f"Помилка при відправці повідомлення соцмереж/контактів: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="На жаль, не вдалося завантажити інформацію про наші соцмережі та контакти. Спробуйте пізніше.",
            )
