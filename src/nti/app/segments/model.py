#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import operator
import time

from zope import component
from zope import interface

from zope.catalog.interfaces import IAttributeIndex

from zope.container.contained import Contained

from zope.intid import IIntIds

from nti.app.segments.interfaces import ICreatedTimeFilterSet
from nti.app.segments.interfaces import IIsDeactivatedFilterSet
from nti.app.segments.interfaces import ILastActiveFilterSet
from nti.app.segments.interfaces import IRelativeOffset
from nti.app.segments.interfaces import IStringProfileFieldFilterSet
from nti.app.segments.interfaces import ITimeRangeFilterSet
from nti.app.segments.interfaces import MATCH_OPS_REQUIRING_VALUE
from nti.app.segments.interfaces import MATCH_OP_EQUAL
from nti.app.segments.interfaces import MATCH_OP_NOT_EQUAL
from nti.app.segments.interfaces import MATCH_OP_NOT_SET
from nti.app.segments.interfaces import MATCH_OP_SET
from nti.app.segments.interfaces import RANGE_OP_AFTER

from nti.coremetadata.interfaces import IX_IS_DEACTIVATED
from nti.coremetadata.interfaces import IX_LASTSEEN
from nti.coremetadata.interfaces import IX_TOPICS

from nti.dataserver.metadata import get_metadata_catalog

from nti.dataserver.metadata.index import IX_CREATEDTIME
from nti.dataserver.metadata.index import IX_MIMETYPE

from nti.dataserver.users import get_entity_catalog

from nti.dataserver.users.interfaces import IUserProfile

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

from nti.segments.model import IntIdSet

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


@interface.implementer(IIsDeactivatedFilterSet)
class IsDeactivatedFilterSet(SchemaConfigured):

    createDirectFieldProperties(IIsDeactivatedFilterSet)

    mimeType = mime_type = "application/vnd.nextthought.segments.isdeactivatedfilterset"

    def __init__(self, **kwargs):
        SchemaConfigured.__init__(self, **kwargs)

    @property
    def entity_catalog(self):
        return get_entity_catalog()

    @property
    def deactivated_intids(self):
        deactivated_idx = self.entity_catalog[IX_TOPICS][IX_IS_DEACTIVATED]
        deactivated_ids = self.entity_catalog.family.IF.Set(deactivated_idx.getIds() or ())

        return deactivated_ids

    def apply(self, initial_set):
        if self.Deactivated:
            return initial_set.intersection(self.deactivated_intids)
        return initial_set.difference(self.deactivated_intids)


_missing_value = object()

#: Our set of operations, taking the actual value and test value, in that order
_operations = {
    MATCH_OP_EQUAL: operator.eq,
    MATCH_OP_NOT_EQUAL: operator.ne,
    MATCH_OP_SET: lambda x, _y: x is not None,
    MATCH_OP_NOT_SET: lambda x, _y: x is None,
}


@interface.implementer(IStringProfileFieldFilterSet)
class StringProfileFieldFilterSet(SchemaConfigured):

    createDirectFieldProperties(IStringProfileFieldFilterSet)

    mimeType = mime_type = "application/vnd.nextthought.segments.stringprofilefieldfilterset"

    def __init__(self, **kwargs):
        SchemaConfigured.__init__(self, **kwargs)

    @property
    def intids(self):
        return component.getUtility(IIntIds)

    @property
    def _operation(self):
        return _operations.get(self.operator)

    @property
    def _entity_catalog(self):
        return get_entity_catalog()

    def _search_index(self, initial_set):
        # Currently only handling `IAttributeIndex` queries, which are used by
        # all supported fields in the entity catalog.  These do not allow values
        # of `None`
        index = self._entity_catalog[self.fieldName]
        if self.operator in MATCH_OPS_REQUIRING_VALUE and self.value is not None:
            matched_intids = index.values_to_documents.get(self.value) or ()
            if self.operator == MATCH_OP_EQUAL:
                result = initial_set.intersection(matched_intids)
            else:
                result = initial_set.difference(matched_intids)
        else:
            matched_intids = index.documents_to_values.keys()

            if self.operator in (MATCH_OP_SET, MATCH_OP_NOT_EQUAL):
                # Objects whose value is set or not equal to None
                result = initial_set.intersection(matched_intids)
            else:
                # Objects whose value is not set or equal to None
                result = initial_set.difference(matched_intids)

        return result

    def _use_index(self):
        if self.fieldName not in self._entity_catalog:
            return False

        # Currently only supporting IFieldIndex queries
        return IAttributeIndex.providedBy(self._entity_catalog[self.fieldName])

    def _search_objects(self, initial_set):
        result = IntIdSet([])
        for uid in initial_set.intids():
            user = self.intids.getObject(uid)
            profile = IUserProfile(user, None)

            # Ensure we handle any missing fields
            # If the operator is not_set, should we return users whose profile
            # interface doesn't even define the field?
            profile_value = getattr(profile, self.fieldName, None)

            # Add to our set if it's a match, as defined by the operation
            if self._operation(profile_value, self.value):
                result.add(uid)

        return result

    def apply(self, initial_set):

        if self._use_index():
            return self._search_index(initial_set)

        return self._search_objects(initial_set)
