import ntpath
import os
import re
import socket
import threading
import zipfile
import io
import sys
import logging

BUFF = 4096
logging.basicConfig(filename='Logs/server_logs.log', filemode='a', format='%(asctime)s ; %(levelname)s - %(message)s',
                    datefmt='%d-%b-%y %H:%M:%S', level=logging.INFO)


def ipVersion(ip_addr):
    try:
        ip_addr = socket.gethostbyname(ip_addr)
    except socket.error:
        pass
    try:
        ip_addr = socket.getaddrinfo(ip_addr, None, socket.AF_INET6)[0][4][0]
    except socket.error:
        pass
    try:
        socket.inet_aton(ip_addr)
        return 4
    except socket.error:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, ip_addr)
        return 6
    except socket.error:
        pass
    return 1


def disconnectClient(conn, addr):
    conn.close()
    print("Disconnected with: " + addr[0] + ":" + str(addr[1]))
    logging.info("Disconnected with: " + addr[0] + ":" + str(addr[1]))


def checkFileConditions(file_name, file_size):
    illegal_characters = re.compile('[/\:*?"<>|]')

    if illegal_characters.search(file_name) is not None:
        return 101

    elif file_size > 524288000:
        return 102

    elif not file_name.endswith(".zip"):
        return 103

    return 100


def saveFile(file_name, file_content):
    counter = 1
    file_name_temp = file_name
    while os.path.exists("uploaded_files/" + file_name_temp):
        if counter == 1:
            file_name_temp = file_name_temp[:-4]
        else:
            if counter % 10 != 0:
                del_chars = 7 + int(len(str(counter)))
            else:
                del_chars = (7 + int(len(str(counter)))) - 1

            file_name_temp = file_name_temp[:-del_chars]

        file_name_temp = file_name_temp + " (" + str(counter) + ")" + ".zip"
        counter += 1

    try:
        file = open("uploaded_files/" + file_name_temp, "wb+")
        file.write(file_content)
        file.close()

    except IOError as io_exc:
        print("I/O error: {0}".format(io_exc))
        logging.error("I/O error: {0}".format(io_exc))
        return False

    return file_name_temp


def zipFileContent(file_name):
    zip_file = zipfile.ZipFile("uploaded_files/" + file_name, "r")
    old_stdout = sys.stdout
    content = io.StringIO()
    sys.stdout = content
    zip_file.printdir()
    sys.stdout = old_stdout
    zip_file.close()
    return content.getvalue()


def checkFileExistence(file_path, zip_file):
    file = zipfile.ZipFile("uploaded_files/" + zip_file, "r")
    if file_path in file.namelist():
        file.close()
        return True
    file.close()
    return False


def getFileFromZip(file_path, zip_file, password):
    if checkFileExistence(file_path, zip_file):
        file = zipfile.ZipFile("uploaded_files/" + zip_file, "r")
        if len(password) > 0:
            opened_file = file.open(file_path, "r", password.encode("utf-8"))
        else:
            opened_file = file.open(file_path, "r")
        file.close()
        file_content = opened_file.read()
        file_size = len(file_content)
        file_data = {"filesize": file_size,
                     "filecontent": file_content}
        return file_data

    return False


