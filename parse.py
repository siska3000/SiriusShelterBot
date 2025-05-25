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
        existing_urls = load_existing_urls_from_db()
        new_animals_count = 0

        # ===== НАЛАШТУВАННЯ SELENIUM =====
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--window-size=1920,1080')

        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 15)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

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
                        if full_url in existing_urls:
                            continue  # вже є

                        logging.info(f"🐾 Новий профіль ({species_name}): {full_url}")
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

                            # Ім'я, вік, стать
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
                                    elif skill.lower() != animal_data['Gender'].lower():
                                        skills.append(skill)
                            animal_data['SkillsAndCharacter'] = ", ".join(skills)

                            # Історія
                            history_block = soup1.find('div', class_='profile-history')
                            if history_block:
                                for h4 in history_block.find_all('h4'): h4.decompose()
                                animal_data['MyStory'] = clean_text(history_block.get_text(separator=' ', strip=True))

                            # Фото
                            photo_url = ''
                            try:
                                wait.until(EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, ".swiper-slide-active img, .profile-photo img")))
                            except TimeoutException:
                                logging.warning("⚠️ Фото не завантажено — таймаут")

                            soup1 = BeautifulSoup(driver.page_source, 'html.parser')
                            img = soup1.select_one('.swiper-slide-active img') or soup1.select_one('.profile-photo img')

                            if img:
                                photo_url = img.get('data-src-default') or img.get('src', '')
                                if photo_url and not photo_url.startswith("http"):
                                    photo_url = f"https://dogcat.com.ua{photo_url}"

                            if photo_url:
                                try:
                                    # Генеруємо унікальний хеш з ProfileURL
                                    url_hash = hashlib.md5(full_url.encode('utf-8')).hexdigest()
                                    # Використовуємо ім'я тварини та хеш для унікальності
                                    cleaned_name = "".join(
                                        c for c in animal_data['Name'] if c.isalnum() or c in (' ', '_')).replace(' ',
                                                                                                                  '_')
                                    if not cleaned_name:
                                        cleaned_name = "unknown_animal"  # Запасний варіант, якщо ім'я порожнє

                                    filename = f"{cleaned_name}_{url_hash}.jpg"
                                    filepath = os.path.join(PHOTO_DIR, filename)

                                    if not os.path.exists(filepath):
                                        response = requests.get(photo_url, timeout=10)
                                        with open(filepath, 'wb') as f:
                                            f.write(response.content)
                                        logging.info(f"🖼️ Фото збережено: {filepath}")
                                    else:
                                        logging.info(f"📂 Фото вже існує: {filepath}")
                                    animal_data['PhotoURL'] = filepath.replace("\\", "/")
                                except Exception as e_img:
                                    logging.warning(f"⚠️ Помилка при завантаженні фото: {e_img}")
                                    animal_data[
                                        'PhotoURL'] = photo_url

                            # Збереження в базу даних
                            # Тепер не вказуємо 'id', бо він AUTOINCREMENT
                            c.execute('''
                                INSERT OR IGNORE INTO animals (ProfileURL, Name, Age, Gender, Size, SkillsAndCharacter, MyStory, PhotoURL, Species)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                animal_data['ProfileURL'], animal_data['Name'], animal_data['Age'],
                                animal_data['Gender'], animal_data['Size'], animal_data['SkillsAndCharacter'],
                                animal_data['MyStory'], animal_data['PhotoURL'], animal_data['Species']
                            ))
                            conn.commit()
                            new_animals_count += 1
                            existing_urls.add(full_url)  # Додаємо новий URL до існуючих

                        except Exception as e_animal:
                            logging.error(f"❌ Помилка обробки профілю ({full_url}): {e_animal}")
                except Exception as e_page:
                    logging.error(f"❌ Критична помилка сторінки ({page_url}): {e_page}")
                    break

                page += 1
                time.sleep(0.5)

        driver.quit()
        conn.close()

        if new_animals_count > 0:
            logging.info(f"✅ Додано нових тварин до '{DB_NAME}': {new_animals_count}")
        else:
            logging.info("🔍 Нових не знайдено.")

        time.sleep(CHECK_INTERVAL)

    except Exception as e_loop:
        logging.error(f"🔥 Помилка в головному циклі: {e_loop}")
        time.sleep(60)
