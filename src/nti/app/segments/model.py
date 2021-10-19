#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time

from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.container.contained import Contained

from nti.app.segments.interfaces import ILastActiveFilterSet
from nti.app.segments.interfaces import IRelativeOffset
from nti.app.segments.interfaces import RANGE_OP_AFTER
from nti.app.segments.interfaces import RANGE_OP_BEFORE

from nti.coremetadata.interfaces import IX_LASTSEEN

from nti.dataserver.metadata import get_metadata_catalog

from nti.dataserver.metadata.index import IX_MIMETYPE

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

logger = __import__('logging').getLogger(__name__)

USER_MIME_TYPE = 'application/vnd.nextthought.user'


@interface.implementer(IRelativeOffset)
class RelativeOffset(SchemaConfigured,
                     Contained):
    createDirectFieldProperties(IRelativeOffset)

    mimeType = mime_type = "application/vnd.nextthought.segments.relativeoffset"

    def __init__(self, **kwargs):
        SchemaConfigured.__init__(self, **kwargs)

    @property
    def start(self):
        if self.operator == RANGE_OP_AFTER:
            return time.time() + self.duration.total_seconds()

        return None

    @property
    def end(self):
        if self.operator == RANGE_OP_BEFORE:
            return time.time() + self.duration.total_seconds()

        return None


@interface.implementer(ILastActiveFilterSet)
class LastActiveFilterSet(SchemaConfigured,
                          Contained):
    createDirectFieldProperties(ILastActiveFilterSet)

    mimeType = mime_type = "application/vnd.nextthought.segments.lastactivefilterset"

    def __init__(self, **kwargs):
        SchemaConfigured.__init__(self, **kwargs)

    @Lazy
    def catalog(self):
        return get_metadata_catalog()

    def included_intids(self, start, end):
        query = {
            IX_MIMETYPE: {'any_of': (USER_MIME_TYPE,)},
            IX_LASTSEEN: {'between': (start, end)},
        }
        return self.catalog.apply(query)

    def apply(self, initial_set):
        return initial_set.intersection(self.included_intids(self.period.start,
                                                             self.period.end))