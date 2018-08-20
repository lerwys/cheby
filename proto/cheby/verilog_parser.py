import hdlparse.verilog_parser as vlog_parser

def parse_verilog(filename):
    vlog_ex = vlog_parser.VerilogExtractor()
    vlog_mods = vlog_ex.extract_objects(filename)

    #for m in vlog_mods:
    #    print('Module "{}":'.format(m.name))
    #    print('  Parameters:')
    #    for p in m.generics:
    #        print('\t{:20}{:8}{:8}{:8}{} bits'.format(p.name, p.mode, p.data_type,
    #                                             p,range, p.size))
    #    print('  Ports:')
    #    for p in m.ports:
    #        print('\t{:20}{:8}{:6}{:8}{:8}{:4}{}'.format(p.name, p.mode, p.data_type, p.sign,
    #                                                      p.range, p.size, p.annotations if p.annotations else ''))
    #    print('  Sections:')
    #    for p, v in m.sections.items():
    #        print('\t{} {}'.format(p, v))

    return vlog_mods
