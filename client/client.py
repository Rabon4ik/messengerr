import socket
import threading
import sys
import os
import json
from common.protocol import Message
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


class MessengerClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self._last_sent = None
        self.current_chat = None
        self.chat_list = []
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.running = True
        self.buffer = ""
        self._auth_event = threading.Event()
        self._auth_ok = False

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    # ─── Отрисовка экранов ────────────────────────────────────────────────────

    def draw_main_screen(self):
        """Главный экран — список чатов."""
        clear()
        console.print(Panel(
            f"[bold cyan]👤 {self.username}[/]",
            title="[bold]💬 Мессенджер[/]",
            border_style="cyan",
            box=box.ROUNDED,
        ))

        if self.chat_list:
            console.print("\n[bold]Ваши чаты:[/]")
            for i, user in enumerate(self.chat_list, 1):
                console.print(f"  [cyan]{i}.[/] {user}")
        else:
            console.print("\n[dim]Чатов пока нет[/]")

        console.print("\n[dim]─────────────────────────────[/]")
        console.print("[dim]/new <username>[/]  — новый чат")
        console.print("[dim]/open <номер>[/]    — открыть чат")
        console.print("[dim]/online[/]          — кто в сети")
        console.print("[dim]─────────────────────────────[/]\n")

    def draw_chat_screen(self, history=None):
        """Экран диалога."""
        clear()
        console.print(Panel(
            f"[bold]Чат с [cyan]{self.current_chat}[/cyan][/]  [dim](/back — выйти)[/]",
            border_style="magenta",
            box=box.ROUNDED,
        ))
        if history:
            for m in history:
                t = str(m.get('time') or m.get('timestamp', '')).split('.')[0]
                sender = m.get('from') or m.get('sender', '?')
                content = m.get('content', '')
                if sender == self.username:
                    console.print(f"[dim]{t}[/]  [bold green]Вы:[/] {content}")
                else:
                    console.print(f"[dim]{t}[/]  [bold cyan]{sender}:[/] {content}")
        else:
            console.print("[dim]История пуста[/]")
        console.print("\n[dim]──────────────────────────────────────────[/]")

    # ─── Приём сообщений ──────────────────────────────────────────────────────

    def receive(self):
        while self.running:
            try:
                data = self.socket.recv(8192).decode('utf-8')
                if not data:
                    break
                self.buffer += data

                buf = self.buffer
                pos = 0
                while pos < len(buf):
                    try:
                        if buf[pos] != '{':
                            pos += 1
                            continue
                        raw, consumed = json.JSONDecoder().raw_decode(buf[pos:])
                        known = {k: v for k, v in raw.items() if k in Message.__dataclass_fields__}
                        self.handle_message(Message(**known))
                        pos += consumed
                    except json.JSONDecodeError:
                        break
                    except Exception:
                        pos += 1
                self.buffer = buf[pos:]

            except Exception as e:
                if self.running:
                    console.print(f"[red]Ошибка receive: {e}[/]")
                break

    def handle_message(self, msg: Message):
        try:
            if msg.type == "message":
                # Входящее сообщение — показываем только если мы в этом чате
                if self.current_chat and msg.from_user == self.current_chat:
                    import time as _time
                    t = _time.strftime('%Y-%m-%d %H:%M:%S')
                    console.print(f"[dim]{t}[/]  [bold cyan]{msg.from_user}:[/] {msg.content}")
                else:
                    # Уведомление если мы не в этом чате
                    console.print(f"\n[bold yellow]🔔 Новое сообщение от {msg.from_user}[/]")

            elif msg.type == "history":
                # Получили историю — рисуем экран чата
                self.draw_chat_screen(history=msg.history)

            elif msg.type == "user_list":
                if not self.current_chat:
                    # Показываем только на главном экране
                    console.print("[bold green]Онлайн:[/]", msg.users or [])

            elif msg.type == "message_sent":
                if self._last_sent:
                    import time as _time
                    t = _time.strftime('%Y-%m-%d %H:%M:%S')
                    console.print(f"[dim]{t}[/]  [bold green]Вы:[/] {self._last_sent} [dim green]✓[/]")
                    self._last_sent = None

            elif msg.type in ["login", "register"]:
                self._auth_ok = getattr(msg, 'success', True)
                self._auth_event.set()
                if not self._auth_ok:
                    console.print(f"[red]❌ {msg.content}[/]")

            elif msg.type == "chat_list":
                self.chat_list = msg.users or []
                self.draw_main_screen()

            elif msg.type == "error":
                console.print(f"[red]❌ {msg.content}[/]")
                if self.current_chat and self.current_chat not in (self.chat_list[:-1] if self.chat_list else []):
                    self.chat_list = [u for u in self.chat_list if u != self.current_chat]
                    self.current_chat = None
                    self.draw_main_screen()

        except Exception as e:
            console.print(f"[red]Ошибка handle_message: {e}[/]")

    def _input_line(self, prompt=""):
        """Ввод с очисткой строки после Enter."""
        sys.stdout.write(prompt)
        sys.stdout.flush()
        line = input()
        # Поднимаемся на строку вверх и стираем её целиком
        sys.stdout.write('\x1b[1A\x1b[2K')
        sys.stdout.flush()
        return line

    # ─── Ввод команд ──────────────────────────────────────────────────────────

    def send_message(self):
        while self.running:
            try:
                text = self._input_line().strip()
                if not text:
                    continue

                # ── Выход из чата ──
                if text == "/back":
                    self.current_chat = None
                    # Запрашиваем свежий список чатов — он перерисует главный экран
                    self.socket.send(Message(type="chat_list").to_json().encode())
                    continue

                # ── Кто онлайн ──
                if text.lower() in ["/online", "!online"]:
                    self.socket.send(Message(type="user_list").to_json().encode())
                    continue

                # ── Новый чат ──
                if text.startswith("/new"):
                    parts = text.split()
                    if len(parts) < 2:
                        console.print("[red]Укажите имя: /new username[/]")
                        continue
                    self.current_chat = parts[1]
                    if self.current_chat not in self.chat_list:
                        self.chat_list.append(self.current_chat)
                    # Запрашиваем историю — она перерисует экран чата
                    self.socket.send(Message(type="history", to_user=self.current_chat).to_json().encode())
                    continue

                # ── Открыть чат по номеру ──
                if text.startswith("/open"):
                    parts = text.split()
                    if len(parts) < 2:
                        continue
                    try:
                        idx = int(parts[1]) - 1
                    except ValueError:
                        console.print("[red]Укажите номер чата[/]")
                        continue
                    if idx < 0 or idx >= len(self.chat_list):
                        console.print("[red]Неверный номер[/]")
                        continue
                    self.current_chat = self.chat_list[idx]
                    self.socket.send(Message(type="history", to_user=self.current_chat).to_json().encode())
                    continue

                # ── Отправить сообщение ──
                if self.current_chat:
                    self._last_sent = text
                    self.socket.send(Message(
                        type="message",
                        to_user=self.current_chat,
                        content=text
                    ).to_json().encode())
                    continue
                else:
                    console.print("[red]Сначала откройте чат (/new username или /open номер)[/]")

            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                console.print(f"[red]Ошибка отправки: {e}[/]")
                break

    # ─── Запуск ───────────────────────────────────────────────────────────────

    def start(self):
        clear()
        console.print(Panel(
            "[bold cyan]Добро пожаловать в мессенджер[/]",
            border_style="cyan",
            box=box.ROUNDED,
        ))

        self.connect()
        console.print(f"[dim]Подключено к {self.host}:{self.port}[/]\n")

        threading.Thread(target=self.receive, daemon=True).start()

        # ── Аутентификация ──
        while not self.username:
            action = Prompt.ask(
                "Действие",
                choices=["register", "login", "r", "l"],
                default="login"
            )
            action = "register" if action in ["r", "register"] else "login"

            username = Prompt.ask("Имя пользователя")
            password = Prompt.ask("Пароль", password=True)

            if len(password) < 1:
                console.print("[red]Пароль не может быть пустым[/]")
                continue

            self._auth_event.clear()
            self._auth_ok = False
            self.socket.send(Message(type=action, from_user=username, content=password).to_json().encode())
            self._auth_event.wait(timeout=5)

            if self._auth_ok:
                self.username = username
            else:
                console.print("[yellow]Попробуйте снова[/]\n")

        # После входа — запрашиваем чаты (handle_message сам нарисует главный экран)
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