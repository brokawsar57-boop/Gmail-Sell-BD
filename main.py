import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ----------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------
BOT_TOKEN = "8958972223:AAHofuuD5Lz0O1sfLZNcHtgElafyLY_XriU"

# প্রাইমারি অ্যাডমিন আইডি (লিস্ট আকারে)
ADMIN_IDS = [6811141921]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ----------------------------------------------------
# DATABASE STRUCTURE
# ----------------------------------------------------
db = {
    "users": {},           # uid: {name, balance, ref_by, referrals: [], completed_tasks: [], rejects: []}
    "admin_list": set(ADMIN_IDS), # বট চলাকালীন অ্যাডমিনদের তালিকা
    "channels": ["https://t.me/Official_Update_Channel"],
    "gmail_settings": {
        "password": "Password123",
        "rate": 20.0,
        "video_url": "https://youtu.be/example"
    },
    "withdraw_settings": {
        "min_limit": 50.0,
        "charge": 5.0,
        "bkash": True,
        "nagad": True,
        "rocket": True
    },
    "referral_bonus": 2.0,
    "custom_tasks": {},    # task_id: {title, link, reward, desc}
    "submitted_gmails": {},# task_id: {user_id, user_name, email, password, status}
    "withdraw_requests": {},# req_id: {user_id, method, number, amount, status}
    "suspended_users": set(),
    "task_counter": 1,
    "withdraw_counter": 1
}

# CONVERSATION STATES
GMAIL_SUBMIT, ADD_ADMIN_STATE = range(2)

# ----------------------------------------------------
# KEYBOARDS
# ----------------------------------------------------
def get_user_keyboard(user_id):
    if user_id in db["suspended_users"]:
        return ReplyKeyboardMarkup([["💬 হেল্পলাইন / সাপোর্ট টিম"]], resize_keyboard=True)
    
    keyboard = [
        ["💼 কাজ", "💰 ব্যালেন্স"],
        ["💳 টাকা উত্তোলন", "🎁 গিফট কোড"],
        ["👥 My Referrals", "🏆 লিডারবোর্ড"],
        ["💬 Admin Support"]
    ]
    # যেকোনো অ্যাডমিন একাউন্টের জন্য বাটনে অ্যাডমিন প্যানেল শো করবে
    if user_id in db["admin_list"]:
        keyboard.append(["⚙️ অ্যাডমিন প্যানেল"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_inline_keyboard():
    buttons = [
        [InlineKeyboardButton("👑 ➕ অ্যাডমিন যোগ / রিমুভ", callback_data="adm_manage_admins")],
        [InlineKeyboardButton("📢 চ্যানেল লিংক এডিট", callback_data="adm_set_channel"),
         InlineKeyboardButton("➕ কাস্টম টাস্ক যোগ", callback_data="adm_add_task")],
        [InlineKeyboardButton("🔑 জিমেইল পাসওয়ার্ড", callback_data="adm_set_gmail_pass"),
         InlineKeyboardButton("💵 জিমেইল রেট", callback_data="adm_set_gmail_rate")],
        [InlineKeyboardButton("⚙️ উইথড্র সেটিংস (On/Off)", callback_data="adm_withdraw_config"),
         InlineKeyboardButton("🎁 রেফারেল বোনাস সেট", callback_data="adm_set_ref_bonus")],
        [InlineKeyboardButton("📊 মোট ইউজার সংখ্যা", callback_data="adm_user_count"),
         InlineKeyboardButton("🚫 সাসপেন্ড ও আনব্যান", callback_data="adm_susp_list")],
        [InlineKeyboardButton("📩 জমা পড়া জিমেইল", callback_data="adm_view_gmails"),
         InlineKeyboardButton("💳 উইথড্র হিস্ট্রি", callback_data="adm_view_withdraws")]
    ]
    return InlineKeyboardMarkup(buttons)

# ----------------------------------------------------
# FORCE SUBSCRIBE CHECK
# ----------------------------------------------------
async def check_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = []
    for idx, ch in enumerate(db["channels"], 1):
        buttons.append([InlineKeyboardButton(f"📢 Join Channel {idx}", url=ch)])
    buttons.append([InlineKeyboardButton("✅ জয়েন সম্পন্ন করেছি", callback_data="verify_join")])
    
    msg = (
        "👋 **আসসালামু আলাইকুম!**\n\n"
        "ফ্রি-তে ইনকাম শুরু করার জন্য আমাদের অফিশিয়াল চ্যানেলে যুক্ত হতে হবে:\n\n"
        "ধাপ ১: নিচের চ্যানেলগুলোতে জয়েন করুন।\n"
        "ধাপ ২: নিচে **'✅ জয়েন সম্পন্ন করেছি'** বাটনে চাপুন।"
    )
    if update.message:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

# ----------------------------------------------------
# START & MAIN USER HANDLER
# ----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid not in db["users"]:
        ref_id = None
        if context.args:
            try:
                ref_id = int(context.args[0])
                if ref_id in db["users"] and uid not in db["users"][ref_id]["referrals"]:
                    db["users"][ref_id]["referrals"].append(uid)
            except ValueError:
                pass
        db["users"][uid] = {
            "name": user.first_name,
            "balance": 0.0,
            "ref_by": ref_id,
            "referrals": [],
            "completed_tasks": [],
            "rejects": []
        }

    if uid in db["suspended_users"]:
        await update.message.reply_text("⚠️ আপনার একাউন্টটি সাসপেন্ড করা হয়েছে!", reply_markup=get_user_keyboard(uid))
        return

    await check_channel_join(update, context)

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if uid in db["suspended_users"] and text != "💬 হেল্পলাইন / সাপোর্ট টিম":
        await update.message.reply_text("⚠️ আপনার একাউন্টটি সাসপেন্ড রয়েছে।", reply_markup=get_user_keyboard(uid))
        return

    if text == "💼 কাজ":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📧 জিমেইল কাজ", callback_data="work_gmail_menu")],
            [InlineKeyboardButton("📌 কাস্টম টাস্ক", callback_data="work_custom_tasks")]
        ])
        await update.message.reply_text("নিচের তালিকা থেকে একটি কাজ সিলেক্ট করুন:", reply_markup=keyboard)

    elif text == "💰 ব্যালেন্স":
        bal = db["users"][uid]["balance"]
        await update.message.reply_text(f"💳 আপনার বর্তমান ব্যালেন্স: {bal:.2f} BDT")

    elif text == "👥 My Referrals":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={uid}"
        ref_count = len(db["users"][uid]["referrals"])
        bal = db["users"][uid]["balance"]
        
        txt = (
            f"🔗 **আপনার রেফারেল লিংক:**\n`{ref_link}`\n\n"
            f"👥 **মোট রেফারেল:** {ref_count} জন\n"
            f"💰 **বর্তমান ব্যালেন্স:** {bal:.2f} BDT\n"
            f"🎁 **প্রতি রেফারেল বোনাস:** {db['referral_bonus']} BDT"
        )
        await update.message.reply_text(txt, parse_mode="Markdown")

    elif text == "💳 টাকা উত্তোলন":
        w = db["withdraw_settings"]
        txt = f"💰 **সর্বনিম্ন উত্তোলন:** {w['min_limit']} BDT\n⚡ **চার্জ:** {w['charge']} BDT\n\nপেমেন্ট মেথড সিলেক্ট করুন:"
        buttons = [
            [InlineKeyboardButton("বিকাশ", callback_data="w_bkash"),
             InlineKeyboardButton("নগদ", callback_data="w_nagad"),
             InlineKeyboardButton("রকেট", callback_data="w_rocket")]
        ]
        await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    elif text == "⚙️ অ্যাডমিন প্যানেল" and uid in db["admin_list"]:
        await update.message.reply_text("⚙️ **অ্যাডমিন কন্ট্রোল প্যানেল**", parse_mode="Markdown", reply_markup=get_admin_inline_keyboard())

