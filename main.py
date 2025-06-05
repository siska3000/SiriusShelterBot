import asyncio
import logging
import inspect
from telegram.ext import ApplicationBuilder, CallbackQueryHandler
from config import TELEGRAM_TOKEN
import handlers
from handlers.base_handler import BaseHandler
from keyboards.callback_handler import ButtonCallbackHandler

# Твої імпорти для watcher
from parser.watcher import main_loop  # Припустимо, що main_loop у файлі watcher.py


logging.basicConfig(level=logging.INFO)
global_button_handler = ButtonCallbackHandler()


async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    for name, obj in inspect.getmembers(handlers):
        if inspect.isclass(obj) and issubclass(obj, BaseHandler) and obj is not BaseHandler:
            obj.register(app, global_button_handler)

    app.add_handler(CallbackQueryHandler(global_button_handler.handle_button_callback))

    # Запускаємо watcher як бекграунд таску
    watcher_task = asyncio.create_task(main_loop())

    # Запускаємо бота
    await app.initialize()
    await app.start()

    logging.info("Бот запущено")

    # Запускаємо polling (бот починає отримувати оновлення)
    await app.updater.start_polling()
    logging.info("Polling стартував")

    # Очікуємо завершення програми (Ctrl+C)
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("Зупинка...")

    # Зупиняємо polling та бота
    await app.updater.stop_polling()
    await app.stop()
    logging.info("Бот зупинено")

    # Скасовуємо watcher
    watcher_task.cancel()
    try:
        await watcher_task
    except asyncio.CancelledError:
        logging.info("Watcher зупинено")


if __name__ == '__main__':
    asyncio.run(main())
