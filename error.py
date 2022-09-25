import my_ast as ast

code_name = ""
code = []
current_pre = "<main>"

class ErrorElement:
    def __init__(self, node: ast.Node, pre: str, sec: str = "", notes: list[str] = None) -> None:
        self.node = node
        self.pre = pre
        self.sec = sec
        self.notes = notes or []

    def print(self, pad: int, final: bool = False) -> None:
        line = " " * pad
        if self.node[0].source != None:
            token = self.node[0].source
            line = str(token.line)
            line = (" " * (pad - len(line))) + line
        else:
            token = None
        str_pad = " " * pad

        if token != None:
            print(f"{str_pad}--> at {code_name}:{token.line}:{token.column} in {self.pre}")
        else:
            print(f"{str_pad}--> in {self.pre}")

        if final:
            print(f"{str_pad} | ")

        if token != None:
            print(f"{line} | {code[token.line - 1]}")
            if self.sec != "":
                print(f"{str_pad} | {' ' * (token.column - 1)}{'^' * (token.end_column - token.column)} {self.sec}")
        else:
            message = ""
            message += "("

            start, end = 0, 0

            for i, item in enumerate(self.node):
                match type(item):
                    case ast.Unit:
                        if i == 0:
                            start = len(message)
                            message += item.value
                            end = len(message)
                        else:
                            message += item.value

                    case ast.Node:
                        message += "(...)"

                if i != len(self.node) - 1:
                    message += " "

            message += ")"

            print(f"{line} | {message}")
            if self.sec != "":
                print(f"{str_pad} | {' ' * start}{'^' * (end - start)} {self.sec}")

        if final:
            print(f"{str_pad} | ")

        for note in self.notes:
           print(f"{str_pad} = {note}")

errors: list[ErrorElement] = []

def change_pre(new_pre: str) -> str:
    global current_pre

    old = current_pre
    current_pre = new_pre

    return old

def append_error_element(node: ast.Node, pre: str, sec: str = "", notes: list[str] = None) -> None:
    global errors

    errors.append(ErrorElement(node, pre, sec, notes))

def init(_code_name: str, _code: list[str]) -> None: # todo multifile support
    global code_name, code

    code_name = _code_name
    code = _code

def special_error(main: str, note: str = "", notes: list[str] = []) -> None: # todo figure out what to do with this
    if note != "":
        notes.append(note)

    print(f"{main}")
    for note in notes:
        print(f"= {note}")
    exit(1)

def error(node: ast.Node, main: str = "", sec: str = "", notes: list[str] = []) -> None:
    errors.append(ErrorElement(node, current_pre, sec, notes))

    # get pad
    pad = 0
    for err in errors:
        if err.node[0].source != None:
            l = len(str(err.node[0].source.line))

            pad = pad if pad >= l else l

    # print errors
    for i, err in enumerate(errors):
        if i == len(errors) - 1:
            print(f"ERROR: {main}")
            err.print(pad, final = True)
            exit(1)
        else:
            err.print(pad)
            print()
