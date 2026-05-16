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

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        console.print(f"[green]Подключено к {self.host}:{self.port}[/]")

    def receive(self):
        while self.running:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break
                msg = Message.from_json(data)

                if msg.type == "message":
                    console.print(f"\n[cyan]{msg.from_user}[/] → [yellow]{msg.content}[/]")
                elif msg.type == "user_list":
                    console.print("[bold green]Онлайн пользователи:[/]", msg.users)
                elif msg.type == "error":
                    console.print(f"[red]Ошибка: {msg.content}[/]")
            except:
                if self.running:
                    console.print("[red]Соединение потеряно[/]")
                break

    def send_message(self):
        console.print("[bold]Напишите сообщение в формате: @username текст[/]")
        while self.running:
            try:
                text = input()
                if text.startswith("@"):
                    to_user, content = text[1:].split(" ", 1)
                    msg = Message(type="message", to_user=to_user, content=content, from_user=self.username)
                    self.socket.send(msg.to_json().encode())
            except:
                break

    def start(self):
        self.connect()

        # Логин / Регистрация
        while not self.username:
            action = Prompt.ask("register или login", choices=["register", "login"])
            self.username = Prompt.ask("Имя пользователя")
            password = Prompt.ask("Пароль", password=True)

            if action == "register":
                self.socket.send(Message(type="register", from_user=self.username, content=password).to_json().encode())
            else:
                self.socket.send(Message(type="login", from_user=self.username, content=password).to_json().encode())

            # Ждём ответа (упрощённо)
            data = self.socket.recv(1024).decode()
            response = Message.from_json(data)
            if response.success:
                console.print(f"[bold green]Добро пожаловать, {self.username}![/]")
            else:
                console.print(f"[red]{response.content}[/]")
                self.username = None

        # Запускаем приём сообщений
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