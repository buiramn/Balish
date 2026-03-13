"""
bālish Telegram Admin Bot
=========================
Мәзірді басқару боты — өзгерістер GitHub-қа автоматты жүктеледі.

Орнату:
  pip install -r requirements.txt

Іске қосу:
  python balish_bot.py
"""

import os
import json
import base64
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
)

load_dotenv()

# ── Конфигурация ────────────────────────────────────────────────
BOT_TOKEN     = os.getenv("BOT_TOKEN")
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN")
GITHUB_REPO   = os.getenv("GITHUB_REPO", "buiramn/Balish")
GITHUB_FILE   = os.getenv("GITHUB_FILE", "balish-menu.json")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
ADMIN_IDS     = set()  # Бос = барлығына ашық. Мысалы: {123456789}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN табылмады!")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN табылмады!")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Conversation states ─────────────────────────────────────────
(
    STATE_MAIN,
    ADD_NAME, ADD_DESC, ADD_PRICE, ADD_ICON, ADD_CAT,
    EDIT_CHOOSE_FIELD, EDIT_VALUE,
    DEL_CONFIRM,
) = range(9)

CAT_LABELS = {
    "sweet":  "🍮 Тәтті",
    "savory": "🥟 Тойымды",
    "spice":  "🌿 Дәмдеуіш",
    "drink":  "🥤 Сусын",
}

# ── GitHub API ──────────────────────────────────────────────────
API = "https://api.github.com"

def gh_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

def github_load():
    """GitHub-тан JSON оқу — (data, sha) қайтарады."""
    url = f"{API}/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    r = requests.get(url, headers=gh_headers(), params={"ref": GITHUB_BRANCH})
    r.raise_for_status()
    resp = r.json()
    content = base64.b64decode(resp["content"]).decode("utf-8")
    return json.loads(content), resp["sha"]

def github_save(data: dict, sha: str, message: str):
    """JSON-ды GitHub-қа жүктеу."""
    url = f"{API}/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    encoded = base64.b64encode(
        json.dumps(data, ensure_ascii=False, indent=2).encode()
    ).decode()
    r = requests.put(url, headers=gh_headers(), json={
        "message": message,
        "content": encoded,
        "sha": sha,
        "branch": GITHUB_BRANCH,
    })
    r.raise_for_status()
    log.info(f"GitHub commit: {message}")

def next_id(data):
    ids = [i["id"] for i in data["menu"]]
    return max(ids) + 1 if ids else 1

def is_admin(uid):
    return not ADMIN_IDS or uid in ADMIN_IDS

# ── Форматтау ───────────────────────────────────────────────────
def fmt(item):
    cat = CAT_LABELS.get(item["cat"], item["cat"])
    return (
        f"{item['icon']} *{item['name']}*\n"
        f"📂 {cat}\n"
        f"📄 {item['desc']}\n"
        f"💰 *{item['price']:,} ₸*"
    )

# ── Клавиатуралар ───────────────────────────────────────────────
def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Мәзірді көру",     callback_data="list")],
        [InlineKeyboardButton("➕ Тағам қосу",       callback_data="add_start")],
        [InlineKeyboardButton("✏️ Тағамды өзгерту",  callback_data="edit_list")],
        [InlineKeyboardButton("🗑 Тағамды жою",      callback_data="del_list")],
    ])

def kb_cancel():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Болдырмау", callback_data="cancel")
    ]])

def kb_back():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Басты мәзір", callback_data="back_main")
    ]])

