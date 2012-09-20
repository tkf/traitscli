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


TODO
----

* Nested class support.
  Set attributes of nested class by ``--sub.attr=val``.

* Upload this to PyPI.

* Support positional arguments.

* Parameter file support (ini/conf, json, yaml, etc.).
  Load parameter from file then set attribute.

* Support `other predefined Traits listed here`__.

__ http://docs.enthought.com/traits/traits_user_manual/defining.html
   #other-predefined-traits
