import socket
import threading
import sys
from common.protocol import Message
from rich.console import Console
from rich.prompt import Prompt

console = Console()

class MessengerClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.running = True
        self.buffer = ""   # ← Добавили буфер

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        console.print(f"[green]✅ Подключено к {self.host}:{self.port}[/]")

    def receive(self):
        while self.running:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                self.buffer += data
                # Разделяем сообщения по }
                while '}' in self.buffer:
                    try:
                        end = self.buffer.index('}') + 1
                        json_str = self.buffer[:end].strip()
                        self.buffer = self.buffer[end:].strip()

                        if json_str:
                            msg = Message.from_json(json_str)
                            self.handle_message(msg)
                    except:
                        break  # Если не получилось распарсить — ждём ещё данных
            except Exception as e:
                if self.running:
                    console.print(f"[red]Соединение потеряно: {e}[/]")
                break

    def handle_message(self, msg: Message):
        if msg.type == "message":
            console.print(f"\n[cyan]{msg.from_user}[/] → [yellow]{msg.content}[/]")
        elif msg.type in ["login", "register"] and msg.success:
            console.print(f"[bold green]✅ {msg.content}[/]")
        elif msg.type == "user_list":
            console.print("[bold green]Онлайн пользователи:[/]", msg.users or [])
        elif msg.type == "message_sent":
            console.print("[green]✓ Сообщение отправлено[/]")
        elif msg.type == "error" or not msg.success:
            console.print(f"[red]❌ {msg.content}[/]")
        else:
            console.print(f"[dim]→ {msg.type}: {msg.content}[/]")

    def send_message(self):
        console.print("[bold]Формат: @username ваше сообщение[/]")
        console.print("[dim]Команды: !online   Пример: @nep Привет как дела?\n")

        while self.running:
            try:
                text = input().strip()
                if not text:
                    continue

                if text.lower() in ["!online", "/online"]:
                    self.socket.send(Message(type="user_list").to_json().encode())
                    continue

                if not text.startswith("@"):
                    console.print("[red]Сообщение должно начинаться с @[/]")
                    continue

                parts = text[1:].split(" ", 1)
                if len(parts) < 2:
                    console.print("[red]Неверный формат! @username сообщение[/]")
                    continue

                to_user = parts[0]
                content = parts[1]

                msg = Message(type="message", from_user=self.username, to_user=to_user, content=content)
                self.socket.send(msg.to_json().encode())
            except:
                break

    def start(self):
        self.connect()

        while not self.username:
            action = Prompt.ask("register или login", choices=["register", "login", "r", "l"])
            action = "register" if action in ["r", "register"] else "login"

            self.username = Prompt.ask("Имя пользователя")
            password = Prompt.ask("Пароль", password=True)

            self.socket.send(Message(type=action, from_user=self.username, content=password).to_json().encode())

            # Небольшая задержка, чтобы успеть получить ответ
            import time
            time.sleep(0.3)

        receive_thread = threading.Thread(target=self.receive, daemon=True)
        receive_thread.start()

        self.send_message()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    client = MessengerClient(host=host)
    try:
        client.start()
    except KeyboardInterrupt:
        console.print("\n[red]Выход...[/]")
    except Exception as e:
        console.print(f"[red]Критическая ошибка: {e}[/]")