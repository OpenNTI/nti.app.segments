#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import interface

from zope.interface import Interface

from zope.schema import PythonIdentifier

from zope.schema import vocabulary

from zope.schema.interfaces import ConstraintNotSatisfied

from nti.app.segments import MessageFactory as _

from nti.app.site.workspaces.interfaces import ISiteAdminCollection

from nti.schema.field import Bool
from nti.schema.field import ListOrTuple
from nti.schema.field import Number
from nti.schema.field import Object
from nti.schema.field import Timedelta
from nti.schema.field import ValidChoice
from nti.schema.field import ValidTextLine

from nti.segments.interfaces import IUserFilterSet


RANGE_OP_BEFORE = u"before"
RANGE_OP_AFTER = u"after"

RANGE_OPS = (RANGE_OP_BEFORE,
             RANGE_OP_AFTER)

RANGE_OP_VOCABULARY = vocabulary.SimpleVocabulary(
    tuple(vocabulary.SimpleTerm(x) for x in RANGE_OPS)
)

MATCH_OP_EQUAL = u"equal"
MATCH_OP_NOT_EQUAL = u"not_equal"
MATCH_OP_SET = u"set"
MATCH_OP_NOT_SET = u"not_set"

MATCH_OPS = (MATCH_OP_EQUAL,
             MATCH_OP_NOT_EQUAL,
             MATCH_OP_SET,
             MATCH_OP_NOT_SET)

MATCH_OPS_REQUIRING_VALUE = frozenset({MATCH_OP_EQUAL,
                                       MATCH_OP_NOT_EQUAL})

MATCH_OP_VOCABULARY = vocabulary.SimpleVocabulary(
    tuple(vocabulary.SimpleTerm(x) for x in MATCH_OPS)
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
    range_tuple.setTaggedValue('_ext_excluded_out', True)


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


class ITimeRangeFilterSet(IUserFilterSet):
    """
    A filter set selecting users with a specific event within a defined time
    range, e.g. when a user was last active.  Initially the range is based on
    some time period from the present (e.g. last 30 days), but could be
    extended to static start and end dates.
    """

    period = Object(ITimeRange,
                    title=u'Period',
                    description=u'Description of a time range encompassing '
                                u'the desired user attribute value.')


class ILastActiveFilterSet(ITimeRangeFilterSet):
    """
    A time-range filter set based on user's most recent activity on the
    platform.
    """


class ICreatedTimeFilterSet(ITimeRangeFilterSet):
    """
    A time-range filter set based on when a user was created in teh system.
    """


class IIsDeactivatedFilterSet(IUserFilterSet):
    """
    A filter set describing users with a given deactivation status.
    """

    Deactivated = Bool(title=u'Deactivated',
                       description=u'Whether to include only deactivated or activated users',
                       required=True,
                       default=False)


class IProfileFieldFilterSet(IUserFilterSet):
    """
    A filter set describing users with attributes from their profiles matching
    certain values.
    """

    fieldName = PythonIdentifier(title=u'Field Name',
                                 description=u'Name of the field on the profile object to test against'
                                             u' values provided.',
                                 required=True)

    # TODO: Should eventually be the following:
    #
    # fieldName = DottedName(title=u'Field Name',
    #                              description=u'Name of the field on the profile object to test against'
    #                                          u' values provided.  Can be nested using dotted'
    #                                          u' identifiers.',
    #                              required=True)


class IStringProfileFieldFilterSet(IProfileFieldFilterSet):
    """
    A profile filter set for string-based values.
    """

    value = ValidTextLine(title=u'Matching Value',
                          description=u'Value of the profile field to match or ',
                          required=False)

    operator = ValidChoice(title=u'Operator',
                           description=u'How to use the supplied value to match records (e.g. '
                                       u'equal to or has a value)',
                           vocabulary=MATCH_OP_VOCABULARY,
                           required=True)

    @interface.invariant
    def ValueInvariant(self):
        # Should we forbid setting `value` for the other operators (e.g. `set`)?
        if self.value == IStringProfileFieldFilterSet['value'].missing_value:
            if self.operator in MATCH_OPS_REQUIRING_VALUE:
                ve = ConstraintNotSatisfied(_(u"Must supply a value for the chosen operator."))
                ve.field = IStringProfileFieldFilterSet['value']

                raise ve
