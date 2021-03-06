"""Generate VHDL from HDL tree"""

import cheby.hdltree as hdltree

style = None

def w(fd, str):
    fd.write(str)


def wln(fd, str=""):
    w(fd, str)
    w(fd, '\n')


def windent(fd, indent):
    w(fd, '  ' * indent)


def generate_header(fd, module):
    wln(fd, "library ieee;")
    wln(fd, "use ieee.std_logic_1164.all;")
    wln(fd, "use ieee.numeric_std.all;")
    if module.libraries:
        wln(fd)
        for l in module.libraries:
            wln(fd, 'library {};'.format(l))
        wln(fd)
    for lib, pkg in module.deps:
        # It is OK in vhdl to duplicate use/library clauses.
        if lib != 'work':
            wln(fd, 'library {};'.format(lib))
        wln(fd, "use {}.{}.all;".format(lib, pkg))


def generate_type_mark(s):
    return {'L': 'std_logic_vector',
            'U': 'unsigned',
            'S': 'signed'}[s.typ]


def generate_vhdl_type(p):
    if p.size is not None:
        if isinstance(p.size, int):
            hi = str(p.lo_idx + p.size - 1)
        else:
            assert p.lo_idx == 0
            hi = generate_expr(p.size)
        return "{}({} downto {})".format(generate_type_mark(p), hi, p.lo_idx)
    else:
        assert p.typ in 'LINP', p.typ
        return {'L': 'std_logic',
                'I': 'integer', 'N': 'natural', 'P': 'positive'}[p.typ]


def generate_decl_comment(fd, comment, indent):
    if comment:
        if style != 'wbgen':
            wln(fd)
        windent(fd, indent)
        wln(fd, "-- {}".format(comment))


def generate_port(fd, p, indent):
    generate_decl_comment(fd, p.comment, indent)
    typ = generate_vhdl_type(p)
    if p.dir == 'IN':
        dir = "in   "
    elif p.dir == 'OUT':
        dir = "out  "
    else:
        dir = "inout"
    windent(fd, indent)
    w(fd, "{:<20} : {dir} {typ}".format(p.name, dir=dir, typ=typ))
    if p.default:
        w(fd,' := {}'.format(generate_expr(p.default)))


def generate_interface_port(fd, itf, dir, indent):
    for p in itf.ports:
        if p.dir == dir:
            windent(fd, indent + 1)
            wln(fd, "{:<16} : {};".format(p.name, generate_vhdl_type(p)))

def generate_interface(fd, itf, indent):
    generate_decl_comment(fd, itf.comment, indent)
    windent(fd, indent)
    wln(fd, "type {}_master_out is record".format(itf.name))
    generate_interface_port(fd, itf, 'OUT', indent)
    windent(fd, indent)
    wln(fd, "end record {}_master_out;".format(itf.name))
    windent(fd, indent)
    wln(fd, "subtype {0}_slave_in is {0}_master_out;".format(itf.name))
    wln(fd)
    windent(fd, indent)
    wln(fd, "type {}_slave_out is record".format(itf.name))
    generate_interface_port(fd, itf, 'IN', indent)
    windent(fd, indent)
    wln(fd, "end record {}_slave_out;".format(itf.name))
    windent(fd, indent)
    wln(fd, "subtype {0}_master_in is {0}_slave_out;".format(itf.name))


def generate_param(fd, p, indent):
    generate_decl_comment(fd, p.comment, indent)
    typ = generate_vhdl_type(p)
    windent(fd, indent)
    w(fd, "{} : {typ}".format(p.name, typ=typ))
    if p.value:
        w(fd, " := {}".format(generate_expr(p.value)))


def generate_signal(fd, s, indent):
    if s.size:
        typ = generate_vhdl_type(s)
    else:
        typ = "std_logic"
    windent(fd, indent)
    w(fd, "signal {:<30} : {typ};\n".format(s.name, typ=typ))


def generate_constant(fd, s, indent):
    typ = generate_vhdl_type(s)
    windent(fd, indent)
    w(fd, "constant {} : {} := {};".format(
        s.name, typ, generate_expr(s.value)))
    if hasattr(s, 'eol_comment'):
        w(fd, "--" + s.eol_comment)
    wln(fd)


def generate_component(fd, comp, indent):
    windent(fd, indent)
    wln(fd, "component {}".format(comp.name))
    print_inters_list(fd, comp.params, "generic", indent + 1)
    print_inters_list(fd, comp.ports, "port", indent + 1)
    windent(fd, indent)
    wln(fd, "end component;")


