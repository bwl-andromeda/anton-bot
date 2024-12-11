import asyncpg
from config import DB_CONFIG


async def init_database():
    # Подключение к базе данных
    conn = await asyncpg.connect(
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        host=DB_CONFIG['host'],
        database='postgres'  # Подключаемся к базе postgres для управления базами данных
    )

    try:
        # Создаем базу данных, если она не существует
        await conn.execute(f"""
            CREATE DATABASE {DB_CONFIG['database']}
            OWNER {DB_CONFIG['user']}
            ENCODING 'UTF8';
        """)
        print(f"База данных {DB_CONFIG['database']} успешно создана.")
    except asyncpg.DuplicateDatabaseError:
        print(f"База данных {DB_CONFIG['database']} уже существует.")
    finally:
        await conn.close()

    # Подключаемся к созданной базе данных
    conn = await asyncpg.connect(**DB_CONFIG)

    try:
        # Создаем таблицы
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT UNIQUE PRIMARY KEY,
                user_name TEXT,
                balance NUMERIC DEFAULT 0
            );
        """)
        print("Таблица users создана.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flowers (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price NUMERIC NOT NULL
            );
        """)
        print("Таблица flowers создана.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                flower_id INT REFERENCES flowers(id),
                quantity INT NOT NULL,
                total_price NUMERIC NOT NULL,
                status TEXT DEFAULT 'pending'
            );
        """)
        print("Таблица orders создана.")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                amount NUMERIC NOT NULL,
                type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Таблица transactions создана.")

    except Exception as e:
        print(f"Ошибка при инициализации базы данных: {e}")
    finally:
        await conn.close()
