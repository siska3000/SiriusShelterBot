from telegram import Update
from telegram.ext import ContextTypes
from handlers.base_handler import BaseHandler
from handlers.animal_handlers.next_pet import NextPetHandler


class PrevPetHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler):
        button_handler.register_callback('prev', cls.callback)

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        current_index = context.user_data.get('pet_index', 0)
        context.user_data['pet_index'] = current_index - 1
        await NextPetHandler.show_pet(update, context)