def oneClient(conn, addr):
    password = ""
    recived_data = b''
    while b'\r\n\r\n' not in recived_data:
        recived_data += conn.recv(BUFF)

    # Check if client requested upload
    if "upload" in recived_data.decode('utf8').splitlines()[0].lower():
        file_data = dict(
            (k.lower(), v) for k, v in [i.split(': ') for i in recived_data[:-4].decode('utf8').splitlines()[1:]])
        file_name = ntpath.basename(file_data.get('filename', "new_file"))
        file_size = int(file_data.get('filesize', 0))
        print("Upload request form: " + addr[0] + ":" + str(addr[1]) + "\n" +
              "File name: " + file_name + "\n" +
              "File size: " + str(file_size) + " B")
        logging.info("Upload request form: " + addr[0] + ":" + str(addr[1]) + "\n" +
                     "File name: " + file_name + "\n" +
                     "File size: " + str(file_size) + " B")

        response_code = checkFileConditions(file_name, file_size)

        if response_code is not 100:
            response = "RESPONSE: " + str(response_code) + "\r\n\r\n"
            print("Uploading failed!")
            logging.error("Uploading failed!")
            conn.send(response.encode('utf8'))
            disconnectClient(conn, addr)
            return

        response = "RESPONSE: 100\r\n\r\n"
        conn.send(response.encode('utf8'))

        if file_size <= 0:
            disconnectClient(conn, addr)
            return

        # Getting file content
        file_content = b''
        while len(file_content) < file_size:
            file_content += conn.recv(file_size - len(file_content))

        if not file_content:
            response = "RESPONSE: 201\r\n\r\n"
            conn.send(response.encode('utf8'))
            disconnectClient(conn, addr)
            return

        save_file_result = saveFile(file_name, file_content)
        if not save_file_result:
            response = "RESPONSE: 201\r\n\r\n"
            conn.send(response.encode('utf8'))
            disconnectClient(conn, addr)
            return

        temp_file_name = save_file_result
        print("File " + file_name + " has been successfully saved on the server as " + temp_file_name)
        logging.info("File " + file_name + " has been successfully saved on the server as " + temp_file_name)
        is_encrypted = False

        try:
            test_zip = zipfile.ZipFile("uploaded_files/" + temp_file_name, "r")
            test_zip.testzip()
        except RuntimeError:
            print("File " + temp_file_name + " is encrypted. A password is required to extraction.")
            logging.info("File " + temp_file_name + " is encrypted. A password is required to extraction.")
            is_encrypted = True
            response = "RESPONSE: 204\r\n\r\n"
            conn.send(response.encode('utf8'))
        except Exception:
            print("File " + temp_file_name + " is damaged")
            logging.error("File " + temp_file_name + " is damaged")
            response = "RESPONSE: 203\r\n\r\n"
            conn.send(response.encode('utf8'))
            disconnectClient(conn, addr)
            os.remove("uploaded_files/" + temp_file_name)
            return

        if is_encrypted:
            while True:
                recived_data = b''
                try:
                    while b'\r\n\r\n' not in recived_data:
                        recived_data += conn.recv(BUFF)
                except socket.error as socket_exc:
                    print("Socket error: {0}".format(socket_exc))
                    logging.error("Socket error: {0}".format(socket_exc))
                    disconnectClient(conn, addr)
                    os.remove("uploaded_files/" + temp_file_name)
                    return

                password_header = recived_data.decode('utf8').split(": ")
                password = password_header[1][:-4]

                try:
                    test = test_zip.infolist()
                    test_open = test_zip.open(test[0].filename, "r", password.encode("utf-8"))
                    test_open.close()
                except IndexError as index_exc:
                    print("Zip file " + temp_file_name + " is empty")
                    logging.error("Zip file " + temp_file_name + " is empty")
                    disconnectClient(conn, addr)
                    os.remove("uploaded_files/" + temp_file_name)
                    return
                except RuntimeError:
                    print("Bad password for file: " + temp_file_name)
                    logging.error("Bad password for file: " + temp_file_name)
                    response = "RESPONSE: 205\r\n\r\n"
                    conn.send(response.encode('utf8'))
                    continue
                print("Correct password for file: " + temp_file_name)
                logging.error("Correct password for file: " + temp_file_name)
                break

        test_zip.close()
        response = "RESPONSE: 200\r\n\r\n"
        conn.send(response.encode('utf8'))

        recived_data = b''
        try:
            while b'\r\n\r\n' not in recived_data:
                recived_data += conn.recv(BUFF)
        except socket.error as socket_exc:
            print("Socket error: {0}".format(socket_exc))
            logging.error("Socket error: {0}".format(socket_exc))
            disconnectClient(conn, addr)
            os.remove("uploaded_files/" + temp_file_name)
            return

        if recived_data is not None and "fileslist_request" in recived_data.decode('utf8').lower():
            response = zipFileContent(temp_file_name) + "\r\n\r\n"
            conn.send(response.encode('utf8'))
        else:
            disconnectClient(conn, addr)
            return

        # Waiting for a client requests
        while True:
            recived_data = b''
            try:
                while b'\r\n\r\n' not in recived_data:
                    recived_data += conn.recv(BUFF)
            except socket.error:
                os.remove("uploaded_files/" + temp_file_name)
                disconnectClient(conn, addr)
                return

            if "quit" in recived_data.decode('utf8').lower():
                os.remove("uploaded_files/" + temp_file_name)
                disconnectClient(conn, addr)
                break

            if "download" in recived_data.decode('utf8').splitlines()[0].lower():
                download_request = dict((k.lower(), v) for k, v in
                                        [i.split(': ') for i in recived_data[:-4].decode('utf8').splitlines()[1:]])
                file_path = download_request.get('filepath')
                print("Download request form: " + addr[0] + ":" + str(addr[1]) + "\n" +
                      "File: " + temp_file_name[:-4] + "/" + file_path + "\n")
                logging.info("Download request form: " + addr[0] + ":" + str(addr[1]) + "\n" +
                             "File: " + temp_file_name[:-4] + "/" + file_path)

                get_file_result = getFileFromZip(file_path, temp_file_name, password)

                if not get_file_result:
                    response = "RESPONSE: 301\r\n" \
                               "FILESIZE: 0\r\n\r\n"
                    conn.send(response.encode('utf8'))
                    print("File " + temp_file_name[:-4] + "/" + file_path + " doesn't exist\n")
                    logging.warning("File " + temp_file_name[:-4] + "/" + file_path + " doesn't exist")
                    continue

                response_header = "RESPONSE: 300\r\n" \
                                  "FILESIZE: " + str(get_file_result["filesize"]) + "\r\n\r\n"
                response = response_header.encode('utf8') + get_file_result["filecontent"]
                try:
                    conn.send(response)
                except socket.error as socket_exc:
                    print("Socket error: {0}".format(socket_exc))
                    logging.error("Socket error: {0}".format(socket_exc))
                else:
                    print("File " + temp_file_name[:-4] + "/" + file_path + " successfully sent to client\n")
                    logging.info("File " + temp_file_name[:-4] + "/" + file_path + " successfully sent to client")
            else:
                os.remove("uploaded_files/" + temp_file_name)
                disconnectClient(conn, addr)
                break


if __name__ == "__main__":
    server_address = ('127.0.0.1', 5000)
    ip_ver = ipVersion(server_address[0])

    if ip_ver == 4:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    elif ip_ver == 6:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    else:
        print("Invalid ip address! The server can't be started")
        exit(1)

    if not os.path.exists("uploaded_files"):
        os.mkdir("uploaded_files")

    try:
        print("Running the server...")
        logging.info("Running the server...")
        sock.bind(server_address)
    except socket.error as socket_exc:
        print("Socket error: {0}".format(socket_exc))
        logging.error("Socket error: {0}".format(socket_exc))
        exit(1)
    else:
        sock.listen(5)
        print("Server is running on port 5000")
        logging.info("Server is running on port 5000")

    while True:
        client, address = sock.accept()
        print("Connected with: " + address[0] + ":" + str(address[1]))
        logging.info("Connected with: " + address[0] + ":" + str(address[1]))
        t = threading.Thread(target=oneClient, args=[client, address])
        t.start()
