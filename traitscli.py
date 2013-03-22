# [[[cog import _cogutils as _; _.inject_readme()]]]
"""
Traits CLI - CLI generator based on class traits
================================================

Traits CLI is based on Enthought's Traits_ library.

Some benefits:

* Automatically set type (int/float/...) of command line argument.
* Help string generation.
* "Deep value"" configuration:
  e.g., ``--dict['a']['b']['c']=1`` is equivalent to
  ``obj.dict['a']['b']['c'] = 1`` in Python code.
* Nested class configuration:
  e.g., ``--sub.attr=val`` is equivalent to
  ``obj.sub.attr = val`` in Python code.
* Parameter file support (ini/conf, json, yaml, etc.).
  Load parameter from file then set attribute.

.. _traits: https://github.com/enthought/traits


Links
-----

* `Documentaions (at Read the Docs) <http://traits-cli.readthedocs.org/>`_
* `Source code repository (at GitHub) <https://github.com/tkf/traitscli>`_
* `Issue tracker (at GitHub) <https://github.com/tkf/traitscli/issues>`_
* `PyPI <http://pypi.python.org/pypi/traitscli>`_
* `Travis CI <https://travis-ci.org/#!/tkf/traitscli>`_


Installation
------------
::

  pip install traitscli


Dependencies
------------

- traits_
- argparse (for Python < 2.7)


Sample
------


Source code::

  from traitscli import TraitsCLIBase
  from traits.api import Bool, Float, Int, Str, Enum


  class SampleCLI(TraitsCLIBase):

      '''
      Sample CLI using `traitscli`.

      Example::

        %(prog)s --yes                # => obj.yes = True
        %(prog)s --string something   # => obj.string = 'string'
        %(prog)s --choice x           # => raise error (x is not in {a, b, c})

      '''

      # These variables are configurable by command line option
      yes = Bool(desc='yes flag for sample CLI', config=True)
      no = Bool(True, config=True)
      fnum = Float(config=True)
      inum = Int(config=True)
      string = Str(config=True)
      choice = Enum(['a', 'b', 'c'], config=True)

      # You can have "internal" attributes which cannot be set via CLI.
      not_configurable_from_cli = Bool()

      def do_run(self):
          names = self.class_trait_names(config=True)
          width = max(map(len, names))
          for na in names:
              print "{0:{1}} : {2!r}".format(na, width, getattr(self, na))


  if __name__ == '__main__':
      # Run command line interface
      SampleCLI.cli()


Example run::

  $ python sample.py --help
  usage: sample.py [-h] [--choice {a,b,c}] [--fnum FNUM] [--inum INUM] [--no]
                   [--string STRING] [--yes]

  Sample CLI using `traitscli`.

  Example::

    sample.py --yes                # => obj.yes = True
    sample.py --string something   # => obj.string = 'string'
    sample.py --choice x           # => raise error (x is not in {a, b, c})

  optional arguments:
    -h, --help        show this help message and exit
    --choice {a,b,c}  (default: a)
    --fnum FNUM       (default: 0.0)
    --inum INUM       (default: 0)
    --no              (default: True)
    --string STRING   (default: )
    --yes             yes flag for sample CLI (default: False)

  $ python sample.py --yes --choice a
  string : ''
  no     : True
  fnum   : 0.0
  choice : 'a'
  inum   : 0
  yes    : True

  $ python sample.py --inum invalid_argument
  usage: sample.py [-h] [--choice {a,b,c}] [--fnum FNUM] [--inum INUM] [--no]
                   [--string STRING] [--yes]
  sample.py: error: argument --inum: invalid int value: 'invalid_argument'


"""
# [[[end]]]

__version__ = '0.1.0'
__author__ = 'Takafumi Arakaki'
__license__ = 'BSD License'
__all__ = ['TraitsCLIBase', 'multi_command_cli', 'flattendict']


import os
import re
import argparse
import ast
from contextlib import contextmanager

