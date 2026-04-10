import time
import random
import os
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# =========================
# 🔐 ENV
# =========================
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# 🗄️ DATABASE (PostgreSQL)
# =========================
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    coins INTEGER,
    farm_level INTEGER,
    mine_level INTEGER,
    storage_level INTEGER,
    last_collect DOUBLE PRECISION,
    shield_until DOUBLE PRECISION,
    boost_until DOUBLE PRECISION,
    last_ad DOUBLE PRECISION,
    last_attack DOUBLE PRECISION
)
""")

# =========================
# 👤 HELPERS
# =========================
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    return cursor.fetchone()

def create_user(user_id):
    cursor.execute("""
        INSERT INTO users VALUES (%s, 100, 1, 1, 1, %s, 0, 0, 0, 0)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id, time.time()))

def update_user(user_id, field, value):
    cursor.execute(f"UPDATE users SET {field}=%s WHERE user_id=%s", (value, user_id))

def inc_user(user_id, field, value):
    cursor.execute(f"UPDATE users SET {field}={field}+%s WHERE user_id=%s", (value, user_id))

# =========================
# 💰 INCOME
# =========================
def get_income(user):
    income = user[2] * 10 + user[3] * 5
    if user[7] > time.time():
        income *= 2
    return income

# =========================
# 📱 MENUS
# =========================
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌾 جمع", callback_data="collect")],
        [InlineKeyboardButton("📺 إعلان", callback_data="ad")],
        [InlineKeyboardButton("⬆️ تطوير", callback_data="upgrade_menu")],
        [InlineKeyboardButton("⚔️ هجوم", callback_data="attack")],
        [InlineKeyboardButton("🏪 متجر", callback_data="shop")],
        [InlineKeyboardButton("🏆 الترتيب", callback_data="leaderboard")],
        [InlineKeyboardButton("📊 حالتي", callback_data="status")]
    ])

def shop_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Boost - 200", callback_data="boost")],
        [InlineKeyboardButton("🛡️ Shield - 150", callback_data="shield")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ])

# =========================
# 🚀 START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    create_user(user_id)
    await update.message.reply_text("🌾 أهلاً بك في لعبة المزرعة!", reply_markup=menu())

# =========================
# 🎮 BUTTONS
# =========================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    create_user(user_id)

    user = get_user(user_id)
    now = time.time()

    _, coins, farm, mine, storage, last_collect, shield, boost, last_ad, last_attack = user

    # 🌾 collect
    if query.data == "collect":
        earned = int(((now - last_collect) / 3600) * get_income(user))
        max_storage = storage * 500

        if earned < 1:
            await query.edit_message_text("⏳ انتظر قليلاً", reply_markup=menu())
            return

        if coins + earned > max_storage:
            earned = max_storage - coins

        update_user(user_id, "coins", coins + earned)
        update_user(user_id, "last_collect", now)

        await query.edit_message_text(f"💰 +{earned}", reply_markup=menu())

    # 📺 ad
    elif query.data == "ad":
        if now - last_ad < 60:
            await query.edit_message_text("⏳ انتظر دقيقة", reply_markup=menu())
            return

        inc_user(user_id, "coins", 100)
        update_user(user_id, "last_ad", now)

        await query.edit_message_text("🎉 +100", reply_markup=menu())

    # ⚔️ attack
    elif query.data == "attack":
        cursor.execute("SELECT * FROM users WHERE user_id != %s", (user_id,))
        enemies = cursor.fetchall()

        if not enemies:
            await query.edit_message_text("😅 لا يوجد لاعبين", reply_markup=menu())
            return

        enemy = random.choice(enemies)

        stolen = min(enemy[1], random.randint(10, 50))

        update_user(enemy[0], "coins", max(0, enemy[1] - stolen))
        inc_user(user_id, "coins", stolen)

        await query.edit_message_text(f"⚔️ سرقت {stolen} 💰", reply_markup=menu())

    # 🏪 shop
    elif query.data == "shop":
        await query.edit_message_text("🏪 المتجر:", reply_markup=shop_menu())

    elif query.data == "boost":
        update_user(user_id, "boost_until", now + 300)
        await query.edit_message_text("⚡ Boost مفعل", reply_markup=menu())

    elif query.data == "shield":
        update_user(user_id, "shield_until", now + 600)
        await query.edit_message_text("🛡️ Shield مفعل", reply_markup=menu())

    # 🏆 leaderboard
    elif query.data == "leaderboard":
        cursor.execute("SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 5")
        top = cursor.fetchall()

        text = "🏆 الأفضل:\n"
        for i, u in enumerate(top, 1):
            text += f"{i}. {u[1]} 💰\n"

        await query.edit_message_text(text, reply_markup=menu())

    elif query.data == "status":
        await query.edit_message_text(
            f"💰 {coins}\n🌾 {farm}\n⛏️ {mine}\n🏦 {storage}",
            reply_markup=menu()
        )

    elif query.data == "upgrade_menu":
        await query.edit_message_text("⬆️ التطوير قريباً 🔧", reply_markup=menu())

    elif query.data == "back":
        await query.edit_message_text("🏠 القائمة", reply_markup=menu())

# =========================
# ▶️ RUN
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()
