import tkinter as tk
from numbers import Number
from tkinter import font, ttk

from lark import Lark, Transformer, v_args
from lark.exceptions import LarkError
from pyfpm.matcher import Matcher

try:
    import readline
except:
    pass


grammar = """
// `?` make the rules inline if they have 1 child
// e.g. (sum (product 2 3)) becomes (product 2 3)

?start: [WS] sum [WS]

?sum: product
    | sum "+" product -> add
    | sum "-" product -> sub

?product: power
        | product "*"? power -> mul
        | product "/" power -> div
        | "-" product -> neg


?power: app
      | app "^" power -> exp

// function application has highest precidence
// besides parentheses
?app: atom
    | var "[" sum ("," sum)* "]" -> application

?var: NAME -> var

// negation has lowest precidence
?atom: NUMBER -> number
     | var
     | "(" sum ")"

%import common.NUMBER
%import common.CNAME -> NAME
%import common.WS
%ignore WS
"""


@v_args(inline=True)
class To_List(Transformer):
    """Used by parser to recursively tansform a syntax tree to a list"""

    def number(self, n):
        try:
            return int(n)
        except:
            return float(n)

    def add(self, a, b):
        return ["+", a, b]

    def sub(self, a, b):
        return ["-", a, b]

    def mul(self, a, b):
        return ["*", a, b]

    def div(self, a, b):
        return ["/", a, b]

    def exp(self, a, b):
        return ["^", a, b]

    def neg(self, n):
        return ["-", n]

    def var(self, v):
        return str(v)

    def application(self, f, *args):
        return [f] + list(args)


# create a lalr parser
parser = Lark(grammar, parser="lalr", transformer=To_List())
parse = parser.parse


class Undefined:
    """represents undefined results like 1/0"""

    def __init__(self):
        pass


