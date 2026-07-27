import os
import re
import sys
import random
import importlib

# --- REQUIREMENT CHECKER START ---
REQUIRED_MODULES = {
    "telebot": "pyTelegramBotAPI",
    "requests": "requests",
    "urllib3": "urllib3",
    "dotenv": "python-dotenv",
}

REQUIRED_FILES = {
    "stats_manager.py": "Core stats registry manager",
    "bomber_engine.py": "SMS Bomber backend engine",
}

def check_startup_requirements():
    print("📋 ========================================================")
    print("        ZENIN BOMBER - STARTUP VERIFICATION             ")
    print("============================================================")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Check Python Package Modules
    print("\n📦 Verifying Python Package Dependencies:")
    print("------------------------------------------------------------")
    missing_packages = []
    for module_name, pip_name in REQUIRED_MODULES.items():
        try:
            importlib.import_module(module_name)
            print(f"  🟢 {pip_name:<20} -> PRESENT")
        except ImportError:
            print(f"  🔴 {pip_name:<20} -> MISSING")
            missing_packages.append(pip_name)

    # 2. Check Vital Files and Folders
    print("\n📂 Verifying Core Codebase Files:")
    print("------------------------------------------------------------")
    missing_files = []
    for file_name, desc in REQUIRED_FILES.items():
        full_path = os.path.join(base_dir, file_name)
        if os.path.exists(full_path):
            print(f"  🟢 {file_name:<22} -> PRESENT ({desc})")
        else:
            print(f"  🔴 {file_name:<22} -> MISSING ({desc})")
            missing_files.append(file_name)

    # 3. Check Environment Configuration
    print("\n🔑 Verifying Environment Settings (.env):")
    print("------------------------------------------------------------")
    env_path = os.path.join(base_dir, ".env")
    env_exists = os.path.exists(env_path)
    if env_exists:
        print("  🟢 .env Configuration File -> FOUND")
        with open(env_path, "r", encoding="utf-8") as f:
            env_content = f.read()

        token_found = False
        admin_found = False
        for line in env_content.splitlines():
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                val = line.split("=", 1)[1].strip().replace("'", "").replace('"', '')
                if val:
                    token_found = True
            elif line.startswith("ADMIN_IDS="):
                val = line.split("=", 1)[1].strip().replace("'", "").replace('"', '')
                if val:
                    admin_found = True

        if token_found:
            print("  🟢 TELEGRAM_BOT_TOKEN      -> CONFIGURED")
        else:
            print("  🔴 TELEGRAM_BOT_TOKEN      -> MISSING OR EMPTY")

        if admin_found:
            print("  🟢 ADMIN_IDS               -> CONFIGURED")
        else:
            print("  🟡 ADMIN_IDS               -> WARNING (Not set in .env)")
    else:
        print("  🔴 .env Configuration File -> MISSING")
        token_found = False
        admin_found = False

    print("============================================================\n")

    has_errors = (
        len(missing_packages) > 0
        or len(missing_files) > 0
        or not env_exists
        or not token_found
    )

    if has_errors:
        print("❌ STARTUP ERROR: Critical requirements are missing!")
        print("👇 Please execute the following commands to resolve the errors:\n")

        if len(missing_packages) > 0:
            print("👉 1. Install missing Python dependencies:")
            print(f"   Command: pip install {' '.join(missing_packages)}\n")

        if len(missing_files) > 0:
            print("👉 2. Restore missing core codebase files:")
            for f in missing_files:
                print(f"   - {f} ({REQUIRED_FILES[f]})")
            print("   Please check your repository to restore these files.\n")

        if not env_exists or not token_found:
            print("👉 3. Configure environment settings:")
            print("   Create a '.env' file in the bot root folder containing:")
            print("   TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE")
            print("   ADMIN_IDS=ADMIN_ID_1,ADMIN_ID_2\n")

        print("============================================================")
        sys.exit(1)
    else:
        print("✨ All requirements are met! Starting Zenin Bomber Telegram Bot...\n")

# Run the checker before importing external dependencies
check_startup_requirements()
# --- REQUIREMENT CHECKER END ---

import telebot
import json
import threading
import time
from telebot import types, apihelper
from dotenv import load_dotenv

# Load environmental variables from .env file
load_dotenv(override=True)

# Force all spawned python subprocesses to use UTF-8 output encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Import bomber engine
import stats_manager
import bomber_engine

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("❌ Error: TELEGRAM_BOT_TOKEN is not defined in the environment or .env file.")
    sys.exit(1)

OWNER_ID_RAW = os.getenv('OWNER_ID', '')
if OWNER_ID_RAW.strip().isdigit():
    OWNER_ID = int(OWNER_ID_RAW.strip())
    print(f"[OWNER] OWNER_ID loaded: {OWNER_ID}")
else:
    print(f"[OWNER] WARNING: OWNER_ID not configured. Raw value: '{OWNER_ID_RAW}'")
    OWNER_ID = None

ADMIN_IDS_RAW = os.getenv('ADMIN_IDS')
if not ADMIN_IDS_RAW:
    print("⚠️ Warning: ADMIN_IDS is not configured in .env.")
    ADMIN_IDS = []
else:
    ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(',') if x.strip().isdigit()]

def is_owner(chat_id):
    return OWNER_ID is not None and int(chat_id) == OWNER_ID

def is_admin_user(chat_id):
    """Returns True if user is an owner-promoted admin (from stats.json)."""
    return int(chat_id) in stats_manager.get_admin_ids()

def is_co_owner(chat_id):
    """Returns True if user is a co-owner (from stats.json)."""
    return int(chat_id) in stats_manager.get_co_owner_ids()

def has_unlimited_key(chat_id):
    """Returns True if user has a valid (non-expired) unlimited access key."""
    info = stats_manager.get_user_key_info(chat_id)
    return info is not None and info.get('type') == 'unlimited'

def is_privileged(chat_id):
    """Owner, co-owner, admin, or unlimited-key holder — all bypass credits."""
    return is_owner(chat_id) or is_co_owner(chat_id) or is_admin_user(chat_id) or has_unlimited_key(chat_id)

def can_access_panel(chat_id):
    """Only owner and co-owner can access the admin/management panel."""
    return is_owner(chat_id) or is_co_owner(chat_id)

def get_developer_username():
    """Gets current developer username (dynamic, set by owner)."""
    return stats_manager.get_developer_username()

def get_help_line():
    """Returns 'Need help?' contact line with dev1 [& dev2] usernames."""
    dev1 = stats_manager.get_developer_username()
    dev2 = stats_manager.get_developer2_username()
    if dev2:
        return f"⛩️ Need help? just a message away ➤ @{dev1} 🗿 & @{dev2} 🐍"
    return f"⛩️ Need help? just a message away ➤ @{dev1} 🗿"

REQUIRED_CHANNELS_RAW = os.getenv('REQUIRED_CHANNEL_IDS')
if not REQUIRED_CHANNELS_RAW:
    print("⚠️ Warning: REQUIRED_CHANNEL_IDS is not configured in .env. Channel check features will be bypassed.")
    REQUIRED_CHANNELS = []
else:
    REQUIRED_CHANNELS = []
    for x in REQUIRED_CHANNELS_RAW.split(','):
        x = x.strip()
        if x:
            if x.startswith('-') and x[1:].isdigit():
                REQUIRED_CHANNELS.append(int(x))
            elif x.isdigit():
                REQUIRED_CHANNELS.append(int(x))
            else:
                REQUIRED_CHANNELS.append(x)

DEVELOPER_USERNAME = os.getenv('DEVELOPER_USERNAME', '')

# Custom Exception Handler to prevent worker thread crashes from bubbling to infinity_polling
class BotExceptionHandler(telebot.ExceptionHandler):
    def handle(self, exception):
        print(f"⚠️ [TELEBOT EXCEPTION] Handled seamlessly: {exception}")
        if "getaddrinfo failed" in str(exception) or "NewConnectionError" in str(exception) or "Max retries exceeded" in str(exception):
            time.sleep(5)
        return True

# Prevent idle socket timeouts by refreshing the HTTP session periodically
apihelper.SESSION_TIME_TO_LIVE = 5 * 60

bot = telebot.TeleBot(TOKEN, parse_mode='HTML', exception_handler=BotExceptionHandler())

# Safe wrappers for sending and editing messages to auto-retry on ConnectionResetError
orig_send_message = bot.send_message
orig_edit_message_text = bot.edit_message_text

