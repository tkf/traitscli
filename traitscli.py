"""
Type-safe CLI generator based on class traits.
"""


from traits.api import (
    HasTraits, Bool, CBool, Complex, CComplex, Float, CFloat,
    Int, CInt, Long, CLong, Str, CStr, Unicode, CUnicode,
    Enum,
)

_trait_simple_type_map = {
    Bool: bool,
    CBool: bool,
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

    @classmethod
    def connect_subparser(cls, subpersers, name):
        return cls.add_parser(subpersers.add_parser(name))

    @classmethod
    def get_argparser(cls):
        from argparse import ArgumentParser
        parser = ArgumentParser(description=cls.__doc__)
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
            elif isinstance(v.trait_type, Enum):
                argkwds['choices'] = v.trait_type.values
            else:
                argkwds['type'] = eval
            parser.add_argument(dest, **argkwds)
        parser.set_defaults(func=cls.run)
        return parser

    @classmethod
    def cli(cls):
        """
        Call `cls.run` using command line arguments.
        """
        parser = cls.get_argparser()
        args = parser.parse_args()
        return applyargs(**vars(args))

    @classmethod
    def run(cls, **kwds):
        """
        Make an instance of this class with args `kwds` and call `do_run`.
        """
        self = cls(**kwds)
        self.do_run()
        return self

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