# ----------------------------------------------------
# ADMIN MANAGE HANDLERS
# ----------------------------------------------------
async def start_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admins_str = "\n".join([f"• `{a}`" for a in db["admin_list"]])
    msg = (
        f"👑 **বর্তমান অ্যাডমিন আইডি সমূহ:**\n{admins_str}\n\n"
        "নতুন কাউকে অ্যাডমিন বানাতে অথবা বিদ্যমান কাউকে সরাতে তার **Telegram User ID** লিখে মেসেজ দিন:"
    )
    await query.message.reply_text(msg, parse_mode="Markdown")
    return ADD_ADMIN_STATE

async def process_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        new_admin_id = int(text)
        if new_admin_id in db["admin_list"]:
            db["admin_list"].remove(new_admin_id)
            await update.message.reply_text(f"❌ User ID `{new_admin_id}` কে অ্যাডমিন তালিকা থেকে রিমুভ করা হয়েছে।", parse_mode="Markdown")
        else:
            db["admin_list"].add(new_admin_id)
            await update.message.reply_text(f"✅ User ID `{new_admin_id}` সফলভাবে নতুন অ্যাডমিন হিসেবে যুক্ত হয়েছেন!", parse_mode="Markdown")
            try:
                await context.bot.send_message(new_admin_id, "🎉 অভিনন্দন! আপনাকে এই বটের অ্যাডমিন বানানো হয়েছে। /start চাপুন।")
            except Exception:
                pass
    except ValueError:
        await update.message.reply_text("⚠️ অনুগ্রহ করে সঠিক অংক/সংখ্যা (Numeric User ID) ইনপুট দিন।")
    
    return ConversationHandler.END

