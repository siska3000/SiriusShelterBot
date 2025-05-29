import hashlib
import logging
import os
import sqlite3
import time
from typing import Set, Tuple, Optional

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ===== КОНСТАНТИ =====
PHOTO_DIR = 'photos'
DB_NAME = 'sirius.db'
CHECK_INTERVAL = 60  # раз на хвилину
MAX_RETRIES = 3
REQUEST_TIMEOUT = 10

# ===== ЛОГУВАННЯ =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ===== ДОПОМІЖНІ ФУНКЦІЇ =====
def initialize_db() -> None:
    """Ініціалізація бази даних."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS animals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def clean_text(text: Optional[str]) -> str:
    """Очищення тексту від зайвих символів та пробілів."""
    if not text:
        return ""
    replacements = ["Додати в обране", "В обраному", "Подарувати сім'ю"]
    for rep in replacements:
        text = text.replace(rep, "")
    return " ".join(text.split())


def load_existing_urls() -> Set[str]:
    """Завантаження існуючих URL з бази даних."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ProfileURL FROM animals")
        return {row[0] for row in cursor.fetchall()}


def setup_driver() -> webdriver.Chrome:
    """Налаштування Selenium WebDriver."""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    return webdriver.Chrome(options=options)


def download_photo(photo_url: str, animal_name: str, profile_url: str) -> str:
    """Завантаження та збереження фото тварини."""
    try:
        url_hash = hashlib.md5(profile_url.encode('utf-8')).hexdigest()
        cleaned_name = "".join(
            c for c in animal_name if c.isalnum() or c in (' ', '_')
        ).replace(' ', '_') or "unknown_animal"

        filename = f"{cleaned_name}_{url_hash}.jpg"
        filepath = os.path.join(PHOTO_DIR, filename)

        if not os.path.exists(filepath):
            response = requests.get(photo_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            with open(filepath, 'wb') as f:
                f.write(response.content)
            logger.info(f"🖼️ Фото збережено: {filepath}")
        else:
            logger.info(f"📂 Фото вже існує: {filepath}")

        return filepath.replace("\\", "/")
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ Помилка завантаження фото {photo_url}: {e}")
        return photo_url
    except Exception as e:
        logger.warning(f"⚠️ Загальна помилка при обробці фото {photo_url}: {e}")
        return photo_url


def process_animal_profile(
        driver: webdriver.Chrome,
        wait: WebDriverWait,
        full_url: str,
        species_name: str,
        conn: sqlite3.Connection
) -> bool:
    """Обробка профілю тварини та збереження даних."""
    try:
        for _ in range(MAX_RETRIES):
            try:
                driver.get(full_url)
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "profile-head")))
                break
            except TimeoutException:
                logger.warning(f"⚠️ Таймаут завантаження сторінки {full_url}, спроба {_ + 1}/{MAX_RETRIES}")
                time.sleep(2)
        else:
            logger.error(f"❌ Не вдалося завантажити сторінку {full_url} після {MAX_RETRIES} спроб")
            return False

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        animal_data = {
            "Name": "", "Age": "", "Gender": "", "Size": "",
            "SkillsAndCharacter": "", "MyStory": "", "PhotoURL": "",
            "ProfileURL": full_url, "Species": species_name
        }

        # Обробка заголовка профілю
        if head := soup.find('div', class_='profile-head'):
            if name_tag := head.find('h3'):
                animal_data['Name'] = clean_text(name_tag.text)

            if secondary := head.find('div', class_='body-secondary'):
                parts = [p.strip() for p in clean_text(secondary.text).split(',')]
                animal_data['Gender'] = parts[0] if parts else ''
                animal_data['Age'] = parts[1] if len(parts) > 1 else ''

        # Обробка навичок та розміру
        if skills_block := soup.find('div', class_='profile-skills'):
            skills = []
            for item in skills_block.find_all('div', class_='item'):
                skill = clean_text(item.text)
                if 'розмір' in skill.lower():
                    animal_data['Size'] = skill
                elif skill.lower() != animal_data['Gender'].lower():
                    skills.append(skill)
            animal_data['SkillsAndCharacter'] = ", ".join(skills)

        # Обробка історії
        if history_block := soup.find('div', class_='profile-history'):
            for h4 in history_block.find_all('h4'):
                h4.decompose()
            animal_data['MyStory'] = clean_text(history_block.get_text(separator=' ', strip=True))

        # Обробка фото
        photo_url_on_site = ''
        try:
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".swiper-slide-active img, .profile-photo img")))
            soup_photo = BeautifulSoup(driver.page_source, 'html.parser')
            if img := (soup_photo.select_one('.swiper-slide-active img') or
                       soup_photo.select_one('.profile-photo img')):
                photo_url_on_site = img.get('data-src-default') or img.get('src', '')
                if photo_url_on_site and not photo_url_on_site.startswith("http"):
                    photo_url_on_site = f"https://dogcat.com.ua{photo_url_on_site}"
        except TimeoutException:
            logger.warning(f"⚠️ Фото не завантажено для {full_url} — таймаут")

        if photo_url_on_site:
            animal_data['PhotoURL'] = download_photo(
                photo_url_on_site, animal_data['Name'], full_url
            )
        else:
            animal_data['PhotoURL'] = ""

        # Збереження в базу даних
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO animals (
                ProfileURL, Name, Age, Gender, Size, 
                SkillsAndCharacter, MyStory, PhotoURL, Species
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            animal_data['ProfileURL'], animal_data['Name'], animal_data['Age'],
            animal_data['Gender'], animal_data['Size'], animal_data['SkillsAndCharacter'],
            animal_data['MyStory'], animal_data['PhotoURL'], animal_data['Species']
        ))

        if cursor.rowcount > 0:
            conn.commit()
            logger.info(f"💾 Нова тваринка додана до БД: {full_url}")
            return True
        return False

    except Exception as e:
        logger.error(f"❌ Помилка обробки профілю ({full_url}): {e}")
        return False


