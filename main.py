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
ADMIN_ID = 7699501193

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ----------------------------------------------------
# DATABASE STRUCTURE
# ----------------------------------------------------
db = {
    "users": {},           # user_id: {balance, suspended, ref_by, tasks_done, rejects: []}
    "gmail_settings": {
        "password": "Password123",
        "rate": 20.0,
    },
    "withdraw_settings": {
        "min_limit": 50.0,
        "charge": 5.0,
        "bkash": True,
        "nagad": True,
        "rocket": True
    },
    "referral_bonus": 2.0,
    "gift_codes": {},
    "submitted_gmails": {}, # task_id: {user_id, email, password, time, status}
    "suspended_users": set(),
    "task_counter": 1
}

GMAIL_SUBMIT, SUPPORT_MSG = range(2)

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
    if user_id == ADMIN_ID:
        keyboard.append(["⚙️ অ্যাডমিন প্যানেল"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_inline_keyboard():
    buttons = [
        [InlineKeyboardButton("🔑 জিমেইল পাসওয়ার্ড", callback_data="adm_set_gmail_pass"),
         InlineKeyboardButton("💵 জিমেইল রেট", callback_data="adm_set_gmail_rate")],
        [InlineKeyboardButton("🎁 গিফট কোড তৈরি", callback_data="adm_create_gift"),
         InlineKeyboardButton("🚫 সাসপেন্ড হিস্ট্রি & আনব্যান", callback_data="adm_susp_list")],
        [InlineKeyboardButton("📩 জমা পড়া জিমেইল সমূহ (Approve/Reject)", callback_data="adm_view_gmails")]
    ]
    return InlineKeyboardMarkup(buttons)

# ----------------------------------------------------
# START & USER HANDLERS
# ----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid not in db["users"]:
        ref_id = None
        if context.args:
            try:
                ref_id = int(context.args[0])
            except ValueError:
                ref_id = None
        db["users"][uid] = {
            "name": user.first_name,
            "balance": 0.0,
            "ref_by": ref_id,
            "tasks_done": 0,
            "rejects": []  # List of timestamps for 24h rejection check
        }

    if uid in db["suspended_users"]:
        await update.message.reply_text(
            "⚠️ আপনার একাউন্টটি বর্তমানে সাসপেন্ড রয়েছে!\n"
            "সাহায্যের জন্য নিচের '💬 হেল্পলাইন / সাপোর্ট টিম' বাটনে চাপ দিন।",
            reply_markup=get_user_keyboard(uid)
        )
        return

    await update.message.reply_text(
        f"স্বাগতম {user.first_name}!\nকাজ শুরু করতে নিচের অপশনগুলো ব্যবহার করুন।",
        reply_markup=get_user_keyboard(uid)
    )

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if uid in db["suspended_users"] and text != "💬 হেল্পলাইন / সাপোর্ট টিম":
        await update.message.reply_text(
            "⚠️ আপনার একাউন্টটি সাসপেন্ড করা হয়েছে। আপনি শুধু হেল্পলাইন সাপোর্ট ব্যবহার করতে পারবেন।",
            reply_markup=get_user_keyboard(uid)
        )
        return

    if text == "💼 কাজ":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📧 জিমেইল কাজ (৳20.00)", callback_data="work_gmail")]
        ])
        await update.message.reply_text("নিচের তালিকা থেকে একটি কাজ সিলেক্ট করুন:", reply_markup=keyboard)

    elif text == "💰 ব্যালেন্স":
        bal = db["users"][uid]["balance"]
        await update.message.reply_text(f"💳 আপনার বর্তমান ব্যালেন্স: {bal:.2f} BDT")

    elif text == "👥 My Referrals":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={uid}"
        await update.message.reply_text(
            f"🔗 আপনার রেফারেল লিংক:\n{ref_link}\n\n"
            f"প্রতি সফল রেফারেলের জন্য পাবেন: {db['referral_bonus']} BDT (ইউজার ১ম কাজ সফলভাবে শেষ করলে)।"
        )

    elif text == "💳 টাকা উত্তোলন":
        w = db["withdraw_settings"]
        txt = f"💰 সর্বনিম্ন উত্তোলন: {w['min_limit']} BDT\n⚡ চার্জ: {w['charge']} BDT"
        await update.message.reply_text(txt)

    elif text == "⚙️ অ্যাডমিন প্যানেল" and uid == ADMIN_ID:
        await update.message.reply_text("⚙️ **অ্যাডমিন কন্ট্রোল প্যানেল**", parse_mode="Markdown", reply_markup=get_admin_inline_keyboard())

