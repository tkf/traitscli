"""
Type-safe CLI generator based on class traits.
"""

from itertools import imap

from traits.api import (
    HasTraits, Bool, CBool, Complex, CComplex, Float, CFloat,
    Int, CInt, Long, CLong, Str, CStr, Unicode, CUnicode,
    Enum,
)

_trait_simple_type_map = {
    Complex: complex,
    CComplex: complex,
    Float: float,
    CFloat: float,
    Int: int,
    CInt: int,
    Long: long,
    CLong: long,
    Str: str,
    CStr: str,
    Unicode: unicode,
    CUnicode: unicode,
}


def trait_simple_type(trait):
    for (tr, ty) in _trait_simple_type_map.iteritems():
        if isinstance(trait, tr):
            return ty


def parse_dict_like_options(argiter, names):
    """
    Parse dict-like option (--dict['key']) in `argiter`.

    Options only listed in `names` will be parsed.

    Return ``(opts, args)`` tuple.  `opts` is the dict-like option
    argument.  It is a list of 2-tuples ``(option, value)``.  `args`
    is rest of argument.

    >>> parse_dict_like_options(['--a[k]=b'], ['a'])
    ([('a[k]', 'b')], [])
    >>> parse_dict_like_options(['--a[k]', 'b'], ['a'])
    ([('a[k]', 'b')], [])
    >>> parse_dict_like_options(['--a[k]', 'b'], [])
    ([], ['--a[k]', 'b'])

    """
    options = []
    positional = []
    argiter = iter(argiter)
    option_prefixes = map("--{0}[".format, names)
    is_dict_like_opt = lambda x: any(imap(x.startswith, option_prefixes))
    while True:
        try:
            arg = argiter.next()
        except StopIteration:
            return (options, positional)
        if is_dict_like_opt(arg):
            key = arg[2:]
            if '=' in key:
                options.append(tuple(key.split('=', 1)))
            else:
                options.append((key, argiter.next()))
        else:
            positional.append(arg)


class TraitsCLIBase(HasTraits):

    """
    CLI generator base class.

    Usage.  You will need to define:

    1. Parameters (traits).  When it has `config` metadata, it is
       configurable via command line argument.
       See:
       http://github.enthought.com/traits/traits_user_manual/defining.html

    2. `do_run` method.  This method gets no argument (except `self`).
       Do whatever this class needs to do based on its attributes.
       `cli` function sets attributes based on command line options
       and then call `do_run` method.

    """

    from argparse import ArgumentParser
    ArgumentParser = ArgumentParser  # to cheat pyflake...

    @classmethod
    def connect_subparser(cls, subpersers, name):
        return cls.add_parser(subpersers.add_parser(name))

    @classmethod
    def get_argparser(cls):
        parser = cls.ArgumentParser(description=cls.__doc__)
        cls.add_parser(parser)
        return parser

    @classmethod
    def add_parser(cls, parser):
        """
        Call `parser.add_argument` based on class traits of `cls`.
        """
        traits = cls.class_traits(config=True)
        for k in sorted(traits):
            v = traits[k]
            dest = '--{0}'.format(k)
            argkwds = dict(default=v.default)
            argkwds['help'] = ''.join(
                ([v.desc, ' '] if v.desc else []) + ['(default: %(default)s)'])
            stype = trait_simple_type(v.trait_type)
            if stype:
                argkwds['type'] = stype
            elif isinstance(v.trait_type, (Bool, CBool)):
                argkwds.update(
                    action='store_const',
                    default=v.trait_type.default_value,
                    const=not v.trait_type.default_value,
                )
            elif isinstance(v.trait_type, Enum):
                argkwds['choices'] = v.trait_type.values
            else:
                argkwds['type'] = eval
            parser.add_argument(dest, **argkwds)
        parser.set_defaults(func=cls.run)
        return parser

    @classmethod
    def cli(cls, args=None):
        """
        Call `cls.run` using command line arguments.

        When `args` is given, it is used instead of ``sys.argv[1:]``.

        """
        if args is None:
            import sys
            args = sys.argv[1:]

        (dopts, args) = parse_dict_like_options(args, cls.config_names())
        parser = cls.get_argparser()
        ns = parser.parse_args(args)
        return applyargs(__dict_like_options=dopts, **vars(ns))

    @classmethod
    def run(cls, **kwds):
        """
        Make an instance of this class with args `kwds` and call `do_run`.
        """
        dopts = kwds.pop('__dict_like_options', [])
        self = cls(**kwds)
        self.__eval_dict_like_options(dopts)
        self.do_run()
        return self

    def __eval_dict_like_options(self, dopts):
        ns = self.config()
        for (rhs, lhs) in dopts:
            exec '{0} = {1}'.format(rhs, lhs) in ns

    @classmethod
    def config_names(cls, **metadata):
        """Get trait attribute names of this class."""
        return cls.class_trait_names(config=True, **metadata)

    def config(self, **metadata):
        """
        Return a dict of configurable attributes of this instance.

        See `self.traits` for the usage of `metadata`.
        Note that ``config=True`` is already specified.

        """
        names = self.config_names(**metadata)
        return dict((n, getattr(self, n)) for n in names)

    def do_run(self):
        """
        Actual implementation of `self.run`.

        Child class must implement this method.

        """


def applyargs(func, **kwds):
    return func(**kwds)


def multi_command_cli(name_class_pairs):
    """
    Launch CLI to call multiple classes.

    Usage::

      multi_command_cli([
          ('init', DoInit),
          ('checkout', DoCheckout),
          ('branch', DoBranch),
      ])

    """
    from argparse import ArgumentParser
    parser = ArgumentParser()
    subpersers = parser.add_subparsers()
    for (name, cls) in name_class_pairs:
        cls.connect_subparser(subpersers, name)
    args = parser.parse_args()
    return applyargs(**vars(args))
