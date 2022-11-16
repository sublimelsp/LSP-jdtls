import socketserver
import threading


class _TestExtensionServerHandler(socketserver.StreamRequestHandler):
    def handle(self):
        print(self.rfile.readline().strip().decode())


class TestExtensionServer():
    def __init__(self):
        self.server = socketserver.ThreadingTCPServer(("localhost", 0), _TestExtensionServerHandler)

    def get_port(self) -> int:
        return self.server.socket.getsockname()[1]

    def serve(self):
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