def generate_component_spec(fd, spec, indent):
    windent(fd, indent)
    wln(fd, "for all : {} use entity {};".format(spec.comp.name, spec.bind))


def generate_decl(fd, d, indent):
    if isinstance(d, hdltree.HDLSignal):
        generate_signal(fd, d, indent)
    elif isinstance(d, hdltree.HDLConstant):
        generate_constant(fd, d, indent)
    elif isinstance(d, hdltree.HDLComponent):
        generate_component(fd, d, indent)
    elif isinstance(d, hdltree.HDLComponentSpec):
        generate_component_spec(fd, d, indent)
    elif isinstance(d, hdltree.HDLComment):
        generate_comment(fd, d, indent)
    elif isinstance(d, hdltree.HDLInterface):
        generate_interface(fd, d, indent)
    else:
        raise AssertionError(d)


operator = {hdltree.HDLAnd: (' and ', 4),
            hdltree.HDLOr:  (' or ', 3),
            hdltree.HDLConcat: (' & ', 0),
            hdltree.HDLNot: ('not', 5),
            hdltree.HDLSub: ('-', 1),
            hdltree.HDLMul: ('*', 2),
            hdltree.HDLEq:  (' = ', 5),
            hdltree.HDLGe:  (' >= ', 5),
            hdltree.HDLLe:  (' <= ', 5)}


def generate_expr(e, prio=-1):
    if isinstance(e, hdltree.HDLObject):
        return e.name
    elif isinstance(e, hdltree.HDLBinary):
        opname, opprio = operator[type(e)]
        res = ''.join([generate_expr(e.left, opprio),
                       opname,
                       generate_expr(e.right, opprio)])
        if opprio <= prio:
            return "({})".format(res)
        else:
            return res
    elif isinstance(e, hdltree.HDLUnary):
        opname, opprio = operator[type(e)]
        res = "{} {}".format(opname, generate_expr(e.expr, opprio))
        if opprio <= prio:
            return "({})".format(res)
        else:
            return res
    elif isinstance(e, hdltree.HDLParen):
        return "({})".format(generate_expr(e.expr))
    elif isinstance(e, hdltree.HDLReplicate):
        return "(others => {})".format(generate_expr(e.expr))
    elif isinstance(e, hdltree.HDLZext):
        return "std_logic_vector(resize(unsigned({}), {}))".format(
            generate_expr(e.expr), e.size)
    elif isinstance(e, hdltree.HDLSext):
        return "std_logic_vector(resize(signed({}), {}))".format(
            generate_expr(e.expr), e.size)
    elif isinstance(e, hdltree.HDLBit):
        return "'{}'".format(e.val)
    elif isinstance(e, hdltree.HDLUndef):
        return "'X'"
    elif isinstance(e, hdltree.HDLHexConst):
        assert (e.size > 0 and (e.size % 4) == 0)
        res = 'X"'
        for i in range(e.size - 4, -1, -4):
            res += '{:X}'.format((e.val >> i) & 15)
        res += '"'
        return res
    elif isinstance(e, hdltree.HDLConst) or isinstance(e, hdltree.HDLBinConst):
        if e.size is None:
            # A bit.
            return "'{}'".format(e.val)

        # Certainly overkill, patches welcome!
        res = '"'
        for i in range(e.size - 1, -1, -1):
            res += '1' if ((e.val >> i) & 1) == 1 else '0'
        res += '"'
        return res
    elif isinstance(e, hdltree.HDLNumber):
        return "{}".format(e.val)
    elif isinstance(e, hdltree.HDLBool):
        if e.val:
            return "true"
        else:
            return "false"
    elif isinstance(e, hdltree.HDLSlice):
        if e.size is None:
            return "{}({})".format(generate_expr(e.prefix), e.index)
        else:
            return "{}({} downto {})".format(
                generate_expr(e.prefix), e.index + e.size - 1, e.index)
    elif isinstance(e, hdltree.HDLIndex):
        return "{}({})".format(generate_expr(e.prefix), e.index)
    elif isinstance(e, hdltree.HDLInterfaceSelect):
        # is_master means the direction is not reversed.
        sfx = 'i' if (e.subport.dir == 'IN') == (e.prefix.is_master) else 'o'
        return "{}_{}.{}".format(e.prefix.name, sfx, e.subport.name)
    else:
        assert False, "unhandled hdl expr {}".format(e)


