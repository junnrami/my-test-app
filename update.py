import os
import sys
import time
import shutil
import subprocess

if len(sys.argv) != 3:
    print("❌ Использование: updater.exe <новый_файл> <старый_файл>")
    sys.exit(1)

new_file = sys.argv[1]
old_file = sys.argv[2]
print("⏳ Ждём, пока завершится старая версия...")

while True:
    try:
        os.remove(old_file)
        print("🧹 Старая версия удалена.")
        break
    except PermissionError:
        print("🔒 Файл ещё занят. Пробуем снова через 1 секунду...")
        time.sleep(1)
    shutil.move(new_file, old_file)
    print("📦 Новая версия установлена.")
print("✅ Обновление завершено.")
sys.exit(0)
