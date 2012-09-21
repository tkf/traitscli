from argparse import ArgumentParser
import unittest

from traits.api import (
    Int, Float, Bool, List, Dict,
    Instance, Callable, Type,
    Event,
)

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

    @property
    def attributes(self):
        # Get trait attribute names
        names = self.class_trait_names(
            # Avoid 'trait_added' and 'trait_modified'
            # (See also `HasTraits.traits`):
            trait_type=lambda t: not isinstance(t, Event))

        return dict((n, self[n]) for n in names)

    def __getitem__(self, key):
        attr = getattr(self, key)
        if isinstance(attr, TraitsCLIBase):
            return attr.attributes
        else:
            return attr


class TestCaseBase(unittest.TestCase):

    cliclass = None
    """Subclass of `TraitsCLIBase`."""

    def run_cli(self, args):
        return self.cliclass.cli(args)

    def assert_invalid_args(self, args):
        self.assertRaises(ArgumentParserExitCalled,
                          self.run_cli, args)

    def assert_attributes(self, attributes, args=[]):
        ret = self.cliclass.cli(args)
        self.assertEqual(ret.attributes, attributes)

    def test_call_format_help(self):
        if self.cliclass:
            parser = self.cliclass.get_argparser()
            parser.format_help()


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
        self.assert_invalid_args(['--inum', 'x'])

    def test_invalid_type_float(self):
        self.assert_invalid_args(['--fnum', 'x'])

    def test_invalid_type_enum(self):
        self.assert_invalid_args(['--choice', 'x'])


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
        self.assert_invalid_args(['--invalid', 'x'])
        self.assert_invalid_args(['--invalid["k"]', 'x'])


class TestMultiCommandCLI(TestCaseBase):

    class cliclass_1(TestingCLIBase):
        int = Int(config=True)
        dict = Dict(config=True)

    class cliclass_2(TestingCLIBase):
        float = Float(config=True)
        list = List(config=True)

    def run_cli(self, args):
        pairs = [('cmd_1', self.cliclass_1),
                 ('cmd_2', self.cliclass_2)]
        return multi_command_cli(pairs, args)

    def test_run_1_empty_args(self):
        ret = self.run_cli(['cmd_1'])
        self.assertTrue(isinstance(ret, self.cliclass_1))

    def test_run_2_empty_args(self):
        ret = self.run_cli(['cmd_2'])
        self.assertTrue(isinstance(ret, self.cliclass_2))

    def test_invalid_args(self):
        self.assert_invalid_args(['--invalid', 'x'])  # no sub-command
        self.assert_invalid_args(['cmd_1', '--invalid', 'x'])
        self.assert_invalid_args(['cmd_1', '--invalid["k"]', 'x'])
        self.assert_invalid_args(['cmd_1', '--list', '[]'])  # cmd_2 option
        self.assert_invalid_args(['cmd_2', '--invalid', 'x'])
        self.assert_invalid_args(['cmd_2', '--invalid["k"]', 'x'])
        self.assert_invalid_args(['cmd_2', '--dict', '{}'])  # cmd_1 option


class TestDottedName(unittest.TestCase):

    class cliclass(TraitsCLIBase):
        class subcliclass(TraitsCLIBase):
            int = Int
        int = Int
        sub = Instance(subcliclass, args=())
    subcliclass = cliclass.subcliclass

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

    def test_ordered_initialization(self):
        obj = self.make_instance({
            'int': 1, 'sub': self.subcliclass(int=3), 'sub.int': 2})
        self.assertEqual(obj.int, 1)
        self.assertEqual(obj.sub.int, 2)


class TestNestedCLI(TestCaseBase):

    class cliclass(TestingCLIBase):
        class subcliclass(TestingCLIBase):
            class subcliclass2(TestingCLIBase):
                int = Int(config=True)
            int = Int(config=True)
            sub2 = Instance(subcliclass2, args=(), config=True)
        int = Int(config=True)
        sub = Instance(subcliclass, args=(), config=True)

    def test_empty_args(self):
        self.assert_attributes(dict(
            int=0,
            sub=dict(int=0,
                     sub2=dict(int=0)),
        ))

    def test_full_args(self):
        self.assert_attributes(
            dict(
                int=1,
                sub=dict(int=2,
                         sub2=dict(int=3)),
            ),
            ["--int=1",
             "--sub.int=2",
             "--sub.sub2.int=3",
            ])

    def test_invalid_args(self):
        self.assert_invalid_args(['--invalid', 'x'])
        self.assert_invalid_args(['--invalid["k"]', 'x'])
        self.assert_invalid_args(['--sub', 'x'])
        self.assert_invalid_args(['--sub.sub2', 'x'])


class TestMetaDataCLI(TestCaseBase):

    class cliclass(TestingCLIBase):
        a = Int(config=True)
        b = Int(cli_positional=True, config=True)
        c = Int(cli_required=True, config=True)
        d = Int(cli_metavar='X', config=True)

    def test_minimal_args(self):
        self.assert_attributes(
            dict(
                a=0,
                b=1,
                c=2,
                d=0,
            ),
            ['1', '--c', '2'])

    def test_invalid_args(self):
        self.assert_invalid_args([])
        self.assert_invalid_args(['1'])
        self.assert_invalid_args(['--c', '2'])
        self.assert_invalid_args(['--invalid', 'x'])


class TestPositionalBooleanCLI(TestCaseBase):

    class cliclass(TestingCLIBase):
        a = Bool(cli_positional=True, config=True)

    def test_minimal_args(self):
        self.assert_attributes(dict(a=True), ['True'])
        self.assert_attributes(dict(a=False), ['False'])

    def test_invalid_args(self):
        self.assert_invalid_args([])
        self.assert_invalid_args(['1', '2'])
