import asyncio
import pathlib

import aiohttp
import aiofiles
import sqlite3
import re
import os
import hashlib
import logging
from bs4 import BeautifulSoup


BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()  # Крок назад від папки parser
DB_PATH = str(BASE_DIR / "sirius.db")


PHOTO_DIR = BASE_DIR / "photos"
PHOTO_DIR.mkdir(exist_ok=True, parents=True)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def sanitize_filename(name: str, url: str) -> str:
    ext = os.path.splitext(url)[1] or '.jpg'
    name_safe = re.sub(r'[^\w\- ]', '_', name).strip()
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
    return f"{name_safe}_{url_hash}{ext}"


async def fetch_html(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        logging.warning(f"[{url}] Неможливо отримати HTML: {e}")
        return None


async def get_photo_url_from_profile(session, profile_url):
    html = await fetch_html(session, profile_url)
    if not html:
        return ""

    soup = BeautifulSoup(html, 'html.parser')
    img = soup.select_one('img.swiper-lazy')
    if img:
        src = img.get('data-src') or img.get('src')
        if src:
            return src if src.startswith('http') else f"https://dogcat.com.ua{src}"
    return ""


async def download_image(session, url, filename):
    path = PHOTO_DIR / filename
    if path.exists():
        return str(path)

    try:
        async with session.get(url, timeout=15) as response:
            response.raise_for_status()
            async with aiofiles.open(path, 'wb') as f:
                await f.write(await response.read())
            logging.info(f"Збережено: {path}")
            return str(path)
    except Exception as e:
        logging.warning(f"Помилка при завантаженні {url}: {e}")
        return ""


async def process_profile(sem, session, db, id_, profile_url, name):
    async with sem:
        logging.info(f"Обробка профілю: {profile_url}")
        image_url = await get_photo_url_from_profile(session, profile_url)

        if image_url:
            filename = sanitize_filename(name or f"id_{id_}", image_url)
            local_path = await download_image(session, image_url, filename)

            if local_path:
                db.execute("UPDATE animals SET PhotoURL = ? WHERE id = ?", (local_path, id_))
        else:
            logging.warning(f"Фото не знайдено: {profile_url}")


async def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, ProfileURL, Name FROM animals WHERE PhotoURL IS NULL OR PhotoURL = ''")
    rows = cursor.fetchall()
    if not rows:
        logging.info("Немає профілів для обробки.")
        return

    sem = asyncio.Semaphore(10)  # Максимум одночасних завантажень
    async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
        tasks = [
            process_profile(sem, session, conn, row["id"], row["ProfileURL"], row["Name"])
            for row in rows
        ]
        await asyncio.gather(*tasks)

    conn.commit()
    conn.close()
    logging.info("Завантаження завершено.")


if __name__ == "__main__":
    asyncio.run(main())
