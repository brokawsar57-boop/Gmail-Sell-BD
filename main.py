import os
import logging
from threading import Thread
from flask import Flask
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
# FLASK SERVER FOR RENDER DEPLOYMENT
# ----------------------------------------------------
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is Live & Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ----------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------
BOT_TOKEN = "8958972223:AAEKCPyi6u7fXVmtIEGO-1liTSRfjspfF4A"
ADMIN_IDS = [6811141921]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ----------------------------------------------------
# DATABASE
# ----------------------------------------------------
db = {
    "users": {},            # uid: {name, balance, ref_by, referrals: [], completed_tasks: [], claimed_codes: []}
    "admin_list": set(ADMIN_IDS),
    "channels": ["https://t.me/FreeIncomeBDksOfficial"], # চ্যানেলের ইউজারনেম দিতে হবে (যেমন: @channelusername)
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
    "gift_codes": {},       # code: {amount, max_users, used_users: []}
    "custom_tasks": {},    
    "submitted_gmails": {},
    "withdraw_requests": {},
    "suspended_users": set(),
    "task_counter": 1,
    "withdraw_counter": 1
}

# STATES
(
    GMAIL_SUBMIT,
    ADMIN_ADD_RM,
    SET_CHANNEL,
    SET_GM_PASS,
    SET_GM_RATE,
    SET_GM_VIDEO,
    SET_REF_BONUS,
    SET_WITHDRAW_LIMIT,
    SUSPEND_UNBAN_USER,
    ADD_TASK_TITLE,
    ADD_TASK_LINK,
    ADD_TASK_REWARD,
    CREATE_CODE_NAME,
    CREATE_CODE_AMT,
    CREATE_CODE_LIMIT,
    CLAIM_GIFT_CODE,
    WITHDRAW_NUM_AMT
) = range(17)

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
    if user_id in db["admin_list"]:
        keyboard.append(["⚙️ অ্যাডমিন প্যানেল"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_inline_keyboard():
    buttons = [
        [InlineKeyboardButton("👑 অ্যাডমিন ম্যানেজ", callback_data="adm_manage_admins"),
         InlineKeyboardButton("🎁 গিফট কোড তৈরি", callback_data="adm_create_code")],
        [InlineKeyboardButton("📢 চ্যানেল লিংক এডিট", callback_data="adm_set_channel"),
         InlineKeyboardButton("🎬 ভিডিও লিংক এডিট", callback_data="adm_set_video")],
        [InlineKeyboardButton("➕ কাস্টম টাস্ক যোগ", callback_data="adm_add_task"),
         InlineKeyboardButton("🔑 জিমেইল পাসওয়ার্ড", callback_data="adm_set_gmail_pass")],
        [InlineKeyboardButton("💵 জিমেইল রেট", callback_data="adm_set_gmail_rate"),
         InlineKeyboardButton("⚙️ উইথড্র লিমিট", callback_data="adm_set_w_limit")],
        [InlineKeyboardButton("🎁 রেফারেল বোনাস সেট", callback_data="adm_set_ref_bonus"),
         InlineKeyboardButton("📊 মোট ইউজার সংখ্যা", callback_data="adm_user_count")],
        [InlineKeyboardButton("🚫 সাসপেন্ড / আনব্যান", callback_data="adm_susp_user"),
         InlineKeyboardButton("📩 জমা পড়া জিমেইল", callback_data="adm_view_gmails")],
        [InlineKeyboardButton("💳 উইথড্র রিকোয়েস্ট", callback_data="adm_view_withdraws")]
    ]
    return InlineKeyboardMarkup(buttons)

# ----------------------------------------------------
# REAL CHANNEL JOIN VERIFICATION
# ----------------------------------------------------
async def check_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id

    not_joined = []
    for ch in db["channels"]:
        try:
            member = await context.bot.get_chat_member(chat_id=ch, user_id=uid)
            if member.status in ['left', 'kicked']:
                not_joined.append(ch)
        except Exception:
            pass # চ্যানেল খুঁজে না পেলে বা বট এডমিন না থাকলে

    if not_joined:
        buttons = []
        for ch in not_joined:
            url = f"https://t.me/{ch.replace('@', '')}"
            buttons.append([InlineKeyboardButton(f"📢 Join {ch}", url=url)])
        buttons.append([InlineKeyboardButton("✅ জয়েন সম্পন্ন করেছি", callback_data="verify_join")])
        
        msg = "⚠️ **বটটি ব্যবহার করতে আপনাকে অবশ্যই নিচের চ্যানেলে জয়েন হতে হবে:**"
        if query:
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        elif update.message:
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        return False
    return True

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
            "claimed_codes": []
        }

    if uid in db["suspended_users"]:
        await update.message.reply_text("⚠️ আপনার একাউন্টটি সাসপেন্ড করা হয়েছে!", reply_markup=get_user_keyboard(uid))
        return

    is_joined = await check_channel_join(update, context)
    if is_joined:
        await update.message.reply_text("👋 **স্বাগতম!** নিচের মেনু থেকে অপশন সিলেক্ট করুন:", reply_markup=get_user_keyboard(uid))

async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if uid in db["suspended_users"]:
        await update.message.reply_text("⚠️ আপনার একাউন্টটি সাসপেন্ড রয়েছে।", reply_markup=get_user_keyboard(uid))
        return

    if text == "💼 কাজ":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📧 জিমেইল কাজ", callback_data="work_gmail_menu")],
            [InlineKeyboardButton("📌 কাস্টম টাস্ক", callback_data="work_custom_tasks")]
        ])
        await update.message.reply_text("নিচের তালিকা থেকে কাজ সিলেক্ট করুন:", reply_markup=keyboard)

    elif text == "💰 ব্যালেন্স":
        bal = db["users"][uid]["balance"]
        await update.message.reply_text(f"💳 আপনার বর্তমান ব্যালেন্স: {bal:.2f} BDT")

    elif text == "🎁 গিফট কোড":
        await update.message.reply_text("🎁 আপনার **গিফট কোডটি** নিচে লিখে পাঠান:")
        return CLAIM_GIFT_CODE

    elif text == "👥 My Referrals":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={uid}"
        ref_count = len(db["users"][uid]["referrals"])
        bal = db["users"][uid]["balance"]
        
        txt = (
            f"🔗 **আপনার রেফারেল লিংক:**\n`{ref_link}`\n\n"
            f"👥 **মোট রেফারেল:** {ref_count} জন\n"
            f"💰 **বর্তমান ব্যালেন্স:** {bal:.2f} BDT\n"
            f"🎁 **রেফারেল বোনাস:** {db['referral_bonus']} BDT (রেফারকৃত মেম্বার ১টি কাজ সম্পন্ন করার পর বোনাস যোগ হবে)"
        )
        await update.message.reply_text(txt, parse_mode="Markdown")

    elif text == "💳 টাকা উত্তোলন":
        w = db["withdraw_settings"]
        txt = f"💰 **সর্বনিম্ন উত্তোলন:** {w['min_limit']} BDT\n⚡ **চার্জ:** {w['charge']} BDT\n\nপেমেন্ট মাধ্যম বেছে নিন:"
        buttons = [
            [InlineKeyboardButton("বিকাশ", callback_data="w_bkash"),
             InlineKeyboardButton("নগদ", callback_data="w_nagad"),
             InlineKeyboardButton("রকেট", callback_data="w_rocket")]
        ]
        await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    elif text == "⚙️ অ্যাডমিন প্যানেল" and uid in db["admin_list"]:
        await update.message.reply_text("⚙️ **অ্যাডমিন কন্ট্রোল প্যানেল**", parse_mode="Markdown", reply_markup=get_admin_inline_keyboard())

