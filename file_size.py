from pathlib import Path;

def get_size(path: Path) -> int:

    """Gets the size of the specified file/directory path in bytes."""

    if path.is_file():
        return get_file_size(path);

    elif path.is_dir():
        return get_directory_size(path);

    else:
        raise Exception("Provided path isn't file or directory.");

def get_directory_size(path: Path) -> int:

    if path.is_dir():
        return sum((get_file_size(p) if p.is_file() else get_directory_size(p)) for p in path.iterdir() if (p.is_file() or p.is_dir()));

    else:
        raise Exception("Provided path isn't directory.");

def get_file_size(path: Path) -> int:

    if path.is_file():
        return path.stat().st_size;

    else:
        raise Exception("Provided path isn't file.");

def get_file_count(dirpath: Path) -> int:

    if dirpath.is_dir():

        n = 0;

        for p in dirpath.iterdir():

            if p.is_file():
                n += 1;
            
            elif p.is_dir():
                n += get_file_count(p);

        return n;

    else:
        raise Exception("Provided path isn't directory.");