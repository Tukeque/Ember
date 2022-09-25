from error import error, special_error, append_error_element, change_pre
from copy import deepcopy as copy
from my_ast import Unit, Node
from emitter import emit
from typing import Any
from lark import Token

scope: list[dict[str, "Value"]] = [{}] # scope[0] is the global scope
macros: dict[str, "Macro"] = {} # global and local macros?

class Value:
    builtins = ["unit", "list", "number", "func", "nil"]

    def __init__(self, type: str, value: Any) -> None:
        self.type = type
        self.value = value

    def __repr__(self) -> str:
        match self.type:
            case "unit":
                return self.value
            
            case "func":
                return f"func({self.value.args})"

            case "number":
                return str(self.value)

            case "list":
                return f"'({' '.join([str(x) for x in self.value])})"

            case "nil":
                return "nil"

            case _:
                special_error(f"cannot convert Value to str")

class Func:
    def __init__(self, args: list[str], code: Node) -> None:
        self.args = args
        self.code = code

class Macro:
    def __init__(self, syntax: list[tuple[list[str], Node]]) -> None:
        self.syntax = syntax

    def replace(self, node: Node, table: dict[str, str]) -> Node:
        new = Node([])

        for x in node:
            if type(x) == Unit:
                if x.value in table:
                    new.append(table[x.value])
                else:
                    new.append(Unit(None, x.value))
            else: # type(x) == Node:
                new.append(self.replace(x, table))

        return new

    def change_source(self, args: list[Unit | Node]) -> list[Unit | Node]:
        new = []

        for x in args:
            if type(x) == Unit:
                new.append(Unit(None, x.value))
            else: # type(x) == Node:
                new.append(Node(self.change_source(x.children)))

        return new

    def macro_replace(self, node: Node, args: list[Unit | Node], name: str) -> Node:
        for s in self.syntax:
            s_args = copy(s[0])
            s_code = s[1]

            if len(s_args) >= 1 and len(s_args[-1]) >= 4 and s_args[-1][-3:] == "...":
                s_args[-1] = s_args[-1][:-3]

                i = len(s_args) - 1
                new_args = args[:i]
                new_args.append(Node([
                    Unit(None, "$quote"),
                    Node(args[i:])
                ]))
                args = new_args

            if not (len(s_args) >= 1 and len(s_args[-1]) >= 3 and s_args[-1][-3:] == "..."):
                if len(args) != len(s_args):
                    continue
            # => len is correct

            append_error_element(node, change_pre(f"<macro {name}>"))
            return self.replace(s_code, {s_arg: val for s_arg, val in zip(s_args, self.change_source(args))})

        error(node, f"no syntax was satisfied for macro", f"encountered an argument length of {len(args)}")

def expect_only_types(node: Node, args: list[Value], types: list[str]) -> None:
    size = len(types)

    if len(args) != size:
        error(node, f"instruction {node[0].value} doesnt have expected argument length of {size}", f"encountered {len(args)}")

    # if here: len(node) == size

    count = 0
    for item, t in zip(args, types):
        if item.type != t and t != "any":
            error(node, f"mismatching types for instruction {node[0].value}", f"expected {t} on argument {count} but found {item.type}")

        count += 1

def num_op(node: Node, args: list[Value], op) -> Value:
    expect_only_types(node, args, ["number", "number"])

    return Value("number", op(args[0].value, args[1].value))

def quote(x: Node | Unit) -> Value:
    if type(x) == Unit:
        return Value("unit", x.value)
    else:
        return Value("list", [quote(y) for y in x])

def quasiquote(x: Node | Unit) -> Value:
    if type(x) == Unit:
        return Value("unit", x.value)
    else:
        if len(x) == 2 and type(x[0]) == Unit and x[0].value == "$unquote":
            return compile(x[1])
        else:
            return Value("list", [quasiquote(y) for y in x])

def free(node: Node, scope_index: int, name: str) -> Value:
    ifglobal = "global " if scope_index == 0 else ""

    if name not in scope[scope_index]:
        error(node, f"tried to {ifglobal}free an unknown variable", f"{ifglobal}variable {name} doesnt exist")

    return scope[scope_index].pop(name)

