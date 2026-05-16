from client.client import MessengerClient
import sys

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 5555

client = MessengerClient(host=host, port=port)
client.start()
