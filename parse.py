import hashlib
import logging
import os
import sqlite3
import time

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait


class SiriusScraper:
    PHOTO_DIR = 'photos'
    DB_NAME = 'sirius.db'
    BASE_URL = 'https://dogcat.com.ua'

    def __init__(self):
        os.makedirs(self.PHOTO_DIR, exist_ok=True)
        self.setup_logging()

        self.conn = sqlite3.connect(self.DB_NAME)
        self.cursor = self.conn.cursor()
        self.create_table()

        self.driver = None
        self.wait = None
        self.session = requests.Session()

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def create_table(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS animals (
            id INTEGER PRIMARY KEY,
            ProfileURL TEXT UNIQUE,
            Name TEXT,
            Age TEXT,
            Gender TEXT,
            Size TEXT,
            Skills TEXT,
            Story TEXT,
            PhotoURL TEXT,
            Species TEXT
        )''')
        self.conn.commit()

    def clean_text(self, text):
        if not text:
            return ""
        return " ".join(text.replace("Додати в обране", "").replace("В обраному", "").split())

    def setup_driver(self):
        if self.driver is None:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--window-size=1920,1080')
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 15)
        return self.wait

    def scrape_page(self, url, species):
        self.driver.get(url)
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')

        data = {
            'ProfileURL': url,
            'Species': species,
            'Name': self.clean_text(soup.find('h3').text if soup.find('h3') else '')
        }

        photo_url = self.get_photo_url(soup)
        data['PhotoURL'] = self.save_photo(photo_url, url)

        secondary = soup.find('div', class_='body-secondary')
        if secondary:
            parts = self.clean_text(secondary.text).split(',')
            data['Gender'] = parts[0].strip() if len(parts) > 0 else ''
            data['Age'] = parts[1].strip() if len(parts) > 1 else ''
        else:
            data['Gender'] = ''
            data['Age'] = ''

        skills = soup.find('div', class_='profile-skills')
        if skills:
            size = ''
            skill_list = []
            for i in skills.find_all('div', class_='item'):
                text = self.clean_text(i.text)
                if 'розмір' in text.lower():
                    size = text
                else:
                    skill_list.append(text)
            data['Size'] = size
            data['Skills'] = ", ".join(skill_list)
        else:
            data['Size'] = ''
            data['Skills'] = ''

        history = soup.find('div', class_='profile-history')
        if history:
            [h4.decompose() for h4 in history.find_all('h4')]
            data['Story'] = self.clean_text(history.get_text())
        else:
            data['Story'] = ''

        return data

    def get_photo_url(self, soup):
        img = soup.select_one('.swiper-slide-active img, .profile-photo img')
        if img:
            src = img.get('src')
            if not src:
                return ''
            if src.startswith('http'):
                return src
            else:
                return f"{self.BASE_URL}{src}"
        return ''

    def save_photo(self, url, profile_url):
        if not url:
            return ""

        filename = hashlib.md5(profile_url.encode()).hexdigest()[:8] + '.jpg'
        path = os.path.join(self.PHOTO_DIR, filename)

        if not os.path.exists(path):
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                with open(path, 'wb') as f:
                    f.write(response.content)
                logging.info(f"Saved photo: {path}")
            except Exception as e:
                logging.warning(f"Failed to save photo {url}: {e}")
                return url  # fallback to original url
        return path

    def run(self):
        try:
            self.setup_driver()
            existing_urls = set(row[0] for row in self.cursor.execute("SELECT ProfileURL FROM animals"))

            for species, url_part in [('Dog', '?animal=1&page='), ('Cat', '?animal=2&page=')]:
                page = 1
                while True:
                    page_url = f"{self.BASE_URL}/adoption{url_part}{page}"
                    self.driver.get(page_url)
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    links = {a['href'] for a in soup.select("a.animalCard__link") if a.get('href')}

                    if not links:
                        logging.info(f"No more links found on page {page} for species {species}.")
                        break

                    for href in links:
                        full_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"

                        # Scrape and insert/update data
                        data = self.scrape_page(full_url, species)

                        if full_url in existing_urls:
                            self.cursor.execute(
                                '''UPDATE animals SET Name=?, Age=?, Gender=?, Size=?, Skills=?, Story=?, PhotoURL=?, Species=?
                                WHERE ProfileURL=?''',
                                (data['Name'], data['Age'], data['Gender'], data['Size'], data['Skills'],
                                 data['Story'], data['PhotoURL'], data['Species'], full_url))
                            logging.info(f"Updated entry: {full_url}")
                        else:
                            self.cursor.execute(
                                '''INSERT INTO animals (ProfileURL, Name, Age, Gender, Size, Skills, Story, PhotoURL, Species)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (data['ProfileURL'], data['Name'], data['Age'], data['Gender'], data['Size'],
                                 data['Skills'], data['Story'], data['PhotoURL'], data['Species']))
                            existing_urls.add(full_url)
                            logging.info(f"Inserted new entry: {full_url}")

                        self.conn.commit()
                        time.sleep(0.5)  # polite delay

                    page += 1
                    time.sleep(1)

        except Exception as e:
            logging.error(f"Error during run: {e}")
        finally:
            if self.driver:
                self.driver.quit()
            self.conn.close()
            self.session.close()


if __name__ == "__main__":
    scraper = SiriusScraper()
    scraper.run()
