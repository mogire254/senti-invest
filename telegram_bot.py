import logging
import requests
import os
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ========== CONFIGURATION ==========
BOT_TOKEN = "8829609308:AAGLLQhi64entHzo1VOmMGf9-Kau8dSuoo8"
API_URL = "https://senti-invest.onrender.com/api"
VOICERSS_API_KEY = "7ca4eeab7dfa4282ad4078514aca3f40"

# Voice settings - MOST NATURAL HUMAN VOICE
VOICE_LANGUAGE = "en-us"
VOICE_NAME = "Amy"       # Female, British - MOST NATURAL VOICE
VOICE_SPEED = "-2"       # Slower = more natural

# Group settings - Already set to your group
GROUP_CHAT_ID = -1004334855180  # Your group ID

# Mute configuration
MUTE_BOT = False
OWNER_USERNAME = "adamsgaller"
OWNER_ID = 8968561395

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== CHECK IF USER IS OWNER ==========
def is_owner(user):
    return user.username == OWNER_USERNAME or user.id == OWNER_ID

# ========== GET OWNER ID COMMAND ==========
async def get_my_id(update: Update, context):
    user = update.effective_user
    await update.message.reply_text(
        f"📋 *Your Info:*\n"
        f"🆔 User ID: `{user.id}`\n"
        f"👤 Username: @{user.username}\n"
        f"📛 First Name: {user.first_name}\n\n"
        f"✅ Owner ID: `{user.id}`",
        parse_mode='Markdown'
    )

# ========== VOICE GENERATION FUNCTIONS ==========
def generate_voice(text):
    """Generate voice using VoiceRSS API - Most human-like voice"""
    try:
        url = "https://api.voicerss.org/"
        
        params = {
            'key': VOICERSS_API_KEY,
            'hl': VOICE_LANGUAGE,
            'v': VOICE_NAME,
            'src': text,
            'r': VOICE_SPEED,
            'c': 'mp3',
            'f': '44khz_16bit_stereo'
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            content = response.content
            if content[:3] == b'\xff\xfb' or content[:3] == b'\x49\x44\x33' or content[:4] == b'\x49\x44\x33':
                file_name = "voice_note.mp3"
                with open(file_name, 'wb') as f:
                    f.write(content)
                return file_name
            else:
                error_msg = response.text[:200]
                logger.error(f"VoiceRSS API error: {error_msg}")
                return generate_voice_google(text)
        else:
            logger.error(f"VoiceRSS API HTTP error: {response.status_code}")
            return generate_voice_google(text)
            
    except Exception as e:
        logger.error(f"Voice generation error: {e}")
        return generate_voice_google(text)

def generate_voice_google(text):
    """Fallback: Generate voice using Google TTS"""
    try:
        url = f"http://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={urllib.parse.quote(text)}"
        
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code == 200:
            file_name = "voice_note.mp3"
            with open(file_name, 'wb') as f:
                f.write(response.content)
            return file_name
        else:
            logger.error(f"Google TTS API error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Google TTS fallback error: {e}")
        return None

# ========== FORWARD OWNER MESSAGES TO GROUP ==========
async def forward_to_group(update: Update, context):
    user = update.effective_user
    
    if not is_owner(user):
        return
    
    message = update.message
    
    if message.voice:
        await context.bot.send_voice(
            chat_id=GROUP_CHAT_ID,
            voice=message.voice.file_id,
            caption="🔊 Voice message from @adamsgaller"
        )
        await update.message.reply_text("✅ Voice note forwarded to the group!")
        return
    
    if message.text and not message.text.startswith('/'):
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"📢 {message.text}"
        )
        await update.message.reply_text("✅ Message forwarded to the group!")
        return

# ========== GET GROUP ID ==========
async def get_group_id(update: Update, context):
    user = update.effective_user
    
    if not is_owner(user):
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    
    if update.message.chat.type in ["group", "supergroup"]:
        group_id = update.message.chat.id
        await update.message.reply_text(
            f"📋 Group ID: `{group_id}`\n\n"
            f"Use /setgroupid {group_id} to save it.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ This is not a group. Please add the bot to a group first and try again.")

async def set_group_id(update: Update, context):
    global GROUP_CHAT_ID
    
    user = update.effective_user
    
    if not is_owner(user):
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    
    try:
        group_id = int(context.args[0])
        GROUP_CHAT_ID = group_id
        await update.message.reply_text(f"✅ Group ID set to: `{group_id}`", parse_mode='Markdown')
        await update.message.reply_text("✅ Now all voice notes will automatically send to the group!")
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ Please provide a valid group ID.\n"
            "Example: `/setgroupid -1001234567890`",
            parse_mode='Markdown'
        )

