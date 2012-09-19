==================================================
 Traits CLI - CLI generator based on class traits
==================================================

Usage::

   from traitscli import TraitsCLIBase
   from traits.api import Bool, Float, Enum


   class SampleCLI(TraitsCLIBase):
       # These variables are configurable by command line option
       yes = Bool(config=True)
       num = Float(config=True)
       choice = Enum(['a', 'b', 'c'], config=True)

       def do_run(self):
           # Do something here.


   if __name__ == '__main__':
       # Run command line interface
       SampleCLI.cli()