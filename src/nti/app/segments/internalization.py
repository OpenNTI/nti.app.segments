#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from nti.app.segments.interfaces import ITimeRange

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import IInternalObjectUpdater


@component.adapter(ITimeRange)
@interface.implementer(IInternalObjectUpdater)
class TimeRangeUpdater(InterfaceObjectIO):

    _ext_iface_upper_bound = ITimeRange

    # InterfaceObjectIO doesn't seem to have a way to pull this
    # info from the iface so we do it manually.
    _excluded_in_ivars_ = frozenset(
        getattr(InterfaceObjectIO, '_excluded_in_ivars_').union({'range_tuple'}))
