import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# Logging configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Configuration
BOT_TOKEN = "8958972223:AAEvH-Qd81T-I1tulHWBnykfwJt_tEMYlpQ"
ADMIN_ID = 6811141921

# Global Database (In-Memory structure; preserves states during session)
db = {
    "users": {},           # user_id: {name, balance, refer_by, task_completed, wrong_attempts, is_banned}
    "admin_config": {
        "gmail_work_active": True,
        "gmail_rate": 20.0,
        "gmail_video_url": "https://t.me/Official_Updat", # Admin customizable
        "req_username": True,  
        "target_username": "",
        "target_password": "Password123", 
        "refer_bonus": 5.0,
        "custom_task": {
            "active": True,
            "title": "নতুন অ্যাপ সাইনআপ কাজ",
            "description": "নিচের লিংকে ক্লিক করে অ্যাপটি ডাউনলোড করুন এবং অ্যাকাউন্ট খুলুন।",
            "link": "https://example.com/download",
            "proof_req": "আপনার ইউজার আইডি এবং সাইনআপ স্ক্রিনশট জমা দিন।"
        },
        "withdraw_methods": {
            "bkash": {"active": False, "min": 100},
            "nagad": {"active": True, "min": 100},
            "rocket": {"active": False, "min": 100}
        }
    },
    "gift_codes": {} # code: {amount, limit, claimed_users: []}
}

# User State Tracking
GMAIL_SUBMIT = "GMAIL_SUBMIT"
TASK_SUBMIT = "TASK_SUBMIT"
GIFT_CLAIM = "GIFT_CLAIM"
BROADCAST_WAIT = "BROADCAST_WAIT"

# --- Keyboard Generators ---
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 কাজ ▸", "💰 ব্যালেন্স"],
        ["💰 টাকা উত্তোলন", "🎁 My Referrals"],
        ["🎁 গিফট কোড", "🏆 লিডারবোর্ড"],
        ["🌐 ভাষা পরিবর্তন", "👨‍✈️ Admin Support"]
    ], resize_keyboard=True)

def get_work_keyboard():
    return ReplyKeyboardMarkup([
        ["📧 জিমেইল কাজ (৳২০.০০)", "📌 কাস্টম টাস্ক"],
        ["❌ বাতিল"]
    ], resize_keyboard=True)

def get_gmail_submenu_keyboard():
    return ReplyKeyboardMarkup([
        ["🔹 জিমেইল সাবমিট করুন", "📹 জিমেইল কাজের ভিডিও"],
        ["⬅️ ফিরে যান"]
    ], resize_keyboard=True)

# Helper function
def is_banned(user_id):
    user = db["users"].get(user_id)
    return user and user.get("is_banned", False)

