import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.givefamily_handler import GiveFamilyHandler
from handlers.base_handler import BaseHandler
import requests
from io import BytesIO


def is_image_url_valid(url):
    try:
        response = requests.get(url)
        # Перевіряємо, чи є успішний HTTP-статус (200 OK) і чи є зображення в відповіді
        return response.status_code == 200 and 'image' in response.headers['Content-Type']
    except requests.exceptions.RequestException as e:
        print(f"Помилка при перевірці URL: {e}")
        return False


class PrevPetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('prev', cls.callback)
        button_handler.register_callback('givefamily', GiveFamilyHandler.start_conversation)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Авторизація
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("sirius_key (2).json", scope)
        client = gspread.authorize(creds)

        # Завантаження даних
        spreadsheet = client.open_by_key("1bwx4LsiH2IFAxvQlZG3skYQSt_zti1yrynRfXlhwlPg")
        worksheet = spreadsheet.sheet1
        df = get_as_dataframe(worksheet, evaluate_formulas=True).dropna(subset=["Name", "Age", "PhotoURL", "MyStory"])

        # Перевірка, чи є стовпець "Species" для виду тварини
        if 'Species' not in df.columns:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="У таблиці відсутній стовпець з видом тварини (Species).",
            )
            return

        # Отримуємо вибір виду тварини
        species_filter = context.user_data.get('species', 'all')  # Вибір виду: all, cat, dog

        # Фільтрація даних в залежності від вибору
        if species_filter == 'all':
            df_filtered = df  # Всі тварини
        elif species_filter == 'Кіт':
            df_filtered = df[df['Species'] == 'Кіт']  # Коти
        elif species_filter == 'Пес':
            df_filtered = df[df['Species'] == 'Пес']  # Пси
        else:
            df_filtered = pd.DataFrame()  # Якщо вибір не визначений, створюємо порожній DataFrame

        # Якщо немає тварин обраних видів
        if df_filtered.empty:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Немає доступних тварин цього виду.",
            )
            return

        # Індекс поточної тварини
        current_index = context.user_data.get("pet_index", 0)
        next_index = (current_index + 1) % len(df_filtered)  # Зациклюється вперед

        context.user_data["pet_index"] = next_index  # Оновлюємо індекс в user_data
        pet = df_filtered.iloc[next_index]

        pet_name = pet['Name']
        pet_story = pet['MyStory']
        pet_age = pet['Age']
        pet_image_url = pet['PhotoURL']  # Посилання на фото

        # Перевірка доступності зображення
        if not is_image_url_valid(pet_image_url):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Неможливо завантажити зображення для цієї тварини.",
            )
            return

        # Скачування зображення
        try:
            image_response = requests.get(pet_image_url)
            image_response.raise_for_status()

            # Якщо все гаразд, збережемо зображення у пам'яті
            image = BytesIO(image_response.content)
            image.name = 'pet_image.jpg'  # Ім'я файлу

            pet_data = f"Ім'я: {pet_name}\nВік: {pet_age} \n`{pet_story}`"

            keyboard = [
                [
                    InlineKeyboardButton('<<', callback_data='prev'),
                    InlineKeyboardButton("Подарувати сім`ю", callback_data='givefamily'),
                    InlineKeyboardButton('>>', callback_data='next')
                ],
                [InlineKeyboardButton('У головне меню', callback_data='menu')],
            ]

            if update.callback_query:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=update.callback_query.message.message_id
                )

            # Відправка фото з підписом
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image,  # Надсилаємо зображення з пам'яті
                caption=pet_data,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except requests.exceptions.RequestException as e:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Помилка при скачуванні зображення: {e}",
            )
