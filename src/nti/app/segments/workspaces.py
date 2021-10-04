#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from nti.app.site.workspaces.interfaces import ISiteAdminWorkspace

from nti.app.segments.interfaces import ISegmentsCollection

from nti.segments.interfaces import ISegmentsContainer

from nti.segments.model import UserSegment

logger = __import__('logging').getLogger(__name__)


@component.adapter(ISiteAdminWorkspace)
@interface.implementer(ISegmentsCollection)
class SegmentsCollection(object):
    """
    Collection of segments accessible by user.
    """

    name = u'Segments'
    __name__ = name
    __parent__ = None

    def __init__(self, user_workspace):
        self.__parent__ = user_workspace

    @property
    def container(self):
        return component.getUtility(ISegmentsContainer)

    @property
    def accepts(self):
        return (UserSegment.mimeType, )

    @property
    def links(self):
        return ()
