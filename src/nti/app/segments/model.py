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

from zope.container.contained import Contained

from nti.app.segments.interfaces import ICreatedTimeFilterSet
from nti.app.segments.interfaces import ILastActiveFilterSet
from nti.app.segments.interfaces import IRelativeOffset
from nti.app.segments.interfaces import ITimeRangeFilterSet
from nti.app.segments.interfaces import RANGE_OP_AFTER

from nti.coremetadata.interfaces import IX_LASTSEEN

from nti.dataserver.metadata import get_metadata_catalog

from nti.dataserver.metadata.index import IX_CREATEDTIME
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
    def range_tuple(self):
        if self.duration is None:
            return None, None

        offset_time = time.time() + self.duration.total_seconds()
        if self.operator == RANGE_OP_AFTER:
            return offset_time, None

        return None, offset_time


class TimeRangeFilterSet(SchemaConfigured, Contained):
    createDirectFieldProperties(ITimeRangeFilterSet)

    def __init__(self, **kwargs):
        SchemaConfigured.__init__(self, **kwargs)

    @property
    def index_name(self):
        raise NotImplementedError()

    @property
    def catalog(self):
        return get_metadata_catalog()

    def _query(self, start, end):
        # Ensure adjacent ranges don't overlap
        exclude_max = False if end is None else True

        query = {
            IX_MIMETYPE: {'any_of': (USER_MIME_TYPE,)},
            self.index_name: {'between': (start, end, False, exclude_max)},
        }

        return query

    def included_intids(self, start, end):
        return self.catalog.apply(self._query(start, end))

    def apply(self, initial_set):
        start, end = self.period.range_tuple
        return initial_set.intersection(self.included_intids(start, end))


@interface.implementer(ILastActiveFilterSet)
class LastActiveFilterSet(TimeRangeFilterSet):
    createDirectFieldProperties(ILastActiveFilterSet)

    mimeType = mime_type = "application/vnd.nextthought.segments.lastactivefilterset"

    @property
    def index_name(self):
        return IX_LASTSEEN


@interface.implementer(ICreatedTimeFilterSet)
class CreatedTimeFilterSet(TimeRangeFilterSet):
    createDirectFieldProperties(ICreatedTimeFilterSet)

    mimeType = mime_type = "application/vnd.nextthought.segments.createdtimefilterset"

    @property
    def index_name(self):
        return IX_CREATEDTIME
