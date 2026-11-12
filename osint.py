import requests
import re
import os
import sys
import time
from datetime import datetime
from urllib.parse import quote

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[!] Установи beautifulsoup4: pip install beautifulsoup4")
    sys.exit(1)

# ===== КОНФИГ =====
OUTPUT_DIR = r"C:\Users\User"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "osint.txt")
TIMEOUT = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

# ===== ANSI =====
if os.name == "nt":
    os.system("")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(text, color=RESET, end="\n"):
    print(f"{color}{text}{RESET}", end=end)


def write_to_file(data):
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(OUTPUT_FILE, "a", encoding="utf-8", errors="ignore") as f:
            f.write(data + "\n")
    except Exception as e:
        log(f"[!] Ошибка записи в файл: {e}", RED)


def header(title):
    title = title.replace("\n", " ")
    line = "=" * 60
    block = f"\n{line}\n  {title}\n{line}"
    log(block, CYAN)
    write_to_file(block)


def result(key, value, found=True):
    if found:
        log(f"[+] {key}: {value}", GREEN)
        write_to_file(f"[+] {key}: {value}")
    else:
        log(f"[-] {key}: {value}", RED)
        write_to_file(f"[-] {key}: {value}")


def safe_get(url, retries=2, **kwargs):
    """GET с ретраями и обработкой любых ошибок."""
    for attempt in range(retries):
        try:
            return requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                                allow_redirects=True, **kwargs)
        except Exception:
            if attempt < retries - 1:
                time.sleep(1)
    return None


# ===== 1. ТЕЛЕФОН (парсинг htmlweb.ru) =====
def phone_lookup(phone):
    header(f"ТЕЛЕФОН: {phone}")
    digits = re.sub(r"\D", "", phone)

    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits

    if len(digits) != 11 or not digits.startswith("7"):
        result("Номер", "некорректный формат", found=False)
        return

    result("Номер", f"+{digits}")

    url = f"https://htmlweb.ru/sendsms/mnp.php?tel={digits}"
    log(f"{YELLOW}[*] Запрашиваю MNP-данные с htmlweb.ru...{RESET}")
    r = safe_get(url)

    if not r or not r.ok:
        result("MNP API", "недоступен или ошибка запроса", found=False)
    else:
        try:
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text("\n", strip=True)
            write_to_file(f"\n[DEBUG] HTMLWEB RAW:\n{text[:1500]}")

            # Регулярки с [^\n] — чтобы не захватывать переносы
            patterns = {
                "Телефонный номер": r"Телефонный номер:[ \t]*([+\d]+)",
                "Город": r"Город:[ \t]*([^\n]+)",
                "Район": r"Район:[ \t]*([^\n]+)",
                "Регион": r"Регион:[ \t]*([^\n]+)",
                "Округ": r"Округ:[ \t]*([^\n]+)",
                "Страна": r"Страна:[ \t]*([^\n]+)",
                "Оператор": r"Оператор:[ \t]*([^\n]+)",
                "MCC": r"MCC код оператора:[ \t]*([\dA-Z]+)",
                "MNC": r"MNC код оператора:[ \t]*([\dA-Z]+)",
                "PLMN": r"PLMN:[ \t]*([\dA-Z]+)",
                "MVNO": r"Виртуальный оператор[^\n]*:[ \t]*([^\n]+)",
            }

            found_any = False
            for field, pattern in patterns.items():
                m = re.search(pattern, text, re.IGNORECASE)
                if m and m.group(1).strip():
                    result(field, m.group(1).strip())
                    found_any = True

            lower = text.lower()
            if "мобильный телефон" in lower:
                result("Тип", "📱 Мобильный")
            elif "городской телефон" in lower:
                result("Тип", "☎️ Городской")

            if not found_any:
                result("MNP", "данные не спарсились (возможно, изменилась вёрстка)", found=False)
        except Exception as e:
            result("MNP парсинг", f"ошибка: {e}", found=False)

    # Ссылки
    result("WhatsApp", f"https://wa.me/{digits}")
    result("Telegram", f"https://t.me/+{digits}")
    result("Viber", f"viber://chat?number=%2B{digits}")
    result("Truecaller", f"https://www.truecaller.com/search/ru/{digits}")
    result("GetContact", f"https://getcontact.com/ru/search/{digits}")
    result("NumBuster", f"https://numbuster.com/ru/search?phone={digits}")