def kb_cats():
    rows = [[InlineKeyboardButton(lbl, callback_data=f"cat_{cid}")]
            for cid, lbl in CAT_LABELS.items()]
    rows.append([InlineKeyboardButton("❌ Болдырмау", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)

def kb_items(items, prefix):
    rows = [[InlineKeyboardButton(
        f"{i['icon']} {i['name']} — {i['price']:,} ₸",
        callback_data=f"{prefix}_{i['id']}"
    )] for i in items]
    rows.append([InlineKeyboardButton("🔙 Артқа", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)

def kb_edit_fields(item_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Атауы",     callback_data=f"ef_name_{item_id}")],
        [InlineKeyboardButton("📄 Сипаттама", callback_data=f"ef_desc_{item_id}")],
        [InlineKeyboardButton("💰 Баға",      callback_data=f"ef_price_{item_id}")],
        [InlineKeyboardButton("😀 Иконка",    callback_data=f"ef_icon_{item_id}")],
        [InlineKeyboardButton("🗂 Санат",     callback_data=f"ef_cat_{item_id}")],
        [InlineKeyboardButton("🔙 Артқа",     callback_data="edit_list")],
    ])

# ── /start ──────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Рұқсат жоқ.")
        return STATE_MAIN
    await update.message.reply_text(
        "👋 Сәлем! *Balish Admin* боты.\n\nНе жасағыңыз келеді?",
        parse_mode="Markdown", reply_markup=kb_main(),
    )
    return STATE_MAIN

async def cb_back_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Не жасағыңыз келеді?", reply_markup=kb_main()
    )
    ctx.user_data.clear()
    return STATE_MAIN

async def cb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Болдырылмады.", reply_markup=kb_main()
    )
    ctx.user_data.clear()
    return STATE_MAIN

# ── 📋 ТІЗІМ ────────────────────────────────────────────────────
async def cb_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("⏳ Жүктелуде...")
    try:
        data, _ = github_load()
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Қате: {e}", reply_markup=kb_main())
        return STATE_MAIN

    lines = []
    for cid, clbl in CAT_LABELS.items():
        items = [i for i in data["menu"] if i["cat"] == cid]
        if items:
            lines.append(f"\n*{clbl}*")
            for i in items:
                lines.append(f"  {i['icon']} {i['name']} — {i['price']:,} ₸")

    await update.callback_query.edit_message_text(
        "📋 *Мәзір:*\n" + ("\n".join(lines) if lines else "Бос."),
        parse_mode="Markdown", reply_markup=kb_back(),
    )
    return STATE_MAIN

# ── ➕ ҚОСУ ─────────────────────────────────────────────────────
async def cb_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    ctx.user_data["new"] = {}
    await update.callback_query.edit_message_text(
        "➕ *Жаңа тағам қосу*\n\n*Атауын* жазыңыз:\n_(мысалы: Бауырсақ)_",
        parse_mode="Markdown", reply_markup=kb_cancel(),
    )
    return ADD_NAME

async def add_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new"]["name"] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Атауы: *{ctx.user_data['new']['name']}*\n\n*Сипаттама* жазыңыз:",
        parse_mode="Markdown", reply_markup=kb_cancel(),
    )
    return ADD_DESC

async def add_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new"]["desc"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ Сипаттама сақталды.\n\n*Бағасын* жазыңыз (тек сан):",
        parse_mode="Markdown", reply_markup=kb_cancel(),
    )
    return ADD_PRICE

async def add_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip().replace(" ", "").replace(",", "")
    if not val.isdigit():
        await update.message.reply_text("⚠️ Тек сан жазыңыз:", reply_markup=kb_cancel())
        return ADD_PRICE
    ctx.user_data["new"]["price"] = int(val)
    await update.message.reply_text(
        f"✅ Баға: *{int(val):,} ₸*\n\nИконка (emoji) жіберіңіз:",
        parse_mode="Markdown", reply_markup=kb_cancel(),
    )
    return ADD_ICON

async def add_icon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new"]["icon"] = update.message.text.strip()
    await update.message.reply_text(
        "✅ Иконка сақталды.\n\n*Санатты* таңдаңыз:",
        parse_mode="Markdown", reply_markup=kb_cats(),
    )
    return ADD_CAT

async def add_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    item = ctx.user_data["new"]
    item["cat"] = update.callback_query.data.replace("cat_", "")
    await update.callback_query.edit_message_text("⏳ GitHub-қа сақталуда...")
    try:
        data, sha = github_load()
        item["id"] = next_id(data)
        data["menu"].append(item)
        github_save(data, sha, f"➕ {item['name']} қосылды")
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Қате: {e}", reply_markup=kb_main())
        return STATE_MAIN
    await update.callback_query.edit_message_text(
        f"✅ *Қосылды! Сайт жаңартылды.*\n\n{fmt(item)}",
        parse_mode="Markdown", reply_markup=kb_back(),
    )
    ctx.user_data.clear()
    return STATE_MAIN

