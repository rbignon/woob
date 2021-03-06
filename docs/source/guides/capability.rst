Create a capability
===================

A method can raise only its own exceptions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you want to return an error, you **must** raise only your own exceptions defined in the capability module.
Never let Python raise his exceptions, for example :py:exc:`KeyError` if a parameter given to method isn't found in a local
list.

Prefer returning objects
^^^^^^^^^^^^^^^^^^^^^^^^

Python is an object-oriented language, so when your capability supports entities (for example
:class:`~woob.capabilities.video.BaseVideo` with the :class:`~woob.capabilities.video.CapVideo` capability),
you have to create a class derived from :py:class:`~woob.capabilities.base.BaseObject`, and create an unique method
to get it (for example :func:`~woob.capabilities.video.CapVideo.get_video`), instead of several methods like
``get_video_url()``, ``get_video_preview()``, etc.

An object has an unique ID.

Filled objects
^^^^^^^^^^^^^^

When an object is fetched, all of its fields are not necessarily loaded.

For example, on a video search, if the *backend* gets information from the search page, the direct URL of the video
isn't available yet.

A field which isn't loaded can be set to :class:`woob.capabilities.base.NotLoaded`.

By default, in the object constructor, every fields should be set to
:class:`NotLoaded <woob.capabilities.base.NotLoaded>`, and when the backend loads them, it replaces them with
the new values.


