import logging  # Додано логування

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.base_handler import BaseHandler

logger = logging.getLogger(__name__)  # Ініціалізація логера


# Видалено функцію escape_markdown_v2, оскільки ми не використовуємо Markdown

class ManagerHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        # Реєструємо callback для кнопки 'FAQ'
        button_handler.register_callback('FAQ', cls.callback)
        # Не реєструємо тут 'menu', він має бути зареєстрований в StartHandler

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

        # --- Формуємо текст для FAQ як звичайний текст ---
        # Використовуємо тільки символи нового рядка '\n' для форматування
        # Без жирного тексту, списків або інших елементів Markdown

        faq_text = "Часті питання (FAQ)\n\n"  # Заголовок

        # Питання 1
        faq_text += "❓ Як я можу взяти тваринку з притулку?\n"
        faq_text += ("Процес адопції зазвичай включає:\n"
                     "1) Перегляд доступних тварин на нашому сайті (https://dogcat.com.ua/) або в телеграм-боті;\n"
                     "2) Заповнення анкети кандидата на адопцію (її можна знайти під профілем тваринки або на сайті);\n"
                     "3) Співбесіду з представником притулку;\n"
                     "4) Візит до притулку для знайомства з тваринкою;\n"
                     "5) Підписання договору адопції.\n\n")

        # Питання 2
        faq_text += "❓ Де знаходиться ваш притулок?\n"
        faq_text += ("Федорівка, Київська область, 07372.\n"
                     "Будь ласка, узгоджуйте ваш візит заздалегідь.\n\n")

        # Питання 3
        faq_text += "❓ Який графік роботи притулку?\n"
        faq_text += "Пн-Пт Зачинено, Сб-Нд 11:00-16:00.\n\n"

        # Питання 4
        faq_text += "❓ Як ще я можу зв'язатися?\n"
        faq_text += ("📞 Телефон: +380931934069\n"
                     "📧 Email: dogcat.sirius@gmail.com\n"
                     "💬 Менеджер: @manager_adopt\n\n")

        faq_text += "Якщо ви не знайшли відповіді на своє питання, будь ласка, зв'яжіться з нами за вказаними контактами або поверніться у головне меню."

        keyboard = [
            [InlineKeyboardButton('У головне меню', callback_data='menu')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Намагаємося видалити попереднє повідомлення (якщо це був callback)
        if update.callback_query:
            try:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )
            except Exception as e:
                logger.warning(f"Failed to delete previous message: {e}")

        # Відправляємо повідомлення з FAQ та клавіатурою як звичайний текст
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=faq_text,  # Використовуємо сформований текст FAQ
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Помилка при відправці повідомлення з FAQ: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="На жаль, виникла помилка при завантаженні Частих питань. Спробуйте пізніше.",
            )
