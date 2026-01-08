# Трекер покерных сессий ПокерОк

Python скрипт **`tracker.py`** для учёта покерных сессий в PokerOK: добавляй сессии, смотри список, считай статистику по периодам и лимитам, редактируй/удаляй записи и экспортируй данные в CSV.

## Возможности

* ✅ Добавление сессий **PokerOK** (через аргументы или интерактивно)
* ✅ Хранение данных локально в `sessions.json`
* ✅ Вывод списка с фильтрами: по датам, лимиту, типу игры
* ✅ Статистика по периоду или диапазону дат:

  * общий профит
  * профит/час
  * суммарная длительность
  * топ-3 лучших/худших сессии
  * группировка по `stake` или `game`
* ✅ Редактирование и удаление сессий по `id`
* ✅ Экспорт в CSV
* ✅ Настройки через `config.json` (валюта, файл данных и т.д.)

---

## Структура проекта

Репозиторий рассчитан на минимализм — **один Python-файл** + файлы данных/настроек, которые создаются автоматически:

```
Session-Tracker/
├─ tracker.py
├─ config.json          # создаётся автоматически при первом запуске
└─ sessions.json        # создаётся автоматически при первом запуске
```

---

## Требования

* Python **3.10+**

Проверить версию:

```bash
python --version
```

---

## Установка

Склонируй репозиторий:

```bash
git clone https://github.com/PokerOk-Q1/Session-Tracker.git
cd Session-Tracker
```

---

## Быстрый старт

### 1) Добавить сессию (через аргументы)

```bash
python tracker.py add --date 2025-12-13 --start 18:10 --end 20:45 --profit 37.5 --stake NL10 --game NLH --notes "evening grind"
```

Пример вывода:

```
Added session #12: 2025-12-13 NL10 NLH 18:10-20:45 (155m) Profit: +37.50 USD
```

### 2) Добавить сессию (интерактивно)

Если не передать обязательные параметры, скрипт включит режим вопросов:

```bash
python tracker.py add
```

---

## Команды

Справка по всем командам:

```bash
python tracker.py --help
```

Справка по конкретной команде:

```bash
python tracker.py stats --help
```

---

## `add` — добавить сессию

### Обязательные поля

* `--date` — `YYYY-MM-DD`
* `--start` — `HH:MM`
* `--end` — `HH:MM`
* `--profit` — число (может быть отрицательным)
* `--stake` — например `NL10`, `PLO25` (разрешены и другие форматы)
* `--game` — `NLH` или `PLO`

### Опциональные поля

* `--hands` — количество рук (>= 0)
* `--tables` — количество столов (>= 0)
* `--notes` — комментарий

Пример:

```bash
python tracker.py add --date 2025-12-10 --start 22:30 --end 01:05 --profit -12.3 --stake NL5 --game NLH --hands 540 --tables 4 --notes "перешёл через полночь"
```

> Если `end` меньше `start`, считается, что сессия **перешла через полночь**, а длительность будет рассчитана корректно.

---

## `list` — список сессий

Показать последние 20 сессий (по умолчанию):

```bash
python tracker.py list
```

Фильтр по диапазону дат:

```bash
python tracker.py list --from 2025-12-01 --to 2025-12-31
```

Фильтр по лимиту и игре:

```bash
python tracker.py list --stake NL10 --game NLH
```

Показать все (без лимита):

```bash
python tracker.py list --limit -1
```

Сортировка по возрастанию:

```bash
python tracker.py list --asc
```

---

## `stats` — статистика

### Статистика за период

По умолчанию — текущий месяц:

```bash
python tracker.py stats
```

Другие периоды:

```bash
python tracker.py stats --period day
python tracker.py stats --period week
python tracker.py stats --period month
python tracker.py stats --period year
python tracker.py stats --period all
```

### Статистика по диапазону дат

```bash
python tracker.py stats --from 2025-12-01 --to 2025-12-31
```

### Группировка

По лимитам:

```bash
python tracker.py stats --from 2025-12-01 --to 2025-12-31 --by stake
```

По типу игры:

```bash
python tracker.py stats --period month --by game
```

---

## `edit` — редактировать сессию по `id`

Редактируются только переданные поля:

```bash
python tracker.py edit --id 7 --profit -12.3 --notes "tilt"
```

Изменить время (длительность пересчитается автоматически):

```bash
python tracker.py edit --id 7 --start 19:00 --end 22:15
```

Очистить notes:

```bash
python tracker.py edit --id 7 --notes ""
```

---

## `delete` — удалить сессию по `id`

```bash
python tracker.py delete --id 7
```

---

## `export` — экспорт в CSV

Экспорт в файл по умолчанию `sessions_export.csv`:

```bash
python tracker.py export
```

Указать имя файла:

```bash
python tracker.py export --out my_sessions.csv
```

---

## `config` — настройки

Показать текущие настройки:

```bash
python tracker.py config
```

Изменить валюту:

```bash
python tracker.py config --set currency=EUR
```

Изменить файл данных:

```bash
python tracker.py config --set data_file=my_sessions.json
```

---

## Формат данных

### `sessions.json`

Все сессии хранятся в JSON-массиве. Основные поля:

* `id` — уникальный идентификатор
* `room` — всегда `"PokerOK"`
* `date`, `start_time`, `end_time`
* `duration_min` — автоматически вычисляется
* `stake`, `game`
* `profit`, `currency`
* `hands`, `tables`, `notes` (опционально)
* `created_at`, `updated_at`

---

## Лицензия

Проект распространяется по лицензии **MIT**.