# ── ✏️ ӨЗГЕРТУ ──────────────────────────────────────────────────
async def cb_edit_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("⏳ Жүктелуде...")
    try:
        data, _ = github_load()
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Қате: {e}", reply_markup=kb_main())
        return STATE_MAIN
    await update.callback_query.edit_message_text(
        "✏️ Қай тағамды өзгертесіз?",
        reply_markup=kb_items(data["menu"], "edit"),
    )
    return EDIT_CHOOSE_FIELD

async def cb_edit_choose(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    item_id = int(update.callback_query.data.split("_")[1])
    ctx.user_data["edit_id"] = item_id
    try:
        data, _ = github_load()
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Қате: {e}")
        return STATE_MAIN
    item = next((i for i in data["menu"] if i["id"] == item_id), None)
    if not item:
        await update.callback_query.edit_message_text("Тағам табылмады.")
        return STATE_MAIN
    await update.callback_query.edit_message_text(
        f"*{item['icon']} {item['name']}*\n\nҚай өрісті өзгертесіз?",
        parse_mode="Markdown", reply_markup=kb_edit_fields(item_id),
    )
    return EDIT_CHOOSE_FIELD

async def cb_edit_field(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, field, item_id = update.callback_query.data.split("_", 2)
    item_id = int(item_id)
    ctx.user_data["edit_id"] = item_id
    ctx.user_data["edit_field"] = field
    if field == "cat":
        await update.callback_query.edit_message_text(
            "Жаңа санатты таңдаңыз:", reply_markup=kb_cats()
        )
        return EDIT_VALUE
    labels = {"name": "атауын", "desc": "сипаттамасын",
              "price": "бағасын (тек сан)", "icon": "иконкасын (emoji)"}
    await update.callback_query.edit_message_text(
        f"Тағамның *{labels.get(field, field)}* жазыңыз:",
        parse_mode="Markdown", reply_markup=kb_cancel(),
    )
    return EDIT_VALUE

async def edit_value(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    field = ctx.user_data["edit_field"]
    item_id = ctx.user_data["edit_id"]
    val = update.message.text.strip()
    if field == "price":
        val = val.replace(" ", "").replace(",", "")
        if not val.isdigit():
            await update.message.reply_text("⚠️ Тек сан жазыңыз:", reply_markup=kb_cancel())
            return EDIT_VALUE
        val = int(val)
    await update.message.reply_text("⏳ GitHub-қа сақталуда...")
    try:
        data, sha = github_load()
        item = next((i for i in data["menu"] if i["id"] == item_id), None)
        item[field] = val
        github_save(data, sha, f"✏️ {item['name']} өзгертілді ({field})")
    except Exception as e:
        await update.message.reply_text(f"❌ Қате: {e}", reply_markup=kb_main())
        return STATE_MAIN
    await update.message.reply_text(
        f"✅ *Сақталды! Сайт жаңартылды.*\n\n{fmt(item)}",
        parse_mode="Markdown", reply_markup=kb_back(),
    )
    ctx.user_data.clear()
    return STATE_MAIN

async def edit_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if ctx.user_data.get("edit_field") != "cat":
        return await add_cat(update, ctx)
    item_id = ctx.user_data["edit_id"]
    cat = update.callback_query.data.replace("cat_", "")
    await update.callback_query.edit_message_text("⏳ GitHub-қа сақталуда...")
    try:
        data, sha = github_load()
        item = next((i for i in data["menu"] if i["id"] == item_id), None)
        item["cat"] = cat
        github_save(data, sha, f"✏️ {item['name']} санаты өзгертілді")
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Қате: {e}", reply_markup=kb_main())
        return STATE_MAIN
    await update.callback_query.edit_message_text(
        f"✅ *Сақталды! Сайт жаңартылды.*\n\n{fmt(item)}",
        parse_mode="Markdown", reply_markup=kb_back(),
    )
    ctx.user_data.clear()
    return STATE_MAIN

# ── 🗑 ЖОЮ ──────────────────────────────────────────────────────
async def cb_del_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("⏳ Жүктелуде...")
    try:
        data, _ = github_load()
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Қате: {e}", reply_markup=kb_main())
        return STATE_MAIN
    await update.callback_query.edit_message_text(
        "🗑 Қай тағамды жоясыз?",
        reply_markup=kb_items(data["menu"], "del"),
    )
    return DEL_CONFIRM

async def cb_del_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    item_id = int(update.callback_query.data.split("_")[1])
    ctx.user_data["del_id"] = item_id
    try:
        data, _ = github_load()
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Қате: {e}")
        return STATE_MAIN
    item = next((i for i in data["menu"] if i["id"] == item_id), None)
    if not item:
        await update.callback_query.edit_message_text("Табылмады.")
        return STATE_MAIN
    await update.callback_query.edit_message_text(
        f"⚠️ Шынымен жоясыз ба?\n\n{fmt(item)}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Иә, жою",   callback_data=f"del_yes_{item_id}")],
            [InlineKeyboardButton("❌ Болдырмау", callback_data="cancel")],
        ]),
    )
    return DEL_CONFIRM