# ----------------------------------------------------
# CALLBACK HANDLER (WORK & SYSTEM)
# ----------------------------------------------------
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "verify_join":
        await query.message.reply_text("✅ ভেরিফিকেশন সফল হয়েছে!", reply_markup=get_user_keyboard(uid))

    elif data == "work_gmail_menu":
        buttons = [
            [InlineKeyboardButton("📤 জিমেইল সাবমিট", callback_data="gmail_submit_start")],
            [InlineKeyboardButton("🎬 জিমেইল কাজ করার ভিডিও/নিয়ম", url=db["gmail_settings"]["video_url"])],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_to_work")]
        ]
        await query.message.edit_text("📧 **জিমেইল কাজ সেকশন:**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "gmail_submit_start":
        gm = db["gmail_settings"]
        msg = (
            f"📌 **জিমেইল কাজ করার নিয়ম:**\n"
            f"🔹 ক্রিয়েট পাসওয়ার্ড: `{gm['password']}`\n\n"
            f"ফরম্যাট: `email@gmail.com:{gm['password']}`\n"
            f"ফরম্যাট ভুল হলে কাজ বাতিল হবে!"
        )
        await query.message.reply_text(msg, parse_mode="Markdown")
        return GMAIL_SUBMIT

    elif data == "work_custom_tasks":
        user_done = db["users"][uid]["completed_tasks"]
        available_tasks = {k: v for k, v in db["custom_tasks"].items() if k not in user_done}

        if not available_tasks:
            await query.message.reply_text("📌 আপনার জন্য নতুন কোনো কাস্টম টাস্ক উপলব্ধ নেই।")
            return

        buttons = []
        for t_id, task in available_tasks.items():
            buttons.append([InlineKeyboardButton(f"{task['title']} - {task['reward']} BDT", callback_data=f"do_task_{t_id}")])
        await query.message.reply_text("📌 **উপলব্ধ কাস্টম টাস্কসমূহ:**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data in ["w_bkash", "w_nagad", "w_rocket"]:
        method = data.split("_")[1]
        if not db["withdraw_settings"][method]:
            await query.message.reply_text("⚠️ বর্তমানে এই পেমেন্ট মাধ্যমটির কার্যক্রম বন্ধ রয়েছে। অন্য মাধ্যমে চেষ্টা করুন।")
        else:
            await query.message.reply_text(f"💳 {method.capitalize()} নম্বর এবং পরিমাণ লিখে অ্যাডমিনকে পাঠান।")

# ----------------------------------------------------
# ADMIN LOGIC & APPROVALS
# ----------------------------------------------------
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "adm_view_gmails":
        pending_tasks = {k: v for k, v in db["submitted_gmails"].items() if v["status"] == "pending"}
        if not pending_tasks:
            await query.message.reply_text("📂 কোনো জমা পড়া জিমেইল পেন্ডিং নেই।")
            return

        for t_id, task in list(pending_tasks.items())[:5]:
            msg = (
                f"🆔 টাস্ক ID: #{t_id}\n"
                f"👤 নাম: {task['user_name']} (`{task['user_id']}`)\n"
                f"📧 জিমেইল: `{task['email']}`\n"
                f"🔑 পাসওয়ার্ড: `{task['password']}`"
            )
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve", callback_data=f"app_{t_id}"),
                 InlineKeyboardButton("❌ Reject", callback_data=f"rej_{t_id}")]
            ])
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=btn)

    elif data.startswith("app_"):
        t_id = int(data.split("_")[1])
        task = db["submitted_gmails"].get(t_id)
        if task and task["status"] == "pending":
            task["status"] = "approved"
            uid = task["user_id"]
            db["users"][uid]["balance"] += db["gmail_settings"]["rate"]
            await query.message.edit_text(f"✅ টাস্ক #{t_id} এপ্রুভ করা হয়েছে!")

    elif data.startswith("rej_"):
        t_id = int(data.split("_")[1])
        task = db["submitted_gmails"].get(t_id)
        if task and task["status"] == "pending":
            task["status"] = "rejected"
            uid = task["user_id"]
            now = datetime.now()
            db["users"][uid]["rejects"].append(now)

            recent = [t for t in db["users"][uid]["rejects"] if now - t <= timedelta(hours=24)]
            db["users"][uid]["rejects"] = recent

            await query.message.edit_text(f"❌ টাস্ক #{t_id} রিজেক্ট করা হয়েছে!")

            if len(recent) >= 3:
                db["suspended_users"].add(uid)
                await context.bot.send_message(uid, "⚠️ ২৪ ঘণ্টার মধ্যে ৩টি ভুল কাজ করায় আপনার একাউন্ট অটো-সাসপেন্ড করা হয়েছে!", reply_markup=get_user_keyboard(uid))

    elif data == "adm_user_count":
        await query.message.reply_text(f"📊 বটের মোট নিবন্ধিত ইউজার: {len(db['users'])} জন")

# ----------------------------------------------------
# MAIN EXECUTION
# ----------------------------------------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    gmail_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_query_handler, pattern="^gmail_submit_start$")],
        states={GMAIL_SUBMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_messages)]},
        fallbacks=[]
    )

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_admin, pattern="^adm_manage_admins$")],
        states={ADD_ADMIN_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_admin)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(gmail_conv)
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^adm_|^app_|^rej_"))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_messages))

    logging.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
