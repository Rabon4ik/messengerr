import socket
import threading
import sys
import os
import json
import time
import ssl 
from common.protocol import Message
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich import box

console = Console()


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


class MessengerClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.running = True
        self.buffer = ""

        self.current_chat = None
        self.current_group_id = None
        self.current_group_name = None

        self.chat_list = []
        self.group_list = []

        self._auth_event = threading.Event()
        self._auth_ok = False
        self._last_sent = None
        self._chat_online = False

        if os.name == 'nt':
            os.system('color')

    def connect(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_socket.connect((self.host, self.port))
        self.socket = context.wrap_socket(raw_socket, server_hostname=self.host)

    # ─── Экраны ───────────────────────────────────────────────────────────────

    def draw_main_screen(self):
        clear()
        console.print(Panel(
            f"[bold cyan]👤 {self.username}[/]",
            title="[bold]💬 Мессенджер[/]",
            border_style="cyan",
            box=box.ROUNDED,
        ))
        if self.chat_list:
            console.print("\n[bold]Личные чаты:[/]")
            for i, user in enumerate(self.chat_list, 1):
                console.print(f"  [cyan]{i}.[/] {user}")
        else:
            console.print("\n[dim]Личных чатов пока нет[/]")

        if self.group_list:
            console.print("\n[bold]Группы:[/]")
            for i, g in enumerate(self.group_list, 1):
                members_str = ", ".join(
                    m['username'] if isinstance(m, dict) else m
                    for m in g['members']
                )
                console.print(f"  [magenta]г{i}.[/] [bold]{g['name']}[/] [dim]({members_str})[/]")
        else:
            console.print("\n[dim]Групп пока нет[/]")

        console.print("\n[dim]──────────────────────────────────────[/]")
        console.print("[dim]/new <username>[/]         — личный чат")
        console.print("[dim]/open <номер>[/]           — открыть личный чат")
        console.print("[dim]/newgroup <название>[/]    — создать группу")
        console.print("[dim]/opengroup <г-номер>[/]    — открыть группу")
        console.print("[dim]/online[/]                 — кто в сети")
        console.print("[dim]──────────────────────────────────────[/]\n")

    def draw_chat_screen(self, history=None, online=False):
        clear()
        status = "[bold green]● онлайн[/]" if online else "[dim]○ оффлайн[/]"
        console.print(Panel(
            f"[bold]Чат с [cyan]{self.current_chat}[/cyan][/]  {status}  [dim](/back — выйти)[/]",
            border_style="magenta",
            box=box.ROUNDED,
        ))
        self._print_history(history)
        console.print("\n[dim]──────────────────────────────────────────[/]")

    def draw_group_screen(self, history=None, group_name=None, members=None):
        clear()
        name = group_name or self.current_group_name or "Группа"
        members_str = ""
        if members:
            members_str = "  [dim]" + ", ".join(
                m['username'] if isinstance(m, dict) else m for m in members
            ) + "[/]"
        console.print(Panel(
            f"[bold]👥 {name}[/]{members_str}\n[dim]/back  /addmember <user>  /kick <user>  /rename <название>[/]",
            border_style="yellow",
            box=box.ROUNDED,
        ))
        self._print_history(history)
        console.print("\n[dim]──────────────────────────────────────────[/]")

    def _print_history(self, history):
        if not history:
            console.print("[dim]История пуста[/]")
            return
        for m in history:
            t = str(m.get('time') or m.get('timestamp', '')).split('.')[0]
            sender = m.get('from') or m.get('sender', '?')
            content = m.get('content', '')
            if sender == self.username:
                console.print(f"[dim]{t}[/]  [bold green]Вы:[/] {content}")
            else:
                console.print(f"[dim]{t}[/]  [bold cyan]{sender}:[/] {content}")

    # ─── Приём ────────────────────────────────────────────────────────────────

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
                if self.current_chat and msg.from_user == self.current_chat:
                    t = time.strftime('%Y-%m-%d %H:%M:%S')
                    console.print(f"[dim]{t}[/]  [bold cyan]{msg.from_user}:[/] {msg.content}")
                else:
                    console.print(f"\n[bold yellow]🔔 {msg.from_user}:[/] {msg.content}")

            elif msg.type == "group_message":
                if self.current_group_id == msg.group_id:
                    t = time.strftime('%Y-%m-%d %H:%M:%S')
                    console.print(f"[dim]{t}[/]  [bold cyan]{msg.from_user}:[/] {msg.content}")
                else:
                    gname = next((g['name'] for g in self.group_list if g['id'] == msg.group_id), f"группа {msg.group_id}")
                    console.print(f"\n[bold yellow]🔔 [{gname}] {msg.from_user}:[/] {msg.content}")

            elif msg.type == "message_sent":
                if self._last_sent:
                    t = time.strftime('%Y-%m-%d %H:%M:%S')
                    console.print(f"[dim]{t}[/]  [bold green]Вы:[/] {self._last_sent} [dim green]✓[/]")
                    self._last_sent = None

            elif msg.type == "history":
                self._chat_online = getattr(msg, 'online', False)
                self.draw_chat_screen(history=msg.history, online=self._chat_online)

            elif msg.type == "group_history":
                self.current_group_name = msg.group_name
                self.draw_group_screen(
                    history=msg.history,
                    group_name=msg.group_name,
                    members=msg.group_members
                )

            elif msg.type == "chat_list":
                self.chat_list = msg.users or []
                self.socket.send(Message(type="group_list").to_json().encode())

            elif msg.type == "group_list":
                self.group_list = msg.groups or []
                self.draw_main_screen()

            elif msg.type == "group_created":
                self.group_list.append({
                    "id": msg.group_id,
                    "name": msg.group_name,
                    "members": msg.group_members or []
                })
                self.current_group_id = msg.group_id
                self.current_group_name = msg.group_name
                self.current_chat = None
                self.socket.send(Message(type="group_history", group_id=msg.group_id).to_json().encode())

            elif msg.type == "group_invite":
                if not any(g['id'] == msg.group_id for g in self.group_list):
                    self.group_list.append({
                        "id": msg.group_id,
                        "name": msg.group_name,
                        "members": msg.group_members or []
                    })
                console.print(f"\n[bold magenta]📨 {msg.from_user} добавил вас в группу '{msg.group_name}'[/]")

            elif msg.type == "group_update":
                for g in self.group_list:
                    if g['id'] == msg.group_id and msg.group_name:
                        g['name'] = msg.group_name
                console.print(f"\n[yellow]ℹ️  {msg.content}[/]")
                if self.current_group_id == msg.group_id and msg.group_name:
                    self.current_group_name = msg.group_name

            elif msg.type == "group_kicked":
                self.group_list = [g for g in self.group_list if g['id'] != msg.group_id]
                console.print(f"\n[bold red]🚫 {msg.content}[/]")
                if self.current_group_id == msg.group_id:
                    self.current_group_id = None
                    self.current_group_name = None
                    time.sleep(1.5)
                    self.socket.send(Message(type="chat_list").to_json().encode())

            elif msg.type == "user_list":
                if not self.current_chat and not self.current_group_id:
                    console.print("[bold green]Онлайн:[/]", msg.users or [])

            elif msg.type == "status":
                is_online = getattr(msg, 'online', False)
                if self.current_chat and msg.from_user == self.current_chat:
                    self._chat_online = is_online
                    status = "[bold green]● онлайн[/]" if is_online else "[dim]○ оффлайн[/]"
                    console.print(Panel(
                        f"[bold]Чат с [cyan]{self.current_chat}[/cyan][/]  {status}  [dim](/back — выйти)[/]",
                        border_style="magenta",
                        box=box.ROUNDED,
                    ))

            elif msg.type == "shutdown":
                clear()
                console.print(Panel("[bold red]Сервер отключён[/]", border_style="red"))
                self.running = False
                self.socket.close()
                sys.exit(0)

            elif msg.type == "error":
                if self.current_chat and self.current_chat not in self.chat_list:
                    self.chat_list = [u for u in self.chat_list if u != self.current_chat]
                    self.current_chat = None
                    self.draw_main_screen()
                console.print(f"\n[bold red]❌ {msg.content}[/]")
                console.print("[dim]Нажмите Enter чтобы продолжить...[/]")

            elif msg.type in ["login", "register"]:
                self._auth_ok = getattr(msg, 'success', True)
                self._auth_event.set()
                if not self._auth_ok:
                    console.print(f"[red]❌ {msg.content}[/]")

        except Exception as e:
            console.print(f"[red]Ошибка handle_message ({msg.type}): {e}[/]")

    # ─── Ввод ─────────────────────────────────────────────────────────────────

    def _input_line(self):
        line = input()
        sys.stdout.write('\x1b[1A\x1b[2K')
        sys.stdout.flush()
        return line

    def send_message(self):
        while self.running:
            try:
                text = self._input_line().strip()

                if not text:
                    if not self.current_chat and not self.current_group_id:
                        self.draw_main_screen()
                    continue

                if text == "/back":
                    self.current_chat = None
                    self.current_group_id = None
                    self.current_group_name = None
                    self.socket.send(Message(type="chat_list").to_json().encode())
                    continue

                if text.lower() in ["/online", "!online"]:
                    self.socket.send(Message(type="user_list").to_json().encode())
                    continue

                if text.startswith("/new "):
                    target = text[5:].strip()
                    self.current_chat = target
                    self.current_group_id = None
                    if target not in self.chat_list:
                        self.chat_list.append(target)
                    self.socket.send(Message(type="history", to_user=target).to_json().encode())
                    continue

                if text.startswith("/open "):
                    try:
                        idx = int(text[6:].strip()) - 1
                        if 0 <= idx < len(self.chat_list):
                            self.current_chat = self.chat_list[idx]
                            self.current_group_id = None
                            self.socket.send(Message(type="history", to_user=self.current_chat).to_json().encode())
                        else:
                            console.print("[red]Неверный номер[/]")
                    except ValueError:
                        console.print("[red]Укажите номер[/]")
                    continue

                if text.startswith("/newgroup "):
                    group_name = text[10:].strip()
                    if not group_name:
                        console.print("[red]Укажите название[/]")
                        continue
                    console.print(f"[cyan]Участники для '{group_name}' (через пробел, Enter — пропустить):[/]")
                    raw = self._input_line().strip()
                    members = raw.split() if raw else []
                    self.socket.send(Message(
                        type="create_group",
                        group_name=group_name,
                        group_members=members
                    ).to_json().encode())
                    continue

                if text.startswith("/opengroup "):
                    try:
                        idx = int(text[11:].strip()) - 1
                        if 0 <= idx < len(self.group_list):
                            g = self.group_list[idx]
                            self.current_group_id = g['id']
                            self.current_group_name = g['name']
                            self.current_chat = None
                            self.socket.send(Message(type="group_history", group_id=g['id']).to_json().encode())
                        else:
                            console.print("[red]Неверный номер группы[/]")
                    except ValueError:
                        console.print("[red]Укажите номер[/]")
                    continue

                if text.startswith("/addmember "):
                    if not self.current_group_id:
                        console.print("[red]Сначала откройте группу[/]")
                        continue
                    self.socket.send(Message(
                        type="group_add",
                        group_id=self.current_group_id,
                        target_user=text[11:].strip()
                    ).to_json().encode())
                    continue

                if text.startswith("/kick "):
                    if not self.current_group_id:
                        console.print("[red]Сначала откройте группу[/]")
                        continue
                    self.socket.send(Message(
                        type="group_kick",
                        group_id=self.current_group_id,
                        target_user=text[6:].strip()
                    ).to_json().encode())
                    continue

                if text.startswith("/rename "):
                    if not self.current_group_id:
                        console.print("[red]Сначала откройте группу[/]")
                        continue
                    self.socket.send(Message(
                        type="group_rename",
                        group_id=self.current_group_id,
                        group_name=text[8:].strip()
                    ).to_json().encode())
                    continue

                if self.current_group_id:
                    self._last_sent = text
                    self.socket.send(Message(
                        type="group_message",
                        group_id=self.current_group_id,
                        content=text
                    ).to_json().encode())
                    continue

                if self.current_chat:
                    self._last_sent = text
                    self.socket.send(Message(
                        type="message",
                        to_user=self.current_chat,
                        content=text
                    ).to_json().encode())
                    continue

                console.print("[red]Сначала откройте чат (/new, /open, /opengroup)[/]")

            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                console.print(f"[red]Ошибка: {e}[/]")
                break

    # ─── Запуск ───────────────────────────────────────────────────────────────

    def start(self):
        clear()
        console.print(Panel("[bold cyan]Добро пожаловать в мессенджер[/]", border_style="cyan", box=box.ROUNDED))
        self.connect()
        console.print(f"[dim]Подключено к {self.host}:{self.port}[/]\n")

        threading.Thread(target=self.receive, daemon=True).start()

        while not self.username:
            action = Prompt.ask("Действие", choices=["register", "login", "r", "l"], default="login")
            action = "register" if action in ["r", "register"] else "login"
            username = Prompt.ask("Имя пользователя")
            password = Prompt.ask("Пароль", password=True)
            if not password:
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