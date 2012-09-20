from argparse import ArgumentParser
import unittest

from traits.api import Event, Callable, Type, Dict, List

from traitscli import TraitsCLIBase
from sample import SampleCLI


class ArgumentParserExitCalled(Exception):
    pass


class ArgumentParserNoExit(ArgumentParser):

    def exit(self, status=0, message=None):
        raise ArgumentParserExitCalled(status, message)

    def error(self, message):
        self.exit(2, message)


class TestingCLIBase(TraitsCLIBase):

    ArgumentParser = ArgumentParserNoExit

    def do_run(self):
        # Get trait attribute names
        names = self.class_trait_names(
            # Avoid 'trait_added' and 'trait_modified'
            # (See also `HasTraits.traits`):
            trait_type=lambda t: not isinstance(t, Event))
        self.attributes = dict((n, getattr(self, n)) for n in names)


class TestCaseBase(unittest.TestCase):

    cliclass = None
    """Subclass of `TraitsCLIBase`."""

    def assert_attributes(self, attributes, args=[]):
        ret = self.cliclass.cli(args)
        self.assertEqual(ret.attributes, attributes)


class TestSampleCLI(TestCaseBase):

    class cliclass(TestingCLIBase, SampleCLI):
        pass

    def test_empty_args(self):
        self.assert_attributes(dict(
            yes=False,
            no=True,
            fnum=0.0,
            inum=0,
            string='',
            choice='a',
            not_configurable_from_cli=False,
        ))

    def test_full_args(self):
        self.assert_attributes(
            dict(
                yes=True,
                no=False,
                fnum=0.2,
                inum=2,
                string='some string',
                choice='b',
                not_configurable_from_cli=False,
            ),
            ['--yes', '--no',
             '--fnum', '0.2',
             '--inum', '2',
             '--string', 'some string',
             '--choice', 'b',
            ])

    def test_invalid_type_int(self):
        self.assertRaises(ArgumentParserExitCalled,
                          self.cliclass.cli, ['--inum', 'x'])

    def test_invalid_type_float(self):
        self.assertRaises(ArgumentParserExitCalled,
                          self.cliclass.cli, ['--fnum', 'x'])

    def test_invalid_type_enum(self):
        self.assertRaises(ArgumentParserExitCalled,
                          self.cliclass.cli, ['--choice', 'x'])


class TestEvalType(TestCaseBase):

    class cliclass(TestingCLIBase):
        callable = Callable(config=True)
        type = Type(config=True)

    def test_full_args(self):
        self.assert_attributes(
            dict(
                callable=id,
                type=int,
            ),
            ['--callable', 'id',
             '--type', 'int',
            ])


class TestDictLikeOptions(TestCaseBase):

    class cliclass(TestingCLIBase):
        dict = Dict(config=True)
        list = List(range(3), config=True)

    def test_empty_args(self):
        self.assert_attributes(dict(
            dict={},
            list=range(3),
        ))

    def test_full_args(self):
        self.assert_attributes(
            dict(
                dict=dict(a=1, b=2),
                list=[0, 100, 2],
            ),
            ["--dict['a']=1",
             "--dict['b']=2",
             "--list[1]=100",
            ])

    def test_invalid_args(self):
        self.assertRaises(ArgumentParserExitCalled,
                          self.cliclass.cli, ['--invalid', 'x'])
        self.assertRaises(ArgumentParserExitCalled,
                          self.cliclass.cli, ['--invalid["k"]', 'x'])
