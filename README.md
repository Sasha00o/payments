# Payments Service

Сервис проведения платёжных операций через внешнего провайдера с идемпотентной отправкой, обработкой callback-квитанций и восстановлением после перезапуска.

## Требования

- Docker
- Docker Compose

## Запуск

Перед запуском необходимо создать файл `.env-non-dev` с переменными окружения для Docker:

```bash
cp .env.example .env-non-dev
```

Затем отредактировать `.env-non-dev`:
- Изменить `DB_HOST` на `Ваше значение`
- Изменить `DB_PORT` на `Ваше значение`
- Изменить `DB_PASS` на `Ваше значение`
- Изменить `DB_USER` на `Ваше значение`
- Изменить `DB_NAME` на `Ваше значение`
- Изменить `POSTGRES_DB` на `Ваше значение`
- Изменить `POSTGRES_USER` на `Ваше значение`
- Изменить `POSTGRES_PASSWORD` на `Ваше значение`

Если вы используете другие значения для базы данных, также измените healthcheck в `docker-compose.yaml`:
- Изменить `pg_isready -U postgres -d payments-docker` на соответствующие ваши значения `POSTGRES_USER` и `POSTGRES_DB`

После настройки запустить:

```bash
docker compose up --build
```

Сервис кандидата: `http://localhost:8080`  
Симулятор провайдера: `http://localhost:8081`

## Проверка готовности

```bash
curl http://localhost:8080/health
```

## Сквозной сценарий

```bash
# 1. Создать операцию
curl -s -X POST http://localhost:8080/operations \
  -H "Content-Type: application/json" \
  -d '{
    "operationId": "operation-123",
    "amount": "1000.00",
    "currency": "RUB",
    "description": "Оплата заказа"
  }'

# 2. Запланировать отправку провайдеру
curl -s -X POST http://localhost:8080/operations/operation-123/submit

# 3. Дождаться callback от симулятора и проверить финальный статус
curl -s http://localhost:8080/operations/operation-123

# 4. Посмотреть историю переходов
curl -s http://localhost:8080/operations/operation-123/events
```

Ожидаемый финальный статус операции: `COMPLETED` или `REJECTED` (зависит от симулятора).

## Локальная разработка

1. Скопировать переменные окружения:

```bash
cp .env.example .env
```

2. Поднять PostgreSQL и применить миграции:

```bash
pip install -r requirements.txt
alembic upgrade head
```

3. Запустить приложение:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## API

| Метод | Маршрут | Описание |
|---|---|---|
| `GET` | `/health` | Проверка готовности |
| `POST` | `/operations` | Создание операции |
| `POST` | `/operations/{id}/submit` | Надёжная отправка провайдеру |
| `POST` | `/receipts` | Callback-квитанция |
| `GET` | `/operations/{id}` | Текущее состояние |
| `GET` | `/operations/{id}/events` | История переходов |