# ========== VOICE NOTE COMMAND (OWNER ONLY) ==========
async def send_voice_note(update: Update, context):
    user = update.effective_user
    
    if not is_owner(user):
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    
    text = update.message.text.replace('/voice', '').strip()
    
    if not text:
        await update.message.reply_text("❌ Please provide text after /voice command.\nExample: `/voice Hello everyone!`", parse_mode='Markdown')
        return
    
    await update.message.reply_text("🎙️ Generating natural human voice... Please wait.")
    
    try:
        voice_file = generate_voice(text)
        
        if voice_file:
            # Send to group
            with open(voice_file, 'rb') as f:
                await context.bot.send_voice(
                    chat_id=GROUP_CHAT_ID,
                    voice=f,
                    caption="🔊 Voice message from @adamsgaller"
                )
            await update.message.reply_text("✅ Voice note sent to the group!")
            
            # Also send to owner for confirmation (text only)
            await update.message.reply_text("🎙️ Voice note delivered to the group!")
            
            if os.path.exists(voice_file):
                os.remove(voice_file)
        else:
            await update.message.reply_text("⚠️ Failed to generate voice message. Please try again.")
            
    except Exception as e:
        logger.error(f"Voice note error: {e}")
        await update.message.reply_text("⚠️ Failed to generate voice message. Please try again.")

# ========== ADMIN COMMANDS ==========
async def mute_bot(update: Update, context):
    user = update.effective_user
    
    if not is_owner(user):
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    
    global MUTE_BOT
    MUTE_BOT = True
    await update.message.reply_text("🔇 Bot is now **MUTED**. I will not reply to any messages.", parse_mode='Markdown')

async def unmute_bot(update: Update, context):
    user = update.effective_user
    
    if not is_owner(user):
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    
    global MUTE_BOT
    MUTE_BOT = False
    await update.message.reply_text("🔊 Bot is now **UNMUTED**. I will reply to messages again.", parse_mode='Markdown')

async def bot_status(update: Update, context):
    user = update.effective_user
    
    if not is_owner(user):
        await update.message.reply_text("❌ Only the owner can use this command.")
        return
    
    status = "🔇 **MUTED**" if MUTE_BOT else "🔊 **ACTIVE**"
    group_status = f"✅ Group ID: {GROUP_CHAT_ID}" if GROUP_CHAT_ID else "❌ No group set"
    voice_info = f"🎙️ Voice: {VOICE_NAME} | Speed: {VOICE_SPEED}"
    await update.message.reply_text(f"Bot status: {status}\n{group_status}\n{voice_info}", parse_mode='Markdown')