def define(node: Node, scope_index: int, name: str) -> Value:
    ifglobal = "global " if scope_index == 0 else ""

    if name in scope[scope_index]:
        error(node, f"tried to {ifglobal}define a variable that already exists", f"{ifglobal}variable {name} already exists")

    if len(name) >= 1 and name[0] == "$":
        error(node, f"cannot define variables with a $ prefix", f"cant define {name}", note="identifiers beginning with $ are reserved to instructions")

    if name in macros:
        error(node, f"trying to define a variable with the same name as a marco", f"{name} is already reserved for a macro")

    scope[scope_index][name] = Value("nil", None)
    return Value("unit", name)

def set(node: Node, scope_index: int, name: str, value: Value) -> Value:
    ifglobal = "global " if scope_index == 0 else ""

    if name not in scope[scope_index]:
        error(node, f"tried to {ifglobal}set an unknown variable", f"{ifglobal}variable {name} doesnt exist")

    scope[scope_index][name] = value
    return value

def get(node: Node, scope_index: int, name: str) -> Value:
    ifglobal = "global " if scope_index == 0 else ""

    if name not in scope[scope_index]:
        error(node, f"tried to {ifglobal}get an unknown variable", f"{ifglobal}variable {name} doesnt exist")

    return scope[scope_index][name]

def call(node: Node, f: Value, args: list[Value]) -> Value:
    if f.type != "func":
        error(node, f"trying to call something that isnt a function", f"got type {f.type}")

    if len(f.value.args) != len(args):
        error(node, f"argument length doesnt match when calling a function") # todo kargs and kwargs

    scope.append({x: args[i] for i, x in enumerate(f.value.args)})

    append_error_element(node, change_pre("<function>"))

    x = compile(f.value.code)
    scope.pop()
    return x

