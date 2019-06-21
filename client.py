import ntpath
import os
import socket
import zipfile
import getpass

from colorama import Fore, Back

BUFF = 4096

errors_dict = \
    {"101": "The server rejected the file because its name contains illegal characters!",
     "102": "The server has rejected the file because its size is too large!",
     "103": "The server rejected the file because it is not a ZIP file!",
     "201": "The server didn't receive the file data!",
     "202": "An error occurred while saving the file to the server!",
     "301": "An invalid file path has been provided or the file does not exist!"}

files_list = ""


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


def renameIfExist(download_path, file_name):
    counter = 1
    filename_without_extension, file_extension = os.path.splitext(file_name)

    while os.path.exists(download_path + file_name):
        if counter == 1:
            file_name = filename_without_extension
        else:
            if counter % 10 != 0:
                del_chars = (3 + len(file_extension)) + int(len(str(counter)))
            else:
                del_chars = ((3 + len(file_extension)) + int(len(str(counter)))) - 1

            file_name = file_name[:-del_chars]

        file_name = file_name + " (" + str(counter) + ")" + file_extension
        counter += 1

    return file_name


def uploadRequest(filename, filesize, sock):
    request = "UPLOAD\r\n" + \
              "FILENAME: " + filename + "\r\n" + \
              "FILESIZE: " + str(filesize) + "\r\n\r\n"

    sock.send(request.encode('utf8'))

    server_data = b''
    try:
        while b'\r\n\r\n' not in server_data:
            server_data += sock.recv(BUFF)
    except socket.error as socket_exc:
        print(Fore.RED + "Socket error: {0}".format(socket_exc))
        return False

    response = server_data.decode('utf8').split(": ")

    if "100" in response[1]:
        sock.send(file_content)
    elif "101" in response[1]:
        print(Fore.RED + "Error: " + errors_dict["101"])
        return False
    elif "102" in response[1]:
        print(Fore.RED + "Error: " + errors_dict["102"])
        return False
    elif "103" in response[1]:
        print(Fore.RED + "Error: " + errors_dict["103"])
        return False

    server_data = b''
    try:
        while b'\r\n\r\n' not in server_data:
            server_data += sock.recv(BUFF)
    except socket.error as socket_exc:
        print(Fore.RED + "Socket error: {0}".format(socket_exc))
        return False

    response = server_data.decode('utf8').split(": ")

    if "204" in response[1]:
        print(Fore.YELLOW + "A selected file is encrypted")
        while True:
            password = input(Fore.CYAN + "Enter password: ")
            request = "PASSWORD: " + password + "\r\n\r\n"
            sock.send(request.encode("utf-8"))
            server_data = b''
            try:
                while b'\r\n\r\n' not in server_data:
                    server_data += sock.recv(BUFF)
            except socket.error as socket_exc:
                print(Fore.RED + "Socket error: {0}".format(socket_exc))
                return False
            response = server_data.decode('utf8').split(": ")
            if "204" in response[1]:
                print(Fore.RED + "Invalid password!")
                continue
            elif "200":
                break

    if "200" in response[1]:
        request = "FILESLIST_REQUEST\r\n\r\n"
        sock.send(request.encode('utf8'))
        server_data = b''
        while b'\r\n\r\n' not in server_data:
            server_data += sock.recv(BUFF)
        if server_data is None:
            return False
        global files_list
        files_list = server_data.decode('utf8')[:-4]
        print(
            "\n" + Back.LIGHTBLACK_EX + "--------------------------------------------------------------------------------" + Back.RESET)
        print(
            Back.LIGHTBLACK_EX + "||" + Back.RESET + Fore.YELLOW + "                           Content of ZIP file                              " + Fore.RESET + Back.LIGHTBLACK_EX + "||" + Back.RESET)
        print(
            Back.LIGHTBLACK_EX + "--------------------------------------------------------------------------------" + Back.RESET)
        print(files_list)
        return True
    elif "201" in response[1]:
        print(Fore.RED + "Error: " + errors_dict["201"])
    elif "202" in response[1]:
        print(Fore.RED + "Error: " + errors_dict["202"])
    elif "203" in response[1]:
        print(Fore.RED + "Error: " + errors_dict["203"])

    return False