from traits.api import (
    HasTraits, Bool, CBool, Complex, CComplex, Float, CFloat,
    Int, CInt, Long, CLong, Str, CStr, Unicode, CUnicode,
    Dict, List, Enum, Instance,
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


class TraitsCLIAttributeError(Exception):

    def __init__(self, message):
        self.args = (message,)
        self.message


class InvalidDictLikeOptionError(TraitsCLIAttributeError):
    pass


_UNSPECIFIED = object()


def parse_and_run(parser, args=None):
    """
    Parse command line `args` using `parser` and run function of it.

    `Namespace` object `ns` returned by ``parser.parse_args(args)``
    must satisfy the following constraints:

    * It has `func` attribute which is an callable object.
      (i.e., you should set it by ``parser.set_default(func=some_callable)``.)
    * The callable `ns.func` can take rest of attributes defined in
      the `Namespace` object.
    * The callable `ns.func` can also take `__dict_like_options`
      keyword argument.  This is the first part of the tuple returned
      by `parse_dict_like_options`.

    `ns.func` is typically `TraitsCLIBase.run`.
    It is set in `TraitsCLIBase.add_parser`.

    """
    if args is None:
        import sys
        args = sys.argv[1:]

    def applyargs(func, **kwds):
        # Strip off unspecified arguments so that attributes set by
        # parameter file will not be override default values.
        # See `TraitsCLIBase.run` (actually, it's `func` here) for
        # the timing of `TraitsCLIBase.load_all_paramfiles`.
        return func(**dict((k, v) for (k, v) in kwds.iteritems()
                           if v is not _UNSPECIFIED))

    (dopts, args) = parse_dict_like_options(args)
    try:
        ns = parser.parse_args(args)
        return applyargs(__dict_like_options=dopts, **vars(ns))
    except TraitsCLIAttributeError as e:
        parser.exit(e.message)


def assert_expr(code, valuetype=ast.expr):
    """
    Raise an error when `code` is not an expression.

    >>> assert_expr('0')
    >>> assert_expr('a[1]')
    >>> assert_expr('a[1] + b.c')
    >>> assert_expr('a; b')  #doctest: +NORMALIZE_WHITESPACE
    Traceback (most recent call last):
      ...
    TraitsCLIAttributeError: 2 nodes (> 1) in code `a; b`.
    Only one expression is allowed.
    >>> assert_expr('print 1')  #doctest: +NORMALIZE_WHITESPACE
    Traceback (most recent call last):
      ...
    TraitsCLIAttributeError: `print 1` is not an expression.
    Only expression is allowed.
    >>> assert_expr('1 + 2', ast.Subscript)  #doctest: +NORMALIZE_WHITESPACE
    Traceback (most recent call last):
      ...
    TraitsCLIAttributeError: Node type of `1 + 2` does not match with
    <class '_ast.Subscript'>

    """
    nodes = list(ast.iter_child_nodes(ast.parse(code)))
    num = len(nodes)
    if num == 0:
        return
    if num > 1:
        raise TraitsCLIAttributeError(
            "{0} nodes (> 1) in code `{1}`. "
            "Only one expression is allowed.".format(num, code))

    node = nodes[0]
    if not isinstance(node, ast.Expr):
        raise TraitsCLIAttributeError(
            "`{0}` is not an expression. "
            "Only expression is allowed.".format(code))
    if not isinstance(node.value, valuetype):
        raise TraitsCLIAttributeError(
            "Node type of `{0}` does not match with {1}"
            .format(code, valuetype))


def eval_for_parser(code):
    try:
        return eval(code)
    except NameError as e:
        raise TraitsCLIAttributeError(
            'Got {0!r} wile evaluating {1}'.format(e, code))


def flattendict(dct):
    """
    Flatten dictionary using key concatenated by dot.

    >>> flattendict({'a': 1, 'b': 2}) == {'a': 1, 'b': 2}
    True
    >>> flattendict({'a': 1, 'b': {'c': 2}}) == {'a': 1, 'b.c': 2}
    True

    """
    flatten = {}
    join = '{0}.{1}'.format
    for (k, v) in dct.iteritems():
        if isinstance(v, dict):
            for (j, u) in flattendict(v).iteritems():
                flatten[join(k, j)] = u
        else:
            flatten[k] = v
    return flatten


def splitdottedname(dottedname):
    return (dottedname if isinstance(dottedname, (tuple, list))
            else dottedname.split('.'))


def getdottedattr(object, dottedname):
    """
    `getattr` which works with dot-separated name.

    `object` is same as in `getattr`.
    `dottedname` can be dot-separated name (string) or already
    separated name (tuple or list).

    >>> class Dotty(object):
    ...     pass
    >>> a = Dotty()
    >>> a.b = Dotty()
    >>> a.b.c = 'value'
    >>> getdottedattr(a, 'b.c')  # dotty access
    'value'
    >>> getdottedattr(a.b, 'c')  # works like normal `getattr`
    'value'

    """
    for name in splitdottedname(dottedname):
        object = getattr(object, name)
    return object


def setdottedattr(object, dottedname, value):
    """
    `setattr` which works with dot-separated name.

    `object` and `value` are same as in `setattr`.
    `dottedname` can be dot-separated name (string) or already
    separated name (tuple or list).

    >>> class Dotty(object):
    ...     pass
    >>> a = Dotty()
    >>> a.b = Dotty()
    >>> setdottedattr(a, 'b.c', 'value')  # dotty access
    >>> a.b.c
    'value'
    >>> setdottedattr(a.b, 'd', 'value')  # works like normal `setattr`
    >>> a.b.d
    'value'

    """
    names = splitdottedname(dottedname)
    setattr(getdottedattr(object, names[:-1]), names[-1], value)


def cleanup_dict(dct,
                 allow=re.compile('^[a-zA-Z_][a-zA-Z0-9_]*$'),
                 deny=re.compile('^_.*_$')):
    """
    Clean up dictionary using allowed and denied regular expression of
    keys.

    >>> d = {'a':1, 'b':2, '0':3 , '__hidden__':4}
    >>> dnew = cleanup_dict(d)
    >>> sorted(dnew)
    ['a', 'b']
    >>> [dnew[k] for k in sorted(dnew)]
    [1, 2]
    >>> dnew = cleanup_dict(d, allow=None)
    >>> sorted(dnew)
    ['0', 'a', 'b']
    >>> [dnew[k] for k in sorted(dnew)]
    [3, 1, 2]
    >>> dnew = cleanup_dict(d, deny=None)
    >>> sorted(dnew)
    ['__hidden__', 'a', 'b']
    >>> [dnew[k] for k in sorted(dnew)]
    [4, 1, 2]
    >>> dnew = cleanup_dict(d, allow='a|0')
    >>> sorted(dnew)
    ['0', 'a']
    >>> [dnew[k] for k in sorted(dnew)]
    [3, 1]

    """
    if isinstance(allow, basestring):
        allow = re.compile(allow)
    if isinstance(deny, basestring):
        deny = re.compile(deny)
    if allow is None:
        isallowed = lambda x: True
    else:
        isallowed = allow.match
    if deny is None:
        isdenied = lambda x: False
    else:
        isdenied = deny.match

    return dict([
        (k, dct[k]) for k in dct
        if isinstance(k, basestring) and isallowed(k) and not isdenied(k)])


@contextmanager
def hidestderr():
    try:
        import sys
        orig = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        yield
        sys.stderr.close()
    finally:
        sys.stderr = orig


def add_parser(cls, parser, prefix=''):
    """
    Call `parser.add_argument` based on class traits of `cls`.

    This classmethod is called from :meth:`get_argparser`.

    """
    traits = cls.class_traits(config=True)
    for k in sorted(traits):
        v = traits[k]

        if (isinstance(v.trait_type, Instance) and
                issubclass(v.trait_type.klass, HasTraits)):
            if issubclass(v.trait_type.klass, TraitsCLIBase):
                adder = v.trait_type.klass.add_parser
            else:
                adder = lambda *args: add_parser(v.trait_type.klass, *args)
            adder(parser, prefix + k + '.')
            # set_defaults is called here and it's redundant...
            # but as there is no harm, let it be like this for now.
            continue

        dest = name = '{0}{1}'.format(prefix, k)
        argkwds = dict(
            help='{0} (default: {1})'.format(v.desc or '', v.default),
        )
        if not v.cli_positional:
            name = '--{0}'.format(dest)
        for arg_key in ['required', 'metavar']:
            attr_val = getattr(v, 'cli_{0}'.format(arg_key))
            if attr_val is not None:
                argkwds[arg_key] = attr_val
        stype = trait_simple_type(v.trait_type)
        if stype:
            argkwds['type'] = stype
        elif isinstance(v.trait_type, (Bool, CBool)) and \
             not v.cli_positional:
            argkwds.update(
                action='store_const',
                const=not v.trait_type.default_value,
            )
        elif isinstance(v.trait_type, Enum):
            argkwds['choices'] = v.trait_type.values
        else:
            argkwds['type'] = eval_for_parser
        parser.add_argument(name, default=_UNSPECIFIED, **argkwds)
    if issubclass(cls, TraitsCLIBase):
        parser.set_defaults(func=cls.run)
    return parser


def config_traits(cls, **metadata):
    """
    Return configurable traits as a (possibly nested) dict.

    The returned dict can be nested if this class has `Instance`
    trait of :class:`TraitsCLIBase`.  Use :func:`flattendict` to
    get a flat dictionary with dotted keys.

    It is equivalent to ``cls.class_traits(config=True)`` if
    ``cls`` has no `Instance` trait.

    >>> class SubObject(TraitsCLIBase):
    ...     int = Int(config=True)
    ...
    >>> class SampleCLI(TraitsCLIBase):
    ...     nonconfigurable = Int()
    ...     int = Int(config=True)
    ...     sub = Instance(SubObject, args=(), config=True)
    ...
    >>> traits = SampleCLI.config_traits()
    >>> traits                                         # doctest: +SKIP
    {'int': <traits.traits.CTrait at ...>,
     'sub': {'int': <traits.traits.CTrait at ...>}}
    >>> traits['int'].trait_type                   # doctest: +ELLIPSIS
    <traits.trait_types.Int object at ...>
    >>> traits['sub']['int'].trait_type            # doctest: +ELLIPSIS
    <traits.trait_types.Int object at ...>

    """
    traits = {}
    for (k, v) in cls.class_traits(config=True).iteritems():
        if (isinstance(v.trait_type, Instance) and
                issubclass(v.trait_type.klass, HasTraits)):
            if issubclass(v.trait_type.klass, TraitsCLIBase):
                traits[k] = v.trait_type.klass.config_traits()
            else:
                traits[k] = config_traits(v.trait_type.klass)
        else:
            traits[k] = v
    return traits


class TraitsCLIBase(HasTraits):

    """
    CLI generator base class.

    Usage.  You will need to define:

    1. Parameters (traits).  When it has ``config=True`` metadata, it is
       configurable via command line argument.
       See: `Defining Traits: Initialization and Validation`_
       section in `Traits user manual`_.

    2. :meth:`do_run` method.  This method gets no argument (except `self`).
       Do whatever this class needs to do based on its attributes.
       :meth:`cli` function sets attributes based on command line options
       and then call :meth:`do_run` method.


    **Examples**

    To make class attribute configurable from command line options,
    set metadata ``config=True``:

    >>> class SampleCLI(TraitsCLIBase):
    ...     int = Int(config=True)
    ...
    >>> obj = SampleCLI.cli(['--int', '1'])
    >>> obj.int
    1


    For dict and list type attribute, you can modify it using
    subscript access:

    >>> class SampleCLI(TraitsCLIBase):
    ...     dict = Dict(config=True)
    ...
    >>> obj = SampleCLI.cli(['--dict["k"]', '1'])
    >>> obj.dict['k']
    1


    You don't need to quote string if dict/list attribute set
    its value trait to str-like trait:

    >>> class SampleCLI(TraitsCLIBase):
    ...     dict = Dict(value_trait=Str, config=True)
    ...
    >>> obj = SampleCLI.cli(['--dict["k"]', 'unquoted string'])
    >>> obj.dict['k']
    'unquoted string'
    >>> obj = SampleCLI.cli(['--dict["k"]=unquoted string'])
    >>> obj.dict['k']
    'unquoted string'


    Attributes of nested class can be set using dot access:

    >>> class SubObject(TraitsCLIBase):
    ...     int = Int(config=True)
    ...
    >>> class SampleCLI(TraitsCLIBase):
    ...     # Here, ``args=()`` is required to initialize `sub`.
    ...     sub = Instance(SubObject, args=(), config=True)
    ...
    >>> obj = SampleCLI.cli(['--sub.int', '1'])
    >>> obj.sub.int
    1


    **Metadata for traits**

    config : bool
       If this metadata of an attribute is True, this attribute is
       configurable via CLI.

       >>> class SampleCLI(TraitsCLIBase):
       ...     configurable = Int(config=True)
       ...     hidden = Int()
       ...
       >>> with hidestderr():
       ...     SampleCLI.cli(['--configurable', '1', '--hidden', '2'])
       ... # `hidden` is not configurable, so it fails:
       Traceback (most recent call last):
         ...
       SystemExit: 2
       >>> obj = SampleCLI.cli(['--configurable', '1'])
       >>> obj.configurable
       1
       >>> obj.hidden = 2
       >>> obj.hidden
       2

    desc : string
       Description of this attribute.  Passed to `help` argument
       of `ArgumentParser.add_argument`.

       >>> class SampleCLI(TraitsCLIBase):
       ...     a = Int(desc='help string for attribute a', config=True)
       ...     b = Float(desc='help string for attribute b', config=True)
       ...
       >>> SampleCLI.get_argparser().print_help()  # doctest: +ELLIPSIS
       usage: ... [-h] [--a A] [--b B]
       <BLANKLINE>
       optional arguments:
         -h, --help  show this help message and exit
         --a A       help string for attribute a (default: 0)
         --b B       help string for attribute b (default: 0.0)

    cli_positional : bool
       If True, corresponding command line argument is interpreted
       as a positional argument.

       >>> class SampleCLI(TraitsCLIBase):
       ...     int = Int(cli_positional=True, config=True)
       ...
       >>> obj = SampleCLI.cli(['1'])  # no `--a` here!
       >>> obj.int
       1

    cli_required : bool
       Passed to `required` argument of `ArgumentParser.add_argument`

       >>> class SampleCLI(TraitsCLIBase):
       ...     int = Int(cli_required=True, config=True)
       ...
       >>> with hidestderr():
       ...     SampleCLI.cli([])
       ...
       Traceback (most recent call last):
         ...
       SystemExit: 2
       >>> obj = SampleCLI.cli(['--int', '1'])
       >>> obj.int
       1

    cli_metavar : str
       Passed to `metavar` argument of `ArgumentParser.add_argument`

       >>> class SampleCLI(TraitsCLIBase):
       ...     int = Int(cli_metavar='NUM', config=True)
       ...
       >>> SampleCLI.get_argparser().print_help()  # doctest: +ELLIPSIS
       usage: ... [-h] [--int NUM]
       <BLANKLINE>
       optional arguments:
         -h, --help  show this help message and exit
         --int NUM   (default: 0)

    cli_paramfile : bool
       This attribute has special meaning.  When this metadata is
       True, this attribute indicate the path to parameter file The
       instance is first initialized using parameters defined in the
       parameter file, then command line arguments are used to
       override the parameters.

       >>> class SampleCLI(TraitsCLIBase):
       ...     int = Int(config=True)
       ...     paramfile = Str(cli_paramfile=True, config=True)
       ...
       >>> import json
       >>> from tempfile import NamedTemporaryFile
       >>> param = {'int': 1}
       >>> with NamedTemporaryFile(suffix='.json') as f:
       ...     json.dump(param, f)
       ...     f.flush()
       ...     obj = SampleCLI.cli(['--paramfile', f.name])
       ...
       >>> obj.int
       1


    **Idioms**

    Get a dictionary containing configurable attributes.

    >>> class SampleCLI(TraitsCLIBase):
    ...     a = Int(0, config=True)
    ...     b = Int(1, config=True)
    ...     c = Int(2)
    ...
    >>> obj = SampleCLI()
    >>> obj.trait_get() == {'a': 0, 'b': 1, 'c': 2}
    True
    >>> obj.trait_get(config=True) == {'a': 0, 'b': 1}
    True

    Get a list of configurable attribute names.

    >>> names = SampleCLI.class_trait_names(config=True)
    >>> sorted(names)
    ['a', 'b']

    See `Traits user manual`_ for more information.
    Especially, `Defining Traits: Initialization and Validation`_
    is useful to quickly glance traits API.

    .. _Traits user manual:
      http://docs.enthought.com/traits/traits_user_manual/index.html

    .. _`Defining Traits: Initialization and Validation`:
      http://docs.enthought.com/traits/traits_user_manual/defining.html

    """

    ArgumentParser = argparse.ArgumentParser
    """
    Argument parser class/factory.

    This attribute must be a callable object which returns
    an instance of `argparse.ArgumentParser` or its subclass.

    """

    def __init__(self, **kwds):
        super(TraitsCLIBase, self).__init__()
        self.setattrs(kwds)

    def setattrs(self, attrs, only_configurable=False):
        """
        Set attribute given a dictionary `attrs`.

        Keys of `attrs` can be dot-separated name (e.g., ``a.b.c``).
        In this case, nested attribute will be set to its attribute.

        The values of `attrs` can be a dict.  If the corresponding
        attribute is an instance of :class:`TraitsCLIBase`, attributes
        of this instance is set using this dictionary.  Otherwise,
        it will issue an error.

        >>> obj = TraitsCLIBase()
        >>> obj.b = TraitsCLIBase()
        >>> obj.setattrs({'a': 1, 'b': {'c': 2}})
        >>> obj.a
        1
        >>> obj.b.c
        2
        >>> obj.setattrs({'b.a': 111, 'b.c': 222})
        >>> obj.b.a
        111
        >>> obj.b.c
        222
        >>> obj.setattrs({'x.a': 0})
        Traceback (most recent call last):
          ...
        AttributeError: 'TraitsCLIBase' object has no attribute 'x'


        If `only_configurable` is `True`, attempt to set
        non-configurable attributes raises an error.

        >>> class SampleCLI(TraitsCLIBase):
        ...     a = Int(config=True)
        ...     b = Int()
        ...
        >>> obj = SampleCLI()
        >>> obj.setattrs({'a': 1}, only_configurable=True)  # This is OK.
        >>> obj.setattrs({'b': 1}, only_configurable=True)  # This is not!
        Traceback (most recent call last):
          ...
        TraitsCLIAttributeError: Non-configurable key is given: b

        """
        for name in sorted(attrs):  # set shallower attributes first
            value = attrs[name]
            if only_configurable and not self.is_configurable(name):
                raise TraitsCLIAttributeError(
                    'Non-configurable key is given: {0}'.format(name))

            current = getattr(self, name, None)
            if isinstance(value, dict) and isinstance(current, TraitsCLIBase):
                current.setattrs(value)
            else:
                setdottedattr(self, name, value)

    @classmethod
    def get_argparser(cls):
        """
        Return an instance of `ArgumentParser` for this class.

        Parser options are set according to the configurable traits of
        this class.

        """
        parser = cls.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=cls.__description())
        cls.add_parser(parser)
        return parser

    @classmethod
    def __description(cls):
        import textwrap
        return textwrap.dedent(cls.__doc__) if cls.__doc__ else None

    add_parser = classmethod(add_parser)

    @classmethod
    def cli(cls, args=None):
        """
        Call :meth:`run` using command line arguments.

        When `args` is given, it is used instead of ``sys.argv[1:]``.

        Essentially, the following two should do the same thing::

            $ python yourcli.py --alpha 1

            >>> YourCLI.run(alpha=1)                        # doctest: +SKIP

        """
        parser = cls.get_argparser()
        return parse_and_run(parser, args)

    @classmethod
    def run(cls, **kwds):
        """
        Make an instance with args `kwds` and call :meth:`do_run`.
        """
        dopts = kwds.pop('__dict_like_options', [])
        (kwds_paramfile, kwds_rest) = cls.__classify_kwds(kwds)

        self = cls(**kwds_paramfile)
        self.load_all_paramfiles()             # from file
        self.setattrs(kwds_rest)               # normal command line options
        self.__eval_dict_like_options(dopts)   # dict-like options

        self.do_run()
        return self

    def load_all_paramfiles(self):
        """
        Load attributes from all parameter files set in paramfile attributes.

        Path of parameter file is defined by attributes whose
        metadata `cli_paramfile` is True.

        >>> from tempfile import NamedTemporaryFile
        >>> from contextlib import nested
        >>> class SampleCLI(TraitsCLIBase):
        ...     int = Int(config=True)
        ...     str = Str(config=True)
        ...     paramfiles = List(cli_paramfile=True, config=True)
        ...
        >>> obj = SampleCLI()
        >>> with nested(NamedTemporaryFile(suffix='.json'),
        ...             NamedTemporaryFile(suffix='.json')) as (f, g):
        ...     f.write('{"int": 1}')
        ...     f.flush()
        ...     g.write('{"str": "a"}')
        ...     g.flush()
        ...     obj.paramfiles = [f.name, g.name]
        ...     obj.load_all_paramfiles()
        ...
        >>> obj.int
        1
        >>> obj.str
        u'a'

        """
        for v in self.trait_get(cli_paramfile=True).itervalues():
            if not v:
                continue
            if isinstance(v, (list, tuple)):
                for path in v:
                    self.load_paramfile(path)
            else:
                self.load_paramfile(v)

    def load_paramfile(self, path, only_configurable=True):
        """
        Load attributes from parameter file at `path`.

        To support new parameter file, add a **class**-method called
        ``loader_{ext}`` where ``{ext}`` is the file extension of the
        parameter file.  You can also redefine `dispatch_paramfile_loader`
        **class**-method to change how loader function is chosen.

        >>> from tempfile import NamedTemporaryFile
        >>> class SampleCLI(TraitsCLIBase):
        ...     int = Int(config=True)
        ...
        >>> obj = SampleCLI()
        >>> with NamedTemporaryFile(suffix='.json') as f:
        ...     f.write('{"int": 1}')
        ...     f.flush()
        ...     obj.load_paramfile(f.name)
        ...
        >>> obj.int
        1


        You can use ``only_configurable=False`` to set
        non-configurable option.

        >>> obj = TraitsCLIBase()
        >>> with NamedTemporaryFile(suffix='.json') as f:
        ...     f.write('{"nonconfigurable": 1}')
        ...     f.flush()
        ...     obj.load_paramfile(f.name, only_configurable=False)
        ...
        >>> obj.nonconfigurable
        1

        """
        param = self.dispatch_paramfile_loader(path)(path)
        try:
            self.setattrs(param, only_configurable=only_configurable)
        except TraitsCLIAttributeError as e:
            raise TraitsCLIAttributeError(
                "Error while loading file {0}: {1}"
                .format(path, e.message))

    @classmethod
    def dispatch_paramfile_loader(cls, path):
        """
        Return an parameter file loader function  based on `path`.

        This classmethod returns classmethod/staticmethod named
        ``laoder_{ext}`` where ``{ext}`` is the file extension of
        `path`.  You can redefine this classmethod to change the
        dispatching behavior.

        Call signature of the loader function must be ``loader(path)``
        where ``path`` is a string file path to the parameter file.

        """
        ext = os.path.splitext(path)[-1][1:].lower()
        return getattr(cls, 'loader_{0}'.format(ext))

    def __footnote_loader_func(func):
        func.__doc__ += """

        ..
           *User* of this class should **NOT** call this function.
           Use `load_paramfile` to load parameter file(s).

           However, you can redefine this classmethod/staticmethod to
           modify how parameter file is loaded.

        """
        return func

    @staticmethod
    @__footnote_loader_func
    def loader_json(path, _open=open):
        """
        Load JSON file located at `path`.

        It is equivalent to ``json.load(open(path))``.

        """
        import json
        with _open(path) as file:
            return json.load(file)

    @staticmethod
    @__footnote_loader_func
    def loader_yaml(path, _open=open):
        """
        Load YAML file located at `path`.

        It is equivalent to ``yaml.load(open(path))``.
        You need PyYAML_ module to use this loader.

        .. _PyYAML: http://pypi.python.org/pypi/PyYAML

        """
        import yaml
        with _open(path) as file:
            return yaml.load(file)

    loader_yml = loader_yaml
    """Alias to :meth:`loader_yaml`."""

    cli_conf_root_section = 'root'
    """
    Root section name for conf/ini file loader (:meth:`loader_conf`).

    Options in this section will not be prefixed by section name.

    """

    @classmethod
    @__footnote_loader_func
    def loader_conf(cls, path, _open=open):
        """
        Load parameter from conf/ini file.

        As conf file has no type information, class traits will be
        used at load time.

        >>> class SubObject(TraitsCLIBase):
        ...     c = Int(config=True)
        >>> class SampleCLI(TraitsCLIBase):
        ...     a = Int(config=True)
        ...     b = Instance(SubObject, args=(), config=True)
        ...     d = Instance(SubObject, args=(), config=True)
        ...     cli_conf_root_section = 'root'  # this is default

        You can write options using dot-separated name.
        Use the section specified by :attr:`cli_conf_root_section`
        for top-level attributes.

        >>> from tempfile import NamedTemporaryFile
        >>> source = '''
        ... [root]
        ... a = 1
        ... b.c = 2
        ... '''
        >>> with NamedTemporaryFile() as f:
        ...     f.write(source)
        ...     f.flush()
        ...     param = SampleCLI.loader_conf(f.name)
        >>> param == {'a': 1, 'b.c': 2}
        True

        Options in sections other than :attr:`cli_conf_root_section`
        are prefixed by section name.

        >>> from tempfile import NamedTemporaryFile
        >>> source = '''
        ... [root]
        ... a = 1
        ... [b]
        ... c = 2
        ... [d]
        ... c = 3
        ... '''
        >>> with NamedTemporaryFile() as f:
        ...     f.write(source)
        ...     f.flush()
        ...     param = SampleCLI.loader_conf(f.name)
        >>> param == {'a': 1, 'b.c': 2, 'd.c': 3}
        True

        """
        import ConfigParser
        config = ConfigParser.ConfigParser()
        with _open(path) as file:
            config.readfp(file)
        sections = config.sections()
        traits = flattendict(cls.config_traits())
        param = {}

        def getoptions(section, prefix=''):
            for option in config.options(section):
                key = prefix + option
                if key in traits:
                    trait_type = traits[key].trait_type
                    if isinstance(trait_type, (Bool, CBool)):
                        param[key] = config.getboolean(section, option)
                    else:
                        val = config.get(section, option)
                        stype = trait_simple_type(trait_type)
                        if stype:
                            param[key] = stype(val)
                        else:
                            param[key] = val
                else:
                    raise TraitsCLIAttributeError(
                        "Key '{0}' is not configurable attribute of "
                        "class {1}.".format(key, cls.__name__))

        for sect in sections:
            if cls.cli_conf_root_section == sect:
                getoptions(sect)
            else:
                getoptions(sect, sect + '.')

        return param

    loader_ini = loader_conf
    """Alias to :meth:`loader_conf`."""

    @staticmethod
    @__footnote_loader_func
    def loader_py(path, _open=open):
        """
        Load parameter from Python file located at `path`.

        >>> from tempfile import NamedTemporaryFile
        >>> source = '''
        ... a = 1
        ... b = dict(c=2)
        ... _underscored_value_ = 'will_not_be_loaded'
        ... '''
        >>> with NamedTemporaryFile() as f:
        ...     f.write(source)
        ...     f.flush()
        ...     param = TraitsCLIBase.loader_py(f.name)
        >>> param == {'a': 1, 'b': {'c': 2}}
        True

        """
        param = {}
        with _open(path) as file:
            exec file.read() in param
        return cleanup_dict(param)

    @classmethod
    def __classify_kwds(cls, kwds):
        kwds_paramfile = {}
        kwds_rest = kwds.copy()
        for k in cls.class_trait_names(cli_paramfile=True):
            if k in kwds_rest:
                kwds_paramfile[k] = kwds_rest.pop(k)
        return (kwds_paramfile, kwds_rest)

    def __eval_dict_like_options(self, dopts):
        traits = flattendict(self.config_traits())
        unknown = set(names_in_dict_like_options(dopts)) - set(traits)
        if unknown:
            unknown = tuple(unknown)
            clargs = ' '.join(
                '--{0}={1}'.format(k, v) for (k, v) in dopts
                if k.startswith(unknown))
            raise InvalidDictLikeOptionError(
                "Unknown dict-like options {0}".format(clargs))

        def value_trait(trait_type):
            if isinstance(trait_type, Dict):
                return trait_type.value_trait.trait_type
            elif isinstance(trait_type, List):
                return trait_type.item_trait.trait_type

        namespace = self.trait_get(config=True)
        for (lhs, rhs) in dopts:
            name = lhs.split('[', 1)[0]
            trait_type = value_trait(traits[name].trait_type)
            assert_expr(lhs, ast.Subscript)
            if isinstance(trait_type, (Str, CStr, Unicode, CUnicode)):
                rhs = repr(rhs)
            else:
                assert_expr(rhs)
            try:
                exec '{0} = {1}'.format(lhs, rhs) in namespace
            except NameError as e:
                raise TraitsCLIAttributeError(
                    'Got {0!r} wile evaluating --{1}={2}'.format(
                        e, lhs, rhs))

    @classmethod
    def is_configurable(cls, dottedname):
        names = dottedname.split('.', 1)
        head = names[0]
        traits = cls.class_traits(config=True)
        if head not in traits:
            return False
        if len(names) == 1:
            return True
        tail = names[1]
        trait_type = traits[head].trait_type
        if (isinstance(trait_type, Instance) and
            issubclass(trait_type.klass, TraitsCLIBase)):
            return trait_type.klass.is_configurable(tail)
        return False

    config_traits = classmethod(config_traits)

    def do_run(self):
        """
        Actual implementation of :meth:`run`.

        Child class must implement this method.

        """


