@echo off
chcp 65001 > nul
echo ========================================
echo     Установка Telegram Task Bot PRO
echo ========================================
echo.

echo 📦 Проверка Python...
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ Python не установлен!
    echo 📥 Установите Python 3.8+ с сайта python.org
    pause
    exit /b 1
)

echo ✅ Python установлен

echo.
echo 📦 Установка зависимостей...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Ошибка установки зависимостей!
    pause
    exit /b 1
)

echo ✅ Зависимости установлены

echo.
echo ⚙️ Создание конфигурационного файла...
if not exist ".env" (
    echo BOT_TOKEN=8490738509:AAHR1X1Ps6M5bbsTMrkHaFSEcqGozTPnZTQ > .env
    echo ADMIN_IDS=[1609256545 , 1386994047] >> .env
    echo WEBHOOK_URL= >> .env
    echo PORT=8080 >> .env
    echo ✅ Файл .env создан
    echo.
    echo ⚠️ Отредактируйте файл .env:
    echo   1. Добавьте токен бота от @BotFather
    echo   2. Добавьте ваш Telegram ID (можно получить у @userinfobot)
    echo   3. При необходимости настройте вебхук
) else (
    echo ✅ Файл .env уже существует
)

echo.
echo 📁 Создание директорий...
mkdir screenshots 2>nul
mkdir cache 2>nul
mkdir events 2>nul
mkdir avatars 2>nul
mkdir reports 2>nul

echo.
echo 🚀 Создание файлов запуска...

echo @echo off > run.bat
echo chcp 65001 >> run.bat
echo echo Запуск Telegram Task Bot PRO... >> run.bat
echo python main.py >> run.bat
echo pause >> run.bat

echo @echo off > run-webhook.bat
echo chcp 65001 >> run-webhook.bat
echo echo Запуск бота в режиме вебхука... >> run-webhook.bat
echo echo Перед запуском настройте WEBHOOK_URL в .env >> run-webhook.bat
echo python main.py >> run-webhook.bat
echo pause >> run-webhook.bat

echo.
echo ========================================
echo          УСТАНОВКА ЗАВЕРШЕНА!
echo ========================================
echo.
echo 🚀 Запустите бота одним из способов:
echo.
echo 1. Обычный режим (polling):
echo    Запустите файл: run.bat
echo.
echo 2. Вебхук режим (для сервера):
echo    а) Настройте WEBHOOK_URL в .env
echo    б) Запустите файл: run-webhook.bat
echo.
echo 👑 ВЫ АДМИНИСТРАТОР!
echo    Добавьте свой ID в ADMIN_IDS в .env
echo.
echo 📋 Функции администратора:
echo    • Проверка заданий
echo    • Управление участниками
echo    • Начисление/списание баллов
echo    • Выдача значков и эмодзи
echo    • Управление ивентами
echo.
pause