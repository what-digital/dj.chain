#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2011 - 2012 by Łukasz Langa
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Module name
   ----

   description"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from django.core.exceptions import FieldError
from lck.lang import unset


class chain(object):
    """Enables chaining multiple iterables to serve them lazily as
    a queryset-compatible object. Supports collective ``count()``, ``exists()``,
    ``exclude``, ``filter`` and ``order_by`` methods.

    Provides special overridable static methods used while yielding values:

      * ``xfilter(value)`` - yield a value only if ``xfilter(value)`` returns
                             ``True``. See known issues below.

      * ``xform(value)`` - transforms the value JIT before yielding it back.
                           It is only called for values within the specified
                           slice and those which passed ``xfilter``.

      * ``xkey(value)`` - returns a value to be used in comparison between
                          elements if sorting should be used. Individual
                          iterables should be presorted for the complete result
                          to be sorted properly.

    Known issues:

    1. If slicing or ``xfilter`` is used, reported ``len()`` is computed by
       iterating over all iterables so performance is weak. Note that
       ``len()`` is used by ``list()`` when you convert your lazy chain to
       a list or when iterating over the lazy chain in Django templates.
       If this is not expected, you can convert to a list using a workaround
       like this::

           list(e for e in some_chain)

    2. Indexing on lazy chains uses iteration underneath so performance
       is weak. This feature is only available as a last resort. Slicing on the
       other hand is also lazy."""

    def __init__(self, *iterables):
        self.iterables = iterables
        self.start = None
        self.stop = None
        self.step = None

    @staticmethod
    def xform(value):
        """Transform the ``value`` just-in-time before yielding it back.
        Default implementation simply returns the ``value`` as is."""
        return value

    @staticmethod
    def xfilter(value=unset):
        """xfilter(value) -> bool

        Only yield the ``value`` if this method returns ``True``.
        Skip to the next iterator value otherwise. Default implementation
        always returns ``True``."""
        return True

    @staticmethod
    def xkey(value=unset):
        """xkey(value) -> comparable value

        Return a value used in comparison between elements if sorting
        should be used."""
        return value

    def copy(self, *iterables):
        """Returns a copy of this lazy chain. If `iterables` are provided,
        they are used instead of the ones in the current object."""
        if not iterables:
            iterables = self.iterables
        result = chain(*iterables)
        result.xfilter = self.xfilter
        result.xform = self.xform
        result.xkey = self.xkey
        result.start = self.start
        result.stop = self.stop
        result.step = self.step
        return result

    def _filtered_next(self, iterator):
        """Raises StopIteration just like regular iterator.next()."""
        result = iterator.next()
        while not self.xfilter(result):
            result = iterator.next()
        return result

    def __iter__(self):
        if self.ordered:
            def _gen():
                candidates = {}
                for iterable in self.iterables:
                    iterator = iter(iterable)
                    try:
                        candidates[iterator] = [self._filtered_next(iterator),
                            iterator]
                    except StopIteration:
                        continue
                while candidates:
                    try:
                        to_yield, iterator = min(candidates.viewvalues(),
                            key=lambda x: self.xkey(x[0]))
                        yield to_yield
                    except ValueError:
                        # sequence empty
                        break
                    try:
                        candidates[iterator] = [self._filtered_next(iterator),
                            iterator]
                    except StopIteration:
                        del candidates[iterator]
        else:
            def _gen():
                for it in self.iterables:
                    for element in it:
                        if not self.xfilter(element):
                            continue
                        yield element
        for index, element in enumerate(_gen()):
            if self.start and index < self.start:
                continue
            if self.step and (index - (self.start or 0)) % self.step:
                continue
            if self.stop and index >= self.stop:
                break
            yield self.xform(element)

    def __getitem__(self, key):
        if isinstance(key, slice):
            if any((key.start and key.start < 0,
                    key.stop and key.stop < 0,
                    key.step and key.step < 0)):
                raise ValueError("lazy chains do not support negative indexing")
            result = self.copy()
            result.start = key.start
            result.stop = key.stop
            result.step = key.step
        elif isinstance(key, int):
            if key < 0:
                raise ValueError("lazy chains do not support negative indexing")
            self_without_transform = self.copy()
            self_without_transform.xform = lambda x: x
            for index, elem in enumerate(self_without_transform):
                if index == key:
                    return self.xform(elem)
            raise IndexError("lazy chain index out of range")
        else:
            raise ValueError("lazy chain supports only integer indexing and "
                "slices.")

        return result

    def __len_parts__(self):
        for iterable in self.iterables:
            try:
                yield iterable.count()
            except:
                try:
                    yield len(iterable)
                except TypeError:
                    yield len(list(iterable))

    def __len__(self):
        try:
            if all((self.xfilter(),
                    not self.start,
                    not self.stop,
                    not self.step or self.step == 1)):
                # fast __len__
                sum = 0
                for sub in self.__len_parts__():
                    sum += sub
                return sum
        except TypeError:
            pass
        # slow __len__ if xfilter or slicing was used
        length = 0
        for length, _ in enumerate(self):
            pass
        return length+1

    def _django_factory(self, _method, *args, **kwargs):
        new_iterables = []
        for it in self.iterables:
            try:
                new_iterables.append(getattr(it, _method)(*args, **kwargs))
            except (AttributeError, ValueError, FieldError):
                new_iterables.append(it)
        return self.copy(*new_iterables)

    def all(self):
        return self

    def count(self):
        """Queryset-compatible ``count`` method. Supports multiple iterables.
        """
        return len(self)

    def exclude(self, *args, **kwargs):
        """Queryset-compatible ``filter`` method. Will silently skip filtering
        for incompatible iterables."""
        return self._django_factory('exclude', *args, **kwargs)

    def exists(self):
        """Queryset-compatible ``exists`` method. Supports multiple iterables.
        """
        return bool(len(self))

    def filter(self, *args, **kwargs):
        """Queryset-compatible ``filter`` method. Will silently skip filtering
        for incompatible iterables."""
        return self._django_factory('filter', *args, **kwargs)

    def none(self, *args, **kwargs):
        return chain()

    def order_by(self, *args, **kwargs):
        """Queryset-compatible ``order_by`` method. Will silently skip ordering
        for incompatible iterables."""
        result = self._django_factory('order_by', *args, **kwargs)
        def xkey(value):
            for name in args:
                if name.startswith('-'):
                    yield -getattr(value, name[1:])
                else:
                    yield getattr(value, name)
        result.xkey = lambda v: list(xkey(v))
        return result

    @property
    def ordered(self):
        try:
            return self.xkey() is not unset
        except TypeError:
            return True
