from abc import ABC, abstractmethod

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN1_ID, ADMIN2_ID


ADMINS = {int(ADMIN1_ID), int(ADMIN2_ID)}


class BaseHandler(ABC):
    session = None

    @classmethod
    @abstractmethod
    def register(cls, app, button_handler):
        pass

    @classmethod
    def set_session(cls, session):
        cls.session = session

    @staticmethod
    def is_admin(user_id: int) -> bool:
        return user_id in ADMINS

    @staticmethod
    async def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        user_id = update.effective_user.id
        if not BaseHandler.is_admin(user_id):
            await update.message.reply_text("У вас немає прав для цієї дії.")
            return False
        return True

    @staticmethod
    def add_admin(user_id: int) -> bool:
        if user_id not in ADMINS:
            ADMINS.add(user_id)
            return True
        return False

    @staticmethod
    def get_admins() -> list:
        return list(ADMINS)