def safe_send_message(*args, **kwargs):
    kwargs.pop('timeout', None)
    for attempt in range(3):
        try:
            return orig_send_message(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if "blocked by the user" in err_str or "Forbidden" in err_str or "chat not found" in err_str or "403" in err_str:
                print(f"🚫 [TELEGRAM SEND FORBIDDEN]: Bot is blocked by user or chat not found. Skipping retries.")
                raise e
            print(f"⚠️ [TELEGRAM SEND RETRY {attempt+1}/3]: {e}")
            if attempt == 2:
                raise e
            time.sleep(1)

def safe_edit_message_text(*args, **kwargs):
    kwargs.pop('timeout', None)
    # Cancel any pending auto-delete for this message so the timer thread
    # doesn't overwrite what the next handler just edited in.
    try:
        _cid = kwargs.get('chat_id')
        _mid = kwargs.get('message_id')
        if _cid and _mid:
            with _auto_delete_lock:
                _auto_delete_store.pop((_cid, _mid), None)
    except Exception:
        pass
    for attempt in range(3):
        try:
            return orig_edit_message_text(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if "message is not modified" in err_str:
                print("📝 [TELEGRAM EDIT]: Message is not modified. Suppressing error.")
                return True
            if "blocked by the user" in err_str or "Forbidden" in err_str or "chat not found" in err_str or "403" in err_str:
                print(f"🚫 [TELEGRAM EDIT FORBIDDEN]: Bot is blocked by user or chat not found. Skipping retries.")
                raise e
            print(f"⚠️ [TELEGRAM EDIT RETRY {attempt+1}/3]: {e}")
            if attempt == 2:
                raise e
            time.sleep(1)

bot.send_message = safe_send_message
bot.edit_message_text = safe_edit_message_text

# ── Auto-delete with live countdown timer ─────────────────────────────────
_auto_delete_store = {}
_auto_delete_lock = threading.Lock()

def _with_timer(text, remaining_secs):
    """Append a live countdown timer line to a message (replaces any existing one)."""
    text = re.sub(r'\n\n⏱ <i>.*?</i>\s*$', '', text, flags=re.DOTALL).rstrip()
    m, s = divmod(int(remaining_secs), 60)
    t_str = f"{m}:{s:02d}" if m else f"{remaining_secs}s"
    return text + f"\n\n⏱ <i>🗑 Deleting in {t_str}</i>"

def schedule_auto_delete(chat_id, message_id, base_text, parse_mode='HTML', reply_markup=None, seconds=60):
    """Schedule a message for auto-deletion with a live countdown that updates every 15s."""
    def _run():
        end_time = time.time() + seconds
        for remaining in [45, 30, 15, 5]:
            sleep_dur = (end_time - remaining) - time.time()
            if sleep_dur > 0:
                time.sleep(sleep_dur)
            with _auto_delete_lock:
                if (chat_id, message_id) not in _auto_delete_store:
                    return
            try:
                orig_edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=_with_timer(base_text, remaining),
                    parse_mode=parse_mode, reply_markup=reply_markup
                )
            except Exception:
                pass
        sleep_dur = end_time - time.time()
        if sleep_dur > 0:
            time.sleep(sleep_dur)
        with _auto_delete_lock:
            if (chat_id, message_id) not in _auto_delete_store:
                return
        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
        with _auto_delete_lock:
            _auto_delete_store.pop((chat_id, message_id), None)

    with _auto_delete_lock:
        _auto_delete_store[(chat_id, message_id)] = True
    threading.Thread(target=_run, daemon=True).start()

def user_send(chat_id, text, parse_mode='HTML', reply_markup=None, seconds=60):
    """Send a user-facing message with auto-delete countdown. NOT for photos/docs."""
    try:
        msg = orig_send_message(chat_id, _with_timer(text, seconds),
                                parse_mode=parse_mode, reply_markup=reply_markup)
        if msg:
            schedule_auto_delete(chat_id, msg.message_id, text, parse_mode, reply_markup, seconds)
        return msg
    except Exception as e:
        raise e

orig_send_photo = bot.send_photo
orig_send_document = bot.send_document

def safe_send_photo(*args, **kwargs):
    kwargs.pop('timeout', None)
    for attempt in range(3):
        try:
            return orig_send_photo(*args, **kwargs)
        except Exception as e:
            print(f"⚠️ [TELEGRAM SEND PHOTO RETRY {attempt+1}/3]: {e}")
            if attempt == 2:
                raise e
            time.sleep(2)

def safe_send_document(*args, **kwargs):
    kwargs.pop('timeout', None)
    for attempt in range(3):
        try:
            return orig_send_document(*args, **kwargs)
        except Exception as e:
            print(f"⚠️ [TELEGRAM SEND DOCUMENT RETRY {attempt+1}/3]: {e}")
            if attempt == 2:
                raise e
            time.sleep(2)

bot.send_photo = safe_send_photo
bot.send_document = safe_send_document


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
user_states = {}

def _get_owner_channels():
    """Returns owner-managed channels list from stats.json."""
    try:
        return stats_manager.get_required_channels()
    except Exception:
        return []

def _resolve_channel_id(ch):
    """
    Returns a usable Telegram channel identifier from a stored channel dict or raw value.
    Prefers stored numeric chat_id, then parses public @username from t.me links.
    Returns None if unresolvable (private invite links with no stored chat_id).
    """
    if isinstance(ch, dict):
        stored_id = ch.get('chat_id')
        if stored_id:
            try:
                return int(stored_id)
            except (ValueError, TypeError):
                pass
        link = ch.get('link', '').strip()
        m = re.match(r'^(?:https?://)?t\.me/([A-Za-z][A-Za-z0-9_]{2,})\s*$', link)
        if m:
            return f"@{m.group(1)}"
        return None
    return ch

# ── Bot admin status helpers ──────────────────────────────────────────────
_bot_me_id = None

def _get_bot_id():
    global _bot_me_id
    if _bot_me_id is None:
        try:
            _bot_me_id = bot.get_me().id
        except Exception:
            pass
    return _bot_me_id

def _bot_is_admin_in(ch_id):
    """Returns True if the bot itself is admin or creator in the given channel/group."""
    try:
        bot_id = _get_bot_id()
        if not bot_id:
            return False
        m = bot.get_chat_member(chat_id=ch_id, user_id=bot_id)
        return m.status in ('administrator', 'creator')
    except Exception:
        return False

def check_user_joined(chat_id):
    """
    Smart channel gate — three modes:
      • No channels set            → grant access immediately (no prompt)
      • Channel set, bot NOT admin → show prompt first time; grant on second attempt (trust user)
      • Channel set, bot IS admin  → verify actual membership OR pending join request
    Bypasses for groups, owner, co-owners, admins, and unlimited-key holders.
    """
    if chat_id < 0:
        return True
    if is_privileged(chat_id):
        return True

    owner_channels = _get_owner_channels()
    channels = owner_channels if owner_channels else (REQUIRED_CHANNELS or [])

    if not channels:
        return True  # No channels configured → open access

    all_ok = True
    for ch in channels:
        ch_id = _resolve_channel_id(ch)

        if ch_id is None:
            # Private invite link — can't call API; use prompt-seen flag as gate
            key = f"invite_{abs(hash(str(ch)))}"
            if not stats_manager.has_seen_join_prompt(chat_id, key):
                all_ok = False
            continue

        if not _bot_is_admin_in(ch_id):
            # ── Bot is NOT admin: trust user on second attempt ────────────
            if not stats_manager.has_seen_join_prompt(chat_id, ch_id):
                all_ok = False
        else:
            # ── Bot IS admin: verify membership or pending join request ───
            try:
                member = bot.get_chat_member(chat_id=ch_id, user_id=chat_id)
                if member.status not in ('member', 'administrator', 'creator', 'restricted'):
                    if not stats_manager.has_join_request(chat_id, ch_id):
                        all_ok = False
            except apihelper.ApiTelegramException as e:
                err_msg = str(e).lower()
                if 'user not found' in err_msg or 'user_not_participant' in err_msg:
                    if not stats_manager.has_join_request(chat_id, ch_id):
                        all_ok = False
                else:
                    print(f"⚠️ [JOIN CHECK] API error for channel {ch_id}, user {chat_id}: {e}")
                    all_ok = False
            except Exception as e:
                print(f"⚠️ [JOIN CHECK] Error for channel {ch_id}, user {chat_id}: {e}")
                all_ok = False

    return all_ok

def _smart_channel_markup(channel_btns, extra_btns=None):
    """Pairs channel buttons 2-per-row; leftover gets its own row."""
    markup = types.InlineKeyboardMarkup()
    i = 0
    while i < len(channel_btns):
        if i + 1 < len(channel_btns):
            markup.row(channel_btns[i], channel_btns[i + 1])
            i += 2
        else:
            markup.row(channel_btns[i])
            i += 1
    if extra_btns:
        for btn in extra_btns:
            markup.row(btn)
    return markup

def prompt_join_channels(chat_id):
    """
    Sends join prompt showing ONLY unjoined channels with progress.
    Uses owner-managed channels if configured, else falls back to .env channels.
    """
    owner_channels = _get_owner_channels()

    if owner_channels:
        total = len(owner_channels)
        joined_list, unjoined_list = [], []
        for ch in owner_channels:
            ch_id = _resolve_channel_id(ch)
            if ch_id is None:
                unjoined_list.append(ch)
                continue
            try:
                member = bot.get_chat_member(chat_id=ch_id, user_id=chat_id)
                (joined_list if member.status in ['member', 'administrator', 'creator'] else unjoined_list).append(ch)
            except Exception:
                unjoined_list.append(ch)

        joined_count = len(joined_list)
        remaining = len(unjoined_list)
        progress_line = (
            f"📊 <b>{joined_count}/{total} channels joined</b> {'✅' * joined_count}"
            if joined_count > 0 else
            f"📊 <b>0/{total} channels joined</b> — Abhi koi bhi join nahi kiya."
        )
        join_text = (
            "⚠️ <b>Join Required Channels</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{progress_line}\n"
            f"👇 <b>{remaining} channel{'s' if remaining != 1 else ''} abhi bhi join karna baaki hai:</b>\n\n"
            "🚀 Neeche join karo, phir <b>Start</b> dabao!"
        )
        channel_btns = []
        for idx, ch in enumerate(unjoined_list, 1):
            if isinstance(ch, dict):
                link = ch.get('link', '').strip()
                name = ch.get('name', '').strip()
                try:
                    is_id = name == str(int(name))
                except (ValueError, TypeError):
                    is_id = False
                label = f"📢 Channel {idx}" if (not name or is_id) else f"📢 {name}"
            else:
                link = f"https://t.me/c/{str(ch).replace('-100', '')}"
                label = f"📢 Channel {idx}"
            if link:
                channel_btns.append(types.InlineKeyboardButton(label, url=link))

        markup = _smart_channel_markup(
            channel_btns,
            extra_btns=[types.InlineKeyboardButton("🔄 Re-Verify / Start", callback_data="check_joined_status")]
        )
        bot.send_message(chat_id, join_text, reply_markup=markup, parse_mode='HTML')
        # Mark all channels as seen — non-admin ones grant access on next attempt
        for _ch in owner_channels:
            _ch_id = _resolve_channel_id(_ch)
            _key = _ch_id if _ch_id is not None else f"invite_{abs(hash(str(_ch)))}"
            stats_manager.mark_seen_join_prompt(chat_id, _key)
        return

    # Fallback: .env-based prompt
    markup = types.InlineKeyboardMarkup(row_width=1)
    join_text = "⚠️ <b>Join Required Channels</b>\n\nBot ko use karne ke liye aapko niche diye gaye channels ko join karna zaroori hai:\n"
    for idx, channel in enumerate(REQUIRED_CHANNELS, 1):
        url = None
        title = f"Channel {idx}"
        try:
            chat_info = bot.get_chat(channel)
            title = chat_info.title or f"Channel {idx}"
            if chat_info.username:
                url = f"https://t.me/{chat_info.username}"
            elif chat_info.invite_link:
                url = chat_info.invite_link
            else:
                try:
                    url = bot.export_chat_invite_link(channel)
                except Exception as ex:
                    print(f"⚠️ [JOIN CHECK] Export invite link failed for {channel}: {ex}")
                    url = f"https://t.me/c/{str(channel).replace('-100', '')}"
        except Exception as e:
            print(f"⚠️ [JOIN CHECK] Error getting chat info for {channel}: {e}")
            url = f"https://t.me/{get_developer_username()}"
        btn = types.InlineKeyboardButton(f"📢 Join {title}", url=url)
        markup.add(btn)

    btn_check = types.InlineKeyboardButton("🔄 Re-Verify / Start", callback_data="check_joined_status")
    markup.add(btn_check)

    bot.send_message(chat_id, join_text, reply_markup=markup, parse_mode='HTML')
    # Mark all channels as seen — non-admin ones grant access on next attempt
    for _ch in REQUIRED_CHANNELS:
        stats_manager.mark_seen_join_prompt(chat_id, _ch)

def esc(s):
    return str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def bold(text):
    result = []
    for c in str(text):
        if 'A' <= c <= 'Z':
            result.append(chr(0x1D5D4 + ord(c) - ord('A')))
        elif 'a' <= c <= 'z':
            result.append(chr(0x1D5EE + ord(c) - ord('a')))
        elif '0' <= c <= '9':
            result.append(chr(0x1D7EC + ord(c) - ord('0')))
        else:
            result.append(c)
    return ''.join(result)

def _get_user_display_name(chat_id):
    try:
        data = stats_manager.load_stats()
        for u in data.get("users", []):
            if isinstance(u, dict) and str(u.get("chat_id")) == str(chat_id):
                return u.get("first_name") or u.get("username") or "User"
    except Exception:
        pass
    return "User"

def get_ui_card(step_num, title, description, target=None, show_tip=True):
    dev = DEVELOPER_USERNAME or 'support'

    if step_num:
        header = f"◆ {bold(title)} • {bold('Step ' + str(step_num) + '/2')}\n"
    else:
        header = f"◆ {bold(title)}\n"

    body = header + "\n"
    body += "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
    body += f"{description}\n"
    if target:
        body += f"\n📡 {bold('Target')}: <code>{target}</code>\n"
    body += f"\n{get_help_line()}\n"
    body += "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
    if show_tip:
        body += "⏳ Waiting for your response...\n\n"
        body += " /cancel to abort  🛑"
    return body

def send_zero_credits_dashboard(chat_id, message_id=None):
    try:
        bot_username = bot.get_me().username
    except Exception as e:
        print(f"⚠️ Failed to get bot username: {e}")
        bot_username = "bot"

    referral_link = f"https://t.me/{bot_username}?start=ref_{chat_id}"

    data = stats_manager.load_stats()

    user_record = None
    for u in data.get("users", []):
        if isinstance(u, dict) and str(u.get("chat_id")) == str(chat_id):
            user_record = u
            break

    join_date = user_record.get("joined", "N/A") if user_record else "N/A"

    history = data.get("cracked_history", [])
    success_count = sum(1 for r in history if str(r.get("chat_id")) == str(chat_id))

    referred_count = 0
    for u in data.get("users", []):
        if isinstance(u, dict):
            ref_by = u.get("referred_by")
            if ref_by is not None and str(ref_by) == str(chat_id):
                referred_count += 1

    zero_credits_text = (
        "⚠️ <b>NO CREDITS REMAINING!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Aapke paas Bombing ke liye credits khatam ho gaye hain. "
        "Naye credits lene ke liye niche diye gaye methods use karein:\n\n"
        "👤 <b>YOUR PROFILE STATS:</b>\n"
        f"  ├─ <b>Telegram ID:</b> <code>{chat_id}</code>\n"
        f"  ├─ <b>Joined Date:</b> <code>{join_date}</code>\n"
        f"  ├─ <b>Credit Balance:</b> <code>0 💳</code>\n"
        f"  ├─ <b>Bombs Sent:</b> <code>{success_count} ✅</code>\n"
        f"  └─ <b>Total Referrals:</b> <code>{referred_count} joined</code>\n\n"
        "🤝 <b>REFER & EARN CREDITS:</b>\n"
        "Apne dosto ko bot par invite karein aur har successful join par <b>1 Credit</b> payein!\n\n"
        "🔗 <b>Your Invite Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💬 Admin/Developer se credits lene ke liye niche direct click karein."
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_buy = types.InlineKeyboardButton("👨‍💻 Contact Admin", url=f"https://t.me/{DEVELOPER_USERNAME}")
    btn_refresh = types.InlineKeyboardButton("🔄 Refresh Credits", callback_data="refresh_zero_credits")
    markup.add(btn_buy, btn_refresh)

    if message_id:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=zero_credits_text, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ [ZERO_CREDITS] Failed to edit welcome text: {e}")
            bot.send_message(chat_id, zero_credits_text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, zero_credits_text, reply_markup=markup, parse_mode='HTML')


def send_welcome_dashboard(chat_id, message_id=None):
    import datetime as _dt
    mode = stats_manager.get_bot_mode()
    dev_uname = get_developer_username()
    user_name = _get_user_display_name(chat_id)

    # Refresh daily key credits if applicable
    try:
        stats_manager.maybe_refresh_daily_key_credits(chat_id)
    except Exception:
        pass

    if is_owner(chat_id):
        role_line = f"👑 {bold('Role')}: Owner"
        role_emoji = "👑"
    elif is_co_owner(chat_id):
        role_line = f"🤝 {bold('Role')}: Co-owner"
        role_emoji = "🤝"
    elif is_admin_user(chat_id):
        role_line = f"🛡 {bold('Role')}: Admin"
        role_emoji = "🛡"
    else:
        role_line = f"👤 {bold('Role')}: User"
        role_emoji = "👤"

    # Credits line
    if is_owner(chat_id) or is_co_owner(chat_id) or is_admin_user(chat_id):
        credits_line = f"🪙 {bold('Credits')}: Unlimited"
    elif has_unlimited_key(chat_id):
        key_info = stats_manager.get_user_key_info(chat_id)
        credits_line = f"🪙 {bold('Credits')}: Unlimited (Key expires {key_info['expires']})"
    elif mode == "paid":
        key_info = stats_manager.get_user_key_info(chat_id)
        credits = stats_manager.get_user_credits(chat_id)
        if key_info and key_info.get('type') == 'daily':
            credits_line = f"🪙 {bold('Credits')}: {credits} (Daily key — expires {key_info['expires']})"
        else:
            credits_line = f"🪙 {bold('Credits')}: {credits}"
    else:
        credits_line = f"🪙 {bold('Credits')}: Unlimited"

    welcome_text = (
        f"💣  {bold('Zenin Bomber')}  💀\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{role_emoji} {bold('Welcome')}, {esc(user_name)}\n\n"
        f"{role_line}\n\n"
        f"{credits_line}\n\n"
        f"{get_help_line()}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f" Select an option below to begin  ⬇️"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_bomb = types.InlineKeyboardButton("💣 Bomb", callback_data="start_bomb")
    markup.add(btn_bomb)

    # Panel button only for owner and co-owner
    if is_owner(chat_id) or is_co_owner(chat_id):
        btn_panel = types.InlineKeyboardButton("⚙️ Panel", callback_data="open_admin_panel")
        markup.add(btn_panel)

    # Developer buttons row — Dev 1 (🗿) and Dev 2 (🐍) side by side
    dev2_uname = stats_manager.get_developer2_username()
    dev_row = [types.InlineKeyboardButton("Developer 🗿", url=f"https://t.me/{dev_uname}")]
    if dev2_uname:
        dev_row.append(types.InlineKeyboardButton("Developer 🐍", url=f"https://t.me/{dev2_uname}"))
    markup.row(*dev_row)

    if message_id:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=welcome_text, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ [WELCOME] Failed to edit welcome text: {e}")
            bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode='HTML')

def send_approval_request(user_chat_id, from_user):
    """Send approve/reject notification to Owner + all Co-owners."""
    fname = getattr(from_user, 'first_name', 'N/A') or 'N/A'
    uname = getattr(from_user, 'username', None)
    uname_str = f"@{uname}" if uname else "N/A"
    text = (
        "👤 <b>New User Approval Request</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 <b>Name:</b> {fname}\n"
        f"🆔 <b>Username:</b> {uname_str}\n"
        f"📟 <b>Chat ID:</b> <code>{user_chat_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Approve or reject this user's access:"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"usr_app_{user_chat_id}"),
        types.InlineKeyboardButton("❌ Reject",  callback_data=f"usr_rej_{user_chat_id}")
    )
    recipients = []
    if OWNER_ID:
        recipients.append(OWNER_ID)
    for co_id in stats_manager.get_co_owner_ids():
        if co_id not in recipients:
            recipients.append(co_id)
    for rid in recipients:
        try:
            bot.send_message(rid, text, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ [APPROVAL] Failed to notify {rid}: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('usr_app_') or call.data.startswith('usr_rej_'))
def handle_approval_callbacks(call):
    reviewer_id = call.message.chat.id
    if not can_access_panel(reviewer_id):
        try: bot.answer_callback_query(call.id, "❌ Access Denied!")
        except: pass
        return
    try: bot.answer_callback_query(call.id)
    except: pass

    action = call.data
    if action.startswith('usr_app_'):
        target_id = int(action[len('usr_app_'):])
        stats_manager.approve_user(target_id)
        try:
            bot.edit_message_reply_markup(
                chat_id=reviewer_id,
                message_id=call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup()
            )
        except: pass
        bot.send_message(reviewer_id, f"✅ User <code>{target_id}</code> approved!", parse_mode='HTML')
        try:
            def_credits = stats_manager.get_default_credits()
            bot.send_message(
                target_id,
                "✅ <b>Request Approved!</b>\n\n"
                f"Aapko bot use karne ka access mil gaya hai.\n"
                f"💳 Starting credits: <b>{def_credits}</b>\n\n"
                "Send /start to begin.",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"⚠️ [APPROVAL] Failed to notify approved user {target_id}: {e}")

    elif action.startswith('usr_rej_'):
        target_id = int(action[len('usr_rej_'):])
        stats_manager.reject_user(target_id)
        try:
            bot.edit_message_reply_markup(
                chat_id=reviewer_id,
                message_id=call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup()
            )
        except: pass
        bot.send_message(reviewer_id, f"🚫 User <code>{target_id}</code> rejected.", parse_mode='HTML')
        try:
            bot.send_message(
                target_id,
                "🚫 <b>Request Rejected</b>\n\n"
                "Aapki access request reject kar di gayi hai.\n"
                "Galti lagne par support se contact karein.",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"⚠️ [APPROVAL] Failed to notify rejected user {target_id}: {e}")


@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id

    # Handle referral rewards first
    parts = message.text.split()
    referrer_id = None
    if len(parts) > 1 and parts[1].startswith("ref_"):
        try:
            referrer_id = int(parts[1].split("_")[1])
        except:
            pass

    is_new_user = not stats_manager.is_user_registered(chat_id)

    try:
        stats_manager.register_visit(chat_id, username=message.from_user.username, first_name=message.from_user.first_name)
    except Exception as e:
        print(f"⚠️ [STATS] Failed to register visit: {e}")

    if is_new_user and referrer_id and referrer_id != chat_id:
        try:
            stats_manager.add_user_credits(referrer_id, 1)
            data = stats_manager.load_stats()
            for u in data.get("users", []):
                if isinstance(u, dict) and u.get("chat_id") == chat_id:
                    u["referred_by"] = referrer_id
                    break
            stats_manager.save_stats(data)
            new_user_name = message.from_user.first_name or "Someone"
            ref_notify = f"User named {new_user_name} joined through your link and you got 1 credit"
            bot.send_message(referrer_id, ref_notify)
        except Exception as ref_err:
            print(f"⚠️ [REFERRAL] Error rewarding referrer {referrer_id}: {ref_err}")

    # Ban gate — blocked users get denied before anything else
    if not is_privileged(chat_id) and stats_manager.is_banned(chat_id):
        bot.send_message(chat_id, "🚫 <b>Access Denied</b>\n\nYou have been banned from this bot.\nContact support if you believe this is an error.", parse_mode='HTML')
        return

    # Check Channel Join Status
    if not check_user_joined(chat_id):
        prompt_join_channels(chat_id)
        return

    # Approval gate — privileged users bypass completely
    if not is_privileged(chat_id) and stats_manager.get_approval_enabled():
        if stats_manager.is_user_rejected(chat_id):
            bot.send_message(
                chat_id,
                "🚫 <b>Access Denied</b>\n\n"
                "Aapki request reject kar di gayi hai.\n"
                "Support se contact karein agar koi galti lagi.",
                parse_mode='HTML'
            )
            return
        if not stats_manager.is_user_approved(chat_id):
            if not stats_manager.is_approval_requested(chat_id):
                stats_manager.set_approval_requested(chat_id)
                send_approval_request(chat_id, message.from_user)
            bot.send_message(
                chat_id,
                "⏳ <b>Approval Pending</b>\n\n"
                "Aapki request owner ko bhej di gayi hai.\n"
                "Approve hone ke baad aap bot use kar sakte hain.\n\n"
                "<i>Kripya wait karein...</i>",
                parse_mode='HTML'
            )
            return

    str_chat_id = str(chat_id)
    active_steps = ['BOMB_RUNNING']
    if user_states.get(chat_id, {}).get('step') in active_steps:
        warn_msg = (
            "⚠️ <b>Active Bomb Running</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⏳ Aapka ek active bomb pehle se chal raha hai.\n"
            "Kripya is task ke complete hone ka wait karein ya bomb rokne ke liye 🛑 Stop button dabayein."
        )
        user_send(chat_id, warn_msg)
        return

    user_states[chat_id] = {'step': 'IDLE'}
    send_welcome_dashboard(chat_id)


@bot.callback_query_handler(func=lambda call: call.data == 'start_bomb')
def handle_start_bomb(call):
    chat_id = call.message.chat.id
    try: bot.answer_callback_query(call.id)
    except: pass

    if not check_user_joined(chat_id):
        try: bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
        except: pass
        prompt_join_channels(chat_id)
        return

    if stats_manager.get_bot_mode() == "paid" and not is_privileged(chat_id):
        credits = stats_manager.get_user_credits(chat_id)
        if credits <= 0:
            send_zero_credits_dashboard(chat_id, message_id=call.message.message_id)
            return

    if bomber_engine.is_bombing(chat_id):
        try: bot.answer_callback_query(call.id, "⚠️ Ek bomb already chal raha hai! Pehle stop karo.", show_alert=True)
        except: pass
        return

    user_states[chat_id] = {'step': 'AWAITING_PHONE'}
    dev = DEVELOPER_USERNAME or 'support'
    bomb_text = (
        f"◆ {bold('SMS Bomb')}\n\n"
        "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
        f"📱 {bold('Target mobile number')} bhejo:\n\n"
        "Format: <code>9876543210</code> (10 digits, without +91)\n\n"
        f"{get_help_line()}\n"
        "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
        "⏳ Waiting for your response...\n\n"
        " /cancel to abort  🛑"
    )
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=bomb_text, parse_mode='HTML')
    except:
        bot.send_message(chat_id, bomb_text, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == 'bomb_stats')
