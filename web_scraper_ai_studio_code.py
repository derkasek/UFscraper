import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time

class UhrforumScraper:
    def __init__(self):
        self.base_url = "https://uhrforum.de"
        self.start_url = "https://uhrforum.de/forums/angebote.11/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        # Filter-Definition
        self.erlaubte_praefixe = ["[Verkauf]", "[Verkauf-Tausch]"]

    def get_soup(self, url):
        """Sendet eine Anfrage und gibt ein BeautifulSoup-Objekt zurück."""
        try:
            # Kurze Pause vor jeder Anfrage, um den Server zu schonen
            time.sleep(1.2) 
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            print(f"Fehler beim Abrufen von {url}: {e}")
            return None

    def clean_price(self, price_str):
        """Bereinigt den Preis-String und konvertiert ihn in eine Zahl."""
        clean = price_str.replace('.', '').replace(',', '.')
        try:
            return float(clean)
        except ValueError:
            return None

    def extract_price(self, text):
        """Sucht nach Preisangaben im Text und gibt den letzten Treffer zurück."""
        price_pattern = r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:€|Euro|EUR)'
        matches = re.findall(price_pattern, text, re.IGNORECASE)
        if matches:
            return self.clean_price(matches[-1])
        return None

    def scrape_thread_details(self, thread_url):
        """Extrahiert Preis und Bilder aus dem ersten Beitrag eines Threads."""
        soup = self.get_soup(thread_url)
        if not soup: return {'price': None, 'images': []}

        first_post = soup.select_one('article.message-body .bbWrapper')
        price = None
        images = []

        if first_post:
            price = self.extract_price(first_post.get_text(separator=' '))
            # Suche Bilder
            img_tags = first_post.find_all('img', class_='bbImage')
            for img in img_tags[:3]:
                img_url = img.get('src') or img.get('data-url')
                if img_url:
                    if not img_url.startswith('http'):
                        img_url = self.base_url + img_url
                    images.append(img_url)

        return {'price': price, 'images': images}

    def run(self, max_results=100):
        """Hauptmethode zum Scrapen der Threads über mehrere Seiten hinweg."""
        threads_data = []
        current_page = 1
        
        print(f"Starte Suche nach {max_results} Verkaufs-Anzeigen...")

        while len(threads_data) < max_results:
            # URL für Pagination anpassen
            page_url = f"{self.start_url}page-{current_page}" if current_page > 1 else self.start_url
            print(f"\n--- Scanne Übersichtsseite {current_page} ---")
            
            soup = self.get_soup(page_url)
            if not soup:
                break

            thread_items = soup.select('div.structItem--thread')
            if not thread_items:
                print("Keine weiteren Threads gefunden.")
                break

            for item in thread_items:
                if len(threads_data) >= max_results:
                    break

                title_element = item.select_one('div.structItem-title a[data-tp-primary]')
                if not title_element: continue

                title = title_element.get_text(strip=True)
                
                # PRÜFUNG: Startet der Titel mit den gewünschten Präfixen?
                if not any(title.startswith(prefix) for prefix in self.erlaubte_praefixe):
                    continue

                link = self.base_url + title_element['href']
                
                print(f"Treffer {len(threads_data)+1}: {title}")
                
                details = self.scrape_thread_details(link)
                
                threads_data.append({
                    "Hersteller/Modell": title,
                    "Preis (€)": details['price'],
                    "Bilder": details['images'],
                    "Link": f'<a href="{link}" target="_blank">Link</a>'
                })

            current_page += 1
            
        self.save_to_html(threads_data)

    def save_to_html(self, data):
        """Erzeugt die HTML-Übersicht."""
        if not data:
            print("Keine Daten zum Speichern vorhanden.")
            return

        df = pd.DataFrame(data)
        
        def format_images(img_list):
            if not img_list: return "Keine Bilder"
            return "".join([f'<img src="{url}" width="120" style="margin:2px;">' for url in img_list])

        df['Bilder'] = df['Bilder'].apply(format_images)

        # Sortierung: Teuerste zuerst (optional)
        # df = df.sort_values(by="Preis (€)", ascending=False)

        html_table = df.to_html(escape=False, index=False, classes='table table-hover')
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <title>Uhrforum Marktplatz Scraper</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            <style>
                body {{ padding: 30px; background-color: #f4f7f6; font-family: sans-serif; }}
                .container-fluid {{ background: white; padding: 20px; border-radius: 10px; shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                img {{ border-radius: 4px; object-fit: cover; height: 80px; }}
                th {{ background-color: #343a40 !important; color: white; }}
                tr:hover {{ background-color: #f1f1f1; }}
            </style>
        </head>
        <body>
            <div class="container-fluid">
                <h1 class="mb-4">Gefundene Verkaufsanzeigen ({len(data)})</h1>
                {html_table}
            </div>
        </body>
        </html>
        """
        
        with open("angebote.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\nFertig! {len(data)} Anzeigen in 'angebote.html' gespeichert.")

if __name__ == "__main__":
    scraper = UhrforumScraper()
    # Startet den Prozess für bis zu 100 Anzeigen
    scraper.run(max_results=100)