def downloadRequest(path, sock, download_path):
    file_name = ntpath.basename(path)
    if not download_path.endswith("/") or not download_path.endswith("\\"):
        download_path = download_path + "/"
    request = "DOWNLOAD\r\n" + \
              "FILEPATH: " + path + "\r\n\r\n"

    sock.send(request.encode('utf8'))
    server_data = b''

    try:
        while b'\r\n\r\n' not in server_data:
            server_data += sock.recv(1)
    except socket.error as socket_exc:
        print(Fore.RED + "Socket error: {0}".format(socket_exc))
        return

    response = dict(
        (k.lower(), v) for k, v in [i.split(': ') for i in server_data[:-4].decode('utf8').splitlines()])

    file_size = int(response.get("filesize"))
    if response.get("response") == "300" and file_size > 0:
        file_content = b''

        try:
            while len(file_content) < file_size:
                file_content += sock.recv(file_size - len(file_content))
        except socket.error as socket_exc:
            print(Fore.RED + "Socket error: {0}".format(socket_exc))
            return

        if not file_content:
            print(Fore.RED + "\nAn error occurred while downloading the file from the server!")
            return

        if os.path.exists(download_path + file_name):
            file_name = renameIfExist(download_path, file_name)

        try:
            file = open(download_path + file_name, "wb+")
            file.write(file_content)
            file.close()
        except IOError as io_exc:
            print(Fore.RED + "I/O error: {0}".format(io_exc))
        else:
            print(Fore.GREEN + "\nThe file has been successfully downloaded! :)")
    elif response.get("response") == "301":
        print(Fore.RED + "\nError: " + errors_dict["301"])


def quitRequest(sock):
    request = "QUIT\r\n\r\n"
    sock.send(request.encode('utf8'))


if __name__ == "__main__":
    server_address = ('127.0.0.1', 5000)
    ip_ver = ipVersion(server_address[0])

    if ip_ver == 4:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    elif ip_ver == 6:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    else:
        print("Invalid ip address!")
        exit(1)

    upload_result = False
    app_title = """
     ___________ _____    ______      _                  _             
    |___  /_   _|  __ \  |  ____|    | |                | |            
       / /  | | | |__) | | |__  __  _| |_ _ __ __ _  ___| |_ ___  _ __ 
      / /   | | |  ___/  |  __| \ \/ / __| '__/ _` |/ __| __/ _ \| '__|
     / /__ _| |_| |      | |____ >  <| |_| | | (_| | (__| || (_) | |   
    /_____|_____|_|      |______/_/\_\\__|_|  \__,_|\___|\__\___/|_|        
        """
    current_download_path = os.path.dirname(os.path.realpath(__file__))
    print(Fore.YELLOW + app_title + Fore.RESET)

    try:
        file_name = input(Fore.CYAN + "Enter path to ZIP file: " + Fore.RESET)
        file = open(file_name, "rb")

    except IOError as io_exc:
        print(Fore.RED + "I/O error: {0}".format(io_exc))
        exit(1)

    file_content = file.read()
    file_size = len(file_content)
    file.close()

    try:
        sock.connect(server_address)
    except socket.error as socket_exc:
        print(Fore.RED + "Socket error: {0}".format(socket_exc))
        exit(1)

    upload_result = uploadRequest(file_name, file_size, sock)

    if upload_result:
        option = 0
        while True:
            option = input(Fore.YELLOW + "\nWhat do you want to do?\n" + Fore.RESET +
                           "1. Download a file\n" +
                           "2. Show content of ZIP file\n" +
                           "3. Set the destination path for downloaded files (current: " + current_download_path + ")\n" +
                           "4. Exit\n" +
                           Fore.CYAN + "Your choice: " + Fore.RESET)
            if option == "1":
                file_path = input(Fore.CYAN + "\nEnter path to the file: " + Fore.RESET)
                downloadRequest(file_path, sock, current_download_path)

            elif option == "2":
                print("\n" + Back.LIGHTBLACK_EX + "--------------------------------------------------------------------------------" + Back.RESET)
                print(Back.LIGHTBLACK_EX + "||" + Back.RESET + Fore.YELLOW + "                           Content of ZIP file                              " + Fore.RESET + Back.LIGHTBLACK_EX + "||" + Back.RESET)
                print(Back.LIGHTBLACK_EX + "--------------------------------------------------------------------------------" + Back.RESET)
                print(Back.RESET + files_list)

            elif option == "3":
                new_path = input(Fore.CYAN + "Enter path: " + Fore.RESET)
                while not os.path.exists(new_path):
                    choice = input(Fore.CYAN + "\nThe path you entered does not exist. Do you want to create it? (y/n) " + Fore.RESET)

                    if choice.lower() == "y" or choice.lower() == "yes":
                        try:
                            os.mkdir(new_path)
                        except IOError as io_exc:
                            print(Fore.RED + "I/O error: {0}".format(io_exc))

                    elif choice.lower() == "n" or choice.lower() == "no":
                        new_path = input(Fore.CYAN + "Enter path: " + Fore.RESET)

                    else:
                        print(Fore.RED + "Invalid choice!")
                        continue

                current_download_path = new_path

            elif option == "4":
                quitRequest(sock)
                print(Fore.RESET + "\nConnection closed")
                break

            else:
                print(Fore.RED + "\nInvalid choice!")
