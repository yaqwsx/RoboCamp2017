import socket
import time
import threading
import sys
import struct
from enum import Enum

def textIp(ip):
    return ".".join(map(str, map(ord, ip)))

def prettyMessage(msg):
    if msg[0] == "a":
        msg = msg[5:]
        msg = msg.split("\n")
        clients = []
        for x in msg[:-1]:
            clients.append(textIp(x[0:4]) + ": " + x[4:])
        return "Available clients: [" + ", ".join(clients) + "]"
    if msg[0] == "c":
        return "New client " + textIp(msg[1:5]) + ": " + msg[5:]
    if msg[0] == "d":
        return "Client disconnected " + textIp(msg[1:5])
    if msg[0] == "m":
        return "Message " + msg[5:]
    if msg[0] == "t":
        return "Typing " + textIp(msg[1:5])
    return "Unknown message"

def hexText(text):
    firstLine = ""
    secondLine = ""
    for x in text:
        secondLine += str(ord(x))
        if x == "\n":
            x = "\\n"
        if x == "\r":
            x = "\\r"
        firstLine += x
        firstLine += " " * (4 - len(firstLine) % 4)
        secondLine += " " * (4 - len(secondLine) % 4)
    return "\t" + firstLine + "\n\t" + secondLine

def addressToBinary(address):
    x = map(int, address.split("."))
    return struct.pack("BBBB", x[0], x[1], x[2], x[3])

class Message(object):
    def __init__(self):
        self.progress = 0
        self.command = None
        self.ip = None
        self.data = None

    def push(self, char, pr):
        pr(self.progress)
        if self.progress == 0:
            self.command = char
            self.ip = ""
            self.data = ""
        elif self.progress < 5:
            self.ip += char
        else:
            if ord(char) == 0:
                self.progress = 0
                return False
            self.data += char
        self.progress += 1
        return True

class ChatServer(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.clients = {}
        self.lock = threading.Lock()

    def listen(self):
        self.sock.listen(10)
        while True:
            socket, address = self.sock.accept()
            address = addressToBinary(address[0]);
            socket.settimeout(1)
            self.clients[socket] = (None, address)
            print("New connection: " + textIp(address))
            thr1 = threading.Thread(target = self.listenToClient,args = (socket,address)).start()
            thr2 = threading.Thread(target = self.keepAliveClient,args = (socket,42)).start()

    def broadcast(self, message):
        hex = ", ".join(map(str, map(ord, message)))
        print("Broadcasting: " + prettyMessage(message));
        print(hexText(message))
        for socket, client in self.clients.items():
            if not client[0]:
                continue
            try:
                self.lock.acquire()
                socket.send(message)
            except:
                continue
            finally:
                self.lock.release()
                pass

    def disconnectClient(self, socket):
        if not socket in self.clients:
            return
        client = self.clients[socket]
        if not client[0]:
            return
        address = client[1]
        self.broadcast("d" + address + "\x00")
        del self.clients[socket]

    def keepAliveClient(self, socket, dummy):
        while True:
            time.sleep(1)
            try:
                self.lock.acquire()
                socket.send("k\x00\x00\x00\x00\x00")
            except:
                self.disconnectClient(socket)
            finally:
                self.lock.release()

    def handleWelcome(self, msg, address):
        sock = self.getClientByIpString(address)
        if not sock:
            print("Warning: unknown client")
            return
        if len(msg.data) > 10:
            print("No long names, please!")
            return
        client = self.clients[sock]
        client = (msg.data, client[1])
        self.clients[sock] = client
        self.broadcast("c" + address + msg.data + "\x00")
        self.sendOnlineTable(sock)

    def sendOnlineTable(self, socket):
        msg = "a\x00\x00\x00\x00"
        for name, address in self.clients.values():
            if name:
                msg += address + name + "\n"
        msg += "\x00"
        print("Sending to " + textIp(self.clients[socket][1]) + ": " + prettyMessage(msg))
        print(hexText(msg))
        try:
            self.lock.acquire()
            socket.send(msg)
        except:
            return
        finally:
            self.lock.release()

    def forwardMessage(self, msg, address):
        msg.ip = address
        if len(msg.data) > 50:
            print("No long messages, please")
            return
        self.broadcast(msg.command + msg.ip + msg.data + "\x00")

    def getClientByIpString(self, ipstring):
        for socket, client in self.clients.items():
            if client[1] == ipstring:
                return socket
        return None

    def notifyData(self, progress, char, address):
        pass
        # print("\t" + textIp(address) + ":" + str(progress) + " = " + str(ord(char)) + "(" + char + ")")

    def listenToClient(self, client, address):
        size = 1
        while True:
            dirty = False
            try:
                msg = Message()
                while True:
                    data = client.recv(size)
                    if len(data):
                        for char in data:
                            dirty = True
                            if msg.push(char, lambda x: self.notifyData(x, char, address) ):
                                continue
                            dirty = False
                            if msg.command == 'w':
                                self.handleWelcome(msg, address)
                            if msg.command in "mt":
                                self.forwardMessage(msg, address)
                            if msg.command == "a":
                                self.sendOnlineTable(client)
            except socket.timeout:
                if dirty:
                    print("Timeout for " + textIp(address));
                continue
            except socket.error, e:
                print( textIp(address) + " E: ", e)
                return

if __name__ == "__main__":
    ChatServer('',int(sys.argv[1])).listen()