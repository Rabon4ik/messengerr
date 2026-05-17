import socket
import threading
import sys
import time
import json
from common.protocol import Message
from rich.console import Console
from rich.prompt import Prompt

console = Console()

class MessengerClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.current_chat = None
        self.chat_list = []
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.running = True
        self.buffer = ""

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        console.print(f"[green]✅ Подключено к {self.host}:{self.port}[/]")

    def receive(self):
       
        while self.running:
            try:
                data = self.socket.recv(8192).decode('utf-8')
                if not data:
                    break

                self.buffer += data

               
                buffer = self.buffer
                pos = 0

                while pos < len(buffer):
                    try:
                        # Ищем начало объекта
                        if buffer[pos] != '{':
                            pos += 1
                            continue

                        # Пытаемся распарсить с текущей позиции
                        msg, consumed = json.JSONDecoder().raw_decode(buffer[pos:])
                        full_msg = Message(**msg)
                        self.handle_message(full_msg)

                        pos += consumed
                    except json.JSONDecodeError:
                        # Не хватает данных — выходим и ждём следующего recv
                        break
                    except Exception:
                        pos += 1

                # Очищаем обработанную часть буфера
                self.buffer = buffer[pos:]

            except Exception as e:
                if self.running:
                    console.print(f"[red]Ошибка в receive: {e}[/]")
                break

    def handle_message(self, msg: Message):
        try:
            if msg.type == "message":
                console.print(f"\n[cyan]{msg.from_user}[/] → [yellow]{msg.content}[/]")

            elif msg.type == "history":
                console.print(f"\n[bold magenta]📜 === История с {msg.to_user} ===[/]")
                
                if not msg.history or len(msg.history) == 0:
                    console.print("[dim]История переписки пуста[/]")
                else:
                    console.print(f"[dim]Записей в истории: {len(msg.history)}[/]")
                    for m in msg.history:
                        try:
                            t = str(m.get('time') or m.get('timestamp', '')).split('.')[0]  # убираем микросекунды
                            sender = m.get('from') or m.get('sender', 'Unknown')
                            content = m.get('content', '')
                            console.print(f"[{t}] [cyan]{sender}[/]: {content}")
                        except Exception as inner_e:
                            console.print(f"[red]Ошибка при выводе одной записи: {inner_e}[/]")
                            console.print(f"Данные: {m}")
                
                console.print("[bold magenta]" + "─" * 60 + "[/]")

            elif msg.type == "user_list":
                console.print("[bold green]Онлайн сейчас:[/]", msg.users or [])

            elif msg.type == "message_sent":
                console.print("[green]✓ Отправлено[/]")

            elif msg.type in ["login", "register"]:
                self._auth_ok = getattr(msg, 'success', True)
                self._auth_event.set()  # будим поток start()
                if self._auth_ok:
                    console.print(f"[bold green]✅ {msg.content}[/]")
                else:
                    console.print(f"[red]❌ {msg.content}[/]")
                return 

            elif msg.type == "error" or not getattr(msg, 'success', True):
                console.print(f"[red]❌ {msg.content}[/]")
            elif msg.type == "chat_list":
                self.chat_list = msg.users or []

                console.print("\n[bold cyan]=== Ваши чаты ===[/]")

                if not self.chat_list:
                    console.print("[dim]Чатов пока нет[/]")
                else:
                    for i, user in enumerate(self.chat_list, 1):
                        console.print(f"{i}. {user}")

                console.print("\n/new username")
                console.print("/open номер")

            else:
                console.print(f"[dim]Неизвестный тип: {msg.type}[/]")

        except Exception as e:
            console.print(f"[red]Критическая ошибка при обработке history: {e}[/]")
            import traceback
            console.print(traceback.format_exc())

    def send_message(self):
        console.print("[bold]Команды:[/]")
        console.print("   /new username")
        console.print("   /open номер")
        console.print("   /back")
        console.print("   /online")

        while self.running:
            try:
                text = input().strip()
                if not text:
                    continue
                if text == "/back":
                    self.current_chat = None
                    console.print("\n[yellow]Вы вышли из чата[/]")
                    continue
              
                if text.lower().startswith("!history"):
                    parts = text.split(maxsplit=1)
                    if len(parts) < 2 or not parts[1].startswith("@"):
                        console.print("[red]Использование: !history @username[/]")
                        continue
                    target = parts[1][1:]
                    self.socket.send(Message(type="history", to_user=target).to_json().encode())
                    continue

                if text.lower() in ["!online", "/online"]:
                    self.socket.send(Message(type="user_list").to_json().encode())
                    continue
                if text.startswith("/new"):
                    parts = text.split()

                    if len(parts) < 2:
                        continue

                    self.current_chat = parts[1]

                    if self.current_chat not in self.chat_list:
                        self.chat_list.append(self.current_chat)

                    console.print(f"\n[bold green]Новый чат: {self.current_chat}[/]")

                    self.socket.send(
                        Message(
                            type="history",
                            to_user=self.current_chat
                        ).to_json().encode()
                    )

                    continue
                if text.startswith("/open"):
                    parts = text.split()

                    if len(parts) < 2:
                        continue

                    idx = int(parts[1]) - 1

                    if idx < 0 or idx >= len(self.chat_list):
                        continue

                    self.current_chat = self.chat_list[idx]

                    self.socket.send(
                        Message(
                            type="history",
                            to_user=self.current_chat
                        ).to_json().encode()
                    )

                    console.print(f"\n[bold green]Чат с {self.current_chat}[/]")
                    continue
                if self.current_chat:
                    msg = Message(
                        type="message",
                        to_user=self.current_chat,
                        content=text
                    )

                    self.socket.send(msg.to_json().encode())
                else:
                    console.print("[red]Сначала откройте чат[/]")
                    continue

            except Exception as e:
                console.print(f"[red]Ошибка отправки: {e}[/]")
                break

    def start(self):
        self.connect()
        self._auth_event = threading.Event()
        self._auth_ok = False
        self._pending_username = None

        threading.Thread(target=self.receive, daemon=True).start()

        while not self.username:
            action = Prompt.ask("register или login", choices=["register", "login", "r", "l"])
            action = "register" if action in ["r", "register"] else "login"

            username = Prompt.ask("Имя пользователя")
            password = Prompt.ask("Пароль", password=True)

            self._pending_username = username
            self._auth_event.clear()

            self.socket.send(Message(type=action, from_user=username, content=password).to_json().encode())

            self._auth_event.wait(timeout=5)  # ждём ответа сервера

            if self._auth_ok:
                self.username = username  # только теперь

        self.socket.send(Message(type="chat_list").to_json().encode())
        self.send_message()

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5555
    client = MessengerClient(host=host, port=port)
    try:
        client.start()
    except KeyboardInterrupt:
        console.print("\n[red]Выход...[/]")