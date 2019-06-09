import ntpath
import os
import re
import socket
import threading


def disconnectClient(conn, addr):
    conn.close()
    print("Disconnected with: " + addr[0])


def oneClient(conn, addr):
    recived_data = b''
    while b'\r\n\r\n' not in recived_data:
        recived_data += conn.recv(1)

    print(recived_data.decode())
    if "upload" in recived_data.decode().splitlines()[0].lower():
        file_data = dict((k.lower(), v) for k, v in [i.split(': ') for i in recived_data[:-4].decode().splitlines()[1:]])
        file_name = ntpath.basename(file_data.get('filename', "new_file"))
        file_size = int(file_data.get('filesize', 0))
        regex = re.compile('[/\:*?"<>|]')

        if regex.search(file_name) is not None:
            response = "RESPONSE: 101\r\n\r\n"
            conn.send(response.encode())
            disconnectClient(conn, addr)
            return
        elif file_size > 50000000:
            response = "RESPONSE: 102\r\n\r\n"
            conn.send(response.encode())
            disconnectClient(conn, addr)
            return
        elif not file_name.endswith(".zip"):
            response = "RESPONSE: 103\r\n\r\n"
            conn.send(response.encode())
            disconnectClient(conn, addr)
            return
        else:
            response = "RESPONSE: 100\r\n\r\n"
            conn.send(response.encode())
            file_content = b''
            if file_size > 0:
                while len(file_content) < file_size:
                    file_content += conn.recv(file_size - len(file_content))

                if not file_content:
                    response = "RESPONSE: 201\r\n\r\n"
                    conn.send(response.encode())
                    disconnectClient(conn, addr)
                    return
                else:
                    try:
                        print(file_content)
                        file = open("uploaded_files/" + file_name, "wb+")
                        file.write(file_content)
                        file.close()
                    except IOError as io_exc:
                        print("I/O error: {0}".format(io_exc))
                        response = "RESPONSE: 202\r\n\r\n"
                        conn.send(response.encode())
                        disconnectClient(conn, addr)
                        return
                    else:
                        print("File: " + file_name + " has been successfully saved on the server")
                        response = "RESPONSE: 200\r\n\r\n"
                        conn.send(response.encode())


server_address = ('127.0.0.1', 5000)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    sock.bind(server_address)
except socket.error as socket_exc:
    print("Socket error: {0}".format(socket_exc))
    exit(1)
else:
    sock.listen(5)

while True:
    client, address = sock.accept()
    print("Connected with: " + address[0])
    t = threading.Thread(target=oneClient, args=[client, address])
    t.start()


