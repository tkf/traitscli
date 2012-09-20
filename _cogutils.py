import os
import subprocess
from itertools import imap, chain

try:
    import cog
except ImportError:
    pass

SAMPLE = 'sample.py'


def sample_run_lines(args):
    command = ['python', SAMPLE] + args
    proc = subprocess.Popen(command,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            cwd=os.path.dirname(__file__) or None)
    return chain([' '.join(['$'] + command)],
                 read_striped_lines(proc.stdout))


def read_striped_lines(file):
    return imap(str.rstrip, iter(file.readline, ''))


def indent_lines(lines, indent=2):
    temp = " " * indent + "{0}"
    for l in lines:
        yield temp.format(l) if l else l


def inject_literal_block(desc, lines):
    cog.out("\n{0}::\n\n".format(desc))
    cog.outl("\n".join(indent_lines(lines)))
    cog.outl()


def inject_sample_run():
    inject_literal_block(
        'Example run',
        chain(
            sample_run_lines(['--help']),
            [''],
            sample_run_lines(['--yes', '--choice', 'a']),
            [''],
            sample_run_lines(['--inum', 'invalid_argument'])))


def inject_sample_source():
    inject_literal_block('Source code', read_striped_lines(open(SAMPLE)))


def inject_sample_doc():
    inject_sample_source()
    inject_sample_run()


def inject_readme():
    cog.outl(
        '"""\n{0}\n"""'
        .format("".join(strip_cog_lines(file('README.rst').readlines()))))


def strip_cog_lines(lines):
    for l in lines:
        if '[[[cog' in l:       # assuming no multiple cog line!
            continue
        if '[[[end]]]' in l:
            continue
        yield l
