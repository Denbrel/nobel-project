import requests
import sqlite3
import math
import time

def measure_time(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"[LOG] '{func.__name__}' выполнено за {time.time() - start:.2f} сек.")
        return result
    return wrapper

class GeoLocation:
    def __init__(self, lat, lon, city, country):
        self.lat = float(lat) if lat else None
        self.lon = float(lon) if lon else None
        self.city, self.country = city, country

    def __str__(self): return f"{self.city}, {self.country}"

class Entity:
    def __init__(self, entity_id, name):
        self.id, self.name = entity_id, name

class Laureate(Entity):
    def __init__(self, entity_id, name, gender, birth_date, birth_location, wikidata_id):
        super().__init__(entity_id, name)
        self.gender, self.birth_date = gender, birth_date
        self.birth_location = birth_location
        self.wikidata_id = wikidata_id
        self.prizes = []
    
    @property
    def birth_year(self):
        return int(self.birth_date[:4]) if self.birth_date and len(self.birth_date) >= 4 else None

class Award:
    def __init__(self, year, category):
        self.year, self.category = int(year), category

class NobelPrize(Award):
    # ДОБАВИЛИ КООРДИНАТЫ РАБОТЫ (AFFILIATION)
    def __init__(self, year, category, motivation, prize_amount, work_lat, work_lon, work_city):
        super().__init__(year, category)
        self.motivation, self.prize_amount = motivation, prize_amount
        self.work_lat = work_lat
        self.work_lon = work_lon
        self.work_city = work_city

class NobelDataset:
    def __init__(self):
        self.laureates = []
    def __len__(self): return len(self.laureates)

    @measure_time
    def load_from_api(self, data):
        for item in data:
            l_id = item.get("id")
            name = item.get("knownName", item.get("orgName", {})).get("en", "Unknown Name")
            birth_info = item.get("birth", {})
            place_info = birth_info.get("place", {}).get("cityNow", {})
            
            geo_loc = GeoLocation(
                place_info.get("latitude"), place_info.get("longitude"),
                place_info.get("en"), birth_info.get("place", {}).get("countryNow", {}).get("en")
            )
            laureate = Laureate(l_id, name, item.get("gender"), birth_info.get("date"), geo_loc, item.get("wikidata", {}).get("id"))
            
            for p in item.get("nobelPrizes", []):
                # ИЗВЛЕКАЕМ КООРДИНАТЫ ИНСТИТУТА
                affiliations = p.get("affiliations", [])
                w_lat, w_lon, w_city = None, None, None
                if affiliations:
                    city_now = affiliations[0].get("cityNow", {})
                    w_lat = city_now.get("latitude")
                    w_lon = city_now.get("longitude")
                    w_city = city_now.get("en")

                laureate.prizes.append(NobelPrize(
                    p.get("awardYear"), p.get("category", {}).get("en"), 
                    p.get("motivation", {}).get("en"), p.get("prizeAmount"),
                    w_lat, w_lon, w_city
                ))
            self.laureates.append(laureate)

class DatabaseManager:
    def __init__(self, db_name="nobel_database.sqlite"):
        self.db_name = db_name
        self._init_db()

    def _init_db(self):
        # СОЗДАЕМ ТАБЛИЦЫ ЗАНОВО С НОВЫМИ КОЛОНКАМИ
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS laureates 
                (id TEXT PRIMARY KEY, name TEXT, gender TEXT, birth_year INTEGER, birth_city TEXT, birth_country TEXT, lat REAL, lon REAL, wikidata_id TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS prizes 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, laureate_id TEXT, award_year INTEGER, category TEXT, motivation TEXT, prize_amount INTEGER, 
                work_lat REAL, work_lon REAL, work_city TEXT)''') # Добавили колонки
            conn.commit()

    @measure_time
    def save_dataset(self, dataset):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            for l in dataset.laureates:
                cursor.execute('''
                    INSERT OR REPLACE INTO laureates (id, name, gender, birth_year, birth_city, birth_country, lat, lon, wikidata_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (l.id, l.name, l.gender, l.birth_year, 
                      l.birth_location.city if l.birth_location else None, l.birth_location.country if l.birth_location else None,
                      l.birth_location.lat if l.birth_location else None, l.birth_location.lon if l.birth_location else None, l.wikidata_id))
                
                cursor.execute('DELETE FROM prizes WHERE laureate_id = ?', (l.id,))
                for p in l.prizes:
                    cursor.execute('''INSERT INTO prizes 
                        (laureate_id, award_year, category, motivation, prize_amount, work_lat, work_lon, work_city) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                        (l.id, p.year, p.category, p.motivation, p.prize_amount, p.work_lat, p.work_lon, p.work_city))
            conn.commit()

def fetch_nobel_laureates():
    base_url, limit, offset, all_data = "https://api.nobelprize.org/2.1/laureates", 50, 0, []
    headers = {"User-Agent": "NobelPrize_DH_Project/1.0"}
    while True:
        try:
            res = requests.get(base_url, params={"limit": limit, "offset": offset}, headers=headers)
            res.raise_for_status()
            batch = res.json().get("laureates", [])
            if not batch: break
            all_data.extend(batch)
            offset += limit
            time.sleep(0.5)
        except Exception:
            break
    return all_data

if __name__ == "__main__":
    raw_data = fetch_nobel_laureates()
    if raw_data:
        dataset = NobelDataset()
        dataset.load_from_api(raw_data)
        db = DatabaseManager()
        db.save_dataset(dataset)
