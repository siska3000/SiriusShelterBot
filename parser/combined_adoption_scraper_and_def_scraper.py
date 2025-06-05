import asyncio
import aiohttp
import aiosqlite
from bs4 import BeautifulSoup
import logging
import os
import pathlib

BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()  # Крок назад від папки parser
DB_NAME = str(BASE_DIR / "sirius.db")
BASE_URL = "https://dogcat.com.ua"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def clean(text):
    return " ".join((text or "").replace("Додати в обране", "").replace("В обраному", "").split())


async def fetch(session, url):
    try:
        async with session.get(url, timeout=15) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        logging.warning(f"❌ Не вдалося отримати {url}: {e}")
        return None


async def extract_profile(html, url, species):
    soup = BeautifulSoup(html, "html.parser")
    name = clean(soup.find("h3").text if soup.find("h3") else "")

    secondary = soup.find("div", class_="body-secondary")
    gender, age = "", ""
    if secondary:
        parts = clean(secondary.text).split(",")
        gender = parts[0].strip() if len(parts) > 0 else ""
        age = parts[1].strip() if len(parts) > 1 else ""

    size = ""
    skills_list = []
    skills = soup.find("div", class_="profile-skills")
    if skills:
        for i in skills.find_all("div", class_="item"):
            text = clean(i.text)
            if "розмір" in text.lower():
                size = text
            else:
                skills_list.append(text)

    story = ""
    history = soup.find("div", class_="profile-history")
    if history:
        [h4.decompose() for h4 in history.find_all("h4")]
        story = clean(history.get_text())

    return {
        "ProfileURL": url,
        "Name": name,
        "Age": age,
        "Gender": gender,
        "Size": size,
        "SkillsAndCharacter": ", ".join(skills_list),
        "MyStory": story,
        "PhotoURL": "",  # тут можна додати фото якщо треба
        "Species": species
    }


async def collect_profile_urls(session, species_id, queue):
    page = 1
    while True:
        url = f"{BASE_URL}/adoption?animal={species_id}&page={page}"
        html = await fetch(session, url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        page_urls = {
            a["href"] for a in soup.select("a.animalCard__link") if a.get("href")
        }

        if not page_urls:
            break

        for href in page_urls:
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            await queue.put((full_url, species_id))

        page += 1

    logging.info(f"Закінчив збір URL для виду {species_id}")


async def collect_profile_urls_list(session, species_id):
    page = 1
    urls = set()
    while True:
        url = f"{BASE_URL}/adoption?animal={species_id}&page={page}"
        html = await fetch(session, url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        page_urls = {
            a["href"] for a in soup.select("a.animalCard__link") if a.get("href")
        }
        if not page_urls:
            break

        for href in page_urls:
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            urls.add(full_url)

        page += 1

    logging.info(f"Закінчив збір URL для виду {species_id}, знайдено {len(urls)}")
    return list(urls)


async def worker(name, session, db, queue):
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break
        url, species = item
        html = await fetch(session, url)
        if html:
            data = await extract_profile(html, url, "Пес" if species == 1 else "Кіт")
            await db.execute('''
                INSERT OR REPLACE INTO animals
                (ProfileURL, Name, Age, Gender, Size, SkillsAndCharacter, MyStory, PhotoURL, Species)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data["ProfileURL"], data["Name"], data["Age"], data["Gender"],
                data["Size"], data["SkillsAndCharacter"], data["MyStory"],
                data["PhotoURL"], data["Species"]
            ))
            await db.commit()
            logging.info(f"[{name}] Збережено профіль: {data['Name']} ({url})")
        else:
            logging.warning(f"[{name}] Пропущено профіль через помилку: {url}")
        queue.task_done()


async def main():
    os.makedirs("photos", exist_ok=True)

    queue = asyncio.Queue()

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS animals (
                id INTEGER PRIMARY KEY,
                ProfileURL TEXT UNIQUE,
                Name TEXT,
                Age TEXT,
                Gender TEXT,
                Size TEXT,
                SkillsAndCharacter TEXT,
                MyStory TEXT,
                PhotoURL TEXT,
                Species TEXT
            )
        ''')
        await db.commit()

        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
            collectors = [
                collect_profile_urls(session, species_id, queue)
                for species_id in [1, 2]
            ]

            workers = [
                asyncio.create_task(worker(f"Worker-{i + 1}", session, db, queue))
                for i in range(10)
            ]

            await asyncio.gather(*collectors)

            for _ in workers:
                await queue.put(None)

            await queue.join()
            await asyncio.gather(*workers)

    logging.info("✅ Асинхронний поточний скрапінг завершено.")


if __name__ == "__main__":
    asyncio.run(main())