def handle_bomb_stats(call):
    chat_id = call.message.chat.id
    try: bot.answer_callback_query(call.id)
    except: pass

    if not bomber_engine.is_bombing(chat_id):
        try:
            bot.edit_message_text(
                chat_id=chat_id, message_id=call.message.message_id,
                text="❌ <b>No active bomb found.</b>\n\nBombing already complete or was stopped.",
                parse_mode='HTML'
            )
        except: pass
        send_welcome_dashboard(chat_id)
        return

    stats = bomber_engine.get_stats(chat_id)
    phone = stats.get('phone', 'N/A')
    sent = stats.get('sent', 0)
    failed = stats.get('failed', 0)
    elapsed = stats.get('elapsed', 0)
    remaining = stats.get('remaining', 0)
    total_apis = stats.get('total_apis', len(bomber_engine.APIS))

    m_e, s_e = divmod(int(elapsed), 60)
    m_r, s_r = divmod(int(remaining), 60)

    stats_text = (
        "📊 <b>LIVE BOMB STATS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>Target:</b> <code>{phone}</code>\n"
        f"✅ <b>OTPs Sent:</b> <code>{sent}</code>\n"
        f"❌ <b>Failed:</b> <code>{failed}</code>\n"
        f"🔫 <b>APIs Used:</b> <code>{total_apis}</code>\n"
        f"⏱ <b>Elapsed:</b> <code>{m_e}:{s_e:02d}</code>\n"
        f"⏳ <b>Remaining:</b> <code>{m_r}:{s_r:02d}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Refresh", callback_data="bomb_stats"),
        types.InlineKeyboardButton("🛑 Stop", callback_data="stop_bomb")
    )
    try:
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id,
            text=stats_text, reply_markup=markup, parse_mode='HTML'
        )
    except: pass


@bot.callback_query_handler(func=lambda call: call.data == 'stop_bomb')
def handle_stop_bomb(call):
    chat_id = call.message.chat.id
    try: bot.answer_callback_query(call.id, "🛑 Stopping bomb...")
    except: pass

    bomber_engine.stop_bombing(chat_id)
    user_states[chat_id] = {'step': 'IDLE'}

    stats = bomber_engine.get_stats(chat_id)
    phone = stats.get('phone', 'N/A')
    sent = stats.get('sent', 0)
    failed = stats.get('failed', 0)

    stop_text = (
        "🛑 <b>Bomb Stopped!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>Target:</b> <code>{phone}</code>\n"
        f"✅ <b>Total OTPs Sent:</b> <code>{sent}</code>\n"
        f"❌ <b>Failed:</b> <code>{failed}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 Home", callback_data="go_home"))
    try:
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id,
            text=stop_text, reply_markup=markup, parse_mode='HTML'
        )
    except:
        bot.send_message(chat_id, stop_text, reply_markup=markup, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data == 'go_home')
def handle_go_home(call):
    chat_id = call.message.chat.id
    try: bot.answer_callback_query(call.id)
    except: pass
    user_states[chat_id] = {'step': 'IDLE'}
    send_welcome_dashboard(chat_id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'open_admin_panel')
def handle_open_admin_panel(call):
    chat_id = call.message.chat.id
    try: bot.answer_callback_query(call.id)
    except: pass
    if not can_access_panel(chat_id):
        try: bot.answer_callback_query(call.id, "❌ Access Denied!")
        except: pass
        return
    send_admin_dashboard(chat_id)