# rules to simplify terms
# the mather finds the first match and returns a new equivalent expression of that form
rules = Matcher(
    [
        # addition rules
        ('["+", x, 0]', lambda x: x),
        ('["+", x, x]', lambda x: ["*", 2, x]),
        ('["+", x, ["*", -1, x]]', lambda x: 0),
        ('["+", ["*", -1, x], x]', lambda x: 0),
        # these help with simplifying numeric parts
        ('["-", x, y]', lambda x, y: ["+", ["*", -1, y], x]),
        ('["-", x]', lambda x: ["*", -1, x]),
        # multiplication rules
        ('["*", x, 1]', lambda x: x),
        ('["*", 1, x]', lambda x: x),
        ('["*", x, 0]', lambda x: 0),
        ('["*", 0, x]', lambda x: 0),
        # add/subtract exponents
        ('["*", ["^", x, y], ["^", x, z]]', lambda x, y, z: ["^", x, ["+", y, z]]),
        ('["/", ["^", x, y], ["^", x, z]]', lambda x, y, z: ["^", x, ["-", y, z]]),
        ('["*", ["^", x, y], x]', lambda x, y: ["^", x, ["+", y, 1]]),
        ('["*", x, ["^", x, y]]', lambda x, y: ["^", x, ["+", y, 1]]),
        ('["/", ["^", x, y], x]', lambda x, y: ["^", x, ["-", y, 1]]),
        ('["/", x, ["^", x, y]]', lambda x, y: ["^", x, ["-", 1, y]]),
        ('["*", x, x]', lambda x: ["^", x, 2]),
        ('["/", x, 0]', lambda x: Undefined()),
        ('["/", 0, x]', lambda x: 0),
        ('["/", x, 1]', lambda x: x),
        ('["/", x, x]', lambda x: 1),
        # exponent rules
        ('["^", 0, 0]', lambda: Undefined()),
        ('["^", x, 0]', lambda x: 1),
        ('["^", 0, x]', lambda x: 0),
        ('["^", 1, x]', lambda x: 1),
        ('["^", x, 1]', lambda x: x),
        ('["^", x, -1]', lambda x: ["/", 1, x]),
        ('["^", ["^", x, y], z]', lambda x, y, z: ["^", x, ["*", y, z]]),
        ('["*", x, ["/", y, x]]', lambda x, y: y),
        ('["*", ["/", y, x], x]', lambda y, x: y),
        ('["/", ["*", x, y], x]', lambda x, y: y),
        ('["/", ["*", y, x], x]', lambda y, x: y),
        ('["+", x, ["-", x]]', lambda x: 0),
        ('["+", ["-", x], x]', lambda x: 0),
        ('["-", ["+", x, y], x]', lambda x, y: y),
        # move numbers to the left
        ('["*", s:str|s:list, n:Number]', lambda s, n: ["*", n, s]),
        # group numbers
        ('["*", n:Number, ["*", m:Number, x]]', lambda n, m, x: ["*", ["*", n, m], x]),
        ('["*", x, ["*", n:Number, y]]', lambda x, n, y: ["*", n, ["*", x, y]]),
        ('["*", ["*", n:Number, x], y]', lambda n, x, y: ["*", n, ["*", x, y]]),
        # for addition move numbers to the right
        ('["+", n:Number, s:str|s:list]', lambda n, s: ["+", s, n]),
        ('["+", ["+", x, m:Number], n:Number]', lambda x, m, n: ["+", x, ["+", n, m]]),
        ('["+", x, ["+", y, n:Number]]', lambda x, y, n: ["+", ["+", x, y], n]),
        ('["+", ["+", x, n:Number], y]', lambda x, n, y: ["+", ["+", x, y], n]),
        # log/trig rules
        # (, lambda: 0),
        ('["ln", 0]', lambda: Undefined()),
        ('["ln", "e"]', lambda: 1),
        ('["sin", 0]', lambda: 0),
        ('["sin", "pi"]', lambda: 0),
        ('["cos", 0]', lambda: 1),
        ('["cos", "pi"]', lambda: -1),
        ('["sin", ["/", "pi", 2]]', lambda: 1),
        ('["cos", ["/", "pi", 2]]', lambda: 0),
        ('["ln", ["^", "e", x]]', lambda x: x),
        ('["^", "e", ["ln", x]]', lambda x: x),
        ('["+", ["ln", x], ["ln", y]]', lambda x, y: ["ln", ["*", x, y]]),
        ('["-", ["ln", x], ["ln", y]]', lambda x, y: ["ln", ["/", x, y]]),
        ('["+", ["^", ["sin", x], 2], ["^", ["cos", x], 2]]', lambda x: 1),
        ('["+", ["^", ["cos", x], 2], ["^", ["sin", x], 2]]', lambda x: 1),
        # dx/dx = 1
        ('["D", x, x]', lambda x: 1),
        # d[u+v]/dx = du/dx + dv/dx
        ('["D", ["+", u, v], x]', lambda u, v, x: ["+", ["D", u, x], ["D", v, x]]),
        ('["D", ["-", u, v], x]', lambda u, v, x: ["-", ["D", u, x], ["D", v, x]]),
        ('["D", ["-", u], x]', lambda u, x: ["-", ["D", u, x]]),
        # product rule
        (
            '["D", ["*", u, v], x]',
            lambda u, v, x: ["+", ["*", u, ["D", v, x]], ["*", v, ["D", u, x]]],
        ),
        # quotient rule
        (
            '["D", ["/", u, v], x]',
            lambda u, v, x: [
                "/",
                ["-", ["*", v, ["D", u, x]], ["*", u, ["D", v, x]]],
                ["^", v, 2],
            ],
        ),
        # exponents
        (
            '["D", ["^", u, v], x]',
            lambda u, v, x: [
                "+",
                ["*", ["*", v, ["^", u, ["-", v, 1]]], ["D", u, x]],
                ["*", ["*", ["^", u, v], ["ln", u]], ["D", v, x]],
            ],
        ),
        ('["D", ["ln", u], x]', lambda u, x: ["/", ["D", u, x], u]),
        ('["D", ["sin", u], x]', lambda u, x: ["*", ["cos", u], ["D", u, x]]),
        ('["D", ["cos", u], x]', lambda u, x: ["-", ["*", ["sin", u], ["D", u, x]]]),
        ('["D", ["^", "e", u], x]', lambda u, x: ["*", ["^", "e", u], ["D", u, x]]),
        # if u doesn't depend on x, du/dx = 0
        ('["D", u, x]', lambda u, x: 0 if not appears(x, u) else False),
        # remove extra parentheses
        ("[x:list]", lambda x: x),
        # evaluate purely numeric expressions
        ('["+", m:Number, n:Number]', lambda m, n: m + n),
        ('["-", m:Number, n:Number]', lambda m, n: m - n),
        ('["*", m:Number, n:Number]', lambda m, n: m * n),
        ('["/", m:Number, n:Number]', lambda m, n: m / n),
        ('["^", m:Number, n:Number]', lambda m, n: m ** n),
        # ('["/", x, y]', lambda x, y: ["*", x, ["^", y, -1]]),
        # no match
        ("_", lambda: False),
    ]
)