# ========== COMMAND HANDLERS ==========
async def start(update: Update, context):
    user = update.effective_user
    welcome_message = f"Welcome to Senti Earn, {user.first_name}! I am your investment assistant. Send /help for commands."
    keyboard = [
        [InlineKeyboardButton("Investment Products", callback_data="products")],
        [InlineKeyboardButton("Daily Earnings", callback_data="earnings")],
        [InlineKeyboardButton("Referral Bonus", callback_data="referral")],
        [InlineKeyboardButton("Contact Admin", callback_data="admin")],
        [InlineKeyboardButton("Visit Website", url="https://senti-earn.onrender.com")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def help_command(update: Update, context):
    help_text = """
📋 *Available Commands:*

/start - Welcome message
/help - Show this help
/products - List investment products
/earnings - Learn about daily returns
/referral - Get referral bonus info
/myreferral - Get your referral link
/admin - Contact admin
/faq - Frequently asked questions
/website - Visit our website
/myid - Get your user ID
/getgroupid - Get group ID (use in group)
/setgroupid - Set group ID

*Admin Commands:*
/mute - Mute the bot (owner only)
/unmute - Unmute the bot (owner only)
/status - Check bot status (owner only)
/voice <text> - Send natural voice note (owner only)
    """
    keyboard = [
        [InlineKeyboardButton("Products", callback_data="products")],
        [InlineKeyboardButton("Earnings", callback_data="earnings")],
        [InlineKeyboardButton("Referral", callback_data="referral")],
        [InlineKeyboardButton("Admin", callback_data="admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

async def products(update: Update, context):
    try:
        response = requests.get(f"{API_URL}/products/")
        if response.status_code == 200:
            data = response.json()
            products = data.get('products', [])
            
            levels = {}
            for p in products:
                level = p.get('level', 'unknown')
                if level not in levels:
                    levels[level] = []
                levels[level].append(p)
            
            message = "📈 *ALL Investment Products:*\n\n"
            for level, items in levels.items():
                message += f"🔹 *{level.upper()} Level:*\n"
                for p in items:
                    message += f"   • {p['name']}: KES {p['min_investment']:,}, Daily: KES {p['daily_earnings']}/day, {p['duration_days']} days\n"
                message += "\n"
            
            message += "🔗 Visit our website for more details: https://senti-earn.onrender.com"
            
            keyboard = [[InlineKeyboardButton("🔗 View on Website", url="https://senti-earn.onrender.com")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ Could not fetch products. Please try again later.")
    except Exception as e:
        logger.error(f"Products error: {e}")
        await update.message.reply_text("⚠️ Service unavailable. Please try again later.")

async def earnings(update: Update, context):
    message = "Daily Earnings: You earn daily returns on your investments. Higher investments = Higher daily returns. Minimum withdrawal is KES 300."
    keyboard = [[InlineKeyboardButton("Start Investing", url="https://senti-earn.onrender.com")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)

async def referral(update: Update, context):
    message = """
🎁 *Referral Bonus System*

Earn up to KES 300-500 for 5 qualified referrals!

📋 *How it works:*

1️⃣ Share your unique referral link
2️⃣ Friends sign up using your link
3️⃣ They must DEPOSIT & INVEST
4️⃣ Admin reviews and adds bonuses manually

✅ *Bonus Rules:*
• Minimum 5 referrals required
• Each referral must deposit & invest
• Bonus added to your wallet by admin
• Claim your bonus instantly

📱 *Your Referral Link:*
Use the command /myreferral to get your link!

🎉 Start referring now!
    """
    keyboard = [
        [InlineKeyboardButton("🔗 Get My Referral Link", callback_data="myreferral")],
        [InlineKeyboardButton("📞 Contact Admin", callback_data="admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def my_referral(update: Update, context):
    message = "To get your referral link: Login to Senti Earn website, go to Referrals page, copy your link, and share with friends! Website: https://senti-earn.onrender.com"
    keyboard = [[InlineKeyboardButton("Visit Website", url="https://senti-earn.onrender.com")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)

async def admin_contact(update: Update, context):
    message = "Contact Admin: WhatsApp: 0142891121, Telegram: @SentiEarn, Website: https://senti-earn.onrender.com"
    keyboard = [
        [InlineKeyboardButton("WhatsApp", url="https://wa.me/254142891121")],
        [InlineKeyboardButton("Website", url="https://senti-earn.onrender.com")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)

async def faq(update: Update, context):
    message = """
❓ *Frequently Asked Questions*

💰 *Investment:*
Q: How do I start investing?
A: Visit our website → Products → Choose plan → Invest

Q: When do I earn?
A: Daily at midnight. Earnings auto-add to wallet.

📤 *Withdrawal:*
Q: Minimum withdrawal?
A: KES 300

Q: Processing time?
A: 1-12 hours after admin approval

🔗 *Referrals:*
Q: How do I refer friends?
A: Get your referral link from the website

Q: How does the bonus work?
A: Admin reviews qualified referrals and adds bonuses manually (KES 300-500 for 5 referrals)

🔒 *Security:*
Q: Is my money safe?
A: Yes, admin-approved withdrawals only

❌ *Fake payments = account ban!*

📞 *Still have questions?* Contact admin below!
    """
    keyboard = [
        [InlineKeyboardButton("📞 Contact Admin", callback_data="admin")],
        [InlineKeyboardButton("🔗 Visit Website", url="https://senti-earn.onrender.com")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def website(update: Update, context):
    keyboard = [[InlineKeyboardButton("Open Website", url="https://senti-earn.onrender.com")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Visit our website: https://senti-earn.onrender.com", reply_markup=reply_markup)

# ========== AUTO-REPLY ==========
async def auto_reply_group(update: Update, context):
    message = update.message
    
    if MUTE_BOT:
        return
    
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if message.from_user.id == context.bot.id:
        return
    
    if message.text and message.text.startswith('/'):
        return
    
    if not message.text:
        return
    
    if message.text and "@SentiEarn" in message.text:
        reply_text = """
        👋 I see you're trying to reach the owner (@SentiEarn)!

        🤖 I'm here to help! Try these commands:
        /products - See investment options
        /earnings - Learn about daily returns
        /referral - Get referral bonus info
        /admin - Contact support

        The owner will respond as soon as possible.
        """
        await message.reply_text(reply_text)
        return
    
    user_id = message.from_user.id
    if not context.user_data.get(f'greeted_{user_id}', False):
        reply_text = f"""
        👋 Hi {message.from_user.first_name}! Welcome to Senti Earn!

        💡 I'm your investment assistant. Here's how to get started:

        📈 /products - View investment plans
        💰 /earnings - Learn about daily returns
        📋 /referral - Get your referral link
        📞 /admin - Contact support

        🔗 Website: https://senti-earn.onrender.com
        """
        await message.reply_text(reply_text)
        context.user_data[f'greeted_{user_id}'] = True
    else:
        await message.reply_text("💡 Type /help to see what I can do for you!")

# ========== WELCOME NEW MEMBERS ==========
async def welcome_new_member(update: Update, context):
    if MUTE_BOT:
        return
    
    message = update.message
    if message.new_chat_members:
        for member in message.new_chat_members:
            if member.id != context.bot.id:
                welcome_text = f"""
👋 Welcome to Senti Earn, {member.first_name}! 🎉

💡 I'm your investment assistant. Here's how to get started:

📈 /products - View investment plans
💰 /earnings - Learn about daily returns
📋 /referral - Get your referral link
📞 /admin - Contact support

🔗 Website: https://senti-earn.onrender.com

Start your investment journey today! 🚀
                """
                await message.reply_text(welcome_text)

# ========== BUTTON HANDLER ==========
async def button_handler(update: Update, context):
    if MUTE_BOT:
        await update.callback_query.answer("🔇 Bot is muted. Please try again later.", show_alert=True)
        return
    
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "products":
            await products(update, context)
        elif query.data == "earnings":
            await earnings(update, context)
        elif query.data == "referral":
            await referral(update, context)
        elif query.data == "myreferral":
            await my_referral(update, context)
        elif query.data == "admin":
            await admin_contact(update, context)
        elif query.data == "faq":
            await faq(update, context)
    except Exception as e:
        logger.error(f"Button handler error: {e}")
        await query.edit_message_text("⚠️ Something went wrong. Please try again.")

# ========== MAIN FUNCTION ==========
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("products", products))
    application.add_handler(CommandHandler("earnings", earnings))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CommandHandler("myreferral", my_referral))
    application.add_handler(CommandHandler("admin", admin_contact))
    application.add_handler(CommandHandler("faq", faq))
    application.add_handler(CommandHandler("website", website))
    
    # ID helpers
    application.add_handler(CommandHandler("myid", get_my_id))
    
    # Group ID handlers
    application.add_handler(CommandHandler("getgroupid", get_group_id))
    application.add_handler(CommandHandler("setgroupid", set_group_id))
    
    # Admin commands
    application.add_handler(CommandHandler("mute", mute_bot))
    application.add_handler(CommandHandler("unmute", unmute_bot))
    application.add_handler(CommandHandler("status", bot_status))
    application.add_handler(CommandHandler("voice", send_voice_note))
    
    # Forward owner messages to group
    application.add_handler(MessageHandler(filters.TEXT & filters.User(username=OWNER_USERNAME), forward_to_group))
    application.add_handler(MessageHandler(filters.VOICE & filters.User(username=OWNER_USERNAME), forward_to_group))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL, auto_reply_group))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    print("="*50)
    print("🤖 Senti Earn Telegram Bot")
    print("="*50)
    print("✅ Bot is running!")
    print("🎙️ VoiceRSS API Key loaded successfully!")
    print(f"🎙️ Voice: {VOICE_NAME} (MOST HUMAN-LIKE VOICE)")
    print(f"🎙️ Speed: {VOICE_SPEED} (slower = more natural)")
    print("")
    print("🔊 Bot is ACTIVE. Use /mute to mute, /unmute to unmute.")
    print("🎙️ Use /voice <text> to send natural voice notes (owner only).")
    print("📤 Owner messages are automatically forwarded to the group!")
    print("")
    print(f"👤 Owner: @{OWNER_USERNAME} (ID: {OWNER_ID})")
    print(f"📋 Group ID: {GROUP_CHAT_ID}")
    print("="*50)
    print("💡 TIP: 'Amy' is the most natural human voice available")
    print("📌 Voice notes automatically go to the group")
    print("="*50)
    print("Press Ctrl+C to stop.")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()