from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from handlers.base_handler import BaseHandler


class SupportHandler(BaseHandler):
    @classmethod
    def register(cls, app, button_handler=None):
        app.add_handler(CallbackQueryHandler(cls.callback, pattern="^support$"))

    @staticmethod
    async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "💸 <b>Реквізити для підтримки:</b>\n\n"
            "<a href='https://www.liqpay.ua/uk/checkout/i56164989738'>Liq Pay</a>\n\n"

            "За реквізитами: р/р ГО Притулок для тварин 'Сіріус'\n"
            "• <b>Код отримувача:</b> <code>42703881</code>\n"
            "• <b>Назва банку:</b> Столична філія АТ КБ \"Приватбанк\"\n"
            "• <b>Рахунок отримувача:</b> <code>UA433052990000026000016800800</code>\n"
            "• <b>Валюта:</b> <code>UAH</code>\n"
            "• <b>Код банку (МФО):</b> <code>305299</code>\n\n"

            "• <b>Privat24:</b> <code>5169 3351 0905 5497</code>\n\n"

            "<a href='https://secure.wayforpay.com/donate/dogcat_com_ua'>WayforPay</a>\n"
            "<a href='https://bekind.ua/en/foundation?id=1499284'>Для Європи та США</a>\n"
            "<a href='https://www.portmone.com.ua/r3/dopomoha-tvarynam-animal-shelter-sirius'>Portmone</a>\n\n"
            "Дякуємо за вашу підтримку! ❤️"
        )

        if update.callback_query:
            await context.bot.delete_message(
                chat_id=update.callback_query.message.chat_id,
                message_id=update.callback_query.message.message_id
            )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
