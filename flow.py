#!/usr/bin/env python3

import re
import sys

RE_REF = re.compile("\(([0-9]+)\)")
RE_TEXT = re.compile("([^(]+)")
RE_COMMENT = re.compile(" *#|$")


def parse_line(line):
    trimmed = line.lstrip(" ")
    spaces = len(line) - len(trimmed)
    assert spaces % 4 == 0, f"Indentation must always be a multiple of four. Error around >>{trimmed}<<"
    indentation = spaces // 4
    parts = []
    while trimmed:
        match = RE_REF.match(trimmed)
        if match is not None:
            parts.append(int(match.group(1)))
            trimmed = trimmed[match.span()[1]:]
            continue
        match = RE_TEXT.match(trimmed)
        if match is not None:
            parts.append(match.group(1))
            trimmed = trimmed[match.span()[1]:]
            continue
        raise AssertionError(f"Cannot parse any further!? >>{trimmed}<< from >>{line}<<")
    return indentation, parts


class Entry:
    def __init__(self, name, own_parts):
        self.name = name
        self.own_parts = own_parts
        self.children = dict()

    def to_jsonable(self):
        return {
            "parts": self.own_parts,
            "children": {str(k): v.to_jsonable() for k, v in self.children.items()},
        }

    def check_into(self, warnings, global_names=None):
        assert (global_names is None) == (self.name == "ROOT"), (global_names, self.name)
        if global_names is None:
            global_names = set()
        else:
            if self.name in global_names:
                warnings.append(f"Multiple (but non-conflicting) definitions of {self.name}")
            global_names.add(self.name)
        usages = [p for p in self.own_parts if isinstance(p, int)]
        usages.sort()
        if len(usages) != len(set(usages)):
            warnings.append(f"Entry {self.name} uses some children multiple times?! {usages=}")
        for usage in usages:
            if usage not in self.children:
                warnings.append(f"Entry {self.name} uses non-existing child {usage}?!")
        unused = set(self.children.keys()).difference(usages)
        if unused:
            warnings.append(f"Entry {self.name} has unused children?! {unused=}")
        for child in self.children.values():
            child.check_into(warnings, global_names)

    def assemble(self):
        str_parts = []
        self.assemble_into(str_parts)
        return "".join(str_parts)

    def assemble_into(self, str_parts):
        for p in self.own_parts:
            if isinstance(p, int):
                self.children[p].assemble_into(str_parts)
            else:
                str_parts.append(p)


def parse_content(flowdata_raw):
    stack = []
    # Invariant: All Entry instances except 'stack[0]' (if exists) are already registered in their parent instance.
    for line in flowdata_raw.split("\n"):
        if RE_COMMENT.match(line):
            continue
        indentation, parts = parse_line(line)
        if not stack:
            # Root Entry
            assert indentation == 0, f"IndentationError Root: {indentation=}, expected 0"
            entry = Entry("ROOT", parts)
        else:
            # Child Entry
            assert 1 <= indentation <= len(stack), f"IndentationError: {indentation=} {line=} {len(stack)=}"
            assert parts and isinstance(parts[0], int), f"Child has no ref name?! {line=}"
            entry = Entry(parts[0], parts[1:])
            while len(stack) > indentation:
                stack.pop()
            parent = stack[-1]
            assert entry.name not in parent.children.keys(), f"Duplicate definitions: {parent.name} has multiple children {entry.name}. {line=}"
            parent.children[entry.name] = entry
        stack.append(entry)
    assert stack, f"No definitions in {len(flowdata_raw)} bytes?!"
    return stack[0]


def run(flowfilename):
    with open(flowfilename, "r") as fp:
        flowdata_raw = fp.read()
    flow_parsed = parse_content(flowdata_raw)
    print(flow_parsed.to_jsonable())
    print("===")
    warnings = []
    flow_parsed.check_into(warnings)
    for warning in warnings:
        print(warning)
    if warnings:
        exit(1)
    print(flow_parsed.assemble())


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1].startswith("-"):
        print(f"USAGE: {sys.argv[0]} /path/to/flowfile.txt", file=sys.stderr)
        exit(1)
    run(sys.argv[1])
