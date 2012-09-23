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
   .. automethod:: loader_json
   .. automethod:: loader_yaml
   .. automethod:: loader_yml
   .. automethod:: loader_conf
   .. automethod:: loader_ini
   .. autoattribute:: cli_conf_root_section
   .. automethod:: loader_py

   **Parser API**

   .. autoattribute:: ArgumentParser
   .. automethod:: get_argparser
   .. automethod:: add_parser


Utility functions
-----------------

.. autofunction:: multi_command_cli
.. autofunction:: flattendict