def appears(x, expr):
    """recursively check if x appears in expr"""
    if isinstance(expr, list):
        return any(map(lambda expr: appears(x, expr), expr))
    else:
        return x == expr


def simplify_expr(expr):
    """match expression to the rules and simplify it accordingly"""
    if rules(expr) is not False:
        return simplify(rules(expr))
    else:
        return expr


def simplify(expr):
    """recursively simplify an expression"""
    if isinstance(expr, list):
        return simplify_expr(list(map(simplify, expr)))
    else:
        return expr


def str_simp(string):
    return pretty(simplify(parse(string)))


def flatten(l):
    """flattens infix operators"""
    if isinstance(l, list) and l[0] in list("+-*/^"):
        new_args = []
        for item in l[1:]:
            if isinstance(item, list) and item[0] == l[0]:
                new_args += flatten(item)[1:]
            else:
                new_args.append(flatten(item))
        return [l[0]] + new_args

    else:
        return l


def operator_greater(op1, op2):
    """tells if op1 has higher precidence than op2"""
    op_map = {None: 0, "+": 1, "-": 1, "*": 2, "/": 2, "^": 3}
    return op_map[op1] > op_map[op2]


def pretty_rules(l):
    l = flatten(l)
    if isinstance(l, list) and len(l) >= 3 and l[0] in list("+-*/^"):
        if l[0] == "*":
            if l[1] == -1:
                if len(l) > 3:
                    return ["-", ["*"] + l[2:]]
                else:
                    return ["-", l[2]]
        elif l[0] == "+":
            pass


def pretty(l, outer=None):
    l = flatten(l)
    print(l)
    if isinstance(l, list) and len(l) >= 3 and l[0] in list("-*/^"):
        separator = ""
        if l[0] not in "*":
            separator = f" {l[0]} "
        elif l[0] == "*":
            if l[1] == -1:
                return pretty(["+", ["*", -1,] + l[2:]])
            separator = " "
        # check if we need parentheses
        if outer is None or operator_greater(l[0], outer):
            return separator.join(list(map((lambda x: pretty(x, l[0])), l[1:])))
        else:
            return (
                "("
                + separator.join(list(map((lambda x: pretty(x, l[0])), l[1:])))
                + ")"
            )
    elif isinstance(l, list) and len(l) >= 2 and l[0] == "+":
        string = ""
        for argument in l[1:]:
            if (
                isinstance(argument, list)
                and len(argument) >= 3
                and argument[0] == "*"
                and isinstance(argument[1], Number)
                and argument[1] < 0
            ):
                if argument[1] == -1:
                    string += " - "
                else:
                    string += f" - {abs(argument[1])} "
                if len(argument) == 3:
                    string += pretty(argument[2], "+")
                else:
                    string += pretty(["*"] + argument[2:])
            elif isinstance(argument, Number) and argument < 0:
                string += f" - {abs(argument)}"
            else:
                string += " + "
                string += pretty(argument)
        # strip off leading space
        string = string[1:]
        # we don't need a leading plus
        if string[0] == "+":
            string = string[2:]
        return string if operator_greater("+", outer) else f"({string})"
    elif isinstance(l, list):
        # if l[0] == '-':
        #    return '(- ' + pretty(l[1]) + ')'
        args = []
        for arg in l[1:]:
            args.append(pretty(arg, None))
        return pretty(l[0], True) + "[" + ", ".join(args) + "]"
    else:
        return str(l)


def main():
    print("Welcome to SymSim, the symbolic expression simplifier.  Type ? for help.")
    while True:
        to_parse = ""
        try:
            to_parse = input("> ")
        except EOFError:
            break
        except KeyboardInterrupt:
            print(f"\nKeyboardInterrupt")
            continue
        if to_parse == "exit":
            break
        elif to_parse == "?":
            help = """You can enter expressions in these forms:
- (x op y) or (x op_expr ...) where op_expr is the pattern `op _`, and op is +, -, *, /, or ^.  Infix operators follow PEMDAS rules.
- (sin x), (cos x), (ln x)
- (D expr x), which represents the derivative of expr with respect to x
- Any combination of these forms.
Examples:
1 + 2 + 3 * 4 => 15
2(3) => 6
3 + x + 5 + x => 2 x + 8
sin[0] => 0
u^2 u^3 => u ^ 5
e^ln[v] => v
D[x, x] => 1
D[x^3, x] => 3 x ^ 2
D[cos[x^2], x] => -2 sin[x ^ 2] x
D[ln[u], u] => 1 / u
D[x ln[x], x] => ln[x] + 1
"""

            print(help)
        else:
            try:
                print(str_simp(to_parse))
            except LarkError as error:
                print(f"Invalid Syntax:\n{error}")
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt")


