import hashlib
import logging
import os
import sqlite3
import time

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

# ===== ЛОГУВАННЯ =====
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ===== СТВОРЕННЯ ПАПКИ ДЛЯ ФОТО =====
os.makedirs(PHOTO_DIR, exist_ok=True)


# ===== ФУНКЦІЯ ІНІЦІАЛІЗАЦІЇ БАЗИ ДАНИХ =====
def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
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
    conn.commit()
    conn.close()


# ===== ФУНКЦІЯ ОЧИСТКИ ТЕКСТУ =====
def clean_text(text):
    if not text:
        return ""
    text = text.replace("Додати в обране", "").replace("В обраному", "")
    text = text.replace("Подарувати сім'ю", "")
    return " ".join(text.split())


# ===== ФУНКЦІЯ ДЛЯ ЗАВАНТАЖЕННЯ ІСНУЮЧИХ URL З БАЗИ ДАНИХ =====
def load_existing_urls_from_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT ProfileURL FROM animals")
    existing_urls = {row[0] for row in c.fetchall()}
    conn.close()
    return existing_urls


# Ініціалізація бази даних при старті скрипта
initialize_db()

# ===== ОСНОВНИЙ ЦИКЛ ПЕРЕВІРКИ =====
while True:
    try:
        # --- Отримати початковий стан URL-адрес у БД ---
        urls_in_db_at_start_of_run = load_existing_urls_from_db()
        # --- Множина для відстеження всіх URL-адрес, знайдених на сайті під час поточного запуску ---
        live_urls_found_this_run = set()
        # --- Множина для URL-адрес, які вже є в БД або оброблені для вставки в цьому запуску (щоб уникнути повторного скрейпінгу деталей) ---
        urls_to_skip_detailed_processing = set(urls_in_db_at_start_of_run)

        new_animals_actually_added_count = 0

        # ===== НАЛАШТУВАННЯ SELENIUM =====
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--window-size=1920,1080')

        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 15)
        conn_insert = sqlite3.connect(DB_NAME)
        c_insert = conn_insert.cursor()

        species_urls = [
            ("Пес", "https://dogcat.com.ua/adoption?animal=1&page="),
            ("Кіт", "https://dogcat.com.ua/adoption?animal=2&page=")
        ]

        for species_name, base_url in species_urls:
            page = 1
            while True:
                page_url = f"{base_url}{page}"
                try:
                    logging.info(f"📄 {species_name} | Сторінка {page}: {page_url}")
                    driver.get(page_url)
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "animalCard__link")))

                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    links_on_page = {a.get('href') for a in soup.find_all('a', class_='animalCard__link preloadPage')}

                    if not links_on_page:
                        break

                    for link_path in links_on_page:
                        full_url = link_path if link_path.startswith("http") else f"https://dogcat.com.ua{link_path}"

                        live_urls_found_this_run.add(full_url)

                        if full_url in urls_to_skip_detailed_processing:
                            continue

                        logging.info(f"🐾 Обробка профілю ({species_name}): {full_url}")
                        try:
                            driver.get(full_url)
                            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "profile-head")))
                            soup1 = BeautifulSoup(driver.page_source, 'html.parser')

                            animal_data = {
                                "Name": "", "Age": "", "Gender": "", "Size": "",
                                "SkillsAndCharacter": "", "MyStory": "", "PhotoURL": "",
                                "ProfileURL": full_url,
                                "Species": species_name
                            }

                            head = soup1.find('div', class_='profile-head')
                            if head:
                                name_tag = head.find('h3')
                                if name_tag:
                                    animal_data['Name'] = clean_text(name_tag.text)

                                secondary = head.find('div', class_='body-secondary')
                                if secondary:
                                    parts = [p.strip() for p in clean_text(secondary.text).split(',')]
                                    animal_data['Gender'] = parts[0] if len(parts) > 0 else ''
                                    animal_data['Age'] = parts[1] if len(parts) > 1 else ''

                            # Навички, розмір
                            skills_block = soup1.find('div', class_='profile-skills')
                            skills = []
                            if skills_block:
                                for item in skills_block.find_all('div', class_='item'):
                                    skill = clean_text(item.text)
                                    if 'розмір' in skill.lower():
                                        animal_data['Size'] = skill
                                    elif skill.lower() != animal_data['Gender'].lower():  # Уникаємо дублювання статі
                                        skills.append(skill)
                            animal_data['SkillsAndCharacter'] = ", ".join(skills)

                            # Історія
                            history_block = soup1.find('div', class_='profile-history')
                            if history_block:
                                for h4 in history_block.find_all('h4'): h4.decompose()
                                animal_data['MyStory'] = clean_text(history_block.get_text(separator=' ', strip=True))

                            # Фото
                            photo_url_on_site = ''
                            try:
                                wait.until(EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, ".swiper-slide-active img, .profile-photo img")))
                            except TimeoutException:
                                logging.warning(f"⚠️ Фото не завантажено для {full_url} — таймаут")

                            # Повторно отримуємо soup після очікування фото, якщо DOM змінився
                            soup_photo = BeautifulSoup(driver.page_source, 'html.parser')
                            img = soup_photo.select_one('.swiper-slide-active img') or soup_photo.select_one(
                                '.profile-photo img')

                            if img:
                                photo_url_on_site = img.get('data-src-default') or img.get('src', '')
                                if photo_url_on_site and not photo_url_on_site.startswith("http"):
                                    photo_url_on_site = f"https://dogcat.com.ua{photo_url_on_site}"

                            animal_data['PhotoURL'] = ""  # За замовчуванням порожньо
                            if photo_url_on_site:
                                try:
                                    url_hash = hashlib.md5(full_url.encode('utf-8')).hexdigest()
                                    cleaned_name = "".join(
                                        c for c in animal_data['Name'] if c.isalnum() or c in (' ', '_')).replace(' ',
                                                                                                                  '_')
                                    if not cleaned_name: cleaned_name = "unknown_animal"

                                    filename = f"{cleaned_name}_{url_hash}.jpg"
                                    filepath = os.path.join(PHOTO_DIR, filename)

                                    if not os.path.exists(filepath):
                                        response = requests.get(photo_url_on_site, timeout=10)
                                        response.raise_for_status()  # Перевірка на помилки HTTP
                                        with open(filepath, 'wb') as f:
                                            f.write(response.content)
                                        logging.info(f"🖼️ Фото збережено: {filepath}")
                                    else:
                                        logging.info(f"📂 Фото вже існує: {filepath}")
                                    animal_data['PhotoURL'] = filepath.replace("\\", "/")
                                except requests.exceptions.RequestException as e_img_req:
                                    logging.warning(
                                        f"⚠️ Помилка запиту при завантаженні фото {photo_url_on_site}: {e_img_req}")
                                    animal_data[
                                        'PhotoURL'] = photo_url_on_site
                                except Exception as e_img:
                                    logging.warning(
                                        f"⚠️ Загальна помилка при завантаженні фото {photo_url_on_site}: {e_img}")
                                    animal_data['PhotoURL'] = photo_url_on_site

                            # --- Збереження в базу даних ---
                            c_insert.execute('''
                                INSERT OR IGNORE INTO animals (ProfileURL, Name, Age, Gender, Size, SkillsAndCharacter, MyStory, PhotoURL, Species)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                animal_data['ProfileURL'], animal_data['Name'], animal_data['Age'],
                                animal_data['Gender'], animal_data['Size'], animal_data['SkillsAndCharacter'],
                                animal_data['MyStory'], animal_data['PhotoURL'], animal_data['Species']
                            ))
                            if c_insert.rowcount > 0:
                                new_animals_actually_added_count += 1
                                conn_insert.commit()
                                urls_to_skip_detailed_processing.add(
                                    full_url)
                                logging.info(f"💾 Нова тваринка додана до БД: {full_url}")

                        except Exception as e_animal:
                            logging.error(f"❌ Помилка обробки профілю ({full_url}): {e_animal}")
                except Exception as e_page:
                    logging.error(f"❌ Критична помилка сторінки ({page_url}): {e_page}")
                    break

                page += 1
                time.sleep(0.5)

        driver.quit()
        conn_insert.close()  # Закриваємо з'єднання для вставок

        if new_animals_actually_added_count > 0:
            logging.info(f"✅ Успішно додано нових тварин до '{DB_NAME}': {new_animals_actually_added_count}")
        else:
            logging.info("🔍 Нових тварин для додавання до БД не знайдено.")

        # --- Видалення тварин, яких більше немає на сайті ---
        urls_to_delete_from_db = urls_in_db_at_start_of_run - live_urls_found_this_run

        if urls_to_delete_from_db:
            logging.info(f"ℹ️ Знайдено {len(urls_to_delete_from_db)} тварин для видалення (більше не на сайті).")
            conn_delete = sqlite3.connect(DB_NAME)
            c_delete = conn_delete.cursor()
            deleted_animals_from_db_count = 0

            for url_to_remove in urls_to_delete_from_db:
                # Спочатку отримуємо шлях до фото, щоб видалити файл
                c_delete.execute("SELECT PhotoURL FROM animals WHERE ProfileURL = ?", (url_to_remove,))
                row = c_delete.fetchone()
                photo_path_to_delete = row[0] if row and row[0] else None

                # Видаляємо запис з БД
                c_delete.execute("DELETE FROM animals WHERE ProfileURL = ?", (url_to_remove,))
                if c_delete.rowcount > 0:  # Якщо запис було фактично видалено
                    deleted_animals_from_db_count += 1
                    logging.info(f"🗑️ Видалено з БД: {url_to_remove}")

                    # Видаляємо фото-файл, якщо він існує і є локальним шляхом
                    if photo_path_to_delete and os.path.exists(
                            photo_path_to_delete) and PHOTO_DIR in photo_path_to_delete:
                        try:
                            os.remove(photo_path_to_delete)
                            logging.info(f"🖼️ Видалено фото-файл: {photo_path_to_delete}")
                        except OSError as e_photo_del:
                            logging.warning(f"⚠️ Не вдалося видалити фото-файл {photo_path_to_delete}: {e_photo_del}")
                    elif photo_path_to_delete:
                        logging.info(
                            f"ℹ️ Фото-файл не видалено (або не знайдено локально, або це URL): {photo_path_to_delete}")
                else:
                    logging.warning(
                        f"⚠️ Тваринка {url_to_remove} не знайдена в БД для видалення (можливо, вже видалена).")

            if deleted_animals_from_db_count > 0:
                conn_delete.commit()  # Комітимо всі видалення
                logging.info(f"✅ Завершено видалення {deleted_animals_from_db_count} тварин з БД.")
            else:
                logging.info(f"ℹ️ Не було фактично видалено тварин з БД під час цієї сесії видалення.")
            conn_delete.close()
        else:
            logging.info("👍 Усі тваринки з бази даних присутні на сайті або були додані щойно.")

        logging.info(f"🕒 Наступна перевірка через {CHECK_INTERVAL} секунд.")
        time.sleep(CHECK_INTERVAL)

    except Exception as e_loop:
        logging.error(f"🔥 Помилка в головному циклі: {e_loop}")
        logging.info(f"🕒 Спроба перезапуску через 60 секунд через помилку.")
        time.sleep(60)
