from bot import main, init_db

if __name__ == "__main__":
    # Инициализация базы данных (создание таблиц, если не созданы)
    init_db()
    # Запуск Telegram-бота
    main()
