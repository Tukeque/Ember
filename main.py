#!/usr/bin/python3

from lark import Lark
import my_ast as ast
import argparse
import compiler
import emitter
import error

SYNTAX_FILE = "syntax.lark"

# args
parser = argparse.ArgumentParser(
    description="Compiler for the Ember programming language. Made by Tukeque"
)
parser.add_argument(
    "input", nargs="?", default="main.ember",
    help="file to compile (.ember)"
)
parser.add_argument(
    "output", nargs="?", default="output.txt",
    help="name of output file"
)
parser.add_argument(
    "-d", "--debug", action="store_true",
    help="give debug information when compiling"
)
parser.add_argument(
    "-p", "--parse", action="store_true",
    help="parse and exit without compiling"
)
args = parser.parse_args()

# parse(using lark)
parser = Lark(open(SYNTAX_FILE, "r").read(), parser="lalr")
tree = parser.parse(open(args.input, "r").read())

if args.parse:
    print(tree.pretty())

node = ast.transform(tree).make_main()
if args.debug:
    print(node)

if not(args.parse):
    error.init(args.input, open(args.input, "r").read().split("\n"))
    emitter.init(args.output)
    compiler.compile(node)
    emitter.exit()