class Cell(tk.Frame):
    def __init__(self, master, number, position, app):
        tk.Frame.__init__(self, master)
        self.position = position
        self.number = number
        self.master = master
        self.app = app

        self.top_frame = tk.Frame(self)
        self.top_frame.pack(side="top", anchor="w", fill="x", expand=True)
        self.entry_text = tk.Label(self.top_frame)
        self.entry_text["text"] = f"In  [{self.number}]:"
        self.entry_text.pack(side="left", anchor="n")
        self.entry = tk.Entry(self.top_frame)
        self.entry.pack(side="left", fill="x", expand=True, anchor="n")
        self.entry.bind("<Return>", self.simplify_entry)
        self.entry.bind("<Up>", self.history_up)
        #       self.entry.bind("<Down>", self.history_down)

        self.bottom_frame = tk.Frame(self)
        self.output_label = tk.Label(self.bottom_frame)
        self.output_label["text"] = f"Out [{self.number}]:"
        self.output_label.pack(side="left", anchor="n")
        self.output = tk.Label(self.bottom_frame, justify="left")
        self.output.pack(side="left", anchor="n", fill="x")
        self.output.bind("<Button-1>", self.output_to_input)

        self.separator = ttk.Separator(self, orient="horizontal")
        self.separator.pack(side="bottom", fill="x", expand=True)

    def history_up(self, event):
        in_entry = self.entry.get()
        if in_entry in self.app.history:
            self.entry.delete(0, "end")
            self.entry.insert(0, self.app.history[self.app.history.index(in_entry) + 1])
        elif in_entry == "":
            self.entry.delete(0, "end")
            self.entry.insert(0, self.app.history[0])

    def output_to_input(self, event):
        text = self.output["text"]
        self.bottom_frame.pack_forget()
        self.app.create_cell(self.position + 1)
        self.app.cells[self.position + 1].entry.insert(0, text)
        for index in range(len(self.app.cells)):
            self.app.cells[index].position = index
        self.app.repack()

    def simplify_entry(self, event):
        self.app.history.insert(0, self.entry.get()) if self.entry.get() != "" else None
        result = str_simp(self.entry.get())
        self.output["text"] = result
        self.bottom_frame.pack(side="top", anchor="w", fill="x", expand=True)
        self.app.repack()
        if self.position + 1 == len(self.app.cells):
            self.app.create_cell(self.position + 1)


class Application:
    def __init__(self, master):
        self.canvas = tk.Canvas(master)
        self.scrollbar = tk.Scrollbar(
            self.canvas, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.frame = tk.Frame(master)
        self.frame.bind("<Configure>", self.reset_scrollregion)
        self.canvas.pack(side="top", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas_frame = self.canvas.create_window(
            (0, 0), window=self.frame, anchor="nw"
        )
        self.canvas.bind("<Configure>", self.change_frame_size)

        self.cells = []
        self.history = []
        self.create_cell(0)

    def change_frame_size(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width - 25)

    def repack(self):
        for cell in self.cells:
            cell.pack_forget()
            cell.pack(side="top", fill="x", expand=True, anchor="w")

    def create_cell(self, position):
        cell = Cell(
            master=self.frame, number=len(self.cells), position=position, app=self
        )
        cell.pack(side="top", fill="x", expand=True, anchor="w")
        self.cells.insert(position, cell)
        cell.entry.focus()

    def reset_scrollregion(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


def new():
    root = tk.Tk()
    root.title("SymSim")
    root.option_add("*Font", "TkFixedFont")
    root.geometry("500x500")
    app = Application(master=root)
    menubar = tk.Menu(root)
    filemenu = tk.Menu(menubar, tearoff=0)
    filemenu.add_command(label="New", command=new)
    filemenu.add_separator()
    filemenu.add_command(label="Exit", command=root.quit)
    menubar.add_cascade(label="File", menu=filemenu)
    root.config(menu=menubar)
    return root


if __name__ == "__main__":
    new().mainloop()
