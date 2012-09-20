from traitscli import TraitsCLIBase
from traits.api import Bool, Float, Int, Str, Enum


class SampleCLI(TraitsCLIBase):

    """
    Sample CLI using `traitscli`.

    Example::

      %(prog)s --yes                # => obj.yes = True
      %(prog)s --string something   # => obj.string = 'string'
      %(prog)s --choice x           # => raise error (x is not in {a, b, c})

    """

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
