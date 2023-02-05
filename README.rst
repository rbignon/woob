Woob
====


Woob is a project which provides a core library, modules and applications.

## Overview

The core library defines capabilities: features common to various websites.
For example, [Youtube](http://www.youtube.com/) and
[Dailymotion](http://www.dailymotion.com/) both provide videos; Woob defines
the `CapVideo` capability for them.

Each module interfaces with a website and implements one or many of these
capabilities. Modules can be configured (becoming a "backend"), which means
that the end-user can provide personal information to access the underlying
website, like a login and password.

Applications allow the end-user to work with many modules in parallel,
in a multi-threaded way. For example, one could search a video on
many websites at once. Applications are toolkit-agnostic. They can use GTK+,
Qt or be text-only. The latter can be used either in an interactive way
or in pipes.

The core library provides base classes which help developers write
modules and applications.


## Installation

Installation is described on [the website](https://woob.tech) or in the
[INSTALL](INSTALL) file.

## License

Woob is written in Python and is distributed under the LGPLv3+ license.

## Documentation

For more information, please go to [the official website](https://woob.tech/).

Some extra info is available in the [Gitlab
wiki](https://gitlab.com/woob/woob/wikis/home).

If you are a developer and looking for how to write a module or contribute to
Woob, you can have a look at the [developer documentation](https://dev.woob.tech/).
