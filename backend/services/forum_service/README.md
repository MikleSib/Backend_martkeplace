## Миграции

При установке на новый сервер или после изменений в схеме базы данных необходимо применить миграции:

```bash
# Применить все миграции
alembic upgrade head

# Создать новую миграцию (например, для новой таблицы post_reports)
alembic revision -m "create post reports table"
```

### Список миграций

1. create_post_reports - создание таблицы для хранения жалоб на сообщения

## Функциональность 