# ----------------------------------------------------
# GIFT CODE CLAIM LOGIC
# ----------------------------------------------------
async def process_gift_code_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code_input = update.message.text.strip()
    uid = update.effective_user.id

    if code_input not in db["gift_codes"]:
        await update.message.reply_text("❌ দুঃখিত! এটি একটি ভুল অথবা মেয়ার্দউত্তীর্ণ গিফট কোড।")
        return ConversationHandler.END

    code_data = db["gift_codes"][code_input]

    if uid in code_data["used_users"]:
        await update.message.reply_text("⚠️ আপনি ইতোমধ্যে এই গিফট কোডটি ক্লেইম করেছেন!")
        return ConversationHandler.END

    if len(code_data["used_users"]) >= code_data["max_users"]:
        await update.message.reply_text("❌ এই গিফট কোডের ইউজার লিমিট শেষ হয়ে গেছে!")
        return ConversationHandler.END

    # Grant reward
    code_data["used_users"].append(uid)
    db["users"][uid]["balance"] += code_data["amount"]
    await update.message.reply_text(f"🎉 অভিনন্দন! আপনি সফলভাবে `{code_data['amount']}` BDT গিফট কোড বোনাস পেয়েছেন।", parse_mode="Markdown")
    return ConversationHandler.END

# ----------------------------------------------------
# ADMIN CONVERSATION LOGICS
# ----------------------------------------------------
async def admin_input_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "adm_manage_admins":
        admins = "\n".join([f"• `{a}`" for a in db["admin_list"]])
        await query.message.reply_text(f"👑 **বর্তমান অ্যাডমিনগণ:**\n{admins}\n\nযোগ বা রিমুভ করতে ইউজার আইডি পাঠান:")
        return ADMIN_ADD_RM

    elif data == "adm_create_code":
        await query.message.reply_text("🎁 গিফট কোডের **নাম/কোড** লিখুন (যেমন: `FREE20`):")
        return CREATE_CODE_NAME

    elif data == "adm_set_channel":
        await query.message.reply_text("📢 নতুন চ্যানেলের ইউজারনেম লিখুন (যেমন: `@channelusername`):")
        return SET_CHANNEL

    elif data == "adm_set_video":
        await query.message.reply_text(f"🎬 বর্তমান ভিডিও লিংক: {db['gmail_settings']['video_url']}\nনতুন লিংক দিন:")
        return SET_GM_VIDEO

    elif data == "adm_set_gmail_pass":
        await query.message.reply_text(f"🔑 পাসওয়ার্ড লিখে পাঠান:")
        return SET_GM_PASS

    elif data == "adm_set_gmail_rate":
        await query.message.reply_text(f"💵 নতুন জিমেইল রেট লিখে পাঠান:")
        return SET_GM_RATE

    elif data == "adm_set_ref_bonus":
        await query.message.reply_text(f"🎁 নতুন রেফারেল বোনাস লিখে পাঠান:")
        return SET_REF_BONUS

    elif data == "adm_set_w_limit":
        await query.message.reply_text(f"💰 সর্বনিম্ন উইথড্র লিমিট লিখুন:")
        return SET_WITHDRAW_LIMIT

    elif data == "adm_susp_user":
        await query.message.reply_text("🚫 ইউজার আইডি লিখে পাঠান:")
        return SUSPEND_UNBAN_USER

    elif data == "adm_add_task":
        await query.message.reply_text("📌 কাস্টম টাস্কের **টাইটেল** লিখুন:")
        return ADD_TASK_TITLE

