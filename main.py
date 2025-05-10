from telegram.ext import ApplicationBuilder, CallbackQueryHandler
from config import TELEGRAM_TOKEN
import handlers
from handlers.base_handler import BaseHandler
from keyboards.callback_handler import ButtonCallbackHandler
import inspect
import logging

# Логування
logging.basicConfig(level=logging.INFO)

# Глобальний екземпляр обробника кнопок
global_button_handler = ButtonCallbackHandler()

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Передаємо глобальний button handler у кожен handler
    for name, obj in inspect.getmembers(handlers):
        if inspect.isclass(obj) and issubclass(obj, BaseHandler) and obj is not BaseHandler:
            obj.register(app, global_button_handler)

    # Один загальний CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(global_button_handler.handle_button_callback))

    app.run_polling()
