.. automodule:: traitscli


CLI base class
--------------

.. autoclass:: TraitsCLIBase

   **Entry points**

   .. automethod:: cli
   .. automethod:: run
   .. automethod:: do_run

   **API to access attributes**

   .. automethod:: config
   .. automethod:: config_names
   .. automethod:: config_traits
   .. automethod:: setattrs
   .. automethod:: load_paramfile

   **Parser API**

   .. autoattribute:: ArgumentParser


Utility functions
-----------------

.. autofunction:: flattendict
.. autofunction:: multi_command_cli
