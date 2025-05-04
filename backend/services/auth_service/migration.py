from sqlalchemy import create_engine, text
import os

# Получаем параметры подключения к базе данных из переменных окружения
DB_USER = os.getenv("DB_USER", "MikleSibFish")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Mishatrof1!?")
DB_HOST = os.getenv("DB_HOST", "db_auth")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "db_auth")

# Формируем строку подключения
DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаем engine для подключения к базе данных
engine = create_engine(DB_URL)

def apply_migrations():
    """Применяет миграцию для добавления колонки is_email_verified в таблицу users"""
    try:
        # Создаем соединение
        with engine.connect() as connection:
            # Начинаем транзакцию
            with connection.begin():
                # Проверяем существование колонки
                result = connection.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'users' AND column_name = 'is_email_verified'"
                ))
                
                column_exists = bool(result.fetchone())
                
                if not column_exists:
                    print("Добавление колонки is_email_verified в таблицу users")
                    # Добавляем колонку
                    connection.execute(text(
                        "ALTER TABLE users ADD COLUMN is_email_verified BOOLEAN DEFAULT FALSE NOT NULL"
                    ))
                    print("Колонка is_email_verified успешно добавлена")
                else:
                    print("Колонка is_email_verified уже существует")
        
        print("Миграция выполнена успешно")
        return True
    
    except Exception as e:
        print(f"Ошибка при выполнении миграции: {str(e)}")
        return False

if __name__ == "__main__":
    apply_migrations() 