Linux
=====

Debian Based (Ubuntu)
---------------------


.. code-block::

   sudo apt-get install 


Windows
=======


Dependencies
------------

In order to run this software you'll need:

- Python 3.4+
- SDL2 (you may found it in your distribution as libsdl2)
- sdl2_ttf https://www.libsdl.org/projects/SDL_ttf/
- sdl2_gfx http://cms.ferzkopp.net/index.php/software/13-sdl-gfx


Installation
------------

It is recomended to install this package into a virtualenv.


Stable version
~~~~~~~~~~~~~~

.. code-block:: bash

   $ pip install pyagar


Usage
-----

Command
~~~~~~~

This package creates the command ``pyagar``.

.. code-block:: bash

   usage: pyagar [-h] [--disable-hw] [-n NICK] [-d] [--version]
                 {play,spectate,bot} ...

   positional arguments:
     {play,spectate,bot}

   optional arguments:
     -h, --help            show this help message and exit
     --disable-hw          Disable hardware acceleration.
     -n NICK, --nick NICK
     -d, --debug           Enable debug mode. Use multiple times to increase the
                           debug level.
     --version             show program's version number and exit


Controls
~~~~~~~~

=========== ============================================
Action      Control
=========== ============================================
Move        Mouse (Relative to the center of the window)
Start       Mouse (Left button)
Eject       ``W`` key
Split       ``Space`` key
Fullscreen  ``F`` key
Zoom        Mouse wheel
Exit        ``ESC`` key
=========== ============================================


Play examples
-------------

Just play
~~~~~~~~~

.. code-block:: bash

   $ pyagar play

Press the left mouse button to start.


Just watch the game
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   $ pyagar spectate


Play automatically using a bot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   $ pyagar bot --type=EatWhenNoPredators


Other implementations
---------------------

- https://github.com/Gjum/pyAgar.io
- https://github.com/Raeon/pygar

