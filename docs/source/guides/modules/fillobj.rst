Filling objects
===============

.. note::

    Filling objects using :func:`~woob.tools.backend.Module.fillobj` should be used whenever you need to fill some fields automatically based on data
    fetched from the scraping. If you only want to fill some fields automatically based on some static data, you should
    just inherit the base object class and set these fields.

An object returned by a method of a capability can be not fully completed.

The class :class:`~woob.tools.backend.Module` provides a method named
:func:`~woob.tools.backend.Module.fillobj`, which can be called by an application to
fill some unloaded fields of a specific object, for example with::

    backend.fillobj(video, ['url', 'author'])

The :func:`~woob.tools.backend.Module.fillobj` method will check on the object which fields (in the ones given in the list argument) are not loaded
(equal to ``NotLoaded``, which is the default value), to reduce the list to the real uncompleted fields, and call the
method associated to the type of the object.

To define what objects are supported to be filled, and what method to call, define the ``OBJECTS``
class attribute in your ``ExampleModule``::

    from woob.tools.backend import Module
    from woob.capabilities.video import CapVideo

    class ExampleModule(Module, CapVideo):
        # ...

        OBJECTS = {Video: fill_video}

The prototype of the function might be::

    func(self, obj, fields)

Then, the function might, for each requested fields, fetch the right data and fill the object. For example::

    from woob.tools.backend import Module
    from woob.capabilities.video import CapVideo

    class ExampleModule(Module, CapVideo):
        # ...

        def fill_video(self, video, fields):
            if 'url' in fields:
                return self.backend.get_video(video.id)

            return video

Here, when the application has got a :class:`Video <woob.capabilities.video.BaseVideo>` object with
:func:`~woob.capabilities.video.CapVideo.search_videos`, in most cases, there are only some meta-data, but not the direct link to the video media.

As our method :func:`~woob.capabilities.video.CapVideo.get_video` will get all
of the missing data, we just call it with the object as parameter to complete it.
