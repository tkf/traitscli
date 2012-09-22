# [[[cog import _cogutils as _; _.inject_readme()]]]
"""
Traits CLI - CLI generator based on class traits
================================================

Traits CLI is based on `Enthought's Traits library <traits>`_.

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
          names = self.config_names()
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

import os
import re
import argparse

from traits.api import (
    HasTraits, Bool, CBool, Complex, CComplex, Float, CFloat,
    Int, CInt, Long, CLong, Str, CStr, Unicode, CUnicode,
    Enum, Instance,
)

__version__ = '0.1.beta0'
__author__ = 'Takafumi Arakaki'
__license__ = 'BSD License'


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
        # the timing of `TraitsCLIBase.load_paramfile`.
        return func(**dict((k, v) for (k, v) in kwds.iteritems()
                           if v is not _UNSPECIFIED))

    (dopts, args) = parse_dict_like_options(args)
    try:
        ns = parser.parse_args(args)
        return applyargs(__dict_like_options=dopts, **vars(ns))
    except TraitsCLIAttributeError as e:
        parser.exit(e.message)


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


    Metadata for traits

    config : bool
       If metadata is True, this attribute is configurable via CLI.

    desc : string
       Description of this attribute.  Passed to `help` argument
       of `ArgumentParser.add_argument`.

    cli_positional : bool (default: False)
       If True, corresponding command line argument is interpreted
       as a positional argument.

    cli_required : bool
       Passed to `required` argument of `ArgumentParser.add_argument`

    cli_metavar : str
       Passed to `metavar` argument of `ArgumentParser.add_argument`

    cli_paramfile : bool
       This attribute has special meaning.  When this metadata is
       True, this attribute indicate the path to parameter file The
       instance is first initialized using parameters defined in the
       parameter file, then command line arguments are used to
       override the parameters.

    """

    ArgumentParser = argparse.ArgumentParser

    def __init__(self, **kwds):
        super(TraitsCLIBase, self).__init__()
        self.setattrs(kwds)

    def setattrs(self, attrs, only_configurable=False):
        """
        Set attribute given a dictionary `attrs`.

        Keys of `attrs` can be dot-separated name.  In this case,
        nested attribute will be set to its attribute.

        The values of `attrs` can be a dict.  If the corresponding
        attribute is an instance of `TraitsCLIBase`, attributes
        of this instance is set using this dictionary.

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
    def connect_subparser(cls, subpersers, name):
        return cls.add_parser(subpersers.add_parser(name))

    @classmethod
    def get_argparser(cls):
        parser = cls.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=cls.__description())
        cls.add_parser(parser)
        return parser

    @classmethod
    def __description(cls):
        import textwrap
        return textwrap.dedent(cls.__doc__) if cls.__doc__ else None

    @classmethod
    def add_parser(cls, parser, prefix=''):
        """
        Call `parser.add_argument` based on class traits of `cls`.
        """
        traits = cls.class_traits(config=True)
        for k in sorted(traits):
            v = traits[k]

            if (isinstance(v.trait_type, Instance) and
                issubclass(v.trait_type.klass, TraitsCLIBase)):
                v.trait_type.klass.add_parser(parser, prefix + k + '.')
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
        (kwds_paramfile, kwds_rest) = cls.__classify_kwds(kwds)

        self = cls(**kwds_paramfile)
        self.load_paramfile()                  # from file
        self.setattrs(kwds_rest)               # normal command line options
        self.__eval_dict_like_options(dopts)   # dict-like options

        self.do_run()
        return self

    def load_paramfile(self):
        """
        Load attributes from parameter file.

        Path of parameter file is defined by attributes whose
        metadata `cli_paramfile` is True.

        To support new parameter file, add a **class**-method called
        ``loader_{ext}`` where ``{ext}`` is the file extension of the
        parameter file.

        """
        for v in self.config(cli_paramfile=True).itervalues():
            if not v:
                continue
            if isinstance(v, (list, tuple)):
                for path in v:
                    self._load_paramfile(path)
            else:
                self._load_paramfile(v)

    def _load_paramfile(self, path):
        ext = os.path.splitext(path)[-1][1:].lower()
        param = getattr(self, 'loader_{0}'.format(ext))(path)
        try:
            self.setattrs(param, only_configurable=True)
        except TraitsCLIAttributeError as e:
            raise TraitsCLIAttributeError(
                "Error while loading file {0}: {1}"
                .format(path, e.message))

    def __footnote_loader_func(func):
        func.__doc__ += """

        *User* of this class should **NOT** call this function.
        Use `load_paramfile` to load parameter file(s).

        However, you can re-define this classmethod function to modify
        how parameter file is loaded.

        """
        return func

    @classmethod
    @__footnote_loader_func
    def loader_json(cls, path, _open=open):
        """Load parameter from JSON file."""
        import json
        with _open(path) as file:
            return json.load(file)

    @classmethod
    @__footnote_loader_func
    def loader_yaml(cls, path, _open=open):
        """Load parameter from YAML file."""
        import yaml
        with _open(path) as file:
            return yaml.load(file)

    @classmethod
    @__footnote_loader_func
    def loader_conf(cls, path, _open=open):
        """Load parameter from conf/ini file."""
        import ConfigParser
        config = ConfigParser.ConfigParser()
        with _open(path) as file:
            config.readfp(file)
        sections = config.sections()
        if len(sections) == 1:
            return dict(config.items(sections[0]))
        else:
            dct = {}
            join = '{0}.{1}'.format
            for sect in sections:
                for (k, v) in config.items(sect):
                    dct[join(sect, k)] = v
            return dct

    loader_ini = loader_conf

    @classmethod
    @__footnote_loader_func
    def loader_py(cls, path, _open=open):
        """Load parameter from Python file."""
        param = {}
        with _open(path) as file:
            exec file.read() in param
        return cleanup_dict(param)

    @classmethod
    def __classify_kwds(cls, kwds):
        kwds_paramfile = {}
        kwds_rest = kwds.copy()
        for k in cls.config_names(cli_paramfile=True):
            if k in kwds_rest:
                kwds_paramfile[k] = kwds_rest.pop(k)
        return (kwds_paramfile, kwds_rest)

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
            try:
                exec '{0} = {1}'.format(rhs, lhs) in ns
            except NameError as e:
                raise TraitsCLIAttributeError(
                    'Got {0!r} wile evaluating --{1}={2}'.format(
                        e, rhs, lhs))

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

    @classmethod
    def config_traits(cls, **metadata):
        """
        Get config traits of this class and return as a dict.

        The returned dict can be nested if this class has `Instance`
        trait of class `TraitsCLIBase`.

        """
        traits = {}
        for (k, v) in cls.class_traits(config=True).iteritems():
            if (isinstance(v.trait_type, Instance) and
                issubclass(v.trait_type.klass, TraitsCLIBase)):
                traits[k] = v.trait_type.klass.config_traits()
            else:
                traits[k] = v
        return traits

    def do_run(self):
        """
        Actual implementation of `self.run`.

        Child class must implement this method.

        """


def multi_command_cli(name_class_pairs, args=None, ArgumentParser=None):
    """
    Launch CLI to call multiple classes.

    Usage::

      multi_command_cli([
          ('init', DoInit),
          ('checkout', DoCheckout),
          ('branch', DoBranch),
      ])

    If `ArgumentParser` is not specified, `ArgumentParser` of the first
    class will be used.

    """
    ArgumentParser = name_class_pairs[0][1].ArgumentParser
    parser = ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subpersers = parser.add_subparsers()
    for (name, cls) in name_class_pairs:
        cls.connect_subparser(subpersers, name)
    return parse_and_run(parser, args)
