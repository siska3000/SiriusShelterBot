import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.base_handler import BaseHandler


class NextPetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        # button_handler.register_callback('allpets', cls.callback)
        # button_handler.register_callback('menu', cls.callback)
        button_handler.register_callback('next', cls.callback)
        # button_handler.register_callback('prev', cls.callback)

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

        # Індекс поточної тварини
        current_index = context.user_data.get("pet_index", 0)
        next_index = (current_index + 1) % len(df)  # Зациклюється

        context.user_data["pet_index"] = next_index
        pet = df.iloc[next_index]

        pet_data = f"Ім'я: {pet['Name']}\nВік: {pet['Age']} років\n`{pet['MyStory']}`\n {pet['PhotoURL']}"

        keyboard = [
            [
                InlineKeyboardButton('<<', callback_data='prev'),
                InlineKeyboardButton('Забрати', callback_data='choose'),
                InlineKeyboardButton('>>', callback_data='next')
            ],
            [InlineKeyboardButton('У головне меню', callback_data='menu')],
        ]

        if update.callback_query:
            await context.bot.delete_message(
                chat_id=update.callback_query.message.chat_id,
                message_id=update.callback_query.message.message_id
            )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=pet_data,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