def get_admin_dashboard_markup(chat_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)

    mode = stats_manager.get_bot_mode()
    mode_btn_text = "🔓 Toggle Mode: FREE" if mode == "free" else "🔒 Toggle Mode: PAID"
    btn_toggle_mode = types.InlineKeyboardButton(mode_btn_text, callback_data="admin_toggle_mode")
    btn_set_def_credits = types.InlineKeyboardButton("💳 Default Credits", callback_data="admin_set_default_credits")
    btn_sys_settings = types.InlineKeyboardButton("⚙️ System Settings", callback_data="admin_settings_menu")
    btn_view_recent_cracks = types.InlineKeyboardButton("📊 Recent Bombs", callback_data="admin_view_recent_cracks")
    btn_grant_credits = types.InlineKeyboardButton("➕ Grant Credits", callback_data="admin_grant_credits")
    btn_remove_credits = types.InlineKeyboardButton("🚫 Remove Credits", callback_data="admin_remove_credits")
    btn_ban_user = types.InlineKeyboardButton("🔨 Ban User", callback_data="admin_ban_user")
    btn_unban_user = types.InlineKeyboardButton("✅ Unban User", callback_data="admin_unban_user")
    btn_broadcast = types.InlineKeyboardButton("📢 Broadcast Msg", callback_data="admin_broadcast")
    btn_view_users = types.InlineKeyboardButton("👥 View Users", callback_data="admin_view_users_page_1")
    btn_export_users = types.InlineKeyboardButton("📥 Export User List", callback_data="admin_download_users")
    btn_view_logs = types.InlineKeyboardButton("👁 View Error Logs", callback_data="admin_view_logs")
    btn_export_logs = types.InlineKeyboardButton("📥 Export Error Logs", callback_data="admin_download_logs")
    btn_cracked = types.InlineKeyboardButton("📂 Download Bomb Logs", callback_data="admin_download_cracked")
    btn_stats = types.InlineKeyboardButton("🔄 Refresh Console", callback_data="admin_stats")

    markup.add(btn_toggle_mode, btn_set_def_credits)
    markup.add(btn_sys_settings, btn_view_recent_cracks)
    markup.add(btn_grant_credits, btn_remove_credits)
    markup.add(btn_ban_user, btn_unban_user)
    markup.add(btn_broadcast)
    markup.add(btn_view_users, btn_export_users)
    markup.add(btn_view_logs, btn_export_logs)
    markup.add(btn_cracked)
    markup.add(btn_stats)

    # ── Approval + Support (shared by owner and co-owner) ────────────────
    if chat_id and can_access_panel(chat_id):
        approval_on = stats_manager.get_approval_enabled()
        approval_label = "👤 Approval: ON ✅" if approval_on else "👤 Approval: OFF ⬜"
        markup.add(
            types.InlineKeyboardButton(approval_label, callback_data="owner_toggle_approval"),
            types.InlineKeyboardButton("📞 Support Contacts", callback_data="owner_support")
        )
        if approval_on:
            pending = stats_manager.get_pending_users()
            if pending:
                markup.add(types.InlineKeyboardButton(f"🕐 Pending Approvals ({len(pending)})", callback_data="owner_pending_approvals"))

    if chat_id and is_owner(chat_id):
        # ── OWNER PANEL ──
        markup.add(types.InlineKeyboardButton("━━━ 👑 OWNER PANEL ━━━", callback_data="owner_noop"))
        markup.add(
            types.InlineKeyboardButton("🛡 Admins", callback_data="owner_admins"),
            types.InlineKeyboardButton("👨‍💻 Developer", callback_data="owner_developer")
        )
        markup.add(
            types.InlineKeyboardButton("🤝 Co-owners", callback_data="owner_coowners"),
            types.InlineKeyboardButton("📢 Set Chat", callback_data="owner_set_chat")
        )
        markup.add(types.InlineKeyboardButton("🔑 Access Keys", callback_data="owner_access_keys"))

    elif chat_id and is_co_owner(chat_id):
        # ── CO-OWNER PANEL ──
        markup.add(types.InlineKeyboardButton("━━━ 🤝 CO-OWNER PANEL ━━━", callback_data="owner_noop"))

    markup.add(types.InlineKeyboardButton("🏠 Back to Home", callback_data="go_home"))
    return markup

def send_admin_dashboard(chat_id):
    summary = stats_manager.get_stats_summary(user_states)
    markup = get_admin_dashboard_markup(chat_id)
    bot.send_message(chat_id, summary, reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('owner_'))
