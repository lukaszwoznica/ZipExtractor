import socket

errors_list = \
    ["The server rejected the file because its name contains illegal characters",
     "The server has rejected the file because its size is too large",
     "The server rejected the file because it is not a ZIP file.",
     "The server didn't receive the file data",
     "An error occurred while saving the file to the server"]


def uploadRequest(filename, filesize):
    request = "UPLOAD\r\n" + \
              "FILENAME: " + filename + "\r\n" + \
              "FILESIZE: " + str(filesize) + "\r\n\r\n"

    sock.send(request.encode())

    server_data = b''
    while b'\r\n\r\n' not in server_data:
        server_data += sock.recv(1)
    response = server_data.decode().split(": ")

    if "100" in response[1]:
        sock.send(file_content)
    elif "101" in response[1]:
        print("Error: " + errors_list[0])
        return False
    elif "102" in response[1]:
        print("Error: " + errors_list[1])
        return False
    elif "103" in response[1]:
        print("Error: " + errors_list[2])
        return False

    server_data = b''
    while b'\r\n\r\n' not in server_data:
        server_data += sock.recv(1)
    response = server_data.decode().split(": ")

    if "200" in response[1]:
        print("The file has been successfully uploaded!")
        return True
    elif "201" in response[1]:
        print("Error: " + errors_list[3])
    elif "202" in response[1]:
        print("Error: " + errors_list[4])

    return False

def downloadRequest(path):
    request = "DOWNLOAD\r\n" + \
              "FILEPATH: " + path + "\r\n\r\n"

    sock.send(request.encode())


server_address = ('127.0.0.1', 5000)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    sock.connect(server_address)
    file_name = input("Enter filename: ")
    file = open(file_name, "rb")
except socket.error as socket_exc:
    print("Socket error: {0}".format(socket_exc))
    exit(1)
except IOError as io_exc:
    print("I/O error: {0}".format(io_exc))
    exit(1)
else:
    file_content = file.read()
    file_size = len(file_content)
    file.close()
    upload_result = uploadRequest(file_name, file_size)

if upload_result:
    print("Download")


