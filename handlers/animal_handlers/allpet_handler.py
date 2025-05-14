import gspread
import pandas as pd
import requests
from io import BytesIO
from gspread_dataframe import get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.givefamily_handler import GiveFamilyHandler
from handlers.base_handler import BaseHandler


class AllpetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('allpets', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

        # 1. Авторизація через JSON-файл ключа
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("sirius_key (2).json", scope)
        client = gspread.authorize(creds)

        # 2. Підключення до таблиці по ключу
        spreadsheet = client.open_by_key("1bwx4LsiH2IFAxvQlZG3skYQSt_zti1yrynRfXlhwlPg")
        worksheet = spreadsheet.sheet1  # або назва аркуша: spreadsheet.worksheet("Назва аркуша")

        # 3. Зчитування у pandas DataFrame
        df = get_as_dataframe(worksheet, evaluate_formulas=True)

        # Перевірка назв стовпців
        print("Стовпці таблиці:", df.columns)  # Друк назв стовпців

        # Перевірка наявності необхідних стовпців
        if 'Name' not in df.columns or 'Age' not in df.columns or 'PhotoURL' not in df.columns:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="У таблиці відсутні необхідні стовпці: Name, Age або PhotoURL.",
            )
            return

        # Вибір випадкової тварини
        random_pet = df.sample(n=1).iloc[0]  # Вибираємо одну випадкову тварину
        pet_name = random_pet['Name']
        pet_story = random_pet['MyStory']
        pet_age = random_pet['Age']
        pet_image_url = random_pet['PhotoURL']  # Посилання на фото

        # Якщо MyStory NaN, замінюємо його на дефолтне значення
        if pd.isna(pet_story):
            pet_story = "Історія не доступна."

        # Скачування зображення
        try:
            image_response = requests.get(pet_image_url)
            image_response.raise_for_status()  # Перевірка на помилки запиту

            # Якщо все гаразд, збережемо зображення у пам'яті
            image = BytesIO(image_response.content)
            image.name = 'pet_image.jpg'  # Ім'я файлу (можна змінити за потреби)

            # Форматування даних
            caption = f"Ім'я: {pet_name}\nВік: {pet_age} \n`{pet_story}`"

            # Створюємо клавіатуру для навігації
            keyboard = [
                [
                    InlineKeyboardButton('<<', callback_data='prev'),
                    InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                    InlineKeyboardButton('>>', callback_data='next')
                ],
                [InlineKeyboardButton('У головне меню', callback_data='menu')],
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            if update.callback_query:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )

            # Відправка фото з підписом
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image,  # Надсилаємо зображення з пам'яті
                caption=caption,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        except requests.exceptions.RequestException as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Помилка при скачуванні зображення: {e}",
            )
