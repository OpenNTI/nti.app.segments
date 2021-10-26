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

from nti.appserver.pyramid_authorization import has_permission

from nti.segments.interfaces import ISegmentsContainer

from nti.segments.model import UserSegment

from nti.dataserver.authorization import ACT_LIST

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ISegmentsCollection)
class SegmentsCollection(object):
    """
    Collection of segments accessible by user.
    """

    name = u'Segments'
    __name__ = name
    __parent__ = None

    def __init__(self, admin_workspace):
        self.__parent__ = admin_workspace

    @property
    def container(self):
        return component.getUtility(ISegmentsContainer)

    @property
    def accepts(self):
        return (UserSegment.mimeType, )

    @property
    def links(self):
        return ()


@component.adapter(ISiteAdminWorkspace)
@interface.implementer(ISegmentsCollection)
def segments_collection(admin_workspace):
    segments_container = component.queryUtility(ISegmentsContainer)
    if has_permission(ACT_LIST, segments_container):
        return SegmentsCollection(admin_workspace)

    return None
