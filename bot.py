import sqlite3
import requests
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "ВАШ_ТОКЕН_ТЕЛЕГРАМ_БОТА"
DB_NAME = "namazbot.db"
scheduler = BackgroundScheduler()
scheduler.start()

# --- Текст утренних азкаров ---
MORNING_AZKAR = """
Утренние азкары

1. Асбахьна́ ва асбلحة-ль-мульку лиЛляхI, ва-ль-хьамду лиЛляхI, ля иляхIа илля-Лло́хIу вахьдахIу́ ля шари́ка ляхI, лях|у-ль-мульку ва ляхIу-ль-хьамду ва хIува Iала́ кулли шайъин къоди́р...
(полный текст см. у пользователя...)

2. Алло́хIумма бика асбахьна́ ва бика амсайна́, ва бика нахьйа́ ва бика наму́т, ва иляйкан-нушу́р.

3. Субхьа́на-Лло́х1и ва би-хьамдихI, Iадада холькъихI(и), ва ридо́ нафсихI(и), ва зината IаршихI(и), ва мида́да калима́тихI. ( 3 раза )

... (другие пункты азкар)

16. АстагIфиру-Лло́хI, ва ату́бу иляйХIи. (100 раз)
"""

EVENING_AZKAR = "Вечерние азкары: (здесь можно добавить текст вечерних азкар)"

# --- База данных ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        telegram_id INTEGER UNIQUE,
        location_lat REAL,
        location_long REAL,
        city TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS prayer_times (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        date DATE,
        fajr TIME,
        dhuhr TIME,
        asr TIME,
        maghrib TIME,
        isha TIME,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')
    conn.commit()
    conn.close()

def save_user(telegram_id, lat, long, city=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (telegram_id, location_lat, location_long, city)
        VALUES (?, ?, ?, ?)
    ''', (telegram_id, lat, long, city))
    conn.commit()
    conn.close()

def get_user_by_telegram_id(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id=?', (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def save_prayer_times(user_id, date, timings):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO prayer_times (user_id, date, fajr, dhuhr, asr, maghrib, isha)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, date, timings['Fajr'], timings['Dhuhr'], timings['Asr'], timings['Maghrib'], timings['Isha']))
    conn.commit()
    conn.close()

# --- Получение времен намазов ---
def fetch_prayer_times(lat, long, date):
    url = f"https://api.aladhan.com/v1/timings/{date}?latitude={lat}&longitude={long}&method=4"
    res = requests.get(url)
    timings = res.json()['data']['timings']
    prayer_filtered = {p: timings[p] for p in ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']}
    return prayer_filtered

# --- Уведомления и азкары ---
async def send_prayer(context, chat_id, prayer_name, time_str):
    await context.bot.send_message(chat_id=chat_id, text=f"Наступило время намаза: {prayer_name} ({time_str})")

async def send_azkar(context, chat_id, azkar_type):
    if azkar_type == "morning":
        await context.bot.send_message(chat_id=chat_id, text=MORNING_AZKAR)
    elif azkar_type == "evening":
        await context.bot.send_message(chat_id=chat_id, text=EVENING_AZKAR)

def schedule_notifications(app: Application, chat_id, prayer_times):
    today = datetime.date.today()
    now = datetime.datetime.now()
    for p_name, time_str in prayer_times.items():
        prayer_dt = datetime.datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M")
        if prayer_dt < now:
            continue
        scheduler.add_job(
            app.create_task,
            'date',
            run_date=prayer_dt,
            args=(send_prayer(app, chat_id, p_name, time_str),)
        )
        if p_name == "Fajr":
            azkar_dt = prayer_dt + datetime.timedelta(minutes=15)
            if azkar_dt > now:
                scheduler.add_job(
                    app.create_task,
                    'date',
                    run_date=azkar_dt,
                    args=(send_azkar(app, chat_id, "morning"),)
                )
        elif p_name == "Maghrib":
            azkar_dt = prayer_dt + datetime.timedelta(minutes=15)
            if azkar_dt > now:
                scheduler.add_job(
                    app.create_task,
                    'date',
                    run_date=azkar_dt,
                    args=(send_azkar(app, chat_id, "evening"),)
                )

# --- Хэндлеры Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("Отправить локацию", request_location=True)]]
    await update.message.reply_text(
        "Добро пожаловать!\nПожалуйста, отправьте свою локацию для расписания намазов.",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))

async def location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    loc = update.message.location
    save_user(user.id, loc.latitude, loc.longitude)
    await update.message.reply_text("Локация сохранена! Бот будет присылать уведомления о намазах и азкары после Фаджра и Магриба.")
    date = datetime.date.today().strftime("%Y-%m-%d")
    timings = fetch_prayer_times(loc.latitude, loc.longitude, date)
    user_db = get_user_by_telegram_id(user.id)
    save_prayer_times(user_db[0], date, timings)
    msg = f"Сегодняшние времена намаза:\n\n"
    for p, t in timings.items():
        msg += f"{p}: {t}\n"
    await update.message.reply_text(msg)
    schedule_notifications(context.application, user.id, timings)

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, location))
    app.run_polling()

if __name__ == '__main__':
    main()
