#!/usr/bin/env python3

from typing import List, Tuple;
from socket import socket as Socket;
import socket;
from struct import pack, unpack;
from argparse import ArgumentParser;
from progress.bar import Bar as ProgressBar;
from pathlib import Path;

import file_exchange;
from file_exchange import NET_INT32_FMT, INT32_SIZE, NET_INT8_FMT, INT8_SIZE, FILE_CONTENT_CODE, DIR_CONTENT_CODE;
import file_size;

DEFAULT_PORT = 59013;

MIN_VALID_PORT = 1024;
MAX_VALID_PORT = 65535;

MODE_UNKNOWN = 0x00;
MODE_SERVER = 0x01;
MODE_CLIENT = 0x02;

MODE_SERVER_INPUTS = ("server", "s", "srv", "0");
MODE_CLIENT_INPUTS = ("client", "c", "cli", "1");

def check_ipaddr(s: str) -> bool:

    if s == "localhost":
        return True;

    try:
        socket.inet_aton(s);
        return True;

    except OSError:
        return False;

def get_ipaddr_input(mode: int) -> str:

    if (mode != MODE_SERVER) and (mode != MODE_CLIENT):
        raise Exception("Invalid mode passed.");

    while True:

        inp = input("Enter IP address to use> " if mode == MODE_SERVER else "Enter server IP address> ");

        if check_ipaddr(inp) or ((mode == MODE_SERVER) and (inp == "")):
            return inp;

        else:
            print("Invalid address.");

def check_port(x: int) -> bool:
    return MIN_VALID_PORT <= x <= MAX_VALID_PORT;

def get_port_input() -> int:

    while True:

        inp = input("Enter port> ");

        if inp.isdigit() and check_port(int(inp)):
            return int(inp);
        else:
            print("Invalid port.");

def parse_mode(s: str) -> int:

    s = s.lower();

    if s in MODE_SERVER_INPUTS:
        return MODE_SERVER;

    elif s in MODE_CLIENT_INPUTS:
        return MODE_CLIENT;

    else:
        return MODE_UNKNOWN;

def get_mode_input() -> int:

    while True:

        inp = input("Choose mode> ");

        m = parse_mode(inp);

        if m != MODE_UNKNOWN:
            return m;

        else:
            print("Invalid mode.");

def check_send_path(p: Path) -> bool:

    return p.is_dir() or p.is_file();

def check_recv_path(p: Path) -> bool:

    return p.is_dir();

def get_path_input(mode: int) -> Path:

    if (mode != MODE_SERVER) and (mode != MODE_CLIENT):
        raise Exception("Invalid mode passed.");

    while True:

        inp = input("File/Directory path to send> " if mode == MODE_CLIENT else "Destination directory> ");

        p = Path(inp).absolute();

        if ((mode == MODE_CLIENT) and check_send_path(p)) or ((mode == MODE_SERVER) and (check_recv_path(p))):
            return p;

        else:
            print("Invalid path.");

def file_size_bytes_to_bar(x: int) -> int:

    """Converts the size of a file in bytes to the size unit that will be displayed to the user in the progress bar."""

    return x // 1024;

def main_server(verbose: bool,
    addr: Tuple[str, int],
    path: Path) -> None:

    path = path.absolute();

    with Socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP) as sock:

        sock.bind(addr);
        sock.listen(0);

        if verbose:
            print(f"Created socket at ({addr[0] if addr[0] != '' else '[all]'}:{addr[1]})");

        if verbose:
            print("Awaiting connection...");

        cli, caddr = sock.accept();

        if verbose:
            print(f"Accepted connection from {caddr}");

        # Receive type code

        bs = cli.recv(INT8_SIZE);
        type_code = unpack(NET_INT8_FMT, bs)[0];

        if verbose:
            print(f"Received type code: {type_code}");

        # Receive expected final size

        bs = cli.recv(INT32_SIZE);
        final_size = unpack(NET_INT32_FMT, bs)[0];

        if verbose:
            print(f"Received final size: {final_size}");

        # Receive file/directory

        if type_code == DIR_CONTENT_CODE:

            # Create progress bar

            prog_bar = ProgressBar(
                "Receiving",
                max = file_size_bytes_to_bar(final_size),
                suffix = r"%(index)iKB / %(max)iKB"
            );

            def file_received(fpath: Path) -> None:
                prog_bar.next(file_size_bytes_to_bar(file_size.get_file_size(fpath)));

            file_exchange.recv_dir(
                cli = cli,
                parent_path = path,
                on_file_received = file_received
            );

            prog_bar.next(prog_bar.max - prog_bar.index); # Complete progress bar to look correct (sometimes it isn't quite but that is fine)
            prog_bar.finish();

        elif type_code == FILE_CONTENT_CODE:

            file_exchange.recv_file(
                cli = cli,
                out_parent_path = path
            );

        else:
            raise Exception(f"Invalid type code received: {type_code}");

        if verbose:
            print("Finished receiving");