# ----------------------------------------------------
# GMAIL SUBMISSION LOGIC
# ----------------------------------------------------
async def work_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "work_gmail":
        gm = db["gmail_settings"]
        msg = (
            f"📌 **জিমেইল কাজ করার নিয়ম:**\n"
            f"🔹 ক্রিয়েট পাসওয়ার্ড: `{gm['password']}`\n\n"
            f"⚠️ **জমা দেওয়ার নিয়ম (অবশ্যই মানতে হবে):**\n"
            f"জিমেইল এবং পাসওয়ার্ড মাঝখানে `:` চিহ্ন দিয়ে জমা দিন।\n"
            f"উদাহরণ: `example@gmail.com:{gm['password']}`\n\n"
            f"ভুল ফরম্যাটে পাঠালে গ্রহণযোগ্য হবে না!"
        )
        await query.message.reply_text(msg, parse_mode="Markdown")
        return GMAIL_SUBMIT

async def process_gmail_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    gm_pass = db["gmail_settings"]["password"]

    if ":" in text and gm_pass in text and "@gmail.com" in text:
        parts = text.split(":")
        email = parts[0].strip()
        pwd = parts[1].strip()

        t_id = db["task_counter"]
        db["submitted_gmails"][t_id] = {
            "user_id": uid,
            "user_name": db["users"][uid]["name"],
            "email": email,
            "password": pwd,
            "time": datetime.now(),
            "status": "pending"
        }
        db["task_counter"] += 1

        await update.message.reply_text("✅ আপনার জিমেইলটি সফলভাবে জমা হয়েছে! অ্যাডমিন রিভিউ করার পর ব্যালেন্স যোগ হবে।")
        
        # Notify Admin
        await context.bot.send_message(
            ADMIN_ID,
            f"📩 **নতুন জিমেইল জমা পড়েছে!**\n"
            f"👤 ইউজার: {db['users'][uid]['name']} (`{uid}`)\n"
            f"📧 জিমেইল: `{email}`\n"
            f"🔑 পাসওয়ার্ড: `{pwd}`",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ আপনার সাবমিট করা জিমেইল ফরম্যাট সঠিক নয়! সঠিক নিয়মে আবার চেষ্টা করুন।")
        return GMAIL_SUBMIT

# ----------------------------------------------------
# ADMIN REVIEW (APPROVE / REJECT & 24H SUSPENSION)
# ----------------------------------------------------
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "adm_view_gmails":
        pending_tasks = {k: v for k, v in db["submitted_gmails"].items() if v["status"] == "pending"}
        if not pending_tasks:
            await query.message.reply_text("📂 কোনো জিমেইল পেন্ডিং নেই।")
            return

        for t_id, task in list(pending_tasks.items())[:5]:
            msg = (
                f"🆔 টাস্ক আইডি: #{t_id}\n"
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
            db["users"][uid]["tasks_done"] += 1
            
            await query.message.edit_text(f"✅ টাস্ক #{t_id} এপ্রুভ করা হয়েছে!")
            try:
                await context.bot.send_message(uid, f"🎉 আপনার জিমেইল ({task['email']}) এপ্রুভ হয়েছে! {db['gmail_settings']['rate']} BDT যোগ করা হয়েছে।")
            except:
                pass

    elif data.startswith("rej_"):
        t_id = int(data.split("_")[1])
        task = db["submitted_gmails"].get(t_id)
        if task and task["status"] == "pending":
            task["status"] = "rejected"
            uid = task["user_id"]
            now = datetime.now()

            # Add timestamp to user's rejects list
            db["users"][uid]["rejects"].append(now)

            # Filter rejects within last 24 hours
            recent_rejects = [t for t in db["users"][uid]["rejects"] if now - t <= timedelta(hours=24)]
            db["users"][uid]["rejects"] = recent_rejects

            await query.message.edit_text(f"❌ টাস্ক #{t_id} রিজেক্ট করা হয়েছে!")

            # 3 Rejects in 24 Hours -> Suspend
            if len(recent_rejects) >= 3:
                db["suspended_users"].add(uid)
                try:
                    await context.bot.send_message(
                        uid,
                        "⚠️ ২৪ ঘণ্টার মধ্যে আপনার ৩টি জিমেইল রিজেক্ট হওয়ায় আপনার একাউন্টটি অটোমেটিক সাসপেন্ড করা হয়েছে!\n"
                        "আনব্যান করতে '💬 হেল্পলাইন / সাপোর্ট টিম' বাটনে যোগাযোগ করুন।",
                        reply_markup=get_user_keyboard(uid)
                    )
                except:
                    pass
            else:
                try:
                    await context.bot.send_message(uid, f"❌ আপনার জমা দেওয়া জিমেইলটি ({task['email']}) রিজেক্ট করা হয়েছে।\n⚠️ ২৪ ঘণ্টায় ৩টি ভুল হলে একাউন্ট সাসপেন্ড হবে। (বর্তমান ভুল: {len(recent_rejects)}/3)")
                except:
                    pass

    elif data == "adm_susp_list":
        if not db["suspended_users"]:
            await query.message.reply_text("✅ বর্তমানে কোনো সাসপেন্ডেড ইউজার নেই।")
            return
        
        buttons = []
        for s_id in list(db["suspended_users"]):
            buttons.append([InlineKeyboardButton(f"🔓 Unban {s_id}", callback_data=f"unban_{s_id}")])
        await query.message.reply_text("🚫 সাসপেন্ড হওয়া ইউজারের তালিকা:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("unban_"):
        target_id = int(data.split("_")[1])
        db["suspended_users"].discard(target_id)
        if target_id in db["users"]:
            db["users"][target_id]["rejects"] = []
        await query.message.reply_text(f"✅ ইউজার ID `{target_id}` আনব্যান করা হয়েছে।", parse_mode="Markdown")
        try:
            await context.bot.send_message(target_id, "🎉 আপনার একাউন্টটি আনব্যান করা হয়েছে!", reply_markup=get_user_keyboard(target_id))
        except:
            pass

# ----------------------------------------------------
# SUPPORT & MAIN INITIALIZATION
# ----------------------------------------------------
async def handle_support_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = update.message.text
    txt = f"📩 **হেল্পলাইন মেসেজ!**\n👤 ইউজার ID: `{uid}`\n💬 মেসেজ: {msg}"
    await context.bot.send_message(ADMIN_ID, txt, parse_mode="Markdown")
    await update.message.reply_text("✅ আপনার বার্তা অ্যাডমিনের কাছে পাঠানো হয়েছে।")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    gmail_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(work_callback_handler, pattern="^work_gmail$")],
        states={GMAIL_SUBMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_gmail_submission)]},
        fallbacks=[]
    )

    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(💬 Admin Support|💬 হেল্পলাইন / সাপোর্ট টিম)$"), handle_user_messages)],
        states={SUPPORT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_support_msg)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(gmail_conv)
    app.add_handler(support_conv)
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^adm_|^app_|^rej_|^unban_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_messages))

    logging.info("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
