import socketserver
import threading


class _TestExtensionServerHandler(socketserver.StreamRequestHandler):
    def handle(self):
        print(self.rfile.readline().strip())


class TestExtensionServer():
    def __init__(self, port: int):
        self.server = socketserver.ThreadingTCPServer(("localhost", port), _TestExtensionServerHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
