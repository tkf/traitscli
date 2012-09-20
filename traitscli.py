"""
Type-safe CLI generator based on class traits.
"""

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


def parse_dict_like_options(argiter):
    """
    Parse dict-like option (--dict['key']) in `argiter`.

    Return ``(opts, args)`` tuple.  `opts` is the dict-like option
    argument.  It is a list of 2-tuples ``(option, value)``.  `args`
    is rest of argument.

    >>> parse_dict_like_options(['--a[k]=b'])
    ([('a[k]', 'b')], [])
    >>> parse_dict_like_options(['--a[k]', 'b'])
    ([('a[k]', 'b')], [])

    """
    options = []
    positional = []
    argiter = iter(argiter)
    while True:
        try:
            arg = argiter.next()
        except StopIteration:
            return (options, positional)
        if arg.startswith('--') and len(arg) > 2 and arg[2].isalpha() \
           and '[' in arg:
            key = arg[2:]
            if '=' in key:
                options.append(tuple(key.split('=', 1)))
            else:
                options.append((key, argiter.next()))
        else:
            positional.append(arg)


def names_in_dict_like_options(dopts):
    """
    Return variable names in `dopts`.

    >>> names_in_dict_like_options([('a[k]', 'b'), ('c[k]', 'd')])
    ['a', 'c']

    """
    return [k.split('[', 1)[0] for (k, v) in dopts]


class InvalidDictLikeOptionError(Exception):

    def __init__(self, message):
        self.message


def parse_and_run(parser, args=None):
    if args is None:
        import sys
        args = sys.argv[1:]

    (dopts, args) = parse_dict_like_options(args)
    ns = parser.parse_args(args)
    try:
        return applyargs(__dict_like_options=dopts, **vars(ns))
    except InvalidDictLikeOptionError as e:
        parser.exit(e.message)


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
        parser = cls.get_argparser()
        return parse_and_run(parser, args)

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
        unknown = set(names_in_dict_like_options(dopts)) - set(ns)
        if unknown:
            unknown = tuple(unknown)
            clargs = ' '.join(
                '--{0}={1}'.format(k, v) for (k, v) in dopts
                if k.startswith(unknown))
            raise InvalidDictLikeOptionError(
                "Unknown dict-like options {0}".format(clargs))
        for (rhs, lhs) in dopts:
            # TODO: Check that rhs/lhs really an expression, rather
            #       than code containing ";" or "\n".
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
