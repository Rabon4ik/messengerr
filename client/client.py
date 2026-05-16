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

            elif msg.type in ["login", "register"] and getattr(msg, 'success', True):
                console.print(f"[bold green]✅ {msg.content or 'Успешно'}[/]")

            elif msg.type == "error" or not getattr(msg, 'success', True):
                console.print(f"[red]❌ {msg.content}[/]")

            else:
                console.print(f"[dim]Неизвестный тип: {msg.type}[/]")

        except Exception as e:
            console.print(f"[red]Критическая ошибка при обработке history: {e}[/]")
            import traceback
            console.print(traceback.format_exc())

    def send_message(self):
        console.print("[bold]Команды:[/]")
        console.print("   @username текст сообщения")
        console.print("   !online")
        console.print("   !history @username\n")

        while self.running:
            try:
                text = input().strip()
                if not text:
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

                if not text.startswith("@"):
                    console.print("[red]Сообщение должно начинаться с @username[/]")
                    continue

                parts = text[1:].split(" ", 1)
                if len(parts) < 2:
                    console.print("[red]Формат: @username текст[/]")
                    continue

                to_user = parts[0]
                content = parts[1]

                msg = Message(type="message", from_user=self.username, to_user=to_user, content=content)
                self.socket.send(msg.to_json().encode())

            except Exception as e:
                console.print(f"[red]Ошибка отправки: {e}[/]")
                break

    def start(self):
        self.connect()

        while not self.username:
            action = Prompt.ask("register или login", choices=["register", "login", "r", "l"])
            action = "register" if action in ["r", "register"] else "login"

            self.username = Prompt.ask("Имя пользователя")
            password = Prompt.ask("Пароль", password=True)

            self.socket.send(Message(type=action, from_user=self.username, content=password).to_json().encode())
            time.sleep(0.7)

        threading.Thread(target=self.receive, daemon=True).start()
        self.send_message()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    client = MessengerClient(host=host)
    try:
        client.start()
    except KeyboardInterrupt:
        console.print("\n[red]Выход...[/]")