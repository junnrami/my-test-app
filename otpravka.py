__version__ = "1.0.0"
import time
import logging
import sys
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright
import requests
import subprocess

VERSION_URL = "https://raw.githubusercontent.com/junnrami/my-test-app/main/version.json"


def check_for_updates(current_version):
    try:
        response = requests.get(VERSION_URL)
        version_data = response.json()
        latest = version_data["latest_version"]
        changelog = version_data.get("changelog", "")
        download_url = version_data.get("download_url", "")

        if latest != current_version:
            print(f"🔔 Доступна новая версия: {latest}")
            print(f"📋 Что нового:\n{changelog}")
            choice = input("Хотите обновиться? [y/n]: ").strip().lower()
            if choice == "y":
                try:
                    new_filename = "otpravka_new.exe"
                    print("⬇️ Скачиваем новую версию...")

                    r = requests.get(download_url, stream=True)
                    r.raise_for_status()
                    with open(new_filename, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                    print("✅ Скачано. Запускаем обновляшку...")

                    current_exe = Path(sys.executable)
                    updater_path = current_exe.parent / "updater.exe"

                    subprocess.Popen([str(updater_path), new_filename, current_exe.name])

                    print("🛑 Завершаем текущую версию...")
                    sys.exit(0)

                except Exception as e:
                    print(f"❌ Ошибка при обновлении: {e}")
                    input("Нажмите Enter для выхода...")
                    sys.exit(1)
            else:
                print("Продолжаем работу в текущей версии.")
        else:
            print("✅ У вас самая свежая версия.")

    except Exception as e:
        print(f"⚠️ Не удалось проверить обновления: {e}")


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("run.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()


def get_base_path() -> Path:
    """Путь к папке с исполняемым файлом или скриптом."""
    if getattr(sys, 'frozen', False):
        # Запуск из PyInstaller exe
        return Path(sys.executable).parent
    else:
        # Запуск из скрипта .py
        return Path(__file__).parent


def find_chromium_path():
    user_home = Path.home()
    base_path = user_home / "AppData" / "Local" / "ms-playwright"
    if not base_path.exists():
        return None
    for item in base_path.iterdir():
        if item.name.startswith("chromium"):
            exe_path = item / "chrome-win" / "chrome.exe"
            if exe_path.exists():
                return str(exe_path)
    return None


def run(playwright: Playwright, url: str, login: str, password: str, codes_file: Path, chromium_path: str) -> None:
    browser = playwright.chromium.launch(executable_path=chromium_path, headless=False)
    context = browser.new_context()
    page = context.new_page()

    logger.info(f"Открываем стенд: {url}")
    page.goto(url)
    time.sleep(2)

    logger.info("Авторизация...")
    page.get_by_role("textbox", name="Логин*").fill(login)
    page.get_by_role("textbox", name="Пароль*").fill(password)
    page.get_by_text("Войти в систему").click()
    time.sleep(2)

    page.get_by_text("Интеграция").nth(1).click()
    time.sleep(1)
    page.get_by_role("link", name="Справочники НСИ").click()
    time.sleep(2)

    codes = read_codes_from_file(codes_file)

    for code in codes:
        check_catalog_by_code(page, code)
        time.sleep(1)

    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("link", name="Отправить все объекты в НСИ по выбранным каталогам").click()

    max_wait = 60 * 120  # максимум 120 минут
    interval = 240  # проверка раз в 4 минуты
    waited = 0
    while waited < max_wait:
        try:
            page.get_by_text("Закрыть", exact=True).wait_for(state="visible", timeout=5000)
            break
        except Exception:
            logger.info(f"Кнопка 'Закрыть' ещё не появилась. Ждем {interval} секунд...")
            time.sleep(interval)
            waited += interval
    else:
        logger.warning("⚠️ Таймаут ожидания кнопки 'Закрыть'. Возможна зависшая отправка.")

    page.get_by_text("Закрыть", exact=True).click()
    time.sleep(1)

    context.close()
    browser.close()
    logger.info("Браузер закрыт.")


def check_catalog_by_code(page, code: str):
    checkbox = page.locator(
        f"xpath=//tr[td[normalize-space(text())='{code}']]//input[@type='checkbox']"
    )

    if checkbox.count() == 0:
        logger.warning(f"⚠️ Справочник с кодом '{code}' не найден.")
    else:
        checkbox.first.check()
        logger.info(f"✅ Справочник с кодом '{code}' отмечен.")


def read_codes_from_file(filepath: Path) -> list[str]:
    with open(filepath, encoding="utf-8") as f:
        codes = [line.strip() for line in f if line.strip()]
    logger.info(f"Прочитано {len(codes)} кодов справочников из файла {filepath.name}")
    return codes


def choose_file_interactive(folder: Path, extensions=None, prompt: str = "файл") -> Path | None:
    files = [f for f in folder.iterdir() if f.is_file()]
    if extensions is not None:
        extensions = set(e.lower() for e in extensions)
        files = [f for f in files if f.suffix.lower() in extensions]
    if not files:
        logger.error(f"В папке нет подходящих {prompt}.")
        return None

    print(f"\n{prompt}:")
    for i, file in enumerate(files, 1):
        print(f"{i}. {file.name}")

    while True:
        choice = input(f"Введите номер файла для выбора: ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(files):
                return files[idx - 1]
        print("Некорректный ввод, попробуйте снова.")


def read_stands_from_file(filepath: Path) -> list[dict]:
    stands = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 4:
                logger.warning(f"Строка пропущена (ожидалось 4 значения, получено {len(parts)}): {line}")
                continue
            name, url, login, password = parts
            stands.append({"name": name, "url": url, "login": login, "password": password})
    logger.info(f"Прочитано {len(stands)} стендов из файла {filepath.name}")
    return stands


def main():
    check_for_updates(__version__)
    base_folder = get_base_path()

    codes_file = choose_file_interactive(base_folder, extensions={".txt", ".csv"}, prompt="Выберите файл, который содержит в себе список справочников")
    if codes_file is None:
        logger.error("Нет выбранного файла со списком кодов. Выход.")
        sys.exit(1)

    stands_file = choose_file_interactive(base_folder, extensions={".txt", ".csv"}, prompt="Выберите файл, который содержит в себе список стендов")
    if stands_file is None:
        logger.error("Нет выбранного файла со списком стендов. Выход.")
        sys.exit(1)

    stands = read_stands_from_file(stands_file)
    if not stands:
        logger.error("Список стендов пустой. Выход.")
        sys.exit(1)

    chromium_path = find_chromium_path()
    if chromium_path is None:
        print("\nОшибка: Chromium-браузер Playwright не найден.")
        print("Пожалуйста, установите браузеры Playwright, запустив в командной строке:")
        print("  playwright install\n")
        sys.exit(1)

    with sync_playwright() as playwright:
        for stand in stands:
            logger.info(f"\nНачалась отправка справочников со стенда '{stand['name']}' ({stand['url']})")
            start_time = time.time()

            try:
                run(playwright, stand['url'], stand['login'], stand['password'], codes_file, chromium_path)
            except Exception as e:
                logger.error(f"Ошибка при работе со стендом '{stand['name']}' ({stand['url']}): {e}")
                logger.info("Продолжаем со следующим стендом...")
                continue

            elapsed = time.time() - start_time
            logger.info(f"Закончена отправка справочников со стенда '{stand['name']}'. Потребовалось {elapsed:.1f} секунд.")


if __name__ == "__main__":
    main()