def get_base_name(s):
    if isinstance(s, hdltree.HDLObject):
        return s
    elif isinstance(s, hdltree.HDLSlice) or isinstance(s, hdltree.HDLIndex):
        return get_base_name(s.prefix)
    elif isinstance(s, hdltree.HDLInterfaceSelect):
        return get_base_name(s.subport)
    else:
        return None


def generate_assign(fd, s):
    base_targ = get_base_name(s.target)
    base_expr = get_base_name(s.expr)
    targ = generate_expr(s.target)
    expr = generate_expr(s.expr)
    if base_expr is not None and base_targ.typ != base_expr.typ:
        wln(fd, "{} <= {}({});".format(
            targ, generate_type_mark(base_targ), expr))
    else:
        wln(fd, "{} <= {};".format(targ, expr))


def generate_seq(fd, s, level):
    indent = '  ' * level
    if isinstance(s, hdltree.HDLAssign):
        w(fd, indent)
        generate_assign(fd, s)
    elif isinstance(s, hdltree.HDLIfElse):
        w(fd, indent)
        while True:
            wln(fd, "if {} then".format(generate_expr(s.cond)))
            for s1 in s.then_stmts:
                generate_seq(fd, s1, level + 1)
            if s.else_stmts is not None:
                w(fd, indent)
                if style != 'wbgen' \
                   and len(s.else_stmts) == 1 \
                   and isinstance(s.else_stmts[0], hdltree.HDLIfElse):
                    w(fd, "els")
                    s = s.else_stmts[0]
                else:
                    wln(fd, "else")
                    for s1 in s.else_stmts:
                        generate_seq(fd, s1, level + 1)
                    break
            else:
                break
        w(fd, indent)
        wln(fd, "end if;")
    elif isinstance(s, hdltree.HDLSwitch):
        w(fd, indent)
        wln(fd, "case {} is".format(generate_expr(s.expr)))
        for c in s.choices:
            w(fd, indent)
            if isinstance(c, hdltree.HDLChoiceExpr):
                wln(fd, "when {} => ".format(generate_expr(c.expr)))
            elif isinstance(c, hdltree.HDLChoiceDefault):
                wln(fd, "when others =>")
            for s1 in c.stmts:
                generate_seq(fd, s1, level + 1)
        w(fd, indent)
        wln(fd, "end case;")
    elif isinstance(s, hdltree.HDLComment):
        w(fd, indent)
        wln(fd, "-- {}".format(s.comment))
    else:
        assert False, "unhandled hdl seq {}".format(s)


def generate_comment(fd, n, indent):
    if n.nl:
        wln(fd)
    if n.comment is not None:
        windent(fd, indent)
        wln(fd, "-- {}".format(n.comment))


