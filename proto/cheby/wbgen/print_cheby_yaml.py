import sys
import cheby.wbgen.tree as tree
import cheby.wbgen.layout as layout

# TODO:
#  xml-ize strings (description, name)
#  check identifiers are uniq and valid


class Writer_YAML(object):
    def __init__(self, file=sys.stdout, verbose=True, strict=True):
        self.file = file
        self.verbose = verbose
        self.block_addr = [0]
        self.indent = 0
        self.islist = [False]
        self.strict = strict      # True to keep strings as is.

    def wraw(self, s):
        """Raw write of string s."""
        self.file.write(s)

    def w(self, s):
        """Write s"""
        self.wraw(s)

    def windent(self):
        """Indent to current level."""
        self.w('  ' * self.indent)

    def wtext(self, text):
        """Write random text."""
        self.w(text)

    def wseq(self, name):
        self.windent()
        if self.islist[-1]:
            self.w('- ')
            self.indent += 1
        self.w('{}:\n'.format(name))
        self.indent += 1
        self.islist.append(False)

    def wlist(self, name):
        self.windent()
        self.w('{}:\n'.format(name))
        self.islist.append(True)

    def welist(self):
        """End list."""
        f = self.islist.pop()
        assert f

    def weseq(self):
        """End seq."""
        f = self.islist.pop()
        assert not f
        self.indent -= 1
        if self.islist[-1]:
            self.indent -= 1

    def wattr_yaml(self, name, val):
        self.windent()
        self.w('{}: {}\n'.format(name, val))

    def wattr_str(self, name, val):
        """Write attribute (only if not None)."""
        if val is None:
            return
        if isinstance(val, bool) or val == 'true' or val == 'false' or val == '':
            self.wattr_yaml(name, '"{}"'.format(val))
        elif ((len(val) > 0 and (val[0] == ' '
                                 or val[-1] == ' '
                                 or ':' in val))
              or val.isdigit()):
            self.wattr_yaml(name, '"' + val + '"')
        else:
            self.wattr_yaml(name, val)

    def wattr_bool(self, name, val):
        if val is None:
            return
        assert isinstance(val, bool)
        self.wattr_yaml(name, val)

    def wattr_num(self, name, val):
        if val is None:
            return
        self.wattr_yaml(name, "{}".format(val))

    def write_pre_comment(self, str):
        if not str:
            return
        for l in str.split('\n'):
            self.w('# {}\n'.format(l))

    def write_address(self, addr):
        self.wattr_num("address", "0x{:08x}".format(
                       (addr - self.block_addr[-1]) * layout.DATA_BYTES))

    def write_comment(self, txt, name='comment'):
        if txt is None:
            return
        self.windent()
        if self.strict:
            s = ''.join({"\n": r'\n', "\\": "\\\\"}.get(c, c) for c in txt)
            self.w('{}: "{}"\n'.format(name, s))
        else:
            self.w('{}: |\n'.format(name))
            self.indent += 1
            for l in txt.rstrip().split('\n'):
                self.windent()
                self.w(l.strip())
                self.w('\n')
            self.indent -= 1

    def write_field_content(self, n, parent):
        if n.reset_value is not None:
            self.wattr_num("preset", n.reset_value)
        elif n.value is not None:
            # Use preset to store CONSTANT value
            self.wattr_num("preset", n.value)
        self.wseq("x-wbgen")
        self.wattr_str("type", n.typ)
        if isinstance(parent, tree.FifoCSReg):
            self.wattr_str("kind", n.kind)
        elif not isinstance(parent, tree.AnyFifoReg):
            self.wattr_str("access_bus", n.access_bus)
            self.wattr_str("access_dev", n.access_dev)
        self.wattr_str("clock", n.clock)
        self.wattr_str("load", n.load)
        self.wattr_str("ack_read", n.ack_read)
        if n.size is not None and n.size == 1:
            # Explicit the size (range is a single value, so there is no
            # difference with no size)
            self.wattr_num("size", 1)
        if n.prefix is None:
            self.wattr_str("field_description", n.name)
            self.write_comment(n.desc, "field_comment")
        self.weseq()
        if n.typ == 'PASS_THROUGH':
            self.wseq("x-hdl")
            self.wattr_str("type", "wire")
            self.wattr_str("write-strobe", "True")
            self.weseq()

    def write_field(self, n, parent):
        self.wseq("field")
        # In wbgen, prefix is optionnal if there is only one child.
        if n.prefix is not None:
            name = n.prefix
        else:
            name = '' # parent.prefix
        self.wattr_str("name", name)
        if n.bit_len != 1:
            self.wattr_str("range",
                           "{}-{}".format(n.bit_offset + n.bit_len - 1,
                                          n.bit_offset))
        else:
            self.wattr_num("range", n.bit_offset)
        self.wattr_str("description", n.name)
        self.write_comment(n.desc)
        self.write_field_content(n, parent)
        self.weseq()

    def write_reg(self, n):
        # Compute access mode
        acc = "--"
        accmap = {'--': {'READ_ONLY': 'ro',
                         'WRITE_ONLY': 'wo',
                         'READ_WRITE': 'rw'},
                  'ro': {'READ_ONLY': 'ro',
                         'WRITE_ONLY': 'rw',
                         'READ_WRITE': 'rw'},
                  'wo': {'READ_ONLY': 'rw',
                         'WRITE_ONLY': 'wo',
                         'READ_WRITE': 'rw'},
                  'rw': {'READ_ONLY': 'rw',
                         'WRITE_ONLY': 'rw',
                         'READ_WRITE': 'rw'}}
        for f in n.fields:
            facc = f.access_bus
            if facc is None:
                facc = {'PASS_THROUGH': 'WRITE_ONLY',
                        'MONOSTABLE': 'WRITE_ONLY',
                        'CONSTANT': 'READ_ONLY',
                        'SLV': 'READ_WRITE',
                        'BIT': 'READ_WRITE'}[f.typ]
            acc = accmap[acc][facc]
        self.write_pre_comment(n.pre_comment)
        self.wseq("reg")
        self.wattr_str("name", n.prefix)
        self.write_address(n.addr_base)
        self.wattr_num("width", layout.DATA_WIDTH)
        self.wattr_str("access", acc)
        self.wattr_str("description", n.name)
        self.write_comment(n.desc)
        if isinstance(n, tree.FifoCSReg):
            self.wseq("x-wbgen")
            self.wattr_str("kind", "fifocs")
            self.weseq()
        if (len (n.fields) == 1
            and n.fields[0].prefix is None
            and n.fields[0].size == layout.DATA_WIDTH):
            f = n.fields[0]
            if f.desc is not None:
                if n.desc is None:
                    self.write_comment(f.desc)
            self.write_field_content(n.fields[0], n)
        else:
            self.wlist("children")
            for f in n.fields:
                self.write_field(f, n)
            self.welist()
        wr_strobe = any([f.load == 'LOAD_EXT' for f in n.fields])
        rd_strobe = any([f.ack_read for f in n.fields])
        if wr_strobe or rd_strobe:
            self.wseq("x-hdl")
            if wr_strobe:
                self.wattr_str("write-strobe", "True")
            if rd_strobe:
                self.wattr_str("read-strobe", "True")
            self.weseq()
        self.weseq()

    def write_fifo(self, n):
        self.write_pre_comment(n.pre_comment)
        addr = n.regs[0].addr_base
        self.wseq("block")
        self.wattr_str("name", n.prefix)
        self.write_address(addr)
        self.wattr_num("size", len(n.regs) * layout.DATA_BYTES)
        self.wattr_str("description", n.name)
        self.write_comment(n.desc)
        self.wattr_str("align", 'False')

        self.wseq("x-wbgen")
        self.wattr_str("kind", "fifo")
        self.wattr_str("direction", n.direction)
        self.wattr_num("depth", n.size)
        self.wattr_str("clock", n.clock)
        if 'FIFO_FULL' in n.flags_dev:
            self.wattr_str("wire_full", 'True')
        if 'FIFO_EMPTY' in n.flags_dev:
            self.wattr_str("wire_empty", 'True')
        if 'FIFO_COUNT' in n.flags_dev:
            self.wattr_str("wire_count", 'True')
        self.wattr_str("optional", n.optional)
        self.weseq()

        self.wlist("children")
        self.block_addr.append(addr)
        for r in n.regs:
            r.pre_comment = None
            self.write_reg(r)
        self.block_addr.pop()
        self.welist()
        self.weseq()

    def write_ram(self, n):
        # self.write_pre_comment(n.pre_comment)
        addr = n.addr_base
        self.wseq("array")
        self.wattr_str("name", n.prefix)
        self.write_address(addr)
        self.wattr_num("repeat", n.size)
        self.wattr_str("description", n.name)
        self.write_comment(n.desc)
        self.wattr_str("align", 'True')

        self.wseq("x-wbgen")
        self.wattr_str("kind", 'ram')
        self.wattr_str("access_dev", n.access_dev)
        self.wattr_str("clock", n.clock)
        self.wattr_bool("byte_select", n.byte_select)
        self.weseq()

        self.wlist("children")
        self.wseq("reg")
        self.wattr_str("name", 'data')
        self.wattr_num("width", n.width)
        accmap = {'READ_ONLY': 'ro', 'WRITE_ONLY': 'wo', 'READ_WRITE': 'rw'}
        self.wattr_str("access", accmap[n.access_bus])
        self.weseq()
        self.welist()
        self.weseq()

    def write_irqs(self, regs, irqs):
        # self.write_pre_comment(n.pre_comment)
        addr = regs[0].addr_base
        self.wseq("block")
        self.wattr_str("name", "eic")
        self.write_address(addr)
        self.wattr_str("align", 'False')

        self.wseq("x-wbgen")
        self.wattr_str("kind", 'irq')
        self.wlist("irqs")
        for irq, pos in irqs:
            self.wseq("irq")
            self.wattr_str("name", irq.prefix)
            self.wattr_str("trigger", irq.trigger)
            self.wattr_num("pos", pos)
            self.wattr_bool("ack_line", irq.ack_line)
            self.wattr_bool("mask_line", irq.mask_line)
            self.wattr_str("description", irq.name)
            self.write_comment(irq.desc)
            self.weseq()
        self.welist()
        self.weseq()

        self.wlist("children")
        self.block_addr.append(addr)
        for r in regs:
            r.pre_comment = None
            self.write_reg(r)
        self.block_addr.pop()
        self.welist()
        self.weseq()

    def write_top(self, n):
        self.write_pre_comment(n.pre_comment)
        self.wseq('memory-map')
        self.wattr_str("bus", 'wb-32-be')
        self.wattr_str("name", n.prefix if n.prefix else n.hdl_prefix)
        self.wattr_str("description", n.name)
        self.write_comment(n.desc)
        self.wseq("x-wbgen")
        self.wattr_str("hdl_entity", n.hdl_entity)
        self.wattr_str("hdl_prefix", n.hdl_prefix)
        self.wattr_str("c_prefix", n.c_prefix)
        self.weseq()
        self.wlist("children")
        # Gather irqs
        irqs = []
        irq_regs = []
        pos = 0
        for r in n.regs:
            if isinstance(r, tree.IrqReg):
                irq_regs.append(r)
            elif isinstance(r, tree.Irq):
                irqs.append((r, pos))
            pos += 1
        # Generate
        for r in n.regs:
            if isinstance(r, tree.Reg):
                self.write_reg(r)
            elif isinstance(r, tree.Fifo):
                self.write_fifo(r)
            elif isinstance(r, tree.Ram):
                self.write_ram(r)
            elif isinstance(r, tree.IrqReg):
                pass
            elif isinstance(r, tree.FifoReg):
                pass
            elif isinstance(r, tree.FifoCSReg):
                pass
            elif isinstance(r, tree.Irq):
                pass
            else:
                assert False, "unhandled register {}".format(r)
        # Generate for irqs
        if irqs:
            self.write_irqs(irq_regs, irqs)
        self.welist()
        self.weseq()


def print_cheby(stream, n, strict=True):
    Writer_YAML(file=stream, strict=strict).write_top(n)
