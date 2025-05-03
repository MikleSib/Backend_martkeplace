"""
Скрипт для применения миграций к базе данных пользователей
"""
from sqlalchemy import create_engine, text
from config.config import DB_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_migration():
    """Создание и применение миграции для добавления новых полей в таблицу user_profiles"""
    engine = create_engine(DB_URL)
    
    # Проверяем наличие таблицы user_profiles
    with engine.connect() as conn:
        # Проверяем существование таблицы
        check_table = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_profiles')"
        ))
        table_exists = check_table.scalar()
        
        # Создаем таблицу, если она не существует
        if not table_exists:
            logger.info("Создание таблицы user_profiles")
            conn.execute(text("""
                CREATE TABLE user_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER UNIQUE NOT NULL,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    full_name VARCHAR(255),
                    about_me TEXT,
                    avatar VARCHAR(255),
                    signature VARCHAR(255),
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    posts_count INTEGER DEFAULT 0,
                    role VARCHAR(50) DEFAULT 'user'
                )
            """))
            conn.commit()
            logger.info("Таблица user_profiles успешно создана")
            return
        
        # Проверяем наличие колонок
        # Проверяем наличие колонки avatar
        check_avatar = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='user_profiles' AND column_name='avatar'"
        ))
        has_avatar = bool(check_avatar.fetchone())
        
        # Проверяем наличие колонки signature
        check_signature = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='user_profiles' AND column_name='signature'"
        ))
        has_signature = bool(check_signature.fetchone())
        
        # Проверяем наличие колонки registration_date
        check_reg_date = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='user_profiles' AND column_name='registration_date'"
        ))
        has_reg_date = bool(check_reg_date.fetchone())
        
        # Проверяем наличие колонки posts_count
        check_posts_count = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='user_profiles' AND column_name='posts_count'"
        ))
        has_posts_count = bool(check_posts_count.fetchone())
        
        # Проверяем наличие колонки role
        check_role = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='user_profiles' AND column_name='role'"
        ))
        has_role = bool(check_role.fetchone())
        
        # Добавляем недостающие колонки
        try:
            if not has_avatar:
                logger.info("Добавление колонки avatar")
                conn.execute(text("ALTER TABLE user_profiles ADD COLUMN avatar VARCHAR DEFAULT NULL"))
                
            if not has_signature:
                logger.info("Добавление колонки signature")
                conn.execute(text("ALTER TABLE user_profiles ADD COLUMN signature VARCHAR DEFAULT NULL"))
                
            if not has_reg_date:
                logger.info("Добавление колонки registration_date")
                conn.execute(text("ALTER TABLE user_profiles ADD COLUMN registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                
            if not has_posts_count:
                logger.info("Добавление колонки posts_count")
                conn.execute(text("ALTER TABLE user_profiles ADD COLUMN posts_count INTEGER DEFAULT 0"))
                
            if not has_role:
                logger.info("Добавление колонки role")
                conn.execute(text("ALTER TABLE user_profiles ADD COLUMN role VARCHAR(50) DEFAULT 'user'"))
            
            conn.commit()
            logger.info("Миграция успешно выполнена!")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при выполнении миграции: {str(e)}")
            raise

if __name__ == "__main__":
    create_migration() 