def multi_command_cli(command_class_pairs, args=None, ArgumentParser=None):
    """
    Launch CLI to call multiple classes.

    Usage:

    >>> class SampleBase(TraitsCLIBase):
    ...     a = Int(config=True)
    ...     def do_run(self):
    ...         print "Running",
    ...         print '{0}(a={1!r})'.format(self.__class__.__name__,
    ...                                     self.a)
    ...
    >>> class SampleInit(SampleBase):
    ...       pass
    ...
    >>> class SampleCheckout(SampleBase):
    ...       pass
    ...
    >>> class SampleBranch(SampleBase):
    ...       pass
    ...
    >>> obj = multi_command_cli(
    ...     # CLI classes and subcommand names
    ...     [('init', SampleInit),
    ...      ('checkout', SampleCheckout),
    ...      ('branch', SampleBranch),
    ...     ],
    ...     # Command line arguments
    ...     ['init', '--a', '1'])
    ...
    Running SampleInit(a=1)
    >>> isinstance(obj, SampleInit)   # used CLI object is returned.
    True

    If `ArgumentParser` is not specified, `ArgumentParser` of the first
    class will be used.

    """
    if ArgumentParser is None:
        ArgumentParser = command_class_pairs[0][1].ArgumentParser
    parser = ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subpersers = parser.add_subparsers()
    for (name, cls) in command_class_pairs:
        cls.add_parser(subpersers.add_parser(name))
    return parse_and_run(parser, args)