# ===== 2. НИК =====
def username_lookup(username):
    header(f"НИКНЕЙМ: {username}")
    username = username.strip().lstrip("@").lower()

    sites = {
        "GitHub": (f"https://github.com/{username}", ["not found", "page not found"]),
        "Reddit": (f"https://www.reddit.com/user/{username}", ["not found", "page not found"]),
        "Pinterest": (f"https://www.pinterest.com/{username}/", ["not found"]),
        "Twitch": (f"https://www.twitch.tv/{username}", ["not found", "does not exist"]),
        "Steam": (f"https://steamcommunity.com/id/{username}", ["the specified profile could not be found"]),
        "Telegram": (f"https://t.me/{username}", []),
        "VK": (f"https://vk.com/{username}", ["not found", "страница не найдена"]),
        "YouTube": (f"https://www.youtube.com/@{username}", ["not found", "this page isn't available"]),
        "SoundCloud": (f"https://soundcloud.com/{username}", ["not found", "404"]),
        "Roblox": (f"https://www.roblox.com/user.aspx?username={username}", ["not found"]),
        "Xbox": (f"https://xboxgamertag.com/search/{username}", ["not found", "no results"]),
        "PSN": (f"https://psnprofiles.com/{username}", ["not found", "profile not found"]),
        "Medium": (f"https://medium.com/@{username}", ["not found", "404"]),
        "Flickr": (f"https://www.flickr.com/people/{username}", ["not found", "404"]),
        "Tumblr": (f"https://{username}.tumblr.com", ["not found", "404", "there's nothing here"]),
        "Patreon": (f"https://www.patreon.com/{username}", ["not found", "404"]),
    }

    found_count = 0
    site_list = list(sites.items())
    for i, (site, (url, nf_markers)) in enumerate(site_list):
        r = safe_get(url)
        if r is None:
            result(site, "ошибка запроса", found=False)
        elif r.status_code == 200:
            lower = r.text.lower()
            if any(m in lower for m in nf_markers):
                result(site, "не найден", found=False)
            else:
                result(site, url)
                found_count += 1
        elif r.status_code in (404, 410):
            result(site, "не найден", found=False)
        else:
            result(site, f"HTTP {r.status_code}", found=False)

        if i < len(site_list) - 1:
            time.sleep(0.8)

    write_to_file(f"\n[+] Найдено: {found_count} из {len(sites)}")
    write_to_file("\n--- Ручная проверка ---")
    result("WhatsMyName", f"https://whatsmyname.app/?q={username}")
    result("InstantUsername", f"https://instantusername.com/#/@{username}")
    result("Sherlock (CLI)", f"pip install sherlock-project && sherlock {username}")


# ===== 3. EMAIL =====
def email_lookup(email):
    header(f"EMAIL: {email}")
    email = email.strip().lower()

    if not re.match(r"^[\w\.\-\+]+@[\w\.\-]+\.\w+$", email):
        result("Email", "некорректный формат", found=False)
        return

    result("Email", email)
    domain = email.split("@")[1]
    result("Домен", domain)

    r = safe_get(f"https://dns.google/resolve?name={domain}&type=MX")
    try:
        if r and r.ok and r.json().get("Answer"):
            result("MX-записи", "существуют (почта принимает письма)")
        else:
            result("MX-записи", "не найдены", found=False)
    except Exception:
        result("MX-записи", "ошибка парсинга ответа", found=False)

    result("HaveIBeenPwned", f"https://haveibeenpwned.com/account/{email}")
    result("DeHashed", f"https://dehashed.com/search?query={email}")
    result("LeakCheck", "https://leakcheck.io/")
    result("Firefox Monitor", "https://monitor.firefox.com/")
    result("EmailRep", f"https://emailrep.io/{email}")
    result("Hunter.io", "https://hunter.io/email-verifier")
    result("Gravatar", f"https://gravatar.com/{email}")
    result("Google", f"https://www.google.com/search?q=%22{quote(email)}%22")
    result("Yandex", f"https://yandex.ru/search/?text=%22{quote(email)}%22")


