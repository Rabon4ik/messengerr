# 💬 Messenger — клиент-серверный мессенджер на Python

Многофункциональный терминальный мессенджер с поддержкой личных и групповых
чатов, шифрованием TLS и хранением истории переписки.

---

## 📋 Возможности

- Регистрация и вход с хешированием паролей (SHA-256)
- Личные чаты с историей переписки и статусом онлайн/офлайн
- Групповые чаты с управлением участниками
- Права администратора группы (кик, переименование, добавление)
- Шифрование трафика (TLS)
- Уведомления о новых сообщениях в фоновых чатах
- Хранение истории между сессиями (SQLite)
- Работает на Linux, Windows и Android (Termux)

---

## ⚙️ Требования

- Python 3.10 и выше
- pip

Зависимости устанавливаются командой:
pip install -r requirements.txt

---

## 🚀 Быстрый старт

### 1. Клонируй репозиторий

git clone https://github.com/Rabon4ik/messengerr.git
cd messengerr

### 2. Установи зависимости

pip install -r requirements.txt

### 3. Сгенерируй TLS-сертификат (один раз)

python -c "
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime, os

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
cert = (x509.CertificateBuilder()
    .subject_name(name).issuer_name(name)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
    .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
    .sign(key, hashes.SHA256()))
open('server.key','wb').write(key.private_bytes(serialization.Encoding.PEM,
    serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
open('server.crt','wb').write(cert.public_bytes(serialization.Encoding.PEM))
print('Сертификат создан')
"

### 4. Запусти сервер

Linux:
bash run_server.sh

Windows:
python server/server.py

### 5. Запусти клиент

Linux:
bash run_client.sh

Windows:
python client/client.py

Подключение к удалённому серверу:
python client/client.py 192.168.1.105 5555

---

## 📱 Android (Termux)

1. Установи Termux из F-Droid (не из Play Market)

2. В Termux:
pkg update && pkg install python
pip install rich cryptography

3. Дай доступ к хранилищу:
termux-setup-storage

4. Скопируй файлы client.py и common/protocol.py на телефон
   (через Telegram или любым удобным способом)

5. Создай структуру папок:
mkdir -p ~/messenger/common
cp ~/storage/downloads/client.py ~/messenger/
cp ~/storage/downloads/protocol.py ~/messenger/common/
touch ~/messenger/common/__init__.py

6. Запусти:
cd ~/messenger
python client.py 192.168.1.105 5555

---

## 🖥️ Готовые исполняемые файлы

Если не хочешь устанавливать Python, скачай готовый бинарник
из раздела Releases на GitHub.

Linux:
./messenger-client
./messenger-server

Windows:
messenger-client.exe
messenger-server.exe

Рядом с исполняемым файлом сервера обязательно должны находиться
файлы server.key и server.crt.

---

## 📖 Команды клиента

Главный экран:
  /new <username>        — открыть чат с пользователем
  /open <номер>          — открыть чат из списка
  /newgroup <название>   — создать группу
  /opengroup <номер>     — открыть группу
  /online                — список пользователей онлайн
  /refresh               — обновить список чатов

Внутри чата:
  /back                  — вернуться на главный экран
  просто текст           — отправить сообщение

Внутри группы:
  /addmember <username>  — добавить участника
  /kick <username>       — исключить участника (только админ)
  /rename <название>     — переименовать группу (только админ)
  /back                  — вернуться на главный экран



---

## 🔒 Безопасность

Весь трафик между клиентом и сервером шифруется по протоколу TLS.
Пароли хранятся в базе данных исключительно в виде SHA-256 хешей —
оригинальный пароль нигде не сохраняется.

В текущей версии используется самоподписанный сертификат, подходящий
для локального использования и учебных целей. Для публичного сервера
рекомендуется получить сертификат от доверенного удостоверяющего центра
(например, Let's Encrypt).

---

## 🐛 Возможные проблемы

Ошибка "unable to open database file"
→ Убедись что рядом с сервером существует папка data/

Ошибка "No such file or directory" при запуске сервера
→ Убедись что рядом с сервером находятся файлы server.crt и server.key

Клиент не подключается к серверу
→ Проверь что сервер запущен и доступен по указанному IP
→ Убедись что порт 5555 не заблокирован брандмауэром

База данных заблокирована ("database is locked")
→ Убедись что запущена только одна копия сервера

---

## 📄 Лицензия

MIT License — свободное использование, модификация и распространение.
