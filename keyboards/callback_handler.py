from telegram import Update
from telegram.ext import ContextTypes
from typing import Callable, Dict


class ButtonCallbackHandler:
    def __init__(self):
        self.callback_map: Dict[str, Callable[[Update, ContextTypes.DEFAULT_TYPE], None]] = {}

    def register_callback(self, action: str, callback: Callable[[Update, ContextTypes.DEFAULT_TYPE], None]):
        """Реєструє колбек для певної дії"""
        self.callback_map[action] = callback

    async def handle_button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data

        print(f"Натиснута кнопка: {data}")

        # Якщо є зареєстрована callback-функція для data — викликаємо її
        if data in self.callback_map:
            await self.callback_map[data](update, context)
        else:
            await query.edit_message_text("Невідома дія.")