# GIFT CODE CREATION STEPS
async def proc_code_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["c_name"] = update.message.text.strip()
    await update.message.reply_text("💵 কোডটির **টাকার পরিমাণ (BDT)** লিখুন:")
    return CREATE_CODE_AMT

async def proc_code_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["c_amt"] = float(update.message.text.strip())
        await update.message.reply_text("👥 **সর্বোচ্চ কতজন ইউজার** এই কোড ক্লেইম করতে পারবে? সংখ্যা লিখুন:")
        return CREATE_CODE_LIMIT
    except ValueError:
        await update.message.reply_text("⚠️ সঠিক সংখ্যা প্রদান করুন।")
        return CREATE_CODE_AMT

async def proc_code_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        limit = int(update.message.text.strip())
        cname = context.user_data["c_name"]
        db["gift_codes"][cname] = {
            "amount": context.user_data["c_amt"],
            "max_users": limit,
            "used_users": []
        }
        await update.message.reply_text(f"✅ গিফট কোড `{cname}` সফলভাবে তৈরি হয়েছে!\n💰 রিওয়ার্ড: {context.user_data['c_amt']} BDT\n👥 ইউজার লিমিট: {limit} জন", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("⚠️ সঠিক লিমিট প্রদান করুন।")
    return ConversationHandler.END

# ADMIN PROCESSORS
async def proc_admin_add_rm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        aid = int(update.message.text.strip())
        if aid in db["admin_list"]:
            db["admin_list"].remove(aid)
            await update.message.reply_text(f"❌ User ID `{aid}` রিমুভ করা হয়েছে।")
        else:
            db["admin_list"].add(aid)
            await update.message.reply_text(f"✅ User ID `{aid}` নতুন অ্যাডমিন যুক্ত হয়েছেন!")
    except ValueError:
        await update.message.reply_text("⚠️ সঠিক সংখ্যা দিন।")
    return ConversationHandler.END

async def proc_set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db["channels"] = [update.message.text.strip()]
    await update.message.reply_text("✅ চ্যানেল ইউজারনেম আপডেট হয়েছে!")
    return ConversationHandler.END

async def proc_set_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db["gmail_settings"]["video_url"] = update.message.text.strip()
    await update.message.reply_text("✅ ভিডিও ইউআরএল আপডেট করা হয়েছে!")
    return ConversationHandler.END

async def proc_set_gm_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db["gmail_settings"]["password"] = update.message.text.strip()
    await update.message.reply_text("✅ জিমেইল পাসওয়ার্ড পরিবর্তিত হয়েছে!")
    return ConversationHandler.END

async def proc_set_gm_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db["gmail_settings"]["rate"] = float(update.message.text.strip())
        await update.message.reply_text("✅ জিমেইল রেট আপডেট হয়েছে!")
    except ValueError:
        pass
    return ConversationHandler.END

async def proc_set_ref_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db["referral_bonus"] = float(update.message.text.strip())
        await update.message.reply_text("✅ রেফার বোনাস আপডেট হয়েছে!")
    except ValueError:
        pass
    return ConversationHandler.END

async def proc_set_w_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db["withdraw_settings"]["min_limit"] = float(update.message.text.strip())
        await update.message.reply_text("✅ উইথড্র লিমিট আপডেট হয়েছে!")
    except ValueError:
        pass
    return ConversationHandler.END

async def proc_susp_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
        if uid in db["suspended_users"]:
            db["suspended_users"].remove(uid)
            await update.message.reply_text(f"✅ User ID `{uid}` আনব্যান হয়েছে!")
        else:
            db["suspended_users"].add(uid)
            await update.message.reply_text(f"🚫 User ID `{uid}` সাসপেন্ড হয়েছে!")
    except ValueError:
        pass
    return ConversationHandler.END

# ----------------------------------------------------
# WORK & CALLBACK SYSTEM
# ----------------------------------------------------
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "verify_join":
        joined = await check_channel_join(update, context)
        if joined:
            await query.message.reply_text("✅ ভেরিফিকেশন সফল হয়েছে!", reply_markup=get_user_keyboard(uid))

    elif data == "work_gmail_menu":
        buttons = [
            [InlineKeyboardButton("📤 জিমেইল সাবমিট", callback_data="gmail_submit_start")],
            [InlineKeyboardButton("🎬 কাজের ভিডিও/নিয়ম", url=db["gmail_settings"]["video_url"])]
        ]
        await query.message.edit_text("📧 **জিমেইল কাজ সেকশন:**", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "gmail_submit_start":
        gm = db["gmail_settings"]
        await query.message.reply_text(f"📌 **পাসওয়ার্ড:** `{gm['password']}`\n\nফরম্যাট: `email@gmail.com:{gm['password']}` লিখে পাঠান:")
        return GMAIL_SUBMIT

    elif data in ["w_bkash", "w_nagad", "w_rocket"]:
        method = data.split("_")[1]
        context.user_data["w_method"] = method
        await query.message.reply_text(f"💳 আপনার {method.capitalize()} নম্বর এবং উত্তোলনের পরিমাণ লিখে পাঠান:\n(উদাহরণ: `017xxxxxxxx 100`)")
        return WITHDRAW_NUM_AMT

    elif data == "adm_user_count":
        await query.message.reply_text(f"📊 মোট নিবন্ধিত ইউজার: {len(db['users'])} জন")

    elif data == "adm_view_gmails":
        pending = {k: v for k, v in db["submitted_gmails"].items() if v["status"] == "pending"}
        if not pending:
            await query.message.reply_text("📂 কোনো জমা পড়া জিমেইল পেন্ডিং নেই।")
            return
        for t_id, task in list(pending.items())[:5]:
            msg = f"🆔 টাস্ক #{t_id}\n👤 ইউজার: `{task['user_id']}`\n📧 জিমেইল: `{task['email']}`\n🔑 পাসওয়ার্ড: `{task['password']}`"
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"app_gm_{t_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_gm_{t_id}")]])
            await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=btn)

    elif data.startswith("app_gm_"):
        t_id = int(data.split("_")[2])
        task = db["submitted_gmails"].get(t_id)
        if task and task["status"] == "pending":
            task["status"] = "approved"
            user_id = task["user_id"]
            db["users"][user_id]["balance"] += db["gmail_settings"]["rate"]
            
            # Referral Bonus Check Logic (First successful work)
            ref_by = db["users"][user_id].get("ref_by")
            if ref_by and ref_by in db["users"]:
                db["users"][ref_by]["balance"] += db["referral_bonus"]
                try:
                    await context.bot.send_message(ref_by, f"🎉 আপনার রেফারকৃত ইউজার সফলভাবে ১টি কাজ সম্পন্ন করায় আপনি {db['referral_bonus']} BDT বোনাস পেয়েছেন!")
                except Exception:
                    pass

            await query.message.edit_text(f"✅ জিমেইল টাস্ক #{t_id} এপ্রুভ করা হয়েছে!")

    elif data.startswith("rej_gm_"):
        t_id = int(data.split("_")[2])
        task = db["submitted_gmails"].get(t_id)
        if task and task["status"] == "pending":
            task["status"] = "rejected"
            await query.message.edit_text(f"❌ জিমেইল টাস্ক #{t_id} রিজেক্ট করা হয়েছে!")