def process_species_page(
        driver: webdriver.Chrome,
        wait: WebDriverWait,
        base_url: str,
        species_name: str,
        conn: sqlite3.Connection,
        existing_urls: Set[str]
) -> Tuple[int, Set[str]]:
    """Обробка сторінок з тваринами одного виду."""
    new_animals_count = 0
    live_urls = set()
    page = 1

    while True:
        page_url = f"{base_url}{page}"
        logger.info(f"📄 {species_name} | Сторінка {page}: {page_url}")

        try:
            driver.get(page_url)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "animalCard__link")))

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            links_on_page = {
                a.get('href') if a.get('href', '').startswith("http")
                else f"https://dogcat.com.ua{a.get('href')}"
                for a in soup.find_all('a', class_='animalCard__link preloadPage')
            }

            if not links_on_page:
                break

            live_urls.update(links_on_page)

            for full_url in links_on_page:
                if full_url not in existing_urls:
                    if process_animal_profile(driver, wait, full_url, species_name, conn):
                        new_animals_count += 1
                        existing_urls.add(full_url)

        except Exception as e:
            logger.error(f"❌ Помилка сторінки ({page_url}): {e}")
            break

        page += 1
        time.sleep(0.5)

    return new_animals_count, live_urls


def remove_missing_animals(urls_to_delete: Set[str]) -> int:
    """Видалення тварин, яких більше немає на сайті."""
    deleted_count = 0
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        for url in urls_to_delete:
            # Отримуємо шлях до фото перед видаленням
            cursor.execute("SELECT PhotoURL FROM animals WHERE ProfileURL = ?", (url,))
            if row := cursor.fetchone():
                photo_path = row[0]
                # Видаляємо запис з БД
                cursor.execute("DELETE FROM animals WHERE ProfileURL = ?", (url,))
                if cursor.rowcount > 0:
                    deleted_count += 1
                    logger.info(f"🗑️ Видалено з БД: {url}")

                    # Видаляємо фото, якщо воно існує локально
                    if (photo_path and os.path.exists(photo_path) and
                            os.path.abspath(PHOTO_DIR) in os.path.abspath(photo_path)):
                        try:
                            os.remove(photo_path)
                            logger.info(f"🖼️ Видалено фото: {photo_path}")
                        except OSError as e:
                            logger.warning(f"⚠️ Не вдалося видалити фото {photo_path}: {e}")

        if deleted_count > 0:
            conn.commit()

    return deleted_count


def main_loop() -> None:
    """Головний цикл програми."""
    os.makedirs(PHOTO_DIR, exist_ok=True)
    initialize_db()

    while True:
        try:
            existing_urls = load_existing_urls()
            live_urls = set()
            new_animals_count = 0

            driver = setup_driver()
            wait = WebDriverWait(driver, 15)

            try:
                with sqlite3.connect(DB_NAME) as conn:
                    species_pages = [
                        ("Пес", "https://dogcat.com.ua/adoption?animal=1&page="),
                        ("Кіт", "https://dogcat.com.ua/adoption?animal=2&page=")
                    ]

                    for species_name, base_url in species_pages:
                        count, urls = process_species_page(
                            driver, wait, base_url, species_name, conn, existing_urls
                        )
                        new_animals_count += count
                        live_urls.update(urls)

                # Видалення тварин, яких більше немає на сайті
                urls_to_delete = existing_urls - live_urls
                if urls_to_delete:
                    deleted_count = remove_missing_animals(urls_to_delete)
                    logger.info(f"✅ Видалено {deleted_count} тварин з БД")
                else:
                    logger.info("👍 Усі тваринки з бази даних присутні на сайті")

                if new_animals_count > 0:
                    logger.info(f"✅ Додано {new_animals_count} нових тварин")
                else:
                    logger.info("🔍 Нових тварин не знайдено")

            finally:
                driver.quit()

            logger.info(f"🕒 Наступна перевірка через {CHECK_INTERVAL} секунд")
            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"🔥 Критична помилка: {e}")
            logger.info("🕒 Спроба перезапуску через 60 секунд")
            time.sleep(60)


if __name__ == "__main__":
    main_loop()