# --- Core Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if is_banned(user_id):
        await update.message.reply_text("❌ আপনার অ্যাকাউন্টটি স্থগিত (Suspended) করা হয়েছে! সাপোর্টে যোগাযোগ করুন।")
        return

    # User Registration
    if user_id not in db["users"]:
        args = context.args
        ref_id = int(args[0]) if args and args[0].isdigit() else None
        
        db["users"][user_id] = {
            "name": user.full_name or user.username or "User",
            "balance": 0.0,
            "refer_by": ref_id,
            "task_completed": False,
            "wrong_attempts": 0,
            "is_banned": False
        }

    await update.message.reply_text(
        f"😊 স্বাগতম {user.first_name}! কাজ শুরু করতে নিচের অপশনগুলো ব্যবহার করুন ⬇️",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text if update.message.text else ""
    user_state = context.user_data.get("state")

    if is_banned(user_id):
        await update.message.reply_text("❌ আপনার অ্যাকাউন্টটি সাসপেন্ড রয়েছে।")
        return

    # --- State Handling ---
    if user_state == GMAIL_SUBMIT and text not in ["⬅️ ফিরে যান", "❌ বাতিল"]:
        await process_gmail_submission(update, context)
        return
    elif user_state == GIFT_CLAIM and text not in ["⬅️ ফিরে যান", "❌ বাতিল"]:
        await claim_gift_code(update, context)
        return
    elif user_state == BROADCAST_WAIT and user_id == ADMIN_ID:
        await execute_broadcast(update, context)
        return

    # --- Menu Navigation ---
    if text == "📝 কাজ ▸":
        await update.message.reply_text("নিচের তালিকা থেকে একটি কাজ সিলেক্ট করুন:", reply_markup=get_work_keyboard())

    elif text == "📧 জিমেইল কাজ (৳২০.০০)":
        await update.message.reply_text("📧 **জিমেইল কাজের মেনু**\nকাজ শুরু করতে বা টিউটোরিয়াল ভিডিও দেখতে নিচের অপশন চাপুন:", 
                                       reply_markup=get_gmail_submenu_keyboard(), parse_mode="Markdown")

    elif text == "📹 জিমেইল কাজের ভিডিও":
        video_url = db["admin_config"]["gmail_video_url"]
        await update.message.reply_text(f"🎬 **জিমেইল অ্যাকাউন্ট ক্রিয়েট ভিডিও নির্দেশিকা:**\n\nকাজ ভালোভাবে বুঝতে নিচের লিংকের ভিডিওটি মনোযোগ দিয়ে দেখুন:\n🔗 {video_url}", parse_mode="Markdown")

    elif text == "🔹 জিমেইল সাবমিট করুন":
        if not db["admin_config"]["gmail_work_active"]:
            await update.message.reply_text("⚠️ দুঃখিত, বর্তমানে জিমেইলের কাজ বন্ধ আছে।")
            return
        
        config = db["admin_config"]
        msg = f"📌 **জিমেইল কাজ করার নিয়ম:**\n\n"
        if config["req_username"] and config["target_username"]:
            msg += f"🔹 ইউজারনেম প্রিফিক্স: `{config['target_username']}`\n"
        msg += f"🔹 পাসওয়ার্ড: `{config['target_password']}`\n\n"
        msg += "সঠিক ইউজারনেম ও পাসওয়ার্ড দিয়ে জিমেইল তৈরি করে এই ফরম্যাটে পাঠান:\n`email@gmail.com:password`"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        context.user_data["state"] = GMAIL_SUBMIT

    elif text == "📌 কাস্টম টাস্ক":
        task = db["admin_config"]["custom_task"]
        if not task.get("active"):
            await update.message.reply_text("⚠️ বর্তমানে কোনো কাস্টম টাস্ক খালি নেই।")
            return

        msg = (
            f"📋 **{task['title']}**\n\n"
            f"📝 **কাজের বিবরণ:** {task['description']}\n\n"
            f"🔗 **কাজের লিংক:** {task['link']}\n\n"
            f"📌 **কী কী জমা দিতে হবে:**\n{task['proof_req']}\n\n"
            "⚠️ কাজ সম্পন্ন করে সব তথ্য প্রমানসহ এই চ্যাটে লিখে মেসেজ পাঠান।"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        context.user_data["state"] = TASK_SUBMIT

    elif text == "💰 ব্যালেন্স":
        u = db["users"].get(user_id, {})
        await update.message.reply_text(f"👤 নাম: {u.get('name')}\n💳 আপনার বর্তমান ব্যালেন্স: ৳{u.get('balance', 0.0):.2f}")

    elif text == "💰 টাকা উত্তোলন":
        methods = db["admin_config"]["withdraw_methods"]
        buttons = []
        for name, data in methods.items():
            if data["active"]:
                buttons.append([InlineKeyboardButton(f"{name.upper()} (সর্বনিম্ন ৳{data['min']})", callback_data=f"withdraw_{name}")])
        
        if not buttons:
            await update.message.reply_text("❌ বর্তমানে কোনো মেথডে উত্তোলন চালু নেই।")
        else:
            await update.message.reply_text("উত্তোলনের মাধ্যম সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(buttons))

    elif text == "🎁 গিফট কোড":
        await update.message.reply_text("🎁 আপনার গিফট কোডটি নিচে লিখে পাঠান:")
        context.user_data["state"] = GIFT_CLAIM

    elif text == "👨‍✈️ Admin Support":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👨‍✈️ এডমিন সাপোর্ট ↗️", url="https://t.me/telegram")],
            [InlineKeyboardButton("✈️ অফিসিয়াল চ্যানেল ↗️", url="https://t.me/Official_Updat")]
        ])
        await update.message.reply_text("📞 যেকোনো সমস্যা বা জিজ্ঞাসার জন্য সরাসরি আমাদের সাপোর্টে যোগাযোগ করুন।", reply_markup=keyboard)

    elif text in ["❌ বাতিল", "⬅️ ফিরে যান"]:
        context.user_data["state"] = None
        await update.message.reply_text("প্রধান মেনুতে ফেরত আসা হয়েছে।", reply_markup=get_main_keyboard())

# --- Processing Gmail Submissions ---
async def process_gmail_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    config = db["admin_config"]
    user_data = db["users"][user_id]

    valid = True
    if ":" not in text:
        valid = False
    else:
        parts = text.split(":")
        email = parts[0].strip()
        pwd = parts[1].strip()

        if pwd != config["target_password"]:
            valid = False
        if config["req_username"] and config["target_username"] and not email.startswith(config["target_username"]):
            valid = False

    if not valid:
        user_data["wrong_attempts"] += 1
        remaining = 3 - user_data["wrong_attempts"]
        await update.message.reply_text(f"❌ ভুল কাজ! পাসওয়ার্ড বা ইউজারনেম মিলেনি।\n⚠️ অবশিষ্ট সুযোগ: {remaining} বার")
        
        if user_data["wrong_attempts"] >= 3:
            user_data["is_banned"] = True
            await update.message.reply_text("🚨 আপনি ৩ বার ভুল তথ্য দিয়েছেন। আপনার অ্যাকাউন্ট সাসপেন্ড করা হলো!")
            await context.bot.send_message(ADMIN_ID, f"⚠️ **ইউজার সাসপেন্ড করা হয়েছে:**\nনাম: {user_data['name']}\nID: `{user_id}`", parse_mode="Markdown")
        
        context.user_data["state"] = None
        return

    # Success
    user_data["balance"] += config["gmail_rate"]
    user_data["wrong_attempts"] = 0 
    
    # Referral Verification
    if not user_data["task_completed"] and user_data["refer_by"]:
        ref_id = user_data["refer_by"]
        if ref_id in db["users"]:
            db["users"][ref_id]["balance"] += config["refer_bonus"]
            await context.bot.send_message(ref_id, f"🎉 আপনার রেফারেল প্রথম কাজ সম্পন্ন করায় আপনি ৳{config['refer_bonus']} বোনাস পেয়েছেন!")
        user_data["task_completed"] = True

    await update.message.reply_text(f"✅ জিমেইল জমা সফল হয়েছে! আপনার ব্যালেন্সে ৳{config['gmail_rate']} যোগ হয়েছে।", reply_markup=get_main_keyboard())
    context.user_data["state"] = None

# --- Gift Code Processor ---
async def claim_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip()

    if code not in db["gift_codes"]:
        await update.message.reply_text("❌ এই গিফট কোডটি সঠিক নয়!")
    else:
        gift = db["gift_codes"][code]
        if user_id in gift["claimed_users"]:
            await update.message.reply_text("⚠️ আপনি ইতিমধ্যে এই গিফট কোডটি ক্লেইম করে নিয়েছেন!")
        elif len(gift["claimed_users"]) >= gift["limit"]:
            await update.message.reply_text("❌ এই গিফট কোডের ইউজার লিমিট শেষ হয়ে গেছে!")
        else:
            gift["claimed_users"].append(user_id)
            db["users"][user_id]["balance"] += gift["amount"]
            await update.message.reply_text(f"🎉 অভিনন্দন! গিফট কোডের মাধ্যমে আপনি ৳{gift['amount']} পেয়েছেন।", reply_markup=get_main_keyboard())

    context.user_data["state"] = None

# --- Broadcast Logic ---
async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_msg = update.message
    all_users = list(db["users"].keys())
    success_count = 0

    await admin_msg.reply_text(f"📢 {len(all_users)} জন ইউজারের কাছে ব্রডকাস্ট পাঠানো শুরু হয়েছে...")

    for u_id in all_users:
        try:
            if admin_msg.text:
                await context.bot.send_message(chat_id=u_id, text=admin_msg.text)
            elif admin_msg.photo:
                await context.bot.send_photo(chat_id=u_id, photo=admin_msg.photo[-1].file_id, caption=admin_msg.caption or "")
            elif admin_msg.voice:
                await context.bot.send_voice(chat_id=u_id, voice=admin_msg.voice.file_id, caption=admin_msg.caption or "")
            success_count += 1
        except Exception:
            pass # Skip if user blocked bot

    await admin_msg.reply_text(f"✅ ব্রডকাস্ট সম্পন্ন হয়েছে!\nসফলভাবে গেছে: {success_count} জনের কাছে।")
    context.user_data["state"] = None

# --- Admin Commands ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    msg = (
        "⚙️ **Admin Control Panel**\n\n"
        "🔹 `/setpass <pass>` - জিমেইল পাসওয়ার্ড সেট করা\n"
        "🔹 `/setuser <user>` - জিমেইল প্রিফিক্স ইউজার সেট করা\n"
        "🔹 `/create_gift <code> <amount> <limit>` - গিফট কোড তৈরি\n"
        "🔹 `/unban <user_id>` - ইউজারকে আনব্যান করা\n"
        "🔹 `/broadcast` - সবাইকে মেসেজ, ফটো বা ভয়েস পাঠানো\n"
        "🔹 `/users` - মোট ইউজার লিস্ট দেখা"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def admin_set_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.args:
        db["admin_config"]["target_password"] = context.args[0]
        await update.message.reply_text(f"✅ নতুন জিমেইল পাসওয়ার্ড সেট করা হয়েছে: `{context.args[0]}`", parse_mode="Markdown")

async def admin_start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("📢 আপনি যে বার্তাটি (Text / Photo / Voice) সবাইকে পাঠাতে চান, সেটি এখন লিখুন বা ফরওয়ার্ড করুন:")
        context.user_data["state"] = BROADCAST_WAIT

async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.args:
        target_id = int(context.args[0])
        if target_id in db["users"]:
            db["users"][target_id]["is_banned"] = False
            db["users"][target_id]["wrong_attempts"] = 0
            await update.message.reply_text(f"✅ ইউজার ID `{target_id}` সফলভাবে আনব্যান করা হয়েছে।", parse_mode="Markdown")

async def admin_create_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and len(context.args) == 3:
        code, amount, limit = context.args[0], float(context.args[1]), int(context.args[2])
        db["gift_codes"][code] = {"amount": amount, "limit": limit, "claimed_users": []}
        await update.message.reply_text(f"🎁 গিফট কোড সফলভাবে তৈরি হয়েছে!\n\nকোড: `{code}`\nবোনাস: ৳{amount}\nইউজার লিমিট: {limit} জন", parse_mode="Markdown")

# Main Runner Function
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Admin Handlers
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("setpass", admin_set_pass))
    app.add_handler(CommandHandler("create_gift", admin_create_gift))
    app.add_handler(CommandHandler("unban", admin_unban))
    app.add_handler(CommandHandler("broadcast", admin_start_broadcast))
    app.add_handler(CommandHandler("start", start))

    # Generic Message Handler (Catches Text, Photo, Voice)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot is up and running...")
    app.run_polling()

if __name__ == "__main__":
    main()
