import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL")
print(f"Connecting to: {db_url.split('@')[-1]}")

try:
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW search_path;")
            print(f"Current search_path: {cur.fetchone()[0]}")
            
            cur.execute("SELECT current_schema();")
            print(f"Current schema: {cur.fetchone()[0]}")
except Exception as e:
    print(f"Error: {e}")
