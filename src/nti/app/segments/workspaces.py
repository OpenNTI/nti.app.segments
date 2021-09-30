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

from zope.cachedescriptors.property import Lazy

from zope.location import ILocation

from zope.location.interfaces import IContained

from nti.app.segments import SEGMENTS

from nti.app.segments.interfaces import ISegmentsWorkspace

from nti.appserver.workspaces.interfaces import IUserService

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization_acl import has_permission

from nti.links import Link

from nti.property.property import alias

from nti.segments.interfaces import ISegmentsContainer

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ISegmentsWorkspace, IContained)
class _SegmentsWorkspace(object):

    __parent__ = None
    __name__ = SEGMENTS

    name = alias('__name__', __name__)

    def __init__(self, user_service):
        self.context = user_service
        self.user = user_service.user

    def __getitem__(self, key):
        """
        Make us traversable to collections.
        """
        # pylint: disable=not-an-iterable
        for i in self.collections:
            if i.__name__ == key:
                return i
        raise KeyError(key)  # pragma: no cover

    def __len__(self):
        return len(self.collections)

    @Lazy
    def collections(self):
        return ()

    @property
    def links(self):
        result = []

        segments_container = component.getUtility(ISegmentsContainer)
        if has_permission(ACT_READ, segments_container, self.user.username):
            link = Link(segments_container,
                        rel='Segments')
            link.__name__ = 'Segments'
            link.__parent__ = segments_container
            interface.alsoProvides(link, ILocation)
            result.append(link)

        return result


@component.adapter(IUserService)
@interface.implementer(ISegmentsWorkspace)
def SegmentsWorkspace(user_service):
    workspace = _SegmentsWorkspace(user_service)
    workspace.__parent__ = workspace.user
    return workspace
