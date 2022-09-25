from typing_extensions import Self
import lark

class Unit:
    def __init__(self, source: lark.Token, value: str):
        self.source = source
        self.value = value

    def __repr__(self) -> str:
        return f"\"{self.value}\" from <{self.source}> at {self.source.line}:{self.source.column}"

class Node:
    def __init__(self, children: "list[Node | Unit]" = None):
        self.children = children or []
        self.main = False

    def make_main(self) -> Self:
        self.main = True
        return self

    def append(self, item: "Node | Unit") -> None:
        self.children.append(item)

    def get_repr(self) -> str:
        thru = "├"
        line = "─"
        corn = "└"
        pipe = "│"

        def connector(i: int) -> str:
            if i == len(self.children) - 1:
                return corn
            return thru

        def try_pipe(i: int) -> str:
            if i == len(self.children) - 1:
                return " "
            return pipe

        def new_make_elems() -> str:
            l = []

            for index, item in enumerate(self.children):
                match type(item).__name__:
                    case "Node":
                        l.append(connector(index) + line + "node")

                        for x in item.get_repr():
                            l.append(try_pipe(index) + " " + x)

                    case "Unit":
                        l.append(connector(index) + line + repr(item))

            return l

        return new_make_elems()

    def __iter__(self) -> Self:
        self.count = 0
        return self

    def __next__(self) -> "Node | Unit":
        if self.count != len(self):
            self.count += 1
            return self[self.count - 1]
        else:
            raise StopIteration

    def __getitem__(self, index: int) -> "Node | Unit":
        if type(index) != int:
            raise Exception("tried to index Node with something that wasnt an int")

        return self.children[index]

    def __len__(self) -> int:
        return len(self.children)

    def __repr__(self) -> str:
        return "node\n" + "\n".join(self.get_repr())

def transform(tree: lark.Tree) -> Node:
    node = Node()

    for item in tree.children:
        match item.data:
            case "atom":
                tok = item.children[0]
                node.append(Unit(tok, tok.value))

            case "str":
                tok = item.children[0]
                node.append(Unit(tok, tok.value[1:-1]))

            case "expr":
                node.append(transform(item))

    return node
