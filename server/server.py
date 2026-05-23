import socket
import threading
import logging
import json
import ssl
from database import Database
from common.protocol import Message

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("logs/server.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class MessengerServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.db = Database()
        self.clients = {}       # username -> socket
        self.lock = threading.Lock()
        self.server_socket = None

    # ─── Запуск / остановка ───────────────────────────────────────────────────

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(15)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain('server.crt', 'server.key')
        self.server_socket = context.wrap_socket(self.server_socket, server_side=True)
        logging.info(f"🚀 Сервер запущен на {self.host}:{self.port}")

        try:
            while True:
                client_socket, addr = self.server_socket.accept()
                logging.info(f"Новое подключение от {addr}")
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, addr),
                    daemon=True
                )
                thread.start()
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        logging.info("🛑 Завершение — отключаем клиентов...")
        with self.lock:
            for sock in list(self.clients.values()):
                try:
                    sock.send(Message(type="shutdown", content="Сервер отключён").to_json().encode())
                    sock.close()
                except:
                    pass
            self.clients.clear()
        if self.server_socket:
            self.server_socket.close()
        logging.info("🛑 Сервер остановлен")

    # ─── Утилиты ──────────────────────────────────────────────────────────────

    def broadcast_status(self, username: str, online: bool):
        msg = Message(type="status", from_user=username, online=online)
        with self.lock:
            for user, sock in list(self.clients.items()):
                if user != username:
                    try:
                        sock.send(msg.to_json().encode())
                    except:
                        self.clients.pop(user, None)

    def send_to_group(self, group_id: int, msg: Message, exclude: str = None):
        """Рассылает сообщение всем онлайн-участникам группы."""
        members = self.db.get_group_members(group_id)
        with self.lock:
            for m in members:
                uname = m['username']
                if uname == exclude:
                    continue
                if uname in self.clients:
                    try:
                        self.clients[uname].send(msg.to_json().encode())
                    except:
                        self.clients.pop(uname, None)

    # ─── Основной обработчик ──────────────────────────────────────────────────

    def handle_client(self, client_socket, addr):
        username = None
        buffer = ""
        try:
            while True:
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                buffer += data

                pos = 0
                while pos < len(buffer):
                    try:
                        if buffer[pos] != '{':
                            pos += 1
                            continue
                        raw, consumed = json.JSONDecoder().raw_decode(buffer[pos:])
                        known = {k: v for k, v in raw.items() if k in Message.__dataclass_fields__}
                        msg = Message(**known)
                        username = self.process(client_socket, addr, username, msg)
                        pos += consumed
                    except json.JSONDecodeError:
                        break
                    except Exception as e:
                        logging.error(f"Ошибка обработки: {e}")
                        pos += 1
                buffer = buffer[pos:]

        except Exception as e:
            logging.error(f"Ошибка у {username or addr}: {e}")
        finally:
            if username:
                with self.lock:
                    self.clients.pop(username, None)
                self.broadcast_status(username, online=False)
                logging.info(f"❌ {username} отключился")
            client_socket.close()

    def process(self, sock, addr, username, msg: Message) -> str:
        """Обрабатывает одно сообщение. Возвращает (возможно обновлённый) username."""

        # ── Регистрация ──────────────────────────────────────────────────────
        if msg.type == "register":
            if self.db.register_user(msg.from_user, msg.content):
                username = msg.from_user
                with self.lock:
                    self.clients[username] = sock
                    user_list = list(self.clients.keys())
                logging.info(f"✅ {username} зарегистрирован")
                self.broadcast_status(username, online=True)
                sock.send(Message(type="register", success=True, content="Регистрация прошла успешно").to_json().encode())
                sock.send(Message(type="user_list", users=user_list).to_json().encode())
            else:
                sock.send(Message(type="register", success=False, content="Пользователь уже существует").to_json().encode())

        # ── Вход ─────────────────────────────────────────────────────────────
        elif msg.type == "login":
            if self.db.check_login(msg.from_user, msg.content):
                username = msg.from_user
                with self.lock:
                    self.clients[username] = sock
                    user_list = list(self.clients.keys())
                logging.info(f"✅ {username} вошёл")
                self.broadcast_status(username, online=True)
                sock.send(Message(type="login", success=True, content=f"Добро пожаловать, {username}!").to_json().encode())
                sock.send(Message(type="user_list", users=user_list).to_json().encode())
            else:
                sock.send(Message(type="login", success=False, content="Неверный логин или пароль").to_json().encode())

        # ── Личное сообщение ─────────────────────────────────────────────────
        elif msg.type == "message" and username:
            self.db.save_message(username, msg.to_user, msg.content)
            msg.from_user = username
            with self.lock:
                if msg.to_user in self.clients:
                    try:
                        self.clients[msg.to_user].send(msg.to_json().encode())
                    except:
                        self.clients.pop(msg.to_user, None)
            sock.send(Message(type="message_sent", content=msg.content).to_json().encode())

        # ── Групповое сообщение ──────────────────────────────────────────────
        elif msg.type == "group_message" and username:
            gid = msg.group_id
            if not self.db.is_group_member(gid, username):
                sock.send(Message(type="error", content="Вы не в этой группе").to_json().encode())
            else:
                self.db.save_group_message(gid, username, msg.content)
                broadcast = Message(
                    type="group_message",
                    group_id=gid,
                    from_user=username,
                    content=msg.content
                )
                self.send_to_group(gid, broadcast, exclude=username)
                sock.send(Message(type="message_sent", content=msg.content).to_json().encode())

        # ── История личного чата ─────────────────────────────────────────────
        elif msg.type == "history" and username:
            target = msg.to_user
            if not target:
                sock.send(Message(type="error", content="Укажите пользователя").to_json().encode())
            elif not self.db.user_exists(target):
                sock.send(Message(type="error", content=f"Пользователь '{target}' не найден").to_json().encode())
            else:
                history = self.db.get_history(username, target)
                with self.lock:
                    is_online = target in self.clients
                sock.send(Message(type="history", to_user=target, history=history, online=is_online).to_json().encode())

        # ── История группового чата ──────────────────────────────────────────
        elif msg.type == "group_history" and username:
            gid = msg.group_id
            if not self.db.is_group_member(gid, username):
                sock.send(Message(type="error", content="Вы не участник этой группы").to_json().encode())
            else:
                group = self.db.get_group(gid)
                history = self.db.get_group_history(gid)
                sock.send(Message(
                    type="group_history",
                    group_id=gid,
                    group_name=group['name'],
                    group_members=[m['username'] for m in group['members']],
                    history=history
                ).to_json().encode())

        # ── Список личных чатов ──────────────────────────────────────────────
        elif msg.type == "chat_list" and username:
            chats = self.db.get_user_chats(username)
            sock.send(Message(type="chat_list", users=chats).to_json().encode())

        # ── Список групп ─────────────────────────────────────────────────────
        elif msg.type == "group_list" and username:
            groups = self.db.get_user_groups(username)
            sock.send(Message(type="group_list", groups=groups).to_json().encode())

        # ── Создание группы ──────────────────────────────────────────────────
        elif msg.type == "create_group" and username:
            name = msg.group_name
            members = msg.group_members or []
            if not name:
                sock.send(Message(type="error", content="Укажите название группы").to_json().encode())
            else:
                # Проверяем что все участники существуют
                invalid = [m for m in members if not self.db.user_exists(m)]
                if invalid:
                    sock.send(Message(type="error", content=f"Не найдены: {', '.join(invalid)}").to_json().encode())
                else:
                    gid = self.db.create_group(name, username, members)
                    group = self.db.get_group(gid)
                    logging.info(f"📢 {username} создал группу '{name}' (id={gid})")
                    # Уведомляем всех участников
                    notify = Message(
                        type="group_invite",
                        group_id=gid,
                        group_name=name,
                        from_user=username,
                        group_members=[m['username'] for m in group['members']]
                    )
                    self.send_to_group(gid, notify, exclude=username)
                    sock.send(Message(
                        type="group_created",
                        group_id=gid,
                        group_name=name,
                        group_members=[m['username'] for m in group['members']]
                    ).to_json().encode())

        # ── Добавить участника ───────────────────────────────────────────────
        elif msg.type == "group_add" and username:
            gid = msg.group_id
            target = msg.target_user
            if not self.db.is_group_member(gid, username):
                sock.send(Message(type="error", content="Вы не в этой группе").to_json().encode())
            elif not self.db.user_exists(target):
                sock.send(Message(type="error", content=f"Пользователь '{target}' не найден").to_json().encode())
            elif self.db.is_group_member(gid, target):
                sock.send(Message(type="error", content=f"{target} уже в группе").to_json().encode())
            else:
                self.db.add_group_member(gid, target)
                group = self.db.get_group(gid)
                notify = Message(
                    type="group_update",
                    group_id=gid,
                    group_name=group['name'],
                    group_members=[m['username'] for m in group['members']],
                    content=f"{username} добавил {target}"
                )
                self.send_to_group(gid, notify, exclude=target)
                # Приглашение новому участнику
                with self.lock:
                    if target in self.clients:
                        self.clients[target].send(Message(
                            type="group_invite",
                            group_id=gid,
                            group_name=group['name'],
                            from_user=username,
                            group_members=[m['username'] for m in group['members']]
                        ).to_json().encode())

        # ── Кикнуть участника ────────────────────────────────────────────────
        elif msg.type == "group_kick" and username:
            gid = msg.group_id
            target = msg.target_user
            if not self.db.is_group_admin(gid, username):
                sock.send(Message(type="error", content="Только администратор может кикать").to_json().encode())
            elif not self.db.is_group_member(gid, target):
                sock.send(Message(type="error", content=f"{target} не в группе").to_json().encode())
            elif target == username:
                sock.send(Message(type="error", content="Нельзя кикнуть себя").to_json().encode())
            else:
                # Уведомляем до удаления чтобы target ещё был в списке
                group = self.db.get_group(gid)
                notify = Message(
                    type="group_update",
                    group_id=gid,
                    group_name=group['name'],
                    content=f"{target} исключён из группы"
                )
                self.send_to_group(gid, notify)
                self.db.kick_group_member(gid, target)
                # Уведомляем кикнутого отдельно
                with self.lock:
                    if target in self.clients:
                        self.clients[target].send(Message(
                            type="group_kicked",
                            group_id=gid,
                            group_name=group['name'],
                            content=f"Вы исключены из группы '{group['name']}'"
                        ).to_json().encode())

        # ── Переименовать группу ─────────────────────────────────────────────
        elif msg.type == "group_rename" and username:
            gid = msg.group_id
            new_name = msg.group_name
            if not self.db.is_group_admin(gid, username):
                sock.send(Message(type="error", content="Только администратор может переименовывать").to_json().encode())
            elif not new_name:
                sock.send(Message(type="error", content="Укажите новое название").to_json().encode())
            else:
                self.db.rename_group(gid, new_name)
                notify = Message(
                    type="group_update",
                    group_id=gid,
                    group_name=new_name,
                    content=f"{username} переименовал группу в '{new_name}'"
                )
                self.send_to_group(gid, notify)

        # ── Кто онлайн ───────────────────────────────────────────────────────
        elif msg.type == "user_list":
            with self.lock:
                sock.send(Message(type="user_list", users=list(self.clients.keys())).to_json().encode())

        return username


if __name__ == "__main__":
    server = MessengerServer()
    server.start()