# ===== 4. ИМЯ =====
def name_lookup(name):
    header(f"ИМЯ: {name}")
    result("Имя", name)
    q = quote(name)
    qp = quote(name.replace(" ", "+"))
    result("Google", f"https://www.google.com/search?q=%22{q}%22")
    result("Yandex", f"https://yandex.ru/search/?text={q}")
    result("VK люди", f"https://vk.com/people?act=search&q={qp}")
    result("OK люди", f"https://ok.ru/search?st.query={qp}")
    result("Facebook", f"https://www.facebook.com/search/people/?q={qp}")
    result("LinkedIn", f"https://www.linkedin.com/search/results/all/?keywords={qp}")


# ===== 5. ДОП. РЕСУРСЫ =====
def extra_tools(query):
    if not query:
        return
    header(f"ДОПОЛНИТЕЛЬНО: {query}")
    q = quote(query)
    result("IntelligenceX", f"https://intelx.io/?s={q}")
    result("Pastebin dumps", f"https://psbdmp.ws/api/search/{q}")
    result("Etherscan", f"https://etherscan.io/search?q={q}")
    result("Bing", f"https://www.bing.com/search?q={q}")
    result("DuckDuckGo", f"https://duckduckgo.com/?q={q}")
    result("Ahmia (Tor)", f"http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={q}")


# ===== БАННЕР =====
def banner():
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")

    log(BOLD + MAGENTA + "#########################################################")
    log("#                                                       #")
    log("#               OSINT RIK AND MORTY                     #")
    log("#                                                       #")
    log("#########################################################" + RESET)
    log("")
    log(f"{YELLOW}Файл сохранения: {OUTPUT_FILE}{RESET}\n")


def menu():
    log(BOLD + CYAN + "Выбери тип поиска:" + RESET)
    log(f"  {GREEN}1{RESET} — по номеру (+7...)")
    log(f"  {GREEN}2{RESET} — по нику")
    log(f"  {GREEN}3{RESET} — по email")
    log(f"  {GREEN}4{RESET} — по имени/строке")
    log(f"  {GREEN}0{RESET} — выход\n")


# ===== ГЛАВНОЕ =====
def main():
    banner()
    menu()

    choice = input(f"{YELLOW}>> {RESET}").strip()

    if choice == "0":
        log(RED + "Выход." + RESET)
        return

    if choice not in ("1", "2", "3", "4"):
        log(RED + "Неверный выбор." + RESET)
        input("Enter для выхода...")
        return

    prompts = {
        "1": "Введи номер (+7XXXXXXXXXX): ",
        "2": "Введи ник: ",
        "3": "Введи email: ",
        "4": "Введи имя/строку: ",
    }
    target = input(f"{GREEN}{prompts[choice]}{RESET}").strip()

    if not target:
        log(RED + "Пустой ввод." + RESET)
        input("Enter для выхода...")
        return

    write_to_file("\n\n" + "#" * 60)
    write_to_file(f"# OSINT REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    write_to_file(f"# Target: {target}")
    write_to_file("#" * 60)

    try:
        if choice == "1":
            phone_lookup(target)
        elif choice == "2":
            username_lookup(target)
        elif choice == "3":
            email_lookup(target)
        elif choice == "4":
            name_lookup(target)

        extra_tools(target)
    except KeyboardInterrupt:
        log(RED + "\nПрервано." + RESET)
    except Exception as e:
        log(RED + f"Ошибка: {e}" + RESET)

    write_to_file("\n" + "=" * 60)
    write_to_file(f"Готово: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    write_to_file("=" * 60)

    log(f"\n{GREEN}{BOLD}[✓] Отчёт сохранён: {OUTPUT_FILE}{RESET}")

    try:
        if os.path.exists(OUTPUT_FILE):
            os.startfile(OUTPUT_FILE)
    except Exception:
        pass

    input(f"\n{YELLOW}Нажми Enter для выхода...{RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log(RED + "\nПрервано." + RESET)
