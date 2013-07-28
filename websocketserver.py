#! /usr/bin/python
#
#  Author : Hans Kramer
#
#    Date : March 2012
#
#    Code : Websocket server written in Python
#           work in progress
#           I only handle receiving payloads of size smaller than 126 chars.
#           It ain't hard to add code for larger messages, I just can't find the time
#

import socket
import threading
import hashlib
import socket
import time
import base64
import struct
import syslog

#
# class to handle them grrrrr Base Framing Protocol
#

class WebSocketFrame:

    def __init__(self, channel):
        self.channel = channel

    def recv_message(self):
        data = self.channel.recv(2)
        x = struct.unpack('!H', data)[0]
        self._fin    = (x & 0x8000) >> 15
        self._rsv    = (x & 0x7000) >> 12
        self._opcode = (x & 0x0f00) >> 8
        self._mask   = (x & 0x0080) >> 7
        self._length = (x & 0x007f)
        #print "FIN",   self._fin
        #print "RSV",   self._rsv
        #print "opcode", self._opcode       
        #print "opcode", self._mask       
        #print "length", self._length       
        # I only handle payload <= 127 
        if self._length == 126:
            pass
        #elif self._length == 127:
        #    pass
        if self._mask:
            data = self.channel.recv(4)
            mask = struct.unpack('BBBB', data)
        payload = self.channel.recv(self._length)
        #print len(payload)
        self._string = ""
        for i in range(0, len(payload)):
            char = struct.unpack("B", payload[i])[0]
            m    = mask[i % 4]
            self._string += unichr(m ^ char)
            #print "%d %x %c" % (i, (m ^ char), (m ^ char))
        #print self._string
  
    def get_length(self):
        return None

    def get_string(self):
        return self._string


class WebSocketThread(threading.Thread):

    TEXT   = 0x01
    BINARY = 0x02

    def __init__(self, channel, details):
        self.channel   = channel
        self.details   = details
        threading.Thread.__init__(self)
        self.daemon    = True

    def build_header(self, length, code = TEXT, fin = True):
        a = 0b10000000 if fin else 0     
        a |= (code & 0b00001111)
        if length < 126:
            data = struct.pack("!BB", a, length)
        elif length < 65536:
            data = struct.pack("!BBH", a, 126, length)
        else:
            data = struct.pack("!BBHQ", a, 127, length)
        return data
        
#    def send_close(self, reason):
#        a = 0b10001000
#        b = len(reason) + 2
#        c = 4000
#        data = struct.pack("!BBH", a, b, c)
#        return data + reason

    def send_ascii(self, data): 
        frame = self.build_header(len(data)) + data
        self.channel.send(frame)

    def connect(self):
        return self.handshake()

    def run(self):
        pass
 
    def receive_header(self):
        header = ""
        while True:
            data = self.channel.recv(1024)
            header += data
            if len(data) != 1024 or (len(header) >= 4 and header[-5:-1] != "\r\n\r\n"):
                data = {}
                for row in header.split('\n'):
                    index = row.find(' ')
                    if index > 0:
                        data[row[0:index]] = row[index:-1].strip()
                return data

    def handshake(self):
        self.header = self.receive_header()
        syslog.syslog(syslog.LOG_INFO, str(self.header))
        # Oops so much more error checking to do here
        if 'Upgrade:' not in self.header or self.header['Upgrade:'] != 'websocket':
            # print "missing or invalid upgrade header"
            return False
        #if 'Connection:' not in self.header or self.header['Connection:'] != 'Upgrade':
        #    # print "missing connection header"
        #    return False
        return self.send_handshake(self.compute_handshake(self.header['Sec-WebSocket-Key:']))

    def send_handshake(self, handshake):
        self.channel.send("HTTP/1.1 101 Switching Protocols\r\n")
        self.channel.send("Upgrade: websocket\r\n")
        self.channel.send("Connection: Upgrade\r\n")
        self.channel.send("Sec-WebSocket-Accept: %s\r\n" % handshake)
        self.channel.send("\r\n")
        return True # what about some error checking?

    def compute_handshake(self, key):
        hash = hashlib.sha1(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest()
        accept = base64.b64encode(hash)
        return accept
        


class WebSocketServer():
 
    def __init__(self, port, connections=1000):
        syslog.syslog(syslog.LOG_INFO, "WebSocketServer.__init__")
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("", port))
        server.listen(connections)
        self.server = server
    
    def close(self):
        self.stop()
        print "close"
        #self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.shutdown(socket.SHUT_RDWR)
        self.server.close()
        
    def run(self, thread):
        self.run = True
        while self.run:
            try:
                channel, details = self.server.accept()
                syslog.syslog(syslog.LOG_INFO,("connected %s:%d" % details))
                t = thread(channel, details)
                if t.connect():
                    t.start()
            except socket.error as err:
                syslog.syslog(syslog.LOG_ERR, str(err))
    
    def stop(self):
        self.run = False



if __name__ == "__main__":
    syslog.openlog("hello", syslog.LOG_PERROR)   # always be friendly ;-)

    from json import dumps

    class DemoServer(WebSocketThread):

        def __init__(self, channel, details):
            WebSocketThread.__init__(self, channel, details)
      
        def handler(self, data):
            for row in data:
                self.send_ascii(dumps([True, row]))
            self.send_ascii(dumps([False, -1]))

        def run(self):
            #code to test receiving messages 
            wsf = WebSocketFrame(self.channel)   
            while True:
                wsf.recv_message()

    def handler(signum, frame):
        print "got signum", signum
        wss.stop()

    import signal

    signal.signal(signal.SIGHUP, handler)  
    
    wss = WebSocketServer(9999)
    try:
        wss.run(DemoServer)
    except KeyboardInterrupt:
        wss.close()
        pass