def compile(node: Node | Unit) -> Value:
    if type(node) == Node:
        if node.main:
            for child in node:
                compile(child)

            return Value("nil", None)
        else:
            if len(node) == 0:
                return Value("nil", None) #? nil or empty node?

            if type(node[0]) != Unit:
                special_error(f"calling a node and not a unit: {node[0]}")

            func = node[0].value

            if func in ["$inline", "$define", "$print", "$get", "$set!",  "$number", "$len", "$index", "$push!", "$pop!", "$insert!", "$delete!", "$type", "$nil", "$+", "$-", "$*", "$/", "$%", "$&", "$|", "$^", "$round", "$==", "$!=", "$>", "$<", "$>=", "$<=", "$free", "$unit", "$exit", "$globalget", "$globalset!", "$globalfree", "$globaldefine", "$call", "$strget", "$strpush!", "$strset!"]:
                args = [compile(x) for x in node.children[1:]]
            else:
                args = []

            match func:
                case "$inline": # $inline code!
                    expect_only_types(node, args, ["unit"])

                    emit(args[0].value + "\n")
                    return Value("unit", args[0])

                case "$define": # $define var!
                    expect_only_types(node, args, ["unit"])

                    return define(node, -1, args[0].value)

                case "$print": # $print var
                    expect_only_types(node, args, ["any"])

                    print(args[0])
                    return args[0]

                case "$get": # $get var!
                    expect_only_types(node, args, ["unit"])

                    return get(node, -1, args[0].value)

                case "$set!": # $set! var! value
                    expect_only_types(node, args, ["unit", "any"])

                    return set(node, -1, args[0].value, args[1])

                case "$globaldefine": # $globaldefine var!
                    expect_only_types(node, args, ["unit"])

                    return define(node, 0, args[0].value)

                case "$globalset!": # $globalset! var! value
                    expect_only_types(node, args, ["unit", "any"])

                    return set(node, 0, args[0].value, args[1])

                case "$globalget": # $globalget var!
                    expect_only_types(node, args, ["unit"])

                    return get(node, 0, args[0].value)

                case "$lambda": # $lambda args% code%
                    # type check
                    for i in range(1):
                        if type(node[i + 1]) != Node:
                            error(node, f"mismatching types for instruction $lambda", f"expected a node on argument {i}, got a unit instead")

                    for x in node[1]:
                        if type(x) != Unit:
                            error(node, f"mismatching types for instruction $lambda", f"expected argument 1 to be all units, found node instead")
                    
                    f = Func([x.value for x in node[1]], node[2])

                    return Value("func", f)

                case "$if": # $if cond% true% false%
                    # type check
                    if len(node) != 4:
                        error(node, f"incorrect length of arguments for instruction $if", f"expected 3, found {len(node) - 1}")

                    for i, x in enumerate([node[2], node[3]]):
                        if type(x) != Node:
                            error(node, f"mismatching types in instruction $if", f"expected node on argument {i + 1}, found unit instead")

                    cond = compile(node[1])
                    
                    if cond.type != "number":
                        error(node, f"mismatching types in instruction $if", f"expected number, found {cond.type}")

                    if cond.value != 0: # condition passed
                        return compile(node[2])
                    else: # condition didnt pass
                        return compile(node[3])

                case "$&&": # $&& cond1 cond2
                    # type check
                    if len(node) != 3:
                        error(node, f"incorrect length of arguments for instruction $&&", f"expected 2 but found {len(node) - 1}")

                    cond1 = compile(node[1])

                    if cond1.type != "number":
                        error(node, f"mismatching types for instruction $&&", f"expected number on argument 0 but found {cond1.type}")

                    if cond1.value != 0: # condition passed
                        cond2 = compile(node[2])

                        if cond1.type != "number":
                            error(node, f"mismatching types for instruction $&&", f"expected number on argument 1 but found {cond1.type}")

                        return cond2
                    else:
                        return cond1 # dont compile the 2nd argument

                case "$||": # $|| cond1 cond2
                    # type check
                    if len(node) != 3:
                        error(node, f"incorrect length of arguments for instruction $||", f"expected 2 but found {len(node) - 1}")

                    cond1 = compile(node[1])

                    if cond1.type != "number":
                        error(node, f"mismatching types for instruction $||", f"expected number on argument 0 but found {cond1.type}")

                    if cond1.value != 0: # condition passed
                        return cond1 # dont compile the 2nd argument
                    else:
                        cond2 = compile(node[2])

                        if cond1.type != "number":
                            error(node, f"mismatching types for instruction $||", f"expected number on argument 1 but found {cond1.type}")

                        return cond2

                case "$number": # $number unit!
                    expect_only_types(node, args, ["unit"])

                    try:
                        x = float(args[0].value)
                    except:
                        error(node, f"cannot convert unit to number")
                    if x.is_integer():
                        x = int(x)

                    return Value("number", x)

                case "$quote": # $quote x
                    if len(node) != 2:
                        error(node, f"invalid argument length for instruction $quote", f"expected 1, got {len(node)}")

                    return quote(node[1])

                case "$quasiquote": # $quasiquote x
                    if len(node) != 2:
                        error(node, f"invalid argument length for instruction $quasiquote", f"expected 1, got {len(node)}")

                    return quasiquote(node[1])

                case "$len": # $len list^
                    expect_only_types(node, args, ["list"])

                    return Value("number", len(args[0].value))
        
                case "$index": # $index list^ i*
                    expect_only_types(node, args, ["list", "number"])

                    if args[1].value >= len(args[0].value):
                        error(node, f"index out of range", f"expected a value between 0 and {len(args[0].value)}, but got {args[1].value}")

                    return args[0].value[args[1].value]

                case "$push!": # $push! list^ x
                    expect_only_types(node, args, ["list", "any"])

                    args[0].value.append(args[1])

                    return args[1]

                case "$pop!": # $pop! list^
                    expect_only_types(node, args, ["list"])

                    if len(args[0].value) == 0:
                        error(node, f"cant pop from an empty list")

                    return args[0].value.pop()

                case "$insert!": # $insert! list^ index* value
                    expect_only_types(node, args, ["list", "number", "any"])

                    if args[1].value < 0 or args[1].value > len(args[0].value) or type(args[1].value) != int:
                        error(node, f"index out of range", f"mr ember says {args[1].value} is not in range")

                    args[0].value.insert(args[1].value, args[2])

                    return args[2]

                case "$delete!": # $delete! list^ index*
                    expect_only_types(node, args, ["list", "number"])

                    if args[1].value < 0 or args[1].value >= len(args[0].value) or type(args[1].value) != int:
                        error(node, f"index out of range", f"mr ember says {args[1].value} is not in range")

                    return args[0].value.pop(args[1].value)

                case "$while!": # $while! cond% code%
                    for i in range(1):
                        if type(node[i + 1]) != Node:
                            error(node, f"mismatching types for instruction $while!", f"expected a node on argument {i}, got a unit instead")

                    ret = Value("list", [])

                    while True:
                        cond = compile(node[1])
                        if cond.type != "number":
                            error(node, f"mismatching type for instruction $while!", f"expected number on argument 0 but got {cond.type}")
                        
                        if cond.value == 0:
                            break
                        
                        ret.value.append(compile(node[2]))

                    return ret

                case "$dowhile!": # $dowhile! cond% code%
                    for i in range(1):
                        if type(node[i + 1]) != Node:
                            error(node, f"mismatching types for instruction $dowhile!", f"expected a node on argument {i}, got a unit instead")

                    ret = Value("list", [])

                    while True:
                        ret.value.append(compile(node[2]))

                        cond = compile(node[1])
                        if cond.type != "number":
                            error(node, f"mismatching type for instruction $dowhile!", f"expected number on argument 0 but got {cond.type}")
                        
                        if cond.value == 0:
                            break

                    return ret

                case "$begin": # $begin nodes...
                    if len(node) == 1:
                        error(node, f"empty $begin")

                    for x in node.children[:-1]:
                        compile(x)

                    return compile(node[-1])

                case "$type": # $type x
                    expect_only_types(node, args, ["any"])

                    return Value("unit", args[0].type)

                case "$nil": # $nil
                    if len(args) != 0:
                        error(node, f"invalid argument length for instruction $nil", f"expected 0, found {len(args)}")

                    return Value("nil", None)

                case "$free": # $free x!
                    expect_only_types(node, args, ["unit"])

                    return free(node, -1, args[0].value)

                case "$globalfree": # $globalfree x!
                    expect_only_types(node, args, ["unit"])

                    return free(node, 0, args[0].value)

                case "$unit": # $unit x
                    expect_only_types(node, args, ["any"])

                    return Value("unit", str(args[0]))

                case "$exit": # $exit n*
                    expect_only_types(node, args, ["number"])

                    exit(args[0].value)

                case "$strget": # $strget unit! index*
                    expect_only_types(node, args, ["unit", "number"])

                    if args[1].value >= len(args[0].value):
                        error(node, f"string index out of range", f"expected a value between 0 and {len(args[0].value)}, but got {args[1].value}")

                    return Value("unit", args[0].value[args[1].value])

                case "$strpush!": # $strpush! dest! source!
                    expect_only_types(node, args, ["unit", "unit"])

                    args[0].value += args[1].value
                    return Value("unit", args[1].value)

                case "$strset!": # $strset! unit! value! index*
                    expect_only_types(node, args, ["unit", "unit", "number"])

                    n = args[2].value # todo not an int errors when indexing
                    args[0].value = args[0].value[:n] + args[1].value + args[0].value[(n + 1):]
                    return Value("unit", args[1].value)

                case "$macro": # $macro name! syntaxes...
                    if len(node) < 3:
                        error(node, f"invalid argument length for instruction $macro", f"expected 2 or more, found {len(node)} instead")

                    if type(node[1]) != Unit:
                        error(node, f"mismatching types for instruction $macro", f"expected unit in argument 0 but found {type(node[1]).__name__}")
                    for i in range(2, len(node)):
                        if type(node[i]) != Node:
                            error(node, f"mismatching types for instruction $macro", f"expected unit in argument {i} but found {type(node[i]).__name__}")

                    keys = [i for s in [list(j.keys()) for j in scope] for i in s]
                    if node[1].value in keys:
                        error(f"trying to define a macro with the same name as a variable", f"variable {node[1].value} already exists")

                    syntax = []

                    for i, s in enumerate(node.children[2:]):
                        if type(s) != Node:
                            error(node, f"invalid macro syntax in syntax {i}", f"expected a node")
                        
                        if len(s) != 2:
                            error(node, f"invalid macro syntax in syntax {i}", f"expected a node of length 2 but found length of {len(s)} instead")

                        args = []
                        args_node = s[0]

                        for j, arg in enumerate(args_node):
                            if type(arg) != Unit:
                                error(node, f"invalid argument in macro syntax {i}", f"expected unit in argument {j} but found {type(arg).__name__} instead")

                            args.append(arg.value)

                        code = s[1]

                        syntax.append((args, code))

                    macros[node[1].value] = Macro(syntax)

                    return Value("str", node[1].value)

                case "$quotemacro": # $quotemacro name! args...
                    if len(node) < 2:
                        error(node, f"invalid argument length for instruction $quotemacro", f"expected 1 or more but got {len(node) - 1}")

                    if type(node[1]) != Unit:
                        error(node, f"mismatching types for instruction $quotemacro", f"expected unit on argument 0 but found {type(node[1])}")

                    if (name := node[1].value) not in macros:
                        error(node, f"tried to expand a macro that doesnt exist", f"{node[1].value} doesnt exist")

                    macro = macros[name]

                    replaced = macro.macro_replace(node, node.children[2:], name)

                    return quote(replaced)

                case "$call": # $call name! args...
                    if len(args) < 1:
                        error(node, f"invalid argument length for instruction $call", f"expected 1 or more but got {len(args)}")

                    if args[0].type != "func":
                        error(node, f"mismatching types for instruction $call", f"expected func on argument 0 but found {args[0].type}")

                    return call(node, args[0], args[1:])

                case "$+": # $+ a* b*
                    return num_op(node, args, lambda x, y: x + y)
                case "$-": # $- a* b*
                    return num_op(node, args, lambda x, y: x - y)
                case "$*": # $* a* b*
                    return num_op(node, args, lambda x, y: x * y)
                case "$/": # $/ a* b*
                    return num_op(node, args, lambda x, y: x / y)
                case "$%": # $% a* b*
                    return num_op(node, args, lambda x, y: x % y)
                case "$&": # $& a* b*
                    return num_op(node, args, lambda x, y: x & y)
                case "$|": # $| a* b*
                    return num_op(node, args, lambda x, y: x | y)
                case "$^": # $^ a* b*
                    return num_op(node, args, lambda x, y: x ^ y)
                
                case "$round": # $round x*
                    expect_only_types(node, args, ["number"])

                    return Value("number", int(args[0].value))

                case "$==": # $== a* b*
                    return num_op(node, args, lambda x, y: (1 if x == y else 0))
                case "$!=": # $!= a* b*
                    return num_op(node, args, lambda x, y: (1 if x != y else 0))
                case "$>": # $> a* b*
                    return num_op(node, args, lambda x, y: (1 if x > y else 0))
                case "$<": # $< a* b*
                    return num_op(node, args, lambda x, y: (1 if x < y else 0))
                case "$>=": # $>= a* b*
                    return num_op(node, args, lambda x, y: (1 if x >= y else 0))
                case "$<=": # $<= a* b*
                    return num_op(node, args, lambda x, y: (1 if x <= y else 0))

                case name:
                    if (name in scope[(scope_index := -1)]) or (name in scope[(scope_index := 0)]): # try call a function
                        args = [compile(x) for x in node.children[1:]]

                        f = scope[scope_index][name]

                        return call(node, f, args)
                    elif name in macros: # calling a macro
                        macro = macros[name]

                        replaced = macro.macro_replace(node, node.children[1:], name)

                        return compile(replaced)

                    special_error(f"unknown function, instruction or macro {func}")
    else:
        assert type(node) == Unit
        return Value("unit", node.value)