def main_client(verbose: bool,
    saddr: Tuple[str, int],
    path: Path) -> None:

    path = path.absolute();

    with Socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP) as sock:

        if verbose:
            print("Connecting to server...");

        try:
            sock.connect(saddr);
        except (TimeoutError, ConnectionRefusedError):
            print("Server wasn't responsive.");
            return;

        if verbose:
            print("Connected to server.");

        # Send type

        if path.is_file():
            code = FILE_CONTENT_CODE;
        elif path.is_dir():
            code = DIR_CONTENT_CODE;
        else:
            raise Exception("Path provided isn't directory or file.");

        sock.send(pack(NET_INT8_FMT, code));

        if verbose:
            print(f"Sent type code: {code}");

        # Send final size

        final_size = file_size.get_size(path);

        sock.send(pack(NET_INT32_FMT, final_size));

        if verbose:
            print(f"Sent final size: {final_size}");

        # Send file/directory

        if path.is_file():

            file_exchange.send_file(
                sock = sock,
                file_path = path
            );

        elif path.is_dir():

            file_exchange.send_dir(
                sock = sock,
                dir_path = path
            );

        if verbose:
            print("Finished sending");

def main() -> None:

    # Parse command line arguments

    argp = ArgumentParser(
        description = "Sends (when running as client) or receives (when running as server) files over a basic socket connection.",
        allow_abbrev = False,
        add_help = True
    );

    argp.add_argument(
        "-v",
        "--verbose",
        dest = "verbose",
        action = "store_true",
        help = "Whether to enable verbose output."
    );

    argp.add_argument(
        "-m",
        "--mode",
        dest = "mode",
        type = str,
        default = None,
        help = "Whether to run as the [c]lient (the client sends files) or the [s]erver (the server receives files)."
    );

    argp.add_argument(
        "-i",
        "--ip",
        "--ip-address",
        dest = "ip",
        type = str,
        default = "",
        help = "The IP address to connect to (if running as client) or the IP address to bind to (if running as server). For server, defaults to all available addresses."
    );

    argp.add_argument(
        "-p",
        "--port",
        dest = "port",
        type = int,
        default = DEFAULT_PORT,
        help = "The port on the server to connect to (if running as client) or the port to bind to (if running as server)."
    );

    argp.add_argument(
        "-f",
        "--file",
        dest = "filepath",
        type = str,
        default = None,
        help = "The file to send (when running as client). When running as server, this is ignored. (cannot be used with -d)"
    );

    argp.add_argument(
        "-d",
        "--dir",
        "--directory",
        dest = "dirpath",
        type = str,
        default = None,
        help = "The directory to send (if running as client) or the path of the parent directory to receive in (if in server mode). (cannot be used with -f)"
    );

    args = argp.parse_args();

    # Check arguments (where provided)

    verbose = None;
    mode = None;
    ip = None;
    port = None;
    path = None;

    if (args.filepath != None) and (args.dirpath != None):
        raise Exception("Not allowed to specify a file and a directory to send.");

    verbose = args.verbose;

    if args.mode == None:
        mode = get_mode_input();
    else:
        mode = parse_mode(args.mode);

    if mode == MODE_UNKNOWN:
        raise Exception("Invalid mode provided.");

    if args.ip == "":
        if mode == MODE_SERVER:
            ip = "";
        else:
            ip = get_ipaddr_input(mode);
    else:
        if check_ipaddr(args.ip):
            ip = args.ip;
        else:
            raise Exception("Invlaid IP address provided.");

    if check_port(args.port):
        port = args.port;
    else:
        raise Exception("Invalid port specified");

    if (mode == MODE_CLIENT) and (args.filepath != None):
        path = Path(args.filepath);

    elif args.dirpath != None:
        path = Path(args.dirpath);

    else:
        path = get_path_input(mode);

    if (mode == MODE_CLIENT) and (not check_send_path(path)):
        raise Exception("Invalid sending path.");
    elif (mode == MODE_SERVER) and (not check_recv_path(path)):
        raise Exception("Invalid receiving path.");

    # Run main programs for server or client

    if mode == MODE_SERVER:
        main_server(verbose = verbose,
            addr = (ip, port),
            path = path);
        
    else:
        main_client(verbose = verbose,
            saddr = (ip, port),
            path = path);

if __name__ == "__main__":
    main();
