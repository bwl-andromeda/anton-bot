import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    TOKEN = str(os.getenv("TOKEN"))
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
else:
    print("dotenv not loaded")

DB_CONFIG = {
    "user": f"{os.getenv('DB_USER')}",
    "password": f"{os.getenv('DB_PASSWORD')}",
    "database": f"{os.getenv('DB')}",
    "host": f"{os.getenv('DB_HOST')}",
}
