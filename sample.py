from traitscli import TraitsCLIBase
from traits.api import Bool, Float, Int, Str, Enum, Event


class SampleCLI(TraitsCLIBase):

    """Sample CLI using `traitscli`."""

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
        # Get trait attribute names
        names = self.class_trait_names(
            # Avoid 'trait_added' and 'trait_modified'
            # (See also `HasTraits.traits`):
            trait_type=lambda t: not isinstance(t, Event))
        width = max(map(len, names))
        for na in names:
            print "{0:{1}} : {2!r}".format(na, width, getattr(self, na))


if __name__ == '__main__':
    # Run command line interface
    SampleCLI.cli()