async def cb_del_yes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    item_id = int(update.callback_query.data.split("_")[2])
    await update.callback_query.edit_message_text("⏳ GitHub-қа сақталуда...")
    try:
        data, sha = github_load()
        item = next((i for i in data["menu"] if i["id"] == item_id), None)
        name = item["name"] if item else "?"
        data["menu"] = [i for i in data["menu"] if i["id"] != item_id]
        github_save(data, sha, f"🗑 {name} жойылды")
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ Қате: {e}", reply_markup=kb_main())
        return STATE_MAIN
    await update.callback_query.edit_message_text(
        f"✅ *{name}* жойылды. Сайт жаңартылды!", parse_mode="Markdown", reply_markup=kb_main()
    )
    ctx.user_data.clear()
    return STATE_MAIN

async def fallback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👇 Батырмаларды қолданыңыз:", reply_markup=kb_main())
    return STATE_MAIN

# ── Main ─────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            STATE_MAIN: [
                CallbackQueryHandler(cb_list,      pattern="^list$"),
                CallbackQueryHandler(cb_add_start, pattern="^add_start$"),
                CallbackQueryHandler(cb_edit_list, pattern="^edit_list$"),
                CallbackQueryHandler(cb_del_list,  pattern="^del_list$"),
                CallbackQueryHandler(cb_back_main, pattern="^back_main$"),
                CallbackQueryHandler(cb_cancel,    pattern="^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, fallback),
            ],
            ADD_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name),  CallbackQueryHandler(cb_cancel, pattern="^cancel$")],
            ADD_DESC:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc),  CallbackQueryHandler(cb_cancel, pattern="^cancel$")],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price), CallbackQueryHandler(cb_cancel, pattern="^cancel$")],
            ADD_ICON:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_icon),  CallbackQueryHandler(cb_cancel, pattern="^cancel$")],
            ADD_CAT:   [CallbackQueryHandler(add_cat,  pattern="^cat_"), CallbackQueryHandler(cb_cancel, pattern="^cancel$")],
            EDIT_CHOOSE_FIELD: [
                CallbackQueryHandler(cb_edit_choose, pattern=r"^edit_\d+$"),
                CallbackQueryHandler(cb_edit_field,  pattern=r"^ef_"),
                CallbackQueryHandler(cb_edit_list,   pattern="^edit_list$"),
                CallbackQueryHandler(cb_back_main,   pattern="^back_main$"),
                CallbackQueryHandler(cb_cancel,      pattern="^cancel$"),
            ],
            EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value),
                CallbackQueryHandler(edit_cat,  pattern="^cat_"),
                CallbackQueryHandler(cb_cancel, pattern="^cancel$"),
            ],
            DEL_CONFIRM: [
                CallbackQueryHandler(cb_del_confirm, pattern=r"^del_\d+$"),
                CallbackQueryHandler(cb_del_yes,     pattern=r"^del_yes_\d+$"),
                CallbackQueryHandler(cb_cancel,      pattern="^cancel$"),
                CallbackQueryHandler(cb_back_main,   pattern="^back_main$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(cb_back_main, pattern="^back_main$"),
            CallbackQueryHandler(cb_cancel,    pattern="^cancel$"),
        ],
    )
    app.add_handler(conv)
    log.info("✅ Balish Admin боты іске қосылды!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