# WITHDRAW USER SUBMIT PROCESS
async def proc_withdraw_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id
    try:
        parts = text.split()
        num = parts[0]
        amt = float(parts[1])
        
        if amt < db["withdraw_settings"]["min_limit"]:
            await update.message.reply_text(f"⚠️ সর্বনিম্ন উইথড্র পরিমাণ {db['withdraw_settings']['min_limit']} BDT।")
            return ConversationHandler.END
            
        if db["users"][uid]["balance"] < amt:
            await update.message.reply_text("⚠️ আপনার একাউন্টে পর্যাপ্ত ব্যালেন্স নেই!")
            return ConversationHandler.END

        # Deduct balance & save request
        db["users"][uid]["balance"] -= amt
        wid = db["withdraw_counter"]
        db["withdraw_requests"][wid] = {
            "user_id": uid,
            "method": context.user_data.get("w_method", "Bkash"),
            "number": num,
            "amount": amt,
            "status": "pending"
        }
        db["withdraw_counter"] += 1
        await update.message.reply_text("✅ আপনার উইথড্র রিকোয়েস্ট অ্যাডমিন প্যানেলে পাঠানো হয়েছে!")
    except Exception:
        await update.message.reply_text("⚠️ ভুল ফরম্যাট! উদাহরণ: `017xxxxxxxx 100` এভাবে পাঠান।")
    return ConversationHandler.END

