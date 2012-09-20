from argparse import ArgumentParser
import unittest

from traits.api import Event, Callable, Type, Dict, List, Int, Float, Instance

from traitscli import TraitsCLIBase, multi_command_cli
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


class TestMultiCommandCLI(unittest.TestCase):

    class cliclass_1(TestingCLIBase):
        int = Int(config=True)
        dict = Dict(config=True)

    class cliclass_2(TestingCLIBase):
        float = Float(config=True)
        list = List(config=True)

    def run_multi_command_cli(self, args):
        pairs = [('cmd_1', self.cliclass_1),
                 ('cmd_2', self.cliclass_2)]
        return multi_command_cli(pairs, args)

    def test_run_1_empty_args(self):
        ret = self.run_multi_command_cli(['cmd_1'])
        self.assertTrue(isinstance(ret, self.cliclass_1))

    def test_run_2_empty_args(self):
        ret = self.run_multi_command_cli(['cmd_2'])
        self.assertTrue(isinstance(ret, self.cliclass_2))

    def assert_invalid_args(self, args):
        self.assertRaises(ArgumentParserExitCalled,
                          self.run_multi_command_cli, args)

    def test_invalid_args(self):
        self.assert_invalid_args(['--invalid', 'x'])  # no sub-command
        self.assert_invalid_args(['cmd_1', '--invalid', 'x'])
        self.assert_invalid_args(['cmd_1', '--invalid["k"]', 'x'])
        self.assert_invalid_args(['cmd_1', '--list', '[]'])  # cmd_2 option
        self.assert_invalid_args(['cmd_2', '--invalid', 'x'])
        self.assert_invalid_args(['cmd_2', '--invalid["k"]', 'x'])
        self.assert_invalid_args(['cmd_2', '--dict', '{}'])  # cmd_1 option


class TestDottedName(unittest.TestCase):

    def setUp(self):
        # Doing this as "class context" yields an name error

        class subcliclass(TraitsCLIBase):
            int = Int

        class cliclass(TraitsCLIBase):
            int = Int
            sub = Instance(subcliclass, args=())

        self.subcliclass = subcliclass
        self.cliclass = cliclass

    def make_instance(self, kwds):
        return self.cliclass(**kwds)

    def test_normal_attr(self):
        obj = self.make_instance({'int': 1})
        self.assertEqual(obj.int, 1)
        self.assertEqual(obj.sub.int, 0)

    def test_dotted_attr(self):
        obj = self.make_instance({'int': 1, 'sub.int': 2})
        self.assertEqual(obj.int, 1)
        self.assertEqual(obj.sub.int, 2)
