.. automodule:: traitscli


CLI base class
--------------

.. autoclass:: TraitsCLIBase

   **Entry points**

   .. automethod:: cli
   .. automethod:: run
   .. automethod:: do_run

   **API to access attributes**

   .. automethod:: config_traits
   .. automethod:: setattrs
   .. automethod:: load_paramfile
   .. automethod:: load_all_paramfiles
   .. automethod:: dispatch_paramfile_loader

   **Parser API**

   .. autoattribute:: ArgumentParser
   .. automethod:: get_argparser
   .. automethod:: add_parser


Utility functions
-----------------

.. autofunction:: multi_command_cli
.. autofunction:: flattendict
