import os
import json
import datetime
import threading
import time
import random
import string

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "stats.json")
ERROR_LOG_FILE = os.path.join(BASE_DIR, "errors.log")
stats_lock = threading.RLock()
error_log_lock = threading.RLock()

def _default_stats():
    return {
        "total_views": 0,
        "today_date": "",
        "today_views": 0,
        "success_count": 0,
        "fail_count": 0,
        "mode": "free",
        "default_credits": 2,
        "users": [],
        "cracked_history": [],
        "today_users": [],
        "cooldown_seconds": 60,
        "max_concurrent_tasks": 15,
        "admin_ids": [],
        "co_owner_ids": [],
        "access_keys": {},
        "developer_username": "Igoan",
        "developer2_username": "",
        "required_channels": [],
        "user_approval_enabled": False,
        "support1_username": "",
        "support2_username": "",
        "join_prompt_seen": {},
        "join_requests": {},
        "banned_users": []
    }

def load_stats():
    """Thread-safe loading of stats.json. Returns default layout if file is missing/corrupted."""
    with stats_lock:
        if not os.path.exists(STATS_FILE) or os.path.getsize(STATS_FILE) == 0:
            return _default_stats()
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults = _default_stats()
                for key, default in defaults.items():
                    if key not in data:
                        data[key] = default
                # Auto-approve existing users (migration: users without 'approved' key)
                for u in data.get("users", []):
                    if isinstance(u, dict) and "approved" not in u:
                        u["approved"] = True
                return data
        except Exception as e:
            print(f"⚠️ [STATS] Error loading stats.json: {e}")
            return _default_stats()

def get_user_by_username(username: str) -> dict | None:
    """Look up a user by Telegram username (case-insensitive, strips leading @).
    Returns user dict or None if not found."""
    with stats_lock:
        data = load_stats()
        needle = username.lstrip("@").strip().lower()
        for u in data.get("users", []):
            if isinstance(u, dict):
                u_name = str(u.get("username") or "").lstrip("@").strip().lower()
                if u_name and u_name == needle:
                    return u
        return None


def save_stats(data):
    """Thread-safe atomic writing to stats.json."""
    with stats_lock:
        try:
            temp_file = STATS_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, STATS_FILE)
        except Exception as e:
            print(f"⚠️ [STATS] Error writing to stats.json: {e}")

