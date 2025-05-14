from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.animal_handlers import AllpetHandler, CatHandler, DogHandler
from handlers.base_handler import BaseHandler

class PetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        # Реєструємо колбеки для кнопок вибору виду тварини
        button_handler.register_callback('allpets', AllpetHandler.callback)
        button_handler.register_callback('cat', cls.cat_callback)
        button_handler.register_callback('dog', cls.dog_callback)
        button_handler.register_callback('menu', cls.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Клавіатура для вибору виду тварини
        keyboard = [
            [InlineKeyboardButton('Всі тварини 😺🐶', callback_data='allpets')],
            [
                InlineKeyboardButton('Коти 😺', callback_data='cat'),
                InlineKeyboardButton('Собаки 🐶', callback_data='dog')
            ],
            [InlineKeyboardButton('У головне меню', callback_data='menu')],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Видалення старого повідомлення перед відправкою нового
        if update.callback_query:
            await context.bot.delete_message(
                chat_id=update.callback_query.message.chat_id,
                message_id=update.callback_query.message.message_id
            )

        # Надсилаємо повідомлення з кнопками вибору виду тварини
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Для початку оберіть вид улюбленця",
            reply_markup=reply_markup
        )

    @staticmethod
    async def cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Зберігаємо вибір виду як "Кіт" у даних користувача
        context.user_data['species'] = 'Кіт'
        await PetHandler.show_pet(update, context)

    @staticmethod
    async def dog_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Зберігаємо вибір виду як "Собака" у даних користувача
        context.user_data['species'] = 'Пес'
        await PetHandler.show_pet(update, context)

    @staticmethod
    async def show_pet(update: Update, context: ContextTypes.DEFAULT_TYPE):
        species = context.user_data.get('species', 'Кіт')  # За замовчуванням коти

        # Тепер фільтруємо тварин залежно від вибору виду
        if species == 'Кіт':
            await CatHandler.callback(update, context)
        elif species == 'Пес':
            await DogHandler.callback(update, context)
        else:
            # Якщо вибір не визначений, показуємо всі тварини
            await AllpetHandler.callback(update, context)
