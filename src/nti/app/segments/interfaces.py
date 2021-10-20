#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.interface import Interface

from zope.schema import vocabulary

from nti.app.site.workspaces.interfaces import ISiteAdminCollection

from nti.schema.field import ListOrTuple
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import Timedelta
from nti.schema.field import ValidChoice

from nti.segments.interfaces import IUserFilterSet

RANGE_OP_BEFORE = u"before"
RANGE_OP_AFTER = u"after"

RANGE_OPS = (RANGE_OP_BEFORE,
             RANGE_OP_AFTER)

RANGE_OP_VOCABULARY = vocabulary.SimpleVocabulary(
    tuple(vocabulary.SimpleTerm(x) for x in RANGE_OPS)
)


class ISegmentsCollection(ISiteAdminCollection):
    """
    Collection of segments supplied as a collection in the site admin workspace.
    """


class ITimeRange(Interface):

    range_tuple = ListOrTuple(title=u'Range Tuple',
                              description=u'Tuple including the start and end of '
                                          u'the range, expressed as epoch times.',
                              value_type=Number(title=u'Start or end time.',
                                                required=False),
                              min_length=2,
                              max_length=2,
                              required=True)


class IRelativeOffset(ITimeRange):
    """
    Time period describing a open-ended range of time either before or after
    some time relative to now (e.g. more or less than 30 days ago). Durations
    are ISO 8601 durations, but are allowed to be negative to represent times in
    the past.
    """

    duration = Timedelta(title=u"Duration",
                         description=u"Offset from present time.",
                         required=True)

    operator = ValidChoice(title=u'Operator',
                           description=u'Whether to include users with activity '
                                       u'before or after the date provided',
                           vocabulary=RANGE_OP_VOCABULARY,
                           required=True)


class ILastActiveFilterSet(IUserFilterSet):
    """
    A filter set describing users active within some time frame, initially
    within some time period from the present (e.g. last 30 days), but could be
    extended to static start and end dates.
    """

    period = Object(ITimeRange,
                    title=u'Period',
                    description=u'Description of a time range encompassing '
                                u'the desired user activity.')