def handle_owner_callbacks(call):
    chat_id = call.message.chat.id
    if not is_owner(chat_id):
        try: bot.answer_callback_query(call.id, "👑 Owner only!")
        except: pass
        return
    try: bot.answer_callback_query(call.id)
    except: pass

    action = call.data

    if action == "owner_noop":
        return

    elif action == "owner_admins":
        admin_ids = stats_manager.get_admin_ids()
        admin_list = "\n".join([f"  • <code>{aid}</code>" for aid in admin_ids]) if admin_ids else "  <i>No admins yet.</i>"
        text = (
            "🛡 <b>ADMIN MANAGEMENT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Current Admins:</b>\n{admin_list}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Promote Admin", callback_data="owner_add_admin"),
            types.InlineKeyboardButton("➖ Remove Admin", callback_data="owner_remove_admin")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_developer":
        current_dev = get_developer_username()
        current_dev2 = stats_manager.get_developer2_username()
        dev2_str = f"@{current_dev2}" if current_dev2 else "<i>Not set</i>"
        text = (
            "👨‍💻 <b>DEVELOPER MANAGEMENT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Developer 1:</b> @{current_dev}\n"
            f"<b>Developer 2:</b> {dev2_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✏️ Change Dev 1", callback_data="owner_set_dev"),
            types.InlineKeyboardButton("✏️ Change Dev 2", callback_data="owner_set_dev2")
        )
        if current_dev2:
            markup.add(types.InlineKeyboardButton("🗑 Clear Developer 2", callback_data="owner_clear_dev2"))
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_back":
        summary = stats_manager.get_stats_summary(user_states)
        markup = get_admin_dashboard_markup(chat_id)
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=summary, reply_markup=markup, parse_mode='HTML')
        except:
            send_admin_dashboard(chat_id)

    elif action == "owner_add_admin":
        user_states[chat_id] = {'step': 'OWNER_ADD_ADMIN'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "🛡 <b>Promote Admin</b>\n\n👇 Us user ka Telegram ID bhejo jise admin banana hai:\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "owner_remove_admin":
        admin_ids = stats_manager.get_admin_ids()
        if not admin_ids:
            bot.send_message(chat_id, "❌ Koi bhi admin nahi hai abhi.", parse_mode='HTML')
            return
        user_states[chat_id] = {'step': 'OWNER_REMOVE_ADMIN'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        admin_list = "\n".join([f"  • <code>{aid}</code>" for aid in admin_ids])
        bot.send_message(chat_id, f"🚫 <b>Remove Admin</b>\n\n<b>Current Admins:</b>\n{admin_list}\n\n👇 Us admin ka ID bhejo jise remove karna hai:\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "owner_set_dev":
        user_states[chat_id] = {'step': 'OWNER_SET_DEV'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        current_dev = get_developer_username()
        bot.send_message(chat_id, f"👨‍💻 <b>Change Developer 1</b>\n\n<b>Current:</b> @{current_dev}\n\n👇 Naya Developer 1 username bhejo (@ ke bina):\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "owner_set_dev2":
        user_states[chat_id] = {'step': 'OWNER_SET_DEV2'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        current_dev2 = stats_manager.get_developer2_username()
        current_str = f"@{current_dev2}" if current_dev2 else "Not set"
        bot.send_message(chat_id, f"👨‍💻 <b>Change Developer 2</b>\n\n<b>Current:</b> {current_str}\n\n👇 Naya Developer 2 username bhejo (@ ke bina):\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "owner_clear_dev2":
        stats_manager.set_developer2_username("")
        bot.answer_callback_query(call.id, "🗑 Developer 2 cleared.")
        current_dev = get_developer_username()
        text = (
            "👨‍💻 <b>DEVELOPER MANAGEMENT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Developer 1:</b> @{current_dev}\n"
            "<b>Developer 2:</b> <i>Not set</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✏️ Change Dev 1", callback_data="owner_set_dev"),
            types.InlineKeyboardButton("✏️ Change Dev 2", callback_data="owner_set_dev2")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_toggle_approval":
        current = stats_manager.get_approval_enabled()
        stats_manager.set_approval_enabled(not current)
        new_state = "ON ✅" if not current else "OFF ⬜"
        summary = stats_manager.get_stats_summary(user_states)
        markup = get_admin_dashboard_markup(chat_id)
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=summary, reply_markup=markup, parse_mode='HTML')
        except:
            send_admin_dashboard(chat_id)
        bot.send_message(chat_id, f"👤 User Approval turned <b>{new_state}</b>", parse_mode='HTML')

    elif action == "owner_support":
        s1, s2 = stats_manager.get_support_usernames()
        s1_str = f"@{s1}" if s1 else "<i>Not set</i>"
        s2_str = f"@{s2}" if s2 else "<i>Not set</i>"
        text = (
            "📞 <b>SUPPORT CONTACTS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Support 1:</b> {s1_str}\n"
            f"<b>Support 2:</b> {s2_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Support contacts replace the Developer button on the welcome screen.</i>"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✏️ Set Support 1", callback_data="owner_set_support1"),
            types.InlineKeyboardButton("✏️ Set Support 2", callback_data="owner_set_support2")
        )
        row2 = []
        if s1:
            row2.append(types.InlineKeyboardButton("🗑 Clear Support 1", callback_data="owner_clear_support1"))
        if s2:
            row2.append(types.InlineKeyboardButton("🗑 Clear Support 2", callback_data="owner_clear_support2"))
        if row2:
            markup.row(*row2)
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_set_support1":
        user_states[chat_id] = {'step': 'OWNER_SET_SUPPORT1'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "📞 <b>Set Support 1</b>\n\n👇 Support 1 ka username bhejo (@ ke bina):\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "owner_set_support2":
        user_states[chat_id] = {'step': 'OWNER_SET_SUPPORT2'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "📞 <b>Set Support 2</b>\n\n👇 Support 2 ka username bhejo (@ ke bina):\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "owner_clear_support1":
        stats_manager.set_support_username(1, "")
        bot.send_message(chat_id, "🗑 Support 1 cleared.", parse_mode='HTML')
        s1, s2 = stats_manager.get_support_usernames()
        s1_str = f"@{s1}" if s1 else "<i>Not set</i>"
        s2_str = f"@{s2}" if s2 else "<i>Not set</i>"
        text = (
            "📞 <b>SUPPORT CONTACTS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Support 1:</b> {s1_str}\n"
            f"<b>Support 2:</b> {s2_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Support contacts replace the Developer button on the welcome screen.</i>"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✏️ Set Support 1", callback_data="owner_set_support1"),
            types.InlineKeyboardButton("✏️ Set Support 2", callback_data="owner_set_support2")
        )
        row2 = []
        if s1:
            row2.append(types.InlineKeyboardButton("🗑 Clear Support 1", callback_data="owner_clear_support1"))
        if s2:
            row2.append(types.InlineKeyboardButton("🗑 Clear Support 2", callback_data="owner_clear_support2"))
        if row2:
            markup.row(*row2)
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_clear_support2":
        stats_manager.set_support_username(2, "")
        bot.send_message(chat_id, "🗑 Support 2 cleared.", parse_mode='HTML')
        s1, s2 = stats_manager.get_support_usernames()
        s1_str = f"@{s1}" if s1 else "<i>Not set</i>"
        s2_str = f"@{s2}" if s2 else "<i>Not set</i>"
        text = (
            "📞 <b>SUPPORT CONTACTS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Support 1:</b> {s1_str}\n"
            f"<b>Support 2:</b> {s2_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Support contacts replace the Developer button on the welcome screen.</i>"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✏️ Set Support 1", callback_data="owner_set_support1"),
            types.InlineKeyboardButton("✏️ Set Support 2", callback_data="owner_set_support2")
        )
        row2 = []
        if s1:
            row2.append(types.InlineKeyboardButton("🗑 Clear Support 1", callback_data="owner_clear_support1"))
        if s2:
            row2.append(types.InlineKeyboardButton("🗑 Clear Support 2", callback_data="owner_clear_support2"))
        if row2:
            markup.row(*row2)
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_pending_approvals":
        pending = stats_manager.get_pending_users()
        if not pending:
            try:
                bot.answer_callback_query(call.id, "✅ No pending approvals!", show_alert=True)
            except:
                pass
            return
        text = (
            "🕐 <b>PENDING APPROVALS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        for u in pending[:10]:
            uid = u.get("chat_id")
            uname = u.get("username", "")
            fname = u.get("first_name", "Unknown")
            label = f"@{uname}" if uname else str(uid)
            text += f"• {fname} ({label})\n"
            markup.add(
                types.InlineKeyboardButton(f"✅ {fname[:12]}", callback_data=f"usr_app_{uid}"),
                types.InlineKeyboardButton(f"❌ {fname[:12]}", callback_data=f"usr_rej_{uid}")
            )
        if len(pending) > 10:
            text += f"\n<i>...and {len(pending) - 10} more.</i>"
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_set_chat":
        channels = stats_manager.get_required_channels()
        if not channels:
            ch_list_str = "  <i>Koi channel set nahi hai abhi.</i>"
        else:
            lines = []
            for i, ch in enumerate(channels, 1):
                if isinstance(ch, dict):
                    name = ch.get('name', '').strip()
                    try:
                        is_id = name == str(int(name))
                    except (ValueError, TypeError):
                        is_id = False
                    label = f"#{i}" if (not name or is_id) else name
                    link = ch.get('link', '—')
                    lines.append(f"  <b>{i}.</b> {label} — <code>{link}</code>")
                else:
                    lines.append(f"  <b>{i}.</b> <code>{ch}</code>")
            ch_list_str = "\n".join(lines)
        text = (
            "📢 <b>CHANNEL MANAGEMENT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Channels ({len(channels)}):</b>\n{ch_list_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "➕ Add: invite link + display name\n"
            "✏️ Edit: number → new link + name\n"
            "🗑 Delete: channel number dena hoga"
        )
        m = types.InlineKeyboardMarkup(row_width=3)
        m.add(
            types.InlineKeyboardButton("➕ Add", callback_data="owner_chat_add"),
            types.InlineKeyboardButton("✏️ Edit", callback_data="owner_chat_edit"),
            types.InlineKeyboardButton("🗑 Delete", callback_data="owner_chat_del"),
        )
        m.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                                  text=text, reply_markup=m, parse_mode='HTML')
        except Exception:
            bot.send_message(chat_id, text, reply_markup=m, parse_mode='HTML')

    elif action == "owner_chat_add":
        user_states[chat_id] = {'step': 'OWNER_CHAT_ADD_CHATID'}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        bot_info = bot.get_me()
        bot_username = bot_info.username
        bot.send_message(chat_id,
            "📢 <b>Add Channel — Step 1/3</b>\n\n"
            f"<b>1.</b> Apne channel/group mein <b>@{bot_username}</b> ko <b>Admin</b> banao.\n\n"
            "<b>2.</b> Phir channel ka <b>Chat ID</b> bhejo:\n"
            "(e.g. <code>-1001234567890</code>)\n\n"
            "💡 Chat ID pane ke liye @username_to_id_bot use karein.\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cm, parse_mode='HTML')

    elif action == "owner_chat_edit":
        channels = stats_manager.get_required_channels()
        if not channels:
            bot.answer_callback_query(call.id, "❌ Koi channel nahi hai edit karne ke liye.")
            return
        user_states[chat_id] = {'step': 'OWNER_CHAT_EDIT_NUM'}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        bot.send_message(chat_id,
            f"✏️ <b>Edit Channel</b>\n\n<b>{len(channels)} channels hain.</b>\n"
            f"👇 Kis number ka channel edit karna hai? (1–{len(channels)})\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cm, parse_mode='HTML')

    elif action == "owner_chat_del":
        channels = stats_manager.get_required_channels()
        if not channels:
            bot.answer_callback_query(call.id, "❌ Koi channel nahi hai delete karne ke liye.")
            return
        user_states[chat_id] = {'step': 'OWNER_CHAT_DEL_NUM'}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        bot.send_message(chat_id,
            f"🗑 <b>Delete Channel</b>\n\n<b>{len(channels)} channels hain.</b>\n"
            f"👇 Kis number ka channel delete karna hai? (1–{len(channels)})\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cm, parse_mode='HTML')

    elif action == "owner_list_admins":
        admin_ids = stats_manager.get_admin_ids()
        dev = get_developer_username()
        if not admin_ids:
            admin_list_str = "  <i>Koi admin promote nahi kiya gaya abhi.</i>"
        else:
            admin_list_str = "\n".join([f"  ├─ <code>{aid}</code>" for aid in admin_ids])
        text = (
            "📋 <b>ADMIN & DEVELOPER LIST</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👑 <b>Owner:</b> <code>{OWNER_ID}</code>\n"
            f"👨‍💻 <b>Developer:</b> @{dev}\n\n"
            f"🛡 <b>Admins ({len(admin_ids)}):</b>\n{admin_list_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_stats"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_coowners":
        co_ids = stats_manager.get_co_owner_ids()
        co_list = "\n".join([f"  • <code>{cid}</code>" for cid in co_ids]) if co_ids else "  <i>No co-owners yet.</i>"
        text = (
            "🤝 <b>CO-OWNER MANAGEMENT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Current Co-owners:</b>\n{co_list}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Add Co-owner", callback_data="owner_add_coowner"),
            types.InlineKeyboardButton("➖ Remove Co-owner", callback_data="owner_remove_coowner")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_add_coowner":
        user_states[chat_id] = {'step': 'OWNER_ADD_COOWNER'}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        bot.send_message(chat_id, "🤝 <b>Add Co-owner</b>\n\n👇 Us user ka Telegram ID bhejo jise Co-owner banana hai:\n\nType <b>Cancel</b> to abort.", reply_markup=cm, parse_mode='HTML')

    elif action == "owner_remove_coowner":
        co_ids = stats_manager.get_co_owner_ids()
        if not co_ids:
            try: bot.answer_callback_query(call.id, "❌ Koi co-owner nahi hai abhi.")
            except: pass
            return
        user_states[chat_id] = {'step': 'OWNER_REMOVE_COOWNER'}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        co_list = "\n".join([f"  • <code>{cid}</code>" for cid in co_ids])
        bot.send_message(chat_id, f"🚫 <b>Remove Co-owner</b>\n\n<b>Current Co-owners:</b>\n{co_list}\n\n👇 Us co-owner ka ID bhejo jise remove karna hai:\n\nType <b>Cancel</b> to abort.", reply_markup=cm, parse_mode='HTML')

    elif action == "owner_access_keys":
        import datetime as _dt
        keys = stats_manager.get_access_keys()
        today = _dt.date.today().isoformat()
        if not keys:
            key_list = "  <i>No access keys created yet.</i>"
        else:
            lines = []
            for code, kdata in keys.items():
                ktype = kdata.get("type", "?")
                exp = kdata.get("expires_date", "?")
                redeemed = len(kdata.get("redeemed_by", []))
                status = "✅" if exp >= today else "❌ EXPIRED"
                lines.append(f"  <code>{code}</code> | {ktype} | exp:{exp} | used:{redeemed} {status}")
            key_list = "\n".join(lines)
        text = (
            "🔑 <b>ACCESS KEY MANAGEMENT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Keys ({len(keys)}):</b>\n{key_list}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Two types:\n"
            "• <b>unlimited</b> — no credit cost, bypass\n"
            "• <b>daily</b> — credits reset to default each day"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Create Key", callback_data="owner_create_key"),
            types.InlineKeyboardButton("🗑 Delete Key", callback_data="owner_delete_key")
        )
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="owner_back"))
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode='HTML')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

    elif action == "owner_create_key":
        user_states[chat_id] = {'step': 'OWNER_KEY_TYPE'}
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("♾ Unlimited", callback_data="owner_key_type_unlimited"),
            types.InlineKeyboardButton("📅 Daily Credits", callback_data="owner_key_type_daily")
        )
        markup.add(types.InlineKeyboardButton("🚫 Cancel", callback_data="owner_back"))
        try:
            bot.edit_message_text(
                chat_id=chat_id, message_id=call.message.message_id,
                text="🔑 <b>Create Access Key</b>\n\n<b>Step 1/2</b> — Key type select karo:",
                reply_markup=markup, parse_mode='HTML'
            )
        except:
            bot.send_message(chat_id, "🔑 <b>Create Access Key</b>\n\n<b>Step 1/2</b> — Key type select karo:", reply_markup=markup, parse_mode='HTML')

    elif action in ("owner_key_type_unlimited", "owner_key_type_daily"):
        ktype = "unlimited" if action == "owner_key_type_unlimited" else "daily"
        user_states[chat_id] = {'step': 'OWNER_KEY_DAYS', 'key_type': ktype}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        bot.send_message(
            chat_id,
            f"🔑 <b>Create Access Key ({ktype.upper()})</b>\n\n"
            "<b>Step 2/2</b> — Kitne days mein expire hoga?\n\n"
            "Examples: <code>7</code> = 1 week, <code>30</code> = 1 month, <code>365</code> = 1 year\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cm, parse_mode='HTML'
        )

    elif action == "owner_delete_key":
        keys = stats_manager.get_access_keys()
        if not keys:
            try: bot.answer_callback_query(call.id, "❌ Koi key nahi hai delete karne ke liye.")
            except: pass
            return
        user_states[chat_id] = {'step': 'OWNER_KEY_DELETE'}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        key_list = "\n".join([f"  • <code>{code}</code>" for code in keys.keys()])
        bot.send_message(
            chat_id,
            f"🗑 <b>Delete Access Key</b>\n\n<b>Existing Keys:</b>\n{key_list}\n\n👇 Key code bhejo jo delete karna hai:\n\nType <b>Cancel</b> to abort.",
            reply_markup=cm, parse_mode='HTML'
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    chat_id = call.message.chat.id
    if not can_access_panel(chat_id):
        try: bot.answer_callback_query(call.id, "Access Denied!")
        except: pass
        return

    try: bot.answer_callback_query(call.id)
    except: pass

    action = call.data
    if action == "admin_stats":
        summary = stats_manager.get_stats_summary(user_states)
        markup = get_admin_dashboard_markup(chat_id)
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=summary, reply_markup=markup, parse_mode='HTML')
        except: pass

    elif action == "admin_settings_menu":
        cooldown = stats_manager.get_cooldown_seconds()
        max_concurrent = stats_manager.get_max_concurrent_tasks()
        settings_text = (
            "⚙️ <b>SYSTEM CONFIGURATION SETTINGS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Cooldown Timer:  <b>{cooldown}s</b>\n"
            f"⚡ Max Concurrency:  <b>{max_concurrent} tasks</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Choose a setting to adjust below:"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_cooldown = types.InlineKeyboardButton(f"⏳ Cooldown ({cooldown}s)", callback_data="admin_set_cooldown")
        btn_concurrency = types.InlineKeyboardButton(f"⚡ Max Concurrent ({max_concurrent})", callback_data="admin_set_concurrent")
        btn_back = types.InlineKeyboardButton("🔙 Back to Main", callback_data="admin_stats")
        markup.add(btn_cooldown, btn_concurrency)
        markup.add(btn_back)
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=settings_text, reply_markup=markup, parse_mode='HTML')
        except: pass

    elif action == "admin_set_cooldown":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_COOLDOWN'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "⏳ <b>Set Global Cooldown</b>\n\n👇 Please enter the global cooldown period in seconds:\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_set_concurrent":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_MAX_CONCURRENT'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "⚡ <b>Set Max Concurrency Limit</b>\n\n👇 Please enter the maximum number of concurrent tasks allowed:\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_view_recent_cracks":
        data = stats_manager.load_stats()
        history = data.get("cracked_history", [])
        recent = history[-5:]
        msg_text = "💣 <b>RECENT BOMB HISTORY (Last 5)</b>\n"
        msg_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        if not recent:
            msg_text += "<i>No bomb history found in database.</i>\n"
        else:
            for idx, record in enumerate(reversed(recent), 1):
                timestamp = record.get("timestamp", "N/A")
                fname = record.get("first_name", "N/A")
                uname = record.get("username", "N/A")
                mobile_num = record.get("mobile", record.get("name", "N/A"))
                sent = record.get("sent", "N/A")
                uname_str = f" (@{uname})" if uname and uname != "N/A" else ""
                msg_text += (
                    f"💣 <b>{idx}.</b>\n"
                    f"  ├─ 📅 Time: <code>{timestamp}</code>\n"
                    f"  ├─ 👤 User: {fname}{uname_str}\n"
                    f"  ├─ 📞 Target: <code>{mobile_num}</code>\n"
                    f"  └─ ✅ OTPs Sent: <code>{sent}</code>\n"
                    f"──────────────────────\n"
                )
        msg_text += "━━━━━━━━━━━━━━━━━━━━━━"
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_refresh = types.InlineKeyboardButton("🔄 Refresh Feed", callback_data="admin_view_recent_cracks")
        btn_back = types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_stats")
        markup.add(btn_refresh, btn_back)
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg_text, reply_markup=markup, parse_mode='HTML')
        except: pass

    elif action == "admin_toggle_mode":
        current_mode = stats_manager.get_bot_mode()
        new_mode = "paid" if current_mode == "free" else "free"
        stats_manager.set_bot_mode(new_mode)
        summary = stats_manager.get_stats_summary(user_states)
        markup = get_admin_dashboard_markup(chat_id)
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=summary, reply_markup=markup, parse_mode='HTML')
        except: pass

    elif action == "admin_set_default_credits":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_DEFAULT_CREDITS'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "💳 <b>Set Default Credits</b>\n\n👇 Please enter the default credits count for new users:\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_grant_credits":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_GRANT_USER_ID'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id,
            "➕ <b>Grant User Credits</b>\n\n"
            "👇 Send the target user's <b>Telegram ID</b> or <b>Username</b>:\n\n"
            "Examples:\n"
            "  • Numeric ID: <code>123456789</code>\n"
            "  • Username: <code>@john_doe</code> or <code>john_doe</code>\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_remove_credits":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_REMOVE_CREDITS_ID'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id,
            "🚫 <b>Remove User Credits</b>\n\n"
            "👇 Send the target user's <b>Telegram ID</b> or <b>Username</b>:\n\n"
            "Examples:\n"
            "  • Numeric ID: <code>123456789</code>\n"
            "  • Username: <code>@john_doe</code> or <code>john_doe</code>\n\n"
            "Their credits will be set to <b>0</b>.\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_ban_user":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_BAN_USER_ID'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id,
            "🔨 <b>Ban User</b>\n\n"
            "👇 Send the target user's <b>Telegram ID</b> or <b>Username</b>:\n\n"
            "Examples:\n"
            "  • Numeric ID: <code>123456789</code>\n"
            "  • Username: <code>@john_doe</code> or <code>john_doe</code>\n\n"
            "Banned users cannot access the bot at all.\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_unban_user":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_UNBAN_USER_ID'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id,
            "✅ <b>Unban User</b>\n\n"
            "👇 Send the target user's <b>Telegram ID</b> or <b>Username</b>:\n\n"
            "Examples:\n"
            "  • Numeric ID: <code>123456789</code>\n"
            "  • Username: <code>@john_doe</code> or <code>john_doe</code>\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_broadcast":
        user_states[chat_id] = {'step': 'AWAITING_BROADCAST_MSG'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "📢 <b>Broadcast Command Triggered</b>\n\n👇 Kripya niche text, image, document ya forward message send karein jo aap saare bot users ko bhejna chahte hain.\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_download_cracked":
        bot.send_message(chat_id, "⏳ <b>Fetching Bomb Log Report...</b>", parse_mode='HTML')
        import shutil
        permanent_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cracked_history.txt")
        temp_report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cracked_history_temp.txt")

        if os.path.exists(permanent_path) and os.path.getsize(permanent_path) > 0:
            try:
                shutil.copy(permanent_path, temp_report_path)
                report_path = temp_report_path
            except Exception as e:
                print(f"⚠️ Failed to copy bomb history: {e}")
                report_path = stats_manager.get_cracked_data_file_path()
        else:
            report_path = stats_manager.get_cracked_data_file_path()

        if report_path and os.path.exists(report_path):
            with open(report_path, 'rb') as f:
                bot.send_document(chat_id, f, caption="📂 <b>Zenin Bomber Log Database</b>")
            try: os.remove(report_path)
            except: pass
        else:
            bot.send_message(chat_id, "❌ Failed to generate report or database is empty.", parse_mode='HTML')

    elif action == "admin_download_users":
        bot.send_message(chat_id, "⏳ <b>Generating User List...</b>", parse_mode='HTML')
        data = stats_manager.load_stats()
        users = data.get("users", [])
        def_credits = stats_manager.get_default_credits()
        if not users:
            bot.send_message(chat_id, "❌ No registered users found in the database.", parse_mode='HTML')
        else:
            users_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users_list.txt")
            with open(users_file, 'w', encoding='utf-8') as f:
                f.write(f"🔒 REGISTERED BOT USERS REPORT ({len(users)} total)\n")
                f.write("============================================================\n\n")
                for idx, u in enumerate(users, 1):
                    if isinstance(u, dict):
                        cid = u.get("chat_id", "N/A")
                        fname = u.get("first_name", "N/A")
                        uname = u.get("username", "N/A")
                        joined = u.get("joined", "N/A")
                        credits = u.get("credits", def_credits)
                        uname_str = f" (@{uname})" if uname and uname != "N/A" else ""
                        f.write(f"{idx}. 👤 {fname}{uname_str}\n   🆔 ID: {cid} | 💳 Credits: {credits} | 📅 Joined: {joined}\n\n")
                    else:
                        f.write(f"{idx}. 🆔 User ID: {u}\n\n")
            with open(users_file, 'rb') as f:
                bot.send_document(chat_id, f, caption=f"👤 <b>Registered Bot Users List ({len(users)} users)</b>")
            try: os.remove(users_file)
            except: pass

    elif action == "admin_download_logs":
        bot.send_message(chat_id, "⏳ <b>Fetching Secure Error Logs...</b>", parse_mode='HTML')
        log_path = stats_manager.get_error_log_file_path()
        if log_path and os.path.exists(log_path):
            with open(log_path, 'rb') as f:
                bot.send_document(chat_id, f, caption="⚠️ <b>Zenin Bomber User Error Logs</b>")
        else:
            bot.send_message(chat_id, "✅ No user errors have been logged yet or log file is empty.", parse_mode='HTML')

    elif action.startswith("admin_view_users_page_"):
        try:
            page = int(action.split("_")[-1])
        except:
            page = 1

        data = stats_manager.load_stats()
        users = data.get("users", [])

        if not users:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ No registered users found in the database.", reply_markup=get_admin_dashboard_markup(chat_id), parse_mode='HTML')
            except: pass
            return

        PAGE_SIZE = 5
        total_users = len(users)
        total_pages = max(1, (total_users + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_users = users[start_idx:end_idx]

        msg_text = f"👥 <b>USER MANAGEMENT DECK (Page {page}/{total_pages})</b>\n"
        msg_text += "━━━━━━━━━━━━━━━━━━━━━━\n"

        def_credits = stats_manager.get_default_credits()
        for idx, u in enumerate(page_users, start=start_idx + 1):
            if isinstance(u, dict):
                cid = u.get("chat_id", "N/A")
                fname = u.get("first_name", "N/A")
                uname = u.get("username", "N/A")
                joined = u.get("joined", "N/A")
                credits = u.get("credits", def_credits)

                uname_str = f" (@{uname})" if uname and uname != "N/A" else ""
                credit_status = f"<code>{credits} 💳</code>" if credits > 0 else "<code>0 💳</code> (Exhausted ❌)"

                msg_text += (
                    f"👤 <b>{idx}. {fname}</b>{uname_str}\n"
                    f"  ├─ 🆔 ID: <code>{cid}</code>\n"
                    f"  ├─ 💳 Balance: {credit_status}\n"
                    f"  └─ 📅 Joined: <code>{joined}</code>\n\n"
                )
            else:
                msg_text += f"🆔 User ID: <code>{u}</code>\n──────────────────────\n\n"

        msg_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg_text += f"Total registered users: <b>{total_users}</b>"

        markup = types.InlineKeyboardMarkup(row_width=2)
        nav_buttons = []
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_view_users_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(types.InlineKeyboardButton("➡️ Next", callback_data=f"admin_view_users_page_{page+1}"))

        if nav_buttons:
            markup.add(*nav_buttons)

        btn_export = types.InlineKeyboardButton("📥 Export Users List", callback_data="admin_download_users")
        btn_back = types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_stats")
        markup.add(btn_export, btn_back)

        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg_text, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ [ADMIN] Error editing message to show users: {e}")

    elif action == "admin_view_logs":
        log_path = stats_manager.get_error_log_file_path()
        if not log_path or not os.path.exists(log_path):
            msg_text = "✅ <b>No user errors have been logged yet or log file is empty.</b>"
        else:
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                last_lines = [line.strip() for line in lines if line.strip()][-10:]

                msg_text = f"⚠️ <b>SYSTEM DIAGNOSTIC LOGS (Last {len(last_lines)})</b>\n"
                msg_text += "━━━━━━━━━━━━━━━━━━━━━━\n"

                for line in last_lines:
                    try:
                        timestamp_part, rest = line.split("] User: ", 1)
                        timestamp = timestamp_part.replace("[", "")
                        user_info_part, error_part = rest.split(" | Error: ", 1)
                        msg_text += (
                            f"📅 <code>{timestamp}</code>\n"
                            f"👤 <b>User:</b> <code>{user_info_part}</code>\n"
                            f"❌ <b>Error:</b> <code>{error_part}</code>\n"
                            f"──────────────────────\n"
                        )
                    except:
                        msg_text += f"▪️ <code>{line}</code>\n──────────────────────\n"

                msg_text += "━━━━━━━━━━━━━━━━━━━━━━"
            except Exception as e:
                msg_text = f"❌ <b>Error reading log file:</b> <code>{e}</code>"

        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_refresh = types.InlineKeyboardButton("🔄 Refresh Logs", callback_data="admin_view_logs")
        btn_export = types.InlineKeyboardButton("📥 Export Logs", callback_data="admin_download_logs")
        btn_back = types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_stats")
        markup.add(btn_refresh, btn_export)
        markup.add(btn_back)

        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg_text, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ [ADMIN] Error editing message to show logs: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'refresh_zero_credits')
def handle_refresh_zero_credits(call):
    chat_id = call.message.chat.id
    try:
        bot.answer_callback_query(call.id, text="Checking credits...", show_alert=False)
    except: pass

    mode = stats_manager.get_bot_mode()

    if is_privileged(chat_id) or mode == "free":
        send_welcome_dashboard(chat_id, message_id=call.message.message_id)
        return

    credits = stats_manager.get_user_credits(chat_id)
    if credits > 0:
        try:
            bot.send_message(chat_id, f"🎉 <b>Credits Received!</b> Aapke account me {credits} credits aa gaye hain.", parse_mode='HTML')
        except: pass
        send_welcome_dashboard(chat_id, message_id=call.message.message_id)
    else:
        send_zero_credits_dashboard(chat_id, message_id=call.message.message_id)
        try:
            bot.answer_callback_query(call.id, text="Still 0 credits. Invite friends or contact admin.", show_alert=True)
        except: pass


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    print(f"📥 [CALLBACK] Generic callback triggered: {call.data} for chat_id: {chat_id}")
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"⚠️ [CALLBACK] Failed to answer generic callback: {e}")

    if call.data == "check_joined_status":
        if check_user_joined(chat_id):
            try:
                bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
            except: pass
            send_welcome_dashboard(chat_id)
        else:
            try:
                bot.answer_callback_query(call.id, text="⚠️ Aapne abhi tak saare channels join nahi kiye hain!", show_alert=True)
            except: pass


@bot.message_handler(commands=['profile'])
def handle_profile(message):
    chat_id = message.chat.id

    if not check_user_joined(chat_id):
        prompt_join_channels(chat_id)
        return

    try:
        str_chat_id = int(chat_id)
    except:
        str_chat_id = chat_id

    data = stats_manager.load_stats()

    user_record = None
    for u in data.get("users", []):
        if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
            user_record = u
            break

    if not user_record:
        try:
            stats_manager.register_visit(chat_id, username=message.from_user.username, first_name=message.from_user.first_name)
            data = stats_manager.load_stats()
            for u in data.get("users", []):
                if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                    user_record = u
                    break
        except: pass

    join_date = user_record.get("joined", "N/A") if user_record else "N/A"
    credits = stats_manager.get_user_credits(chat_id)
    mode = stats_manager.get_bot_mode()

    history = data.get("cracked_history", [])
    success_count = sum(1 for r in history if r.get("chat_id") == str_chat_id)

    if is_owner(chat_id):
        role_badge = "👑 Owner"
        credits_line = ""
    elif is_admin_user(chat_id):
        role_badge = "🛡 Admin"
        credits_line = ""
    elif mode == "free":
        role_badge = "👤 User"
        credits_line = f"  ├─ <b>Credit Balance:</b> <b>Unlimited 💳</b>\n"
    else:
        role_badge = "👤 User"
        credits_line = f"  ├─ <b>Credit Balance:</b> <b>{credits} 💳</b>\n"

    profile_text = (
        "👤 <b>USER PROFILE DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  ├─ <b>Role:</b> {role_badge}\n"
        f"  ├─ <b>First Name:</b> {message.from_user.first_name}\n"
        f"  ├─ <b>Username:</b> @{message.from_user.username or 'N/A'}\n"
        f"  ├─ <b>Telegram ID:</b> <code>{chat_id}</code>\n"
        f"  ├─ <b>Joined Date:</b> <code>{join_date}</code>\n"
        f"{credits_line}"
        f"  └─ <b>Bombs Sent:</b> <code>{success_count} ✅</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(chat_id, profile_text, parse_mode='HTML')

@bot.message_handler(commands=['key'])
def handle_key_command(message):
    chat_id = message.chat.id
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        dev1 = get_developer_username()
        dev2 = stats_manager.get_developer2_username()
        contact_str = f"@{dev1} and @{dev2}" if dev2 else f"@{dev1}"
        bot.send_message(
            chat_id,
            "🔑 <b>Access Key Activation</b>\n\n"
            "Agar aapke paas koi access key hai, use karne ke liye:\n\n"
            "<code>/key YOUR_KEY_CODE</code>\n\n"
            f"Key lene ke liye developer se contact karein: {contact_str}",
            parse_mode='HTML'
        )
        return

    if can_access_panel(chat_id):
        bot.send_message(chat_id, "ℹ️ Owner/Co-owner ke liye access key ki zaroorat nahi — aapka access unlimited hai.", parse_mode='HTML')
        return
    if is_admin_user(chat_id):
        bot.send_message(chat_id, "ℹ️ Admins ka access already unlimited hai — key redeem karne ki zaroorat nahi.", parse_mode='HTML')
        return

    key_code = parts[1].strip()
    ok, msg, ktype = stats_manager.redeem_access_key(chat_id, key_code)
    if ok:
        if ktype == "unlimited":
            type_desc = "♾ Unlimited access (no credit cost)"
        else:
            key_info = stats_manager.get_user_key_info(chat_id)
            exp = key_info['expires'] if key_info else "N/A"
            type_desc = f"📅 Daily credits reset — expires {exp}"
        bot.send_message(
            chat_id,
            f"✅ <b>Access Key Activated!</b>\n\n"
            f"🔑 Key: <code>{key_code.upper()}</code>\n"
            f"📋 Type: {type_desc}\n\n"
            "Send /start to see your updated access.",
            parse_mode='HTML'
        )
    else:
        bot.send_message(chat_id, msg, parse_mode='HTML')

@bot.message_handler(commands=['refer'])
def handle_refer(message):
    chat_id = message.chat.id

    if not check_user_joined(chat_id):
        prompt_join_channels(chat_id)
        return

    try:
        bot_username = bot.get_me().username
    except Exception as e:
        print(f"⚠️ Failed to get bot username: {e}")
        bot_username = "bot"

    referral_link = f"https://t.me/{bot_username}?start=ref_{chat_id}"

    data = stats_manager.load_stats()
    referred_count = 0
    for u in data.get("users", []):
        if isinstance(u, dict) and u.get("referred_by") == chat_id:
            referred_count += 1

    refer_text = (
        "🤝 <b>REFERRAL & INVITE SYSTEM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Apne dosto ko bot par invite karein aur har successful join par <b>1 Credit</b> payein!\n\n"
        "🔗 <b>Your Invite Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"👥 <b>Total Referrals:</b> <code>{referred_count} joined</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Tip: Click the link above to copy it and share.</i>"
    )
    bot.send_message(chat_id, refer_text, parse_mode='HTML')

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    chat_id = message.chat.id
    if not can_access_panel(chat_id):
        bot.send_message(chat_id, "❌ <b>Access Denied!</b>\nThis command is for Owner and Co-owner only.", parse_mode='HTML')
        return
    send_admin_dashboard(chat_id)

def perform_broadcast(message):
    admin_chat_id = message.chat.id
    data = stats_manager.load_stats()
    users = data.get("users", [])

    success = 0
    failed = 0
    total = len(users)

    if total == 0:
        bot.send_message(admin_chat_id, "⚠️ Broadcast completed: No users found in database.")
        return

    start_time = time.time()
    for u in users:
        if isinstance(u, dict):
            user_id = u.get("chat_id")
        else:
            user_id = u
        if not user_id:
            continue
        try:
            bot.copy_message(chat_id=user_id, from_chat_id=admin_chat_id, message_id=message.message_id)
            success += 1
            time.sleep(0.05)
        except Exception as e:
            print(f"⚠️ [BROADCAST] Failed to send to {user_id}: {e}")
            failed += 1

    elapsed = int(time.time() - start_time)
    report = (
        "📢 <b>Broadcast Completed!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Total Targeted:</b> <code>{total}</code>\n"
        f"✅ <b>Successfully Sent:</b> <code>{success}</code>\n"
        f"❌ <b>Failed / Blocked:</b> <code>{failed}</code>\n"
        f"⏱ <b>Time Taken:</b> <code>{elapsed} sec</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(admin_chat_id, report, parse_mode='HTML')

@bot.message_handler(content_types=['text', 'photo', 'audio', 'video', 'document', 'sticker', 'voice', 'location', 'contact', 'video_note', 'animation'])
def handle_all(message):
    chat_id = message.chat.id
    try:
        stats_manager.register_visit(chat_id)
    except Exception as e:
        print(f"⚠️ [STATS] Failed to register visit: {e}")

    # Ban gate
    if not is_privileged(chat_id) and stats_manager.is_banned(chat_id):
        return

    if message.text and message.text.strip().startswith('/start'):
        pass
    elif not check_user_joined(chat_id):
        prompt_join_channels(chat_id)
        return

    state = user_states.get(chat_id, {})
    str_chat_id = str(chat_id)

    # Broadcast Message Interceptor
    if state.get('step') == 'AWAITING_BROADCAST_MSG':
        text_val = message.text.strip() if message.text else ""
        if text_val.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Broadcast cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return

        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, "🚀 <b>Broadcast started in background...</b>\nUsers ko delivery messages report send ki jayegi.", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())

        threading.Thread(target=perform_broadcast, args=(message,), daemon=True).start()
        return

    # Guard: ignore non-text messages
    if not message.text:
        return
    text = message.text.strip()

    # --- ADMIN CONFIGURATION & CREDIT SYSTEM INTERCEPTORS ---
    if state.get('step') == 'AWAITING_ADMIN_COOLDOWN':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ Invalid number. Please send an integer value:")
            return
        val = int(text)
        stats_manager.set_cooldown_seconds(val)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Global cooldown set to <b>{val}s</b> successfully!", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'AWAITING_ADMIN_MAX_CONCURRENT':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ Invalid number. Please send an integer value:")
            return
        val = int(text)
        stats_manager.set_max_concurrent_tasks(val)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Max concurrency limit set to <b>{val}</b> successfully!", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'AWAITING_ADMIN_DEFAULT_CREDITS':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ Invalid number. Please send an integer value:")
            return
        count = int(text)
        stats_manager.set_default_credits(count)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Default credits set to <b>{count}</b> successfully!", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'AWAITING_ADMIN_GRANT_USER_ID':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return

        target_id = None
        resolved_name = ""

        if text.strip().isdigit():
            target_id = int(text.strip())
            resolved_name = f"ID: <code>{target_id}</code>"
        else:
            username_input = text.strip()
            user_rec = stats_manager.get_user_by_username(username_input)
            if user_rec:
                target_id = user_rec.get("chat_id")
                u_name = user_rec.get("username", "N/A")
                u_first = user_rec.get("first_name", "N/A")
                resolved_name = f"@{u_name} (<code>{u_first}</code>) — ID: <code>{target_id}</code>"
            else:
                bot.send_message(chat_id,
                    "⚠️ <b>User not found!</b>\n\n"
                    "Try one of:\n"
                    "• Numeric Telegram ID (e.g. <code>123456789</code>)\n"
                    "• Username with @ (e.g. <code>@john_doe</code>)\n"
                    "• Username without @ (e.g. <code>john_doe</code>)\n\n"
                    "User must have used the bot at least once for username lookup to work.\n\n"
                    "Type <b>Cancel</b> to abort.", parse_mode='HTML')
                return

        current_credits = stats_manager.get_user_credits(target_id)
        user_states[chat_id] = {
            'step': 'AWAITING_ADMIN_GRANT_AMOUNT',
            'target_user_id': target_id
        }
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id,
            f"➕ <b>Grant User Credits</b>\n\n"
            f"👤 Target: {resolved_name}\n"
            f"💳 Current Balance: <b>{current_credits}</b>\n\n"
            f"👇 Enter the number of credits to add (e.g. 5, or negative like -2 to deduct):\n\n"
            f"Type <b>Cancel</b> to abort.",
            reply_markup=cancel_markup, parse_mode='HTML')
        return

    if state.get('step') == 'AWAITING_ADMIN_GRANT_AMOUNT':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return

        is_negative = text.startswith('-')
        clean_val = text[1:] if is_negative else text
        if not clean_val.isdigit():
            bot.send_message(chat_id, "⚠️ Invalid amount. Please send a numeric integer value:")
            return

        amount = int(clean_val)
        if is_negative:
            amount = -amount

        target_id = state.get('target_user_id')
        new_bal = stats_manager.add_user_credits(target_id, amount)

        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Successfully updated credits for user <code>{target_id}</code>.\n💳 Added: <b>{amount}</b>\n💳 New Balance: <b>{new_bal}</b>", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'AWAITING_ADMIN_REMOVE_CREDITS_ID':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        target_id = None
        resolved_name = ""
        if text.strip().isdigit():
            target_id = int(text.strip())
            resolved_name = f"ID: <code>{target_id}</code>"
        else:
            user_rec = stats_manager.get_user_by_username(text.strip())
            if user_rec:
                target_id = user_rec.get("chat_id")
                u_name = user_rec.get("username", "N/A")
                u_first = user_rec.get("first_name", "N/A")
                resolved_name = f"@{u_name} (<code>{u_first}</code>) — ID: <code>{target_id}</code>"
            else:
                bot.send_message(chat_id,
                    "⚠️ <b>User not found!</b>\n\nTry numeric Telegram ID or @username.\nUser must have used the bot at least once.\n\nType <b>Cancel</b> to abort.", parse_mode='HTML')
                return
        current_credits = stats_manager.get_user_credits(target_id)
        stats_manager.set_user_credits(target_id, 0)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id,
            f"✅ <b>Credits Removed</b>\n\n"
            f"👤 User: {resolved_name}\n"
            f"💳 Previous Balance: <b>{current_credits}</b>\n"
            f"💳 New Balance: <b>0</b>",
            parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'AWAITING_ADMIN_BAN_USER_ID':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        target_id = None
        resolved_name = ""
        if text.strip().isdigit():
            target_id = int(text.strip())
            resolved_name = f"ID: <code>{target_id}</code>"
        else:
            user_rec = stats_manager.get_user_by_username(text.strip())
            if user_rec:
                target_id = user_rec.get("chat_id")
                u_name = user_rec.get("username", "N/A")
                u_first = user_rec.get("first_name", "N/A")
                resolved_name = f"@{u_name} (<code>{u_first}</code>) — ID: <code>{target_id}</code>"
            else:
                bot.send_message(chat_id,
                    "⚠️ <b>User not found!</b>\n\nTry numeric Telegram ID or @username.\nUser must have used the bot at least once.\n\nType <b>Cancel</b> to abort.", parse_mode='HTML')
                return
        if is_owner(target_id) or is_co_owner(target_id):
            bot.send_message(chat_id, "⚠️ <b>Cannot ban the owner or co-owners.</b>", parse_mode='HTML')
            return
        stats_manager.ban_user(target_id)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id,
            f"🔨 <b>User Banned</b>\n\n"
            f"👤 User: {resolved_name}\n"
            f"🚫 This user can no longer access the bot.",
            parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'AWAITING_ADMIN_UNBAN_USER_ID':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        target_id = None
        resolved_name = ""
        if text.strip().isdigit():
            target_id = int(text.strip())
            resolved_name = f"ID: <code>{target_id}</code>"
        else:
            user_rec = stats_manager.get_user_by_username(text.strip())
            if user_rec:
                target_id = user_rec.get("chat_id")
                u_name = user_rec.get("username", "N/A")
                u_first = user_rec.get("first_name", "N/A")
                resolved_name = f"@{u_name} (<code>{u_first}</code>) — ID: <code>{target_id}</code>"
            else:
                bot.send_message(chat_id,
                    "⚠️ <b>User not found!</b>\n\nTry numeric Telegram ID or @username.\nUser must have used the bot at least once.\n\nType <b>Cancel</b> to abort.", parse_mode='HTML')
                return
        stats_manager.unban_user(target_id)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id,
            f"✅ <b>User Unbanned</b>\n\n"
            f"👤 User: {resolved_name}\n"
            f"🟢 This user can access the bot again.",
            parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # Owner: Add Admin
    if state.get('step') == 'OWNER_ADD_ADMIN':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        if not text.strip().isdigit():
            bot.send_message(chat_id, "⚠️ Invalid Telegram ID. Please send a numeric ID only:")
            return
        new_admin_id = int(text.strip())
        if new_admin_id == OWNER_ID:
            bot.send_message(chat_id, "⚠️ Owner ID ko admin promote nahi kar sakte.", reply_markup=types.ReplyKeyboardRemove())
            return
        stats_manager.add_admin(new_admin_id)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ User <code>{new_admin_id}</code> ko Admin promote kar diya gaya! 🛡", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # Owner: Remove Admin
    if state.get('step') == 'OWNER_REMOVE_ADMIN':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        if not text.strip().isdigit():
            bot.send_message(chat_id, "⚠️ Invalid Telegram ID. Please send a numeric ID only:")
            return
        rem_id = int(text.strip())
        if rem_id not in stats_manager.get_admin_ids():
            bot.send_message(chat_id, f"⚠️ ID <code>{rem_id}</code> admin list mein nahi hai.", parse_mode='HTML')
            return
        stats_manager.remove_admin(rem_id)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ User <code>{rem_id}</code> ko Admin list se hata diya gaya!", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # Owner: Set Developer 1 Username
    if state.get('step') == 'OWNER_SET_DEV':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        uname = text.strip().lstrip('@')
        if not uname:
            bot.send_message(chat_id, "⚠️ Invalid username. Please try again:")
            return
        stats_manager.set_developer_username(uname)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Developer 1 username set to @{uname} successfully! 👨‍💻", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # Owner: Set Developer 2 Username
    if state.get('step') == 'OWNER_SET_DEV2':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        uname = text.strip().lstrip('@')
        if not uname:
            bot.send_message(chat_id, "⚠️ Invalid username. Please try again:")
            return
        stats_manager.set_developer2_username(uname)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Developer 2 username set to @{uname} successfully! 👨‍💻", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # Owner/Co-owner: Set Support 1 Username
    if state.get('step') == 'OWNER_SET_SUPPORT1':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        uname = text.strip().lstrip('@')
        if not uname:
            bot.send_message(chat_id, "⚠️ Invalid username. Please try again:")
            return
        stats_manager.set_support_username(1, uname)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Support 1 set to @{uname} successfully! 📞", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # Owner/Co-owner: Set Support 2 Username
    if state.get('step') == 'OWNER_SET_SUPPORT2':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        uname = text.strip().lstrip('@')
        if not uname:
            bot.send_message(chat_id, "⚠️ Invalid username. Please try again:")
            return
        stats_manager.set_support_username(2, uname)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Support 2 set to @{uname} successfully! 📞", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # ── Channel Management States ─────────────────────────────────────────────

    if state.get('step') == 'OWNER_CHAT_ADD_CHATID':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        raw = text.strip()
        try:
            channel_id = int(raw)
        except ValueError:
            bot.send_message(chat_id, "⚠️ Invalid Chat ID. Numeric ID bhejo (e.g. <code>-1001234567890</code>):", parse_mode='HTML')
            return
        try:
            bot_info = bot.get_me()
            member = bot.get_chat_member(chat_id=channel_id, user_id=bot_info.id)
            if member.status not in ['administrator', 'creator']:
                bot.send_message(chat_id,
                    f"❌ <b>Bot admin nahi hai!</b>\n\n"
                    f"Pehle @{bot_info.username} ko us channel/group ka <b>Admin</b> banao, phir dobara Chat ID bhejo:",
                    parse_mode='HTML')
                return
        except Exception as e:
            bot.send_message(chat_id,
                f"❌ <b>Channel access nahi mila.</b>\n\n"
                f"Verify karein:\n"
                f"• Bot channel mein admin hai?\n"
                f"• Chat ID sahi hai?\n\n"
                f"Error: <code>{str(e)[:100]}</code>",
                parse_mode='HTML')
            return
        user_states[chat_id] = {'step': 'OWNER_CHAT_ADD_NAME', 'pending_chatid': channel_id}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        bot.send_message(chat_id,
            "✅ <b>Bot admin hai!</b>\n\n"
            "📢 <b>Add Channel — Step 2/3</b>\n\n"
            "👇 Ab channel ka <b>display name</b> bhejo:\n"
            "(e.g. <code>Zenin Updates</code>)\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cm, parse_mode='HTML')
        return

    if state.get('step') == 'OWNER_CHAT_ADD_NAME':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        name = text.strip()
        pending_chatid = state.get('pending_chatid')
        pending_link = state.get('pending_link')
        if pending_link is not None and pending_chatid is None:
            channels = list(stats_manager.get_required_channels())
            channels.append({'id': f'ch_{len(channels)+1}', 'link': pending_link, 'name': name})
            stats_manager.set_required_channels(channels)
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, f"✅ Channel <b>{name}</b> add kar diya gaya!\n🔗 <code>{pending_link}</code>",
                             parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        user_states[chat_id] = {'step': 'OWNER_CHAT_ADD_LINK', 'pending_chatid': pending_chatid, 'pending_name': name}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        bot.send_message(chat_id,
            "📢 <b>Add Channel — Step 3/3</b>\n\n"
            "👇 Channel ka <b>join link</b> bhejo jo users ko dikhega:\n"
            "(e.g. <code>https://t.me/yourchannel</code>)\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cm, parse_mode='HTML')
        return

    if state.get('step') == 'OWNER_CHAT_ADD_LINK':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        link = text.strip()
        if not (link.startswith('http://') or link.startswith('https://') or link.startswith('t.me/')):
            bot.send_message(chat_id, "⚠️ Invalid link. Valid join link bhejo (e.g. https://t.me/yourchannel):")
            return
        pending_chatid = state.get('pending_chatid')
        name = state.get('pending_name', '')
        channels = list(stats_manager.get_required_channels())
        entry = {'id': f'ch_{len(channels)+1}', 'link': link, 'name': name}
        if pending_chatid:
            entry['chat_id'] = pending_chatid
        channels.append(entry)
        stats_manager.set_required_channels(channels)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id,
            f"✅ <b>Channel linked!</b>\n\n"
            f"🏷 <b>Name:</b> {name}\n"
            f"🔗 <b>Link:</b> <code>{link}</code>\n"
            f"🆔 <b>Chat ID:</b> <code>{pending_chatid}</code>",
            parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'OWNER_CHAT_EDIT_NUM':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        channels = stats_manager.get_required_channels()
        if not text.strip().isdigit() or not (1 <= int(text.strip()) <= len(channels)):
            bot.send_message(chat_id, f"⚠️ Invalid number. 1–{len(channels)} ke beech bhejo:")
            return
        idx = int(text.strip()) - 1
        user_states[chat_id] = {'step': 'OWNER_CHAT_EDIT_LINK', 'edit_idx': idx}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        bot.send_message(chat_id,
            f"✏️ <b>Edit Channel #{idx+1} — Step 1/2</b>\n\n"
            "👇 Naya <b>invite link</b> bhejo:\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cm, parse_mode='HTML')
        return

    if state.get('step') == 'OWNER_CHAT_EDIT_LINK':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        link = text.strip()
        if not (link.startswith('http://') or link.startswith('https://') or link.startswith('t.me/')):
            bot.send_message(chat_id, "⚠️ Invalid link. Valid invite link bhejo:")
            return
        idx = state.get('edit_idx', 0)
        user_states[chat_id] = {'step': 'OWNER_CHAT_EDIT_NAME', 'edit_idx': idx, 'pending_link': link}
        cm = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cm.add("Cancel")
        bot.send_message(chat_id,
            f"✏️ <b>Edit Channel #{idx+1} — Step 2/2</b>\n\n"
            "👇 Naya <b>display name</b> bhejo:\n\n"
            "Type <b>Cancel</b> to abort.",
            reply_markup=cm, parse_mode='HTML')
        return

    if state.get('step') == 'OWNER_CHAT_EDIT_NAME':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        name = text.strip()
        link = state.get('pending_link', '')
        idx = state.get('edit_idx', 0)
        channels = list(stats_manager.get_required_channels())
        old = channels[idx] if isinstance(channels[idx], dict) else {}
        updated = {'id': old.get('id', f'ch_{idx+1}'), 'link': link, 'name': name}
        if old.get('chat_id'):
            updated['chat_id'] = old['chat_id']
        channels[idx] = updated
        stats_manager.set_required_channels(channels)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id,
            f"✅ Channel #{idx+1} update ho gaya!\n🏷 <b>{name}</b>\n🔗 <code>{link}</code>",
            parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'OWNER_CHAT_DEL_NUM':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        channels = list(stats_manager.get_required_channels())
        if not text.strip().isdigit() or not (1 <= int(text.strip()) <= len(channels)):
            bot.send_message(chat_id, f"⚠️ Invalid number. 1–{len(channels)} ke beech bhejo:")
            return
        idx = int(text.strip()) - 1
        removed = channels.pop(idx)
        stats_manager.set_required_channels(channels)
        if isinstance(removed, dict):
            label = removed.get('name') or removed.get('link') or f"Channel #{idx+1}"
        else:
            label = str(removed)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ <b>{label}</b> delete kar diya gaya!",
                         parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # ── Co-owner Add ──────────────────────────────────────────────────────────

    if state.get('step') == 'OWNER_ADD_COOWNER':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        if not text.strip().isdigit():
            bot.send_message(chat_id, "⚠️ Invalid Telegram ID. Numeric ID bhejo:")
            return
        new_co_id = int(text.strip())
        if new_co_id == OWNER_ID:
            bot.send_message(chat_id, "⚠️ Owner ko co-owner nahi bana sakte.", reply_markup=types.ReplyKeyboardRemove())
            return
        added = stats_manager.add_co_owner(new_co_id)
        user_states[chat_id] = {'step': 'IDLE'}
        if added:
            bot.send_message(chat_id, f"✅ User <code>{new_co_id}</code> ko Co-owner promote kar diya! 🤝", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        else:
            bot.send_message(chat_id, f"⚠️ User <code>{new_co_id}</code> already co-owner hai.", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # ── Co-owner Remove ───────────────────────────────────────────────────────

    if state.get('step') == 'OWNER_REMOVE_COOWNER':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        if not text.strip().isdigit():
            bot.send_message(chat_id, "⚠️ Invalid Telegram ID. Numeric ID bhejo:")
            return
        rem_co_id = int(text.strip())
        removed = stats_manager.remove_co_owner(rem_co_id)
        user_states[chat_id] = {'step': 'IDLE'}
        if removed:
            bot.send_message(chat_id, f"✅ User <code>{rem_co_id}</code> co-owner list se hata diya gaya!", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        else:
            bot.send_message(chat_id, f"⚠️ ID <code>{rem_co_id}</code> co-owner list mein nahi hai.", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # ── Access Key: Days Input ────────────────────────────────────────────────

    if state.get('step') == 'OWNER_KEY_DAYS':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        if not text.strip().isdigit() or int(text.strip()) < 1:
            bot.send_message(chat_id, "⚠️ Valid number of days bhejo (e.g. 7, 30, 365):")
            return
        ktype = state.get('key_type', 'unlimited')
        days = int(text.strip())
        code = stats_manager.create_access_key(ktype, days)
        import datetime as _dt
        expires = (_dt.date.today() + _dt.timedelta(days=days)).isoformat()
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(
            chat_id,
            f"✅ <b>Access Key Created!</b>\n\n"
            f"🔑 <b>Key Code:</b> <code>{code}</code>\n"
            f"📋 <b>Type:</b> {ktype.upper()}\n"
            f"📅 <b>Expires:</b> {expires} ({days} days)\n\n"
            f"Share this key with users. They can activate it using:\n"
            f"<code>/key {code}</code>",
            parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove()
        )
        send_admin_dashboard(chat_id)
        return

    # ── Access Key: Delete ────────────────────────────────────────────────────

    if state.get('step') == 'OWNER_KEY_DELETE':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
        code = text.strip().upper()
        deleted = stats_manager.delete_access_key(code)
        user_states[chat_id] = {'step': 'IDLE'}
        if deleted:
            bot.send_message(chat_id, f"✅ Key <code>{code}</code> delete kar diya gaya!", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        else:
            bot.send_message(chat_id, f"⚠️ Key <code>{code}</code> nahi mili. Check karein key list.", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # ─────────────────────────────────────────────────────────────────────────

    # 💣 Bomb Flow — Phone Number Input
    if state.get('step') == 'AWAITING_PHONE':
        if text.lower() in ['/cancel', 'cancel']:
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Bombing cancelled.")
            send_welcome_dashboard(chat_id)
            return
        phone = re.sub(r'\D', '', text.strip())
        if phone.startswith('91') and len(phone) == 12:
            phone = phone[2:]
        if not re.match(r'^[6-9]\d{9}$', phone):
            bot.send_message(chat_id,
                "⚠️ <b>Invalid mobile number!</b>\n\n"
                "10 digit Indian mobile number bhejo (without +91).\n"
                "Example: <code>9876543210</code>\n\n"
                "Dobara bhejo:", parse_mode='HTML')
            return
        user_states[chat_id] = {'step': 'AWAITING_DURATION', 'phone': phone}
        duration_text = (
            f"◆ {bold('SMS Bomb')} • {bold('Step 2/2')}\n\n"
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            f"📱 Target: <code>{phone}</code>\n\n"
            f"⏱ {bold('Bombing duration')} bhejo (minutes mein):\n\n"
            "Range: <code>1</code> to <code>60</code> minutes\n\n"
            f"{get_help_line()}\n"
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\n"
            "⏳ Waiting for your response...\n\n"
            " /cancel to abort  🛑"
        )
        bot.send_message(chat_id, duration_text, parse_mode='HTML')
        return

    # 💣 Bomb Flow — Duration Input
    if state.get('step') == 'AWAITING_DURATION':
        if text.lower() in ['/cancel', 'cancel']:
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Bombing cancelled.")
            send_welcome_dashboard(chat_id)
            return
        if not text.strip().isdigit():
            bot.send_message(chat_id, "⚠️ Valid number bhejo (1-60 minutes):")
            return
        duration = int(text.strip())
        if not (1 <= duration <= 60):
            bot.send_message(chat_id, "⚠️ Duration 1-60 minutes ke beech hona chahiye:")
            return
        phone = state.get('phone')
        user_states[chat_id] = {'step': 'BOMB_RUNNING', 'phone': phone, 'duration': duration}

        # Deduct credit in paid mode
        if stats_manager.get_bot_mode() == "paid" and not is_privileged(chat_id):
            stats_manager.deduct_user_credit(chat_id)

        # Start bombing in background thread
        threading.Thread(target=bomber_engine.start_bombing, args=(chat_id, phone, duration), daemon=True).start()

        # Give the engine a moment to initialise
        time.sleep(0.3)

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📊 Live Stats", callback_data="bomb_stats"),
            types.InlineKeyboardButton("🛑 Stop", callback_data="stop_bomb")
        )
        started_text = (
            "💣 <b>BOMBING STARTED!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>Target:</b> <code>{phone}</code>\n"
            f"⏱ <b>Duration:</b> <code>{duration} minutes</code>\n"
            f"🔫 <b>APIs:</b> <code>{len(bomber_engine.APIS)} endpoints</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💥 OTPs are being sent continuously!\n"
            "Use the buttons below to track or stop."
        )
        bot.send_message(chat_id, started_text, reply_markup=markup, parse_mode='HTML')

        # Register in bomb history
        def _log_bomb_complete():
            total_wait = duration * 60 + 5
            time.sleep(total_wait)
            if not bomber_engine.is_bombing(chat_id):
                stats = bomber_engine.get_stats(chat_id)
                # Log to cracked_history for admin tracking
                try:
                    import datetime as _dt
                    data = stats_manager.load_stats()
                    if "cracked_history" not in data:
                        data["cracked_history"] = []
                    user_record = None
                    for u in data.get("users", []):
                        if isinstance(u, dict) and u.get("chat_id") == chat_id:
                            user_record = u
                            break
                    data["cracked_history"].append({
                        "timestamp": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "chat_id": chat_id,
                        "first_name": user_record.get("first_name", "N/A") if user_record else "N/A",
                        "username": user_record.get("username", "N/A") if user_record else "N/A",
                        "mobile": phone,
                        "sent": stats.get("sent", 0),
                    })
                    stats_manager.save_stats(data)
                except Exception as e:
                    print(f"⚠️ [BOMB LOG] Failed to log bomb: {e}")
                user_states[chat_id] = {'step': 'IDLE'}

        threading.Thread(target=_log_bomb_complete, daemon=True).start()
        return

    # Session Cancellation Interceptor
    if text.lower() in ['/cancel', 'cancel', 'reset', '/reset']:
        if bomber_engine.is_bombing(chat_id):
            bomber_engine.stop_bombing(chat_id)
        user_states[chat_id] = {'step': 'IDLE'}
        cancel_text = (
            "❌ <b>Process Cancelled Successfully!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Aapka active session cancel kar diya gaya hai."
        )
        bot.send_message(chat_id, cancel_text, parse_mode='HTML')
        send_welcome_dashboard(chat_id)
        return

@bot.chat_join_request_handler()
def handle_chat_join_request(update):
    """Records join requests so bot-admin channels can verify user eligibility."""
    try:
        user_id = update.from_user.id
        channel_id = update.chat.id
        print(f"📨 [JOIN REQUEST] User {user_id} requested to join channel {channel_id}")
        stats_manager.add_join_request(user_id, channel_id)
    except Exception as e:
        print(f"⚠️ [JOIN REQUEST] Handler error: {e}")

if __name__ == "__main__":
    print("🤖 Zenin Bomber is now LIVE.")

    # Infinite Polling Loop
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60, allowed_updates=['message', 'callback_query', 'chat_join_request'])
        except Exception as e:
            print(f"⚠️ Polling Exception: {e}")
            time.sleep(5)