def register_visit(chat_id, username=None, first_name=None):
    """Increments view counters and records user details for broadcasting."""
    with stats_lock:
        data = load_stats()
        today = datetime.date.today().isoformat()
        
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
            
        if "today_users" not in data:
            data["today_users"] = []
            
        if data["today_date"] != today:
            data["today_date"] = today
            data["today_views"] = 1
            data["today_users"] = [str_chat_id]
            data["total_views"] += 1
        else:
            if str_chat_id not in data["today_users"]:
                data["today_users"].append(str_chat_id)
                data["today_views"] += 1
                data["total_views"] += 1
            
        users_list = data.get("users", [])
        updated_users = []
        user_ids_seen = set()
        
        for u in users_list:
            if isinstance(u, dict):
                cid = u.get("chat_id")
                if cid not in user_ids_seen:
                    user_ids_seen.add(cid)
                    updated_users.append(u)
            else:
                try:
                    cid = int(u)
                    if cid not in user_ids_seen:
                        user_ids_seen.add(cid)
                        updated_users.append({
                            "chat_id": cid,
                            "first_name": "N/A",
                            "username": "N/A",
                            "joined": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                except:
                    pass
        
        existing_user = None
        for u in updated_users:
            if u["chat_id"] == str_chat_id:
                existing_user = u
                break
                
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if existing_user:
            if first_name and (existing_user.get("first_name") == "N/A" or existing_user.get("first_name") != first_name):
                existing_user["first_name"] = first_name
            if username and (existing_user.get("username") == "N/A" or existing_user.get("username") != username):
                existing_user["username"] = username
        else:
            updated_users.append({
                "chat_id": str_chat_id,
                "first_name": first_name or "N/A",
                "username": username or "N/A",
                "joined": now_str,
                "credits": data.get("default_credits", 2)
            })
            
        data["users"] = updated_users
        save_stats(data)

def record_success(chat_id, user_info, name, mobile, uid, password, eid=None):
    """Increments success count and appends database record with user mappings and timestamps."""
    with stats_lock:
        data = load_stats()
        data["success_count"] += 1
        
        username = user_info.get("username", "N/A") if user_info else "N/A"
        first_name = user_info.get("first_name", "N/A") if user_info else "N/A"
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        record = {
            "timestamp": now,
            "chat_id": chat_id,
            "username": username,
            "first_name": first_name,
            "name": name,
            "mobile": mobile,
            "uid": uid,
            "password": password,
            "eid": eid or "N/A"
        }
        
        data["cracked_history"].append(record)
        save_stats(data)
        
        txt_file_path = os.path.join(BASE_DIR, "cracked_history.txt")
        try:
            with open(txt_file_path, "a", encoding="utf-8") as f:
                f.write("============================================================\n")
                f.write(f"{data['success_count']}. [Timestamp: {now}]\n")
                f.write(f"   👤 Telegram User: {first_name} (@{username}) [ID: {chat_id}]\n")
                f.write(f"   🆔 Holder Name: {name}\n")
                f.write(f"   📞 Mobile Number: {mobile}\n")
                f.write(f"   🆔 Enrollment ID (EID): {eid or 'N/A'}\n")
                f.write(f"   🔑 Cracked Aadhaar UID: {uid}\n")
                f.write(f"   🔓 PDF Password: {password}\n")
                f.write("============================================================\n\n")
        except Exception as e:
            print(f"⚠️ [STATS] Failed to write to cracked_history.txt: {e}")
        
        try:
            deduct_user_credit(chat_id)
        except Exception as e:
            print(f"⚠️ [STATS] Error during success credit deduction: {e}")

def record_failure():
    """Increments failure counter."""
    with stats_lock:
        data = load_stats()
        data["fail_count"] += 1
        save_stats(data)

def get_stats_summary(active_user_states):
    """Compiles statistics into a premium dashboard for the Admin Telegram Panel."""
    data = load_stats()
    
    steps_breakdown = {}
    for uid, state_dict in active_user_states.items():
        step = state_dict.get("step", "IDLE")
        if step != "IDLE":
            steps_breakdown[step] = steps_breakdown.get(step, 0) + 1
            
    active_count = sum(steps_breakdown.values())
    
    active_details = ""
    if active_count > 0:
        for step, count in steps_breakdown.items():
            active_details += f"  ├─ <code>{step:<18}</code>: <b>{count} user(s)</b>\n"
    else:
        active_details = "  └─ <i>No users are running active tasks.</i>\n"

    mode = data.get("mode", "free").upper()
    def_credits = data.get("default_credits", 2)
    cooldown = data.get("cooldown_seconds", 60)
    max_concurrent = data.get("max_concurrent_tasks", 15)
    
    total_runs = data['success_count'] + data['fail_count']
    success_rate = 100
    if total_runs > 0:
        success_rate = int((data['success_count'] / total_runs) * 100)
        
    total_users = 0
    total_groups = 0
    for u in data.get("users", []):
        if isinstance(u, dict):
            cid = u.get("chat_id", 0)
        else:
            try:
                cid = int(u)
            except:
                cid = 0
        if cid > 0:
            total_users += 1
        elif cid < 0:
            total_groups += 1
    
    co_owners = len(data.get("co_owner_ids", []))
    admins = len(data.get("admin_ids", []))
    access_keys = len(data.get("access_keys", {}))
        
    summary = (
        "<b>ADMINISTRATION DASHBOARD v4.0</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>SYSTEM CONFIGURATION:</b>\n"
        f"  ├─ Bot Mode:       <b>{mode} Mode</b>\n"
        f"  ├─ Def. Credits:   <code>{def_credits}</code>\n"
        f"  ├─ Global Cooldown: <code>{cooldown}s</code>\n"
        f"  └─ Max Concurrency: <code>{max_concurrent}</code>\n\n"
        "👥 <b>ROLE COUNTS:</b>\n"
        f"  ├─ Co-owners:  <code>{co_owners}</code>\n"
        f"  ├─ Admins:     <code>{admins}</code>\n"
        f"  └─ Access Keys: <code>{access_keys}</code>\n\n"
        "📊 <b>LIVE SYSTEM METRICS:</b>\n"
        f"  ├─ Total Views:      <code>{data['total_views']}</code>\n"
        f"  ├─ Today Views:      <code>{data['today_views']}</code>\n"
        f"  ├─ Total Users:      <code>{total_users}</code>\n"
        f"  ├─ Total Groups:     <code>{total_groups}</code>\n"
        f"  ├─ Registered All:   <code>{len(data['users'])}</code>\n"
        f"  └─ Success Rate:    <b>{success_rate}%</b> (<code>{data['success_count']} ✅</code> / <code>{data['fail_count']} ❌</code>)\n\n"
        f"👥 <b>ACTIVE ROOMS:</b> <code>{active_count} active</code>\n"
        f"{active_details}"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    return summary

def get_cracked_data_file_path():
    """Generates a text report of all cracked history database records."""
    data = load_stats()
    report_path = os.path.join(BASE_DIR, "cracked_history_report.txt")
    
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("============================================================\n")
            f.write("🔒 CRACKED ZENIN AADHAR DATABASE REPORT\n")
            f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Successes: {data['success_count']}\n")
            f.write("============================================================\n\n")
            
            history = data.get("cracked_history", [])
            if not history:
                f.write("No cracked Aadhaar records found in database history yet.\n")
            else:
                for idx, record in enumerate(history, 1):
                    f.write("============================================================\n")
                    f.write(f"{idx}. [Timestamp: {record.get('timestamp', 'N/A')}]\n")
                    f.write(f"   👤 Telegram User: {record.get('first_name', 'N/A')} (@{record.get('username', 'N/A')}) [ID: {record.get('chat_id', 'N/A')}]\n")
                    f.write(f"   🆔 Holder Name: {record.get('name', 'N/A')}\n")
                    f.write(f"   📞 Mobile Number: {record.get('mobile', 'N/A')}\n")
                    f.write(f"   🆔 Enrollment ID (EID): {record.get('eid', 'N/A')}\n")
                    f.write(f"   🔑 Cracked Aadhaar UID: {record.get('uid', 'N/A')}\n")
                    f.write(f"   🔓 PDF Password: {record.get('password', 'N/A')}\n")
                    f.write("============================================================\n\n")
        return report_path
    except Exception as e:
        print(f"⚠️ [STATS] Failed to generate text database report: {e}")
        return None

def log_error(chat_id, user_info, error_msg):
    """Appends an error entry to errors.log with timestamps and user details."""
    with error_log_lock:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = user_info.get("username", "N/A") if user_info else "N/A"
        first_name = user_info.get("first_name", "N/A") if user_info else "N/A"
        
        entry = f"[{now}] User: {first_name} (@{username}) [ID: {chat_id}] | Error: {error_msg}\n"
        try:
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            print(f"⚠️ [STATS] Failed to write to errors.log: {e}")

def get_error_log_file_path():
    """Returns the path to errors.log if it exists and is not empty."""
    if os.path.exists(ERROR_LOG_FILE) and os.path.getsize(ERROR_LOG_FILE) > 0:
        return ERROR_LOG_FILE
    return None

# --- CREDIT & COOLDOWN MANAGEMENT SYSTEM ---

def get_bot_mode():
    """Returns the current bot mode ('free' or 'paid')."""
    with stats_lock:
        data = load_stats()
        return data.get("mode", "free")

def set_bot_mode(mode):
    """Sets the bot mode ('free' or 'paid')."""
    with stats_lock:
        data = load_stats()
        data["mode"] = mode
        save_stats(data)

def get_default_credits():
    """Returns the default credits count (owner-configurable, no floor)."""
    with stats_lock:
        data = load_stats()
        return int(data.get("default_credits", 2))

def set_default_credits(count):
    """Sets the default credits count. Allows 0 and above."""
    with stats_lock:
        data = load_stats()
        data["default_credits"] = max(0, int(count))
        save_stats(data)

def get_user_credits(chat_id):
    """Returns the credits of the user. Defaults to default_credits."""
    with stats_lock:
        data = load_stats()
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
            
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                return u.get("credits", data.get("default_credits", 2))
        return data.get("default_credits", 2)

def set_user_credits(chat_id, amount):
    """Sets user credits to a specific value."""
    with stats_lock:
        data = load_stats()
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
        
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                u["credits"] = max(0, int(amount))
                save_stats(data)
                return
        data["users"].append({
            "chat_id": str_chat_id,
            "first_name": "N/A",
            "username": "N/A",
            "joined": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "credits": max(0, int(amount))
        })
        save_stats(data)

def add_user_credits(chat_id, amount):
    """Adds (or subtracts if negative) user credits. Returns the new credit balance."""
    with stats_lock:
        data = load_stats()
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
            
        user_found = False
        new_balance = 0
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                current_credits = u.get("credits", data.get("default_credits", 2))
                u["credits"] = max(0, current_credits + amount)
                new_balance = u["credits"]
                user_found = True
                break
                
        if not user_found:
            new_balance = max(0, data.get("default_credits", 2) + amount)
            data["users"].append({
                "chat_id": str_chat_id,
                "first_name": "N/A",
                "username": "N/A",
                "joined": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "credits": new_balance
            })
            
        save_stats(data)
        return new_balance

def deduct_user_credit(chat_id):
    """Deducts 1 credit from user if bot is in paid mode."""
    with stats_lock:
        data = load_stats()
        if data.get("mode", "free") != "paid":
            return
            
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
            
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                current_credits = u.get("credits", data.get("default_credits", 2))
                u["credits"] = max(0, current_credits - 1)
                break
        save_stats(data)

# In-memory global variables for cooldown tracking
last_global_run_time = 0

def check_global_cooldown():
    """Checks if the global cooldown is active. Returns (allowed, remaining_seconds)."""
    global last_global_run_time
    now = time.time()
    elapsed = now - last_global_run_time
    cooldown_limit = get_cooldown_seconds()
    if elapsed >= cooldown_limit:
        return True, 0
    else:
        return False, max(1, cooldown_limit - int(elapsed))

def update_global_run_time():
    """Updates the global cooldown timer to the current time."""
    global last_global_run_time
    last_global_run_time = time.time()

def get_cooldown_seconds():
    """Returns the configured global cooldown in seconds (default: 60)."""
    with stats_lock:
        data = load_stats()
        return data.get("cooldown_seconds", 60)

def set_cooldown_seconds(val):
    """Sets the global cooldown in seconds."""
    with stats_lock:
        data = load_stats()
        data["cooldown_seconds"] = int(val)
        save_stats(data)

def get_max_concurrent_tasks():
    """Returns the configured concurrency limit (default: 15)."""
    with stats_lock:
        data = load_stats()
        return data.get("max_concurrent_tasks", 15)

def set_max_concurrent_tasks(val):
    """Sets the concurrency limit."""
    with stats_lock:
        data = load_stats()
        data["max_concurrent_tasks"] = int(val)
        save_stats(data)

def is_user_registered(chat_id):
    """Checks if a user is already registered in our database."""
    with stats_lock:
        data = load_stats()
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                return True
        return False

def find_cracked_record(mobile):
    """Searches the cracked history database for a record matching the mobile number."""
    import re
    with stats_lock:
        data = load_stats()
        clean_mobile = re.sub(r'\D', '', str(mobile))
        for record in data.get("cracked_history", []):
            rec_mobile = re.sub(r'\D', '', str(record.get("mobile", "")))
            if rec_mobile == clean_mobile:
                return record
        return None

# --- ADMIN & OWNER MANAGEMENT SYSTEM ---

def get_admin_ids():
    """Returns the list of admin IDs from stats.json (dynamic, owner-managed)."""
    with stats_lock:
        data = load_stats()
        return [int(x) for x in data.get("admin_ids", []) if str(x).isdigit()]

def add_admin(user_id):
    """Adds a user_id to the admin list. Returns True if added, False if already exists."""
    with stats_lock:
        data = load_stats()
        uid = int(user_id)
        admin_ids = [int(x) for x in data.get("admin_ids", [])]
        if uid in admin_ids:
            return False
        admin_ids.append(uid)
        data["admin_ids"] = admin_ids
        save_stats(data)
        return True

def remove_admin(user_id):
    """Removes a user_id from the admin list. Returns True if removed, False if not found."""
    with stats_lock:
        data = load_stats()
        uid = int(user_id)
        admin_ids = [int(x) for x in data.get("admin_ids", [])]
        if uid not in admin_ids:
            return False
        admin_ids.remove(uid)
        data["admin_ids"] = admin_ids
        save_stats(data)
        return True

# --- CO-OWNER MANAGEMENT ---

def get_co_owner_ids():
    """Returns the list of co-owner IDs."""
    with stats_lock:
        data = load_stats()
        return [int(x) for x in data.get("co_owner_ids", []) if str(x).isdigit()]

def add_co_owner(user_id):
    """Adds a user_id to the co-owner list. Returns True if added, False if already exists."""
    with stats_lock:
        data = load_stats()
        uid = int(user_id)
        co_owner_ids = [int(x) for x in data.get("co_owner_ids", [])]
        if uid in co_owner_ids:
            return False
        co_owner_ids.append(uid)
        data["co_owner_ids"] = co_owner_ids
        save_stats(data)
        return True

def remove_co_owner(user_id):
    """Removes a user_id from the co-owner list. Returns True if removed, False if not found."""
    with stats_lock:
        data = load_stats()
        uid = int(user_id)
        co_owner_ids = [int(x) for x in data.get("co_owner_ids", [])]
        if uid not in co_owner_ids:
            return False
        co_owner_ids.remove(uid)
        data["co_owner_ids"] = co_owner_ids
        save_stats(data)
        return True

def get_developer_username():
    """Returns the current developer username from stats.json."""
    with stats_lock:
        data = load_stats()
        return data.get("developer_username", "Igoan")

def set_developer_username(username):
    """Sets the developer username (owner-only action)."""
    with stats_lock:
        data = load_stats()
        data["developer_username"] = username.lstrip('@').strip()
        save_stats(data)

def get_developer2_username():
    """Returns the current developer 2 username from stats.json."""
    with stats_lock:
        data = load_stats()
        return data.get("developer2_username", "")

def set_developer2_username(username):
    """Sets the developer 2 username (owner-only action)."""
    with stats_lock:
        data = load_stats()
        data["developer2_username"] = username.lstrip('@').strip()
        save_stats(data)

def get_required_channels():
    """Returns the owner-managed required channels list from stats.json."""
    data = load_stats()
    return data.get("required_channels", [])

def set_required_channels(channels):
    """Replaces the full required channels list (owner-only)."""
    with stats_lock:
        data = load_stats()
        data["required_channels"] = channels
        save_stats(data)

def add_required_channel(channel_dict):
    """Appends a channel dict {id, link, name} to required_channels."""
    with stats_lock:
        data = load_stats()
        channels = data.get("required_channels", [])
        channels.append(channel_dict)
        data["required_channels"] = channels
        save_stats(data)

# --- ACCESS KEY MANAGEMENT ---

def _gen_key_code():
    """Generates a random 10-character uppercase access key code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=10))

def create_access_key(key_type, days, custom_code=None):
    """
    Creates a new access key.
    key_type: 'unlimited' or 'daily'
    days: integer number of days until expiry
    custom_code: optional custom key string; auto-generated if None
    Returns the key code string.
    """
    with stats_lock:
        data = load_stats()
        keys = data.get("access_keys", {})
        
        code = custom_code.upper().strip() if custom_code else _gen_key_code()
        while code in keys and not custom_code:
            code = _gen_key_code()
        
        created = datetime.date.today().isoformat()
        expires = (datetime.date.today() + datetime.timedelta(days=int(days))).isoformat()
        
        keys[code] = {
            "type": key_type,
            "created": created,
            "expires_date": expires,
            "days": int(days),
            "redeemed_by": []
        }
        data["access_keys"] = keys
        save_stats(data)
        return code

def get_access_keys():
    """Returns the access_keys dict from stats.json."""
    with stats_lock:
        data = load_stats()
        return data.get("access_keys", {})

def delete_access_key(code):
    """Deletes an access key by code. Returns True if deleted, False if not found."""
    with stats_lock:
        data = load_stats()
        keys = data.get("access_keys", {})
        code = code.upper().strip()
        if code not in keys:
            return False
        del keys[code]
        data["access_keys"] = keys
        save_stats(data)
        return True

def redeem_access_key(chat_id, code):
    """
    Attempts to redeem an access key for a user.
    Returns (ok: bool, message: str, key_type: str|None)
    """
    with stats_lock:
        data = load_stats()
        code = code.upper().strip()
        keys = data.get("access_keys", {})
        
        if code not in keys:
            return False, "❌ Invalid key. Please check and try again.", None
        
        key = keys[code]
        today = datetime.date.today().isoformat()
        
        if key.get("expires_date", "") < today:
            return False, "❌ This access key has expired.", None
        
        try:
            uid = int(chat_id)
        except:
            uid = chat_id
        
        redeemed_by = key.get("redeemed_by", [])
        if uid in redeemed_by:
            return False, "⚠️ You have already redeemed this key.", None
        
        redeemed_by.append(uid)
        key["redeemed_by"] = redeemed_by
        data["access_keys"] = keys
        
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == uid:
                u["access_key_code"] = code
                u["access_key_type"] = key["type"]
                u["access_key_expires"] = key["expires_date"]
                u["access_key_refresh_date"] = ""
                break
        else:
            data["users"].append({
                "chat_id": uid,
                "first_name": "N/A",
                "username": "N/A",
                "joined": today,
                "credits": data.get("default_credits", 2),
                "access_key_code": code,
                "access_key_type": key["type"],
                "access_key_expires": key["expires_date"],
                "access_key_refresh_date": ""
            })
        
        save_stats(data)
        return True, "✅ Key redeemed successfully!", key["type"]

def get_user_key_info(chat_id):
    """
    Returns active key info for a user or None.
    Result: {'type': 'unlimited'|'daily', 'expires': 'YYYY-MM-DD'} or None
    """
    with stats_lock:
        data = load_stats()
        try:
            uid = int(chat_id)
        except:
            uid = chat_id
        
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == uid:
                code = u.get("access_key_code")
                ktype = u.get("access_key_type")
                expires = u.get("access_key_expires", "")
                if code and ktype and expires:
                    today = datetime.date.today().isoformat()
                    if expires >= today:
                        return {"type": ktype, "expires": expires, "code": code}
                return None
        return None

def maybe_refresh_daily_key_credits(chat_id):
    """
    If user has a valid 'daily' access key and hasn't had credits refreshed today,
    reset their credits to default_credits. Returns True if refreshed.
    """
    with stats_lock:
        data = load_stats()
        try:
            uid = int(chat_id)
        except:
            uid = chat_id
        
        today = datetime.date.today().isoformat()
        
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == uid:
                ktype = u.get("access_key_type")
                expires = u.get("access_key_expires", "")
                last_refresh = u.get("access_key_refresh_date", "")
                
                if ktype == "daily" and expires >= today and last_refresh != today:
                    u["credits"] = data.get("default_credits", 2)
                    u["access_key_refresh_date"] = today
                    save_stats(data)
                    return True
                return False
        return False

# --- USER APPROVAL SYSTEM ---

def get_approval_enabled():
    """Returns whether the user approval gate is enabled."""
    with stats_lock:
        data = load_stats()
        return bool(data.get("user_approval_enabled", False))

def set_approval_enabled(val):
    """Enables or disables the user approval gate."""
    with stats_lock:
        data = load_stats()
        data["user_approval_enabled"] = bool(val)
        save_stats(data)

def is_user_approved(chat_id):
    """Returns True if the user is approved (or approval is disabled)."""
    with stats_lock:
        data = load_stats()
        if not data.get("user_approval_enabled", False):
            return True
        try:
            uid = int(chat_id)
        except:
            uid = chat_id
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == uid:
                return bool(u.get("approved", False))
        return False

def is_user_rejected(chat_id):
    """Returns True if the user was explicitly rejected."""
    with stats_lock:
        data = load_stats()
        try:
            uid = int(chat_id)
        except:
            uid = chat_id
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == uid:
                return bool(u.get("rejected", False))
        return False

def is_approval_requested(chat_id):
    """Returns True if the user already submitted an approval request."""
    with stats_lock:
        data = load_stats()
        try:
            uid = int(chat_id)
        except:
            uid = chat_id
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == uid:
                return bool(u.get("approval_requested", False))
        return False

def set_approval_requested(chat_id):
    """Marks that the user has already sent an approval request."""
    with stats_lock:
        data = load_stats()
        try:
            uid = int(chat_id)
        except:
            uid = chat_id
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == uid:
                u["approval_requested"] = True
                save_stats(data)
                return

def approve_user(chat_id):
    """Marks a user as approved. Returns True if updated."""
    with stats_lock:
        data = load_stats()
        try:
            uid = int(chat_id)
        except:
            uid = chat_id
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == uid:
                u["approved"] = True
                u["rejected"] = False
                save_stats(data)
                return True
        return False

def reject_user(chat_id):
    """Marks a user as rejected. Returns True if updated."""
    with stats_lock:
        data = load_stats()
        try:
            uid = int(chat_id)
        except:
            uid = chat_id
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == uid:
                u["approved"] = False
                u["rejected"] = True
                save_stats(data)
                return True
        return False

def get_pending_users():
    """Returns list of user dicts waiting for approval (requested but not yet approved/rejected)."""
    with stats_lock:
        data = load_stats()
        pending = []
        for u in data.get("users", []):
            if isinstance(u, dict):
                if u.get("approval_requested") and not u.get("approved") and not u.get("rejected"):
                    pending.append(u)
        return pending

# --- SUPPORT USERNAME MANAGEMENT ---

def get_support_usernames():
    """Returns (support1_username, support2_username) tuple. Empty string if not set."""
    with stats_lock:
        data = load_stats()
        return (
            data.get("support1_username", "").strip(),
            data.get("support2_username", "").strip()
        )

def set_support_username(n, username):
    """Sets support1 (n=1) or support2 (n=2) username. Pass empty string to clear."""
    with stats_lock:
        data = load_stats()
        key = f"support{n}_username"
        data[key] = username.lstrip('@').strip()
        save_stats(data)

# --- BAN MANAGEMENT ---

def is_banned(chat_id):
    """Returns True if the user is banned from the bot."""
    with stats_lock:
        data = load_stats()
        return int(chat_id) in [int(x) for x in data.get("banned_users", [])]

def ban_user(chat_id):
    """Bans a user. Returns True if newly banned, False if already banned."""
    with stats_lock:
        data = load_stats()
        if "banned_users" not in data:
            data["banned_users"] = []
        uid = int(chat_id)
        if uid not in [int(x) for x in data["banned_users"]]:
            data["banned_users"].append(uid)
            save_stats(data)
            return True
        return False

def unban_user(chat_id):
    """Unbans a user. Returns True if removed, False if wasn't banned."""
    with stats_lock:
        data = load_stats()
        uid = int(chat_id)
        banned = [int(x) for x in data.get("banned_users", [])]
        if uid in banned:
            data["banned_users"] = [x for x in data["banned_users"] if int(x) != uid]
            save_stats(data)
            return True
        return False

def get_banned_users():
    """Returns list of banned user IDs."""
    with stats_lock:
        data = load_stats()
        return list(data.get("banned_users", []))

# --- CHANNEL JOIN TRACKING ---

def has_seen_join_prompt(user_id, channel_id):
    """Returns True if this user has already been shown the join prompt for this channel."""
    with stats_lock:
        data = load_stats()
        store = data.get("join_prompt_seen", {})
        return str(channel_id) in store.get(str(user_id), [])

def mark_seen_join_prompt(user_id, channel_id):
    """Records that the user has been shown the join prompt for a channel."""
    with stats_lock:
        data = load_stats()
        if "join_prompt_seen" not in data:
            data["join_prompt_seen"] = {}
        uid = str(user_id)
        cid = str(channel_id)
        if uid not in data["join_prompt_seen"]:
            data["join_prompt_seen"][uid] = []
        if cid not in data["join_prompt_seen"][uid]:
            data["join_prompt_seen"][uid].append(cid)
            save_stats(data)

def has_join_request(user_id, channel_id):
    """Returns True if the bot has received a join request from this user for this channel."""
    with stats_lock:
        data = load_stats()
        store = data.get("join_requests", {})
        return str(channel_id) in store.get(str(user_id), [])

def add_join_request(user_id, channel_id):
    """Records that a user sent a join request to a channel (from chat_join_request update)."""
    with stats_lock:
        data = load_stats()
        if "join_requests" not in data:
            data["join_requests"] = {}
        uid = str(user_id)
        cid = str(channel_id)
        if uid not in data["join_requests"]:
            data["join_requests"][uid] = []
        if cid not in data["join_requests"][uid]:
            data["join_requests"][uid].append(cid)
            save_stats(data)