async def proc_gmail_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id
    if ":" in text:
        parts = text.split(":")
        tid = db["task_counter"]
        db["submitted_gmails"][tid] = {"user_id": uid, "email": parts[0], "password": parts[1], "status": "pending"}
        db["task_counter"] += 1
        await update.message.reply_text("✅ জিমেইল জমা হয়েছে! অ্যাডমিন চেক করে রিওয়ার্ড দেবে।")
    else:
        await update.message.reply_text("⚠️ ভুল ফরম্যাট! `email@gmail.com:password` এভাবে পাঠান।")
    return ConversationHandler.END

# ----------------------------------------------------
# MAIN EXECUTION
# ----------------------------------------------------
def main():
    keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()

    # CONVERSATION HANDLERS
    gift_code_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 গিফট কোড$"), handle_user_messages)],
        states={CLAIM_GIFT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_gift_code_claim)]},
        fallbacks=[]
    )

    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_query_handler, pattern="^w_")],
        states={WITHDRAW_NUM_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_withdraw_submit)]},
        fallbacks=[]
    )

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_input_start, pattern="^adm_")],
        states={
            ADMIN_ADD_RM: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_admin_add_rm)],
            CREATE_CODE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_code_name)],
            CREATE_CODE_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_code_amt)],
            CREATE_CODE_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_code_limit)],
            SET_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_set_channel)],
            SET_GM_VIDEO: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_set_video)],
            SET_GM_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_set_gm_pass)],
            SET_GM_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_set_gm_rate)],
            SET_REF_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_set_ref_bonus)],
            SET_WITHDRAW_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_set_w_limit)],
            SUSPEND_UNBAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_susp_user)],
        },
        fallbacks=[]
    )

    gmail_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_query_handler, pattern="^gmail_submit_start$")],
        states={GMAIL_SUBMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, proc_gmail_submit)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(gift_code_conv)
    app.add_handler(withdraw_conv)
    app.add_handler(admin_conv)
    app.add_handler(gmail_conv)
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_messages))

    logging.info("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