def generate_stmts(fd, stmts, indent):
    sindent = "  " * indent
    gen_num = 0
    for s in stmts:
        if isinstance(s, hdltree.HDLComment):
            generate_comment(fd, s, indent)
        elif isinstance(s, hdltree.HDLAssign):
            w(fd, sindent)
            generate_assign(fd, s)
        elif isinstance(s, hdltree.HDLComb):
            w(fd, sindent)
            if s.name is not None:
                w(fd, '{}: '.format(s.name))
            w(fd, "process (")
            first = True
            for e in s.sensitivity:
                if first:
                    first = False
                else:
                    w(fd, ", ")
                w(fd, generate_expr(e))
            if style == 'wbgen':
                wln (fd, "  )")
                w(fd, sindent)
            else:
                w(fd, ") ")
            wln(fd, "begin")
            # wln(fd, "  begin")
            for s1 in s.stmts:
                generate_seq(fd, s1, 2)
            w(fd, "  end process")
            if s.name is not None:
                w(fd, ' {}'.format(s.name))
            wln(fd, ";")
        elif isinstance(s, hdltree.HDLSync):
            w(fd, sindent)
            if s.name is not None:
                w(fd, '{}: '.format(s.name))
            w(fd, "process ({}".format(generate_expr(s.clk)))
            if s.rst is not None:
                w(fd, ", {}".format(generate_expr(s.rst)))
            if style == 'wbgen':
                wln(fd, ')')
                w(fd, sindent)
                wln(fd, 'begin')
            else:
                wln(fd, ") begin")
            # wln(fd, sindent + "begin")
            if s.rst is not None:
                cond = "{} = '0'".format(generate_expr(s.rst))
                if style == 'wbgen':
                    cond = '(' + cond + ')'
                wln(fd, sindent + "  if {} then ".format(cond))
                for s1 in s.rst_stmts:
                    generate_seq(fd, s1, indent + 2)
                w(fd, sindent + "  elsif ")
            else:
                w(fd, sindent + "  if ")
            wln(fd, "rising_edge({}) then".format(
                generate_expr(s.clk)))
            for s1 in s.sync_stmts:
                generate_seq(fd, s1, indent + 2)
            wln(fd, sindent + "  end if;")
            w(fd, sindent + "end process")
            if s.name is not None:
                w(fd, ' {}'.format(s.name))
            wln(fd, ";")
        elif isinstance(s, hdltree.HDLInstance):
            wln(fd, sindent + "{}: {}".format(s.name, s.module_name))

            def generate_map(mapping, indent):
                first = True
                for p, e in mapping:
                    if first:
                        first = False
                    else:
                        wln(fd, ",")
                    w(fd, "  " * indent)
                    w(fd, "  {:<20} => {}".format(p, generate_expr(e)))
                wln(fd)
            if s.params:
                wln(fd, sindent + "  generic map (")
                generate_map(s.params, indent + 1)
                wln(fd, sindent + "  )")
            if s.conns:
                wln(fd, sindent + "  port map (")
                generate_map(s.conns, indent + 1)
                wln(fd, sindent + "  );")
            wln(fd, sindent)
        elif isinstance(s, hdltree.HDLGenIf):
            wln(fd, sindent + "genblock_{}: if ({}) generate".format(
                gen_num, generate_expr(s.cond)))
            generate_stmts(fd, s.stmts, indent + 1)
            wln(fd, sindent + "end generate genblock_{};".format(gen_num))
            gen_num += 1
        else:
            assert False, "unhandled hdl stmt {}".format(s)


def print_inters_list(fd, lst, name, indent):
    if not lst:
        return
    windent(fd, indent)
    wln(fd, "{} (".format(name))
    first = True
    for p in lst:
        if first:
            first = False
        else:
            wln(fd, ";")
        if isinstance(p, hdltree.HDLPort):
            generate_port(fd, p, indent + 1)
        elif isinstance(p, hdltree.HDLParam):
            generate_param(fd, p, indent + 1)
        elif isinstance(p, hdltree.HDLPortGroup):
            generate_decl_comment(fd, p.comment, indent + 1)
            group_typename = '{}_{}'.format(p.interface.name,
                'master' if p.is_master else 'slave')
            windent(fd, indent + 1)
            w(fd, "{:<20} : in    {}_in".format(p.name + '_i', group_typename))
            wln(fd, ";")
            windent(fd, indent + 1)
            w(fd, "{:<20} : out   {}_out".format(p.name + '_o', group_typename))
        else:
            raise AssertionError
    wln(fd)
    windent(fd, indent)
    wln(fd, ");")

def print_module(fd, module):
    if module.global_decls:
        generate_header(fd, module)
        wln(fd)
        wln(fd, "package {}_pkg is".format(module.name))
        for s in module.global_decls:
            generate_decl(fd, s, 1)
        wln(fd, "end {}_pkg;".format(module.name))
        wln(fd)

    generate_header(fd, module)
    if module.global_decls:
        wln(fd, "use work.{}_pkg.all;".format(module.name))
    wln(fd)
    wln(fd, "entity {} is".format(module.name))
    print_inters_list(fd, module.params, "generic", 1)
    print_inters_list(fd, module.ports, "port", 1)
    wln(fd, "end {};".format(module.name))
    wln(fd)
    wln(fd, "architecture syn of {} is".format(module.name))
    if style == 'wbgen':
        wln(fd)
    for s in module.decls:
        generate_decl(fd, s, 1)
    if style == 'wbgen':
        wln(fd)
    wln(fd, "begin")
    generate_stmts(fd, module.stmts, 1)
    wln(fd, "end syn;")

def print_package(fd, n):
    generate_header(fd, n)
    wln(fd)
    wln(fd, "package {} is".format(n.name))
    for d in n.decls:
        generate_decl(fd, d, 1)
    wln(fd, "end {};".format(n.name))

def print_vhdl(fd, n):
    if isinstance(n, hdltree.HDLModule):
        print_module(fd, n)
    elif isinstance(n, hdltree.HDLPackage):
        print_package(fd, n)
    else:
        raise AssertionError
