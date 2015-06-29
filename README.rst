pyagar
======

``pyagar`` is a client implementation of http://agar.io for Python 3.4.

This package allows you to play as in the original site, see the game as
an spectator and also play automatically with a simple bot.

.. image:: docs/images/shot.png
   :alt: Screenshot
   :align: center


Dependencies
------------

In order to run this software you'll need:

- Python 3.4+
- SDL2 (you may found in your distribution as libsdl2)


Installation
------------

It is recomended to install this package into a virtualenv.


Stable version
~~~~~~~~~~~~~~

.. code-block:: bash

   $ pip install pyagar


Develop version
~~~~~~~~~~~~~~~

.. code-block:: bash

   $ git clone https://github.com/nilp0inter/pyagar
   $ cd pyagar
   $ python setup.py develop


Usage
-----

Command
~~~~~~~

This package creates the command ``agar.io``.

.. code-block:: bash

   $ agar.io --help
   usage: agar.io [-h] [--no-visualize] [-n NICK] [--auto] [--debug] [--spectate]

    optional arguments:
      -h, --help            show this help message and exit
      --no-visualize
      -n NICK, --nick NICK
      --auto
      --debug
      --spectate

Controls
~~~~~~~~

**Movement**: Mouse
**Split**: Mouse (Left button)
**Eject mass**: Not implemented yet

Play examples
-------------

Play setting a custom nick
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   $ agar.io -n doge


Just watch the game
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   $ agar.io --spectate


Play automatically using the default bot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   $ agar.io --auto


Play using the bot, but without a window
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Please, **do not abuse** the system with this!

.. code-block:: bash

   $ agar.io --auto --no-visualize
