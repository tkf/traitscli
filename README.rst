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

.. [[[cog import _cogutils as _; _.inject_sample_doc() ]]]

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

.. [[[end]]]
