import asyncio
import logging
import pathlib

import aiosqlite
from .combined_adoption_scraper_and_def_scraper import fetch, extract_profile, collect_profile_urls_list
from .adoption_photos_downloader import process_profile
import aiohttp

BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()  # Крок назад від папки parser
DB_NAME = str(BASE_DIR / "sirius.db")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def update_profiles(session, db, species_id):
    urls = await collect_profile_urls_list(session, species_id)
    logging.info(f"Зібрано {len(urls)} профілів виду {species_id}")

    async with db.execute("SELECT id, ProfileURL, MyStory, PhotoURL FROM animals WHERE Species = ?",
                          (species_id,)) as cursor:
        existing_profiles = {row["ProfileURL"]: row for row in await cursor.fetchall()}
    logging.info(f"Існуючі профілі виду {species_id}: {len(existing_profiles)}")

    for url in urls:
        try:
            html = await fetch(session, url)
            if not html:
                continue
            data = await extract_profile(html, url, "Пес" if species_id == 1 else "Кіт")
            existing = existing_profiles.get(url)

            if not existing:
                try:
                    cursor = await db.execute('''
                        INSERT OR IGNORE INTO animals
                        (ProfileURL, Name, Age, Gender, Size, SkillsAndCharacter, MyStory, PhotoURL, Species)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data["ProfileURL"], data["Name"], data["Age"], data["Gender"],
                        data["Size"], data["SkillsAndCharacter"], data["MyStory"],
                        data["PhotoURL"], data["Species"]
                    ))

                    if cursor.rowcount > 0:
                        logging.info(f"Новий профіль додано: {data['Name']} ({url})")
                        # Додаємо в existing_profiles, щоб не дублювати
                        existing_profiles[url] = data
                    else:
                        logging.info(f"Профіль вже існує, пропускаємо: {url}")

                except Exception as e:
                    logging.error(f"Помилка при вставці нового профілю {url}: {e}")
            else:
                if existing["MyStory"] != data["MyStory"] or existing["PhotoURL"] != data["PhotoURL"]:
                    try:
                        await db.execute('''
                            UPDATE animals SET
                            Name = ?, Age = ?, Gender = ?, Size = ?, SkillsAndCharacter = ?, MyStory = ?, PhotoURL = ?
                            WHERE ProfileURL = ?
                        ''', (
                            data["Name"], data["Age"], data["Gender"], data["Size"],
                            data["SkillsAndCharacter"], data["MyStory"], data["PhotoURL"], data["ProfileURL"]
                        ))
                        logging.info(f"Оновлено профіль: {data['Name']} ({url})")
                        # Оновлюємо existing_profiles теж
                        existing_profiles[url] = data
                    except Exception as e:
                        logging.error(f"Помилка при оновленні профілю {url}: {e}")

        except Exception as e:
            logging.error(f"Помилка при обробці профілю {url}: {e}")

    await db.commit()
    return urls


async def update_photos(session, db, urls):
    to_process = []
    if not urls:
        return
    try:
        async with db.execute(
                "SELECT id, ProfileURL, Name, PhotoURL FROM animals WHERE ProfileURL IN ({seq})".format(
                    seq=','.join('?' for _ in urls)), tuple(urls)
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                to_process.append((row["id"], row["ProfileURL"], row["Name"]))
    except Exception as e:
        logging.error(f"Помилка при вибірці профілів для фото: {e}")
        return

    sem = asyncio.Semaphore(5)

    async def process(id_, url, name):
        try:
            await process_profile(sem, session, db, id_, url, name)
        except Exception as e:
            logging.error(f"Помилка при завантаженні фото профілю {url}: {e}")

    await asyncio.gather(*(process(id_, url, name) for id_, url, name in to_process))
    await db.commit()


async def main_loop():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
            try:
                while True:
                    logging.info("Починаємо цикл оновлення профілів")
                    all_urls = set()
                    for species_id in [1, 2]:
                        urls = await update_profiles(session, db, species_id)
                        all_urls.update(urls)

                    if all_urls:
                        logging.info("Оновлюємо фото профілів")
                        await update_photos(session, db, all_urls)

                    logging.info("Чекаємо день до наступної перевірки")
                    await asyncio.sleep(86400)
            except asyncio.CancelledError:
                logging.info("Основний цикл зупинено користувачем")
            except Exception as e:
                logging.error(f"Несподівана помилка в основному циклі: {e}")
            finally:
                await db.commit()
                logging.info("Збережено всі зміни перед виходом.")


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt as e:
        logging.info(f"Програма зупинена користувачем {e}")
