import socket
import threading
import logging
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
        self.clients = {}          # username -> socket
        self.lock = threading.Lock()

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(15)
        
        logging.info(f"🚀 Сервер запущен на {self.host}:{self.port}")

        while True:
            client_socket, addr = server_socket.accept()
            logging.info(f"Новое подключение от {addr}")
            thread = threading.Thread(target=self.handle_client, args=(client_socket, addr), daemon=True)
            thread.start()

    def handle_client(self, client_socket, addr):
        username = None
        try:
            while True:
                data = client_socket.recv(4096).decode('utf-8').strip()
                if not data:
                    break
                
                msg = Message.from_json(data)

                # Регистрация
                if msg.type == "register":
                    if self.db.register_user(msg.from_user, msg.content):
                        client_socket.send(Message(type="register", success=True, content="Регистрация прошла успешно").to_json().encode())
                    else:
                        client_socket.send(Message(type="register", success=False, content="Пользователь уже существует").to_json().encode())

                # Логин
                elif msg.type == "login":
                    if self.db.check_login(msg.from_user, msg.content):
                        username = msg.from_user
                        with self.lock:
                            self.clients[username] = client_socket
                        logging.info(f"✅ {username} вошёл в систему")
                        
                        client_socket.send(Message(type="login", success=True, content=f"Добро пожаловать, {username}!").to_json().encode())
                        
                        # Отправляем список онлайн
                        with self.lock:
                            client_socket.send(Message(type="user_list", users=list(self.clients.keys())).to_json().encode())
                    else:
                        client_socket.send(Message(type="login", success=False, content="Неверный логин или пароль").to_json().encode())

                # Обычное сообщение
                elif msg.type == "message" and username:
                    self.db.save_message(username, msg.to_user, msg.content)
                    msg.from_user = username

                    sent = False
                    with self.lock:
                        if msg.to_user in self.clients:
                            try:
                                self.clients[msg.to_user].send(msg.to_json().encode())
                                sent = True
                            except:
                                self.clients.pop(msg.to_user, None)

                    if sent:
                        client_socket.send(Message(type="message_sent", success=True).to_json().encode())
                    else:
                        client_socket.send(Message(type="error", content=f"Пользователь {msg.to_user} не в сети").to_json().encode())

                # История сообщений
                elif msg.type == "history" and username:
                    target = msg.to_user
                    if target:
                        history = self.db.get_history(username, target)
                        client_socket.send(Message(
                            type="history",
                            to_user=target,
                            history=history
                        ).to_json().encode())
                    else:
                        client_socket.send(Message(type="error", content="Используйте: !history @username").to_json().encode())
                elif msg.type == "chat_list" and username:
                    chats = self.db.get_user_chats(username)

                    client_socket.send(
                        Message(
                            type="chat_list",
                            users=chats
                        ).to_json().encode()
                    )
                # Список онлайн
                elif msg.type == "user_list":
                    with self.lock:
                        client_socket.send(Message(type="user_list", users=list(self.clients.keys())).to_json().encode())

        except Exception as e:
            logging.error(f"Ошибка у {username or addr}: {e}")
        finally:
            if username:
                with self.lock:
                    self.clients.pop(username, None)
                logging.info(f"❌ {username} отключился")
            client_socket.close()


if __name__ == "__main__":
    server = MessengerServer(host='0.0.0.0', port=5555)
    try:
        server.start()
    except KeyboardInterrupt:
        logging.info("🛑 Сервер остановлен вручную")
    except Exception as e:
        logging.error(f"Критическая ошибка сервера: {e}")