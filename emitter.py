file = None

def init(file_name: str) -> None:
    global file

    file = open(file_name, "w")

def exit() -> None:
    global file

    file.close()

def emit(string: str) -> None:
    if file == None:
        raise Exception("emitting but file isnt open")
    else:
        file.write(string)
