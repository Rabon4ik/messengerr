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


### 3. Запусти сервер

Linux:
bash run_server.sh

Windows:
python server/server.py

### 4. Запусти клиент

Linux:
bash run_client.sh

Windows:
python client/client.py

Подключение к удалённому серверу:
python client/client.py 192.168.1.105 5555

---

## 📱 Android (Termux)

1. Установи Termux 

2. В Termux:
pkg update && pkg install python
pip install rich cryptography

3. Дай доступ к хранилищу:
termux-setup-storage

4. Скопируй файлы client.py и common/protocol.py на телефон
   

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


---

## 📖 Команды клиента

Главный экран:<br>
  /new <username>        — открыть чат с пользователем<br>
  /open <номер>          — открыть чат из списка<br>
  /newgroup <название>   — создать группу<br>
  /opengroup <номер>     — открыть группу<br>
  /online                — список пользователей онлайн<br>
  /refresh               — обновить список чатов<br>

Внутри чата:<br>
  /back                  — вернуться на главный экран<br>
  просто текст           — отправить сообщение<br>

Внутри группы:
  /addmember <username>  — добавить участника<br>
  /kick <username>       — исключить участника (только админ)<br>
  /rename <название>     — переименовать группу (только админ)<br>
  /back                  — вернуться на главный экран<br>



---

## 🔒 Безопасность

Весь трафик между клиентом и сервером шифруется по протоколу TLS.
Пароли хранятся в базе данных исключительно в виде SHA-256 хешей —
оригинальный пароль нигде не сохраняется.


---

## 🐛 Возможные проблемы

Ошибка "unable to open database file"
→ Убедись что рядом с сервером существует папка data/<br>



Клиент не подключается к серверу
→ Проверь что сервер запущен и доступен по указанному IP<br>
→ Убедись что порт 5555 не заблокирован брандмауэром<br>
→ Убедись что запущена только одна копия сервера<br>

База данных заблокирована ("database is locked")<br>
→ Убедись что запущена только одна копия сервера<br>


