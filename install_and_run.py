import os

print("=== Начинается установка Telegram Namaz Bot ===")

telegram_token = input("Введите токен вашего Telegram-бота: ")

# Функция для замены токена в bot.py
bot_file = "bot.py"

with open(bot_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip().startswith("TOKEN = "):
        new_lines.append(f'TOKEN = "{telegram_token}"
')
    else:
        new_lines.append(line)

with open(bot_file, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Установка зависимостей...")
os.system("pip install -r requirements.txt")

print("Запуск бота...")
os.system("python main.py")

print("=== Установка и запуск завершены ===")
