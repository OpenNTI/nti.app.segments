#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from zope.container.contained import Contained

from zope.traversing.interfaces import IPathAdapter

from nti.app.segments import MEMBERS

from nti.segments.interfaces import IUserSegment


@interface.implementer(IPathAdapter)
@component.adapter(IUserSegment)
class MembersPathAdapter(Contained):

    __name__ = MEMBERS

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.__parent__ = context
