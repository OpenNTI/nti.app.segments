#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import copy

from datetime import timedelta

import fudge

from hamcrest import assert_that
from hamcrest import contains
from hamcrest import has_length
from hamcrest import is_
from hamcrest import not_none

from nti.app.segments.generations import evolve2

from nti.app.segments.interfaces import IIsDeactivatedFilterSet as NewIIsDeactivatedFilterSet
from nti.app.segments.interfaces import ILastActiveFilterSet
from nti.app.segments.interfaces import RANGE_OP_BEFORE

from nti.app.segments.model import IsDeactivatedFilterSet as NewDeactivatedFilterSet
from nti.app.segments.model import LastActiveFilterSet
from nti.app.segments.model import RelativeOffset

from nti.app.site.hostpolicy import create_site

from nti.dataserver.tests import mock_dataserver as mock_dataserver

from nti.dataserver.tests.mock_dataserver import DataserverLayerTest
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.segments.model import IntersectionUserFilterSet
from nti.segments.model import IsDeactivatedFilterSet as OldIsDeactivatedFilterSet
from nti.segments.model import UnionUserFilterSet
from nti.segments.model import UserSegment
from nti.segments.model import install_segments_container

from nti.testing import verifiably_provides

__docformat__ = "restructuredtext en"


def simple_filterset(*filter_sets):
    union_filterset = UnionUserFilterSet(filter_sets=list(filter_sets))
    return IntersectionUserFilterSet(filter_sets=[union_filterset])


def simple_segment(*filter_set):
    return UserSegment(title=u'My Segment',
                       filter_set=simple_filterset(*filter_set))


class TestEvolve2(DataserverLayerTest):

    @WithMockDSTrans
    @fudge.patch('nti.app.segments.generations.evolve2.logger')
    def test_evolve2(self, logger):
        captured_logs = []

        def capturing_logger(*args):
            captured_logs.append(args)

        logger.provides('info').calls(capturing_logger)

        conn = mock_dataserver.current_transaction

        class _Context(object):
            pass
        context = _Context()
        context.connection = conn

        # Set up multiple segments using old class
        site_one = create_site('site.one')
        site_one_segments = install_segments_container(site_one)

        segment = simple_segment(OldIsDeactivatedFilterSet(Deactivated=True))
        site_one_segments['seg.one'] = segment

        relative_offset = RelativeOffset(duration=timedelta(days=1),
                                         operator=RANGE_OP_BEFORE)
        last_active_filter_set = LastActiveFilterSet(period=relative_offset)
        segment = simple_segment(last_active_filter_set)
        site_one_segments['seg.two'] = segment

        segment = simple_segment(OldIsDeactivatedFilterSet(Deactivated=False))
        site_one_segments['seg.three'] = segment

        # Set up a complex filterset using the old class
        site_two = create_site('site.two')
        site_two_segments = install_segments_container(site_two)

        segment = simple_segment(copy.deepcopy(last_active_filter_set),
                                 OldIsDeactivatedFilterSet(Deactivated=False))
        site_two_segments['seg.one'] = segment

        # Set up a site where the old class isn't used
        site_three = create_site('site.three')
        site_three_segments = install_segments_container(site_three)

        segment = simple_segment(copy.deepcopy(last_active_filter_set))
        site_three_segments['seg.one'] = segment

        evolve2.do_evolve(context)

        # Verify site one segment
        assert_that(site_one_segments, has_length(3))
        filter_set = site_one_segments['seg.one'].filter_set
        assert_that(filter_set.filter_sets[0].filter_sets[0],
                    verifiably_provides(NewIIsDeactivatedFilterSet))
        assert_that(filter_set.filter_sets[0].filter_sets[0],
                    is_(NewDeactivatedFilterSet))
        assert_that(filter_set.filter_sets[0].filter_sets[0].Deactivated,
                    is_(True))

        filter_set = site_one_segments['seg.two'].filter_set
        assert_that(filter_set.filter_sets[0].filter_sets[0],
                    verifiably_provides(ILastActiveFilterSet))
        assert_that(filter_set.filter_sets[0].filter_sets[0],
                    is_(LastActiveFilterSet))

        filter_set = site_one_segments['seg.three'].filter_set
        assert_that(filter_set.filter_sets[0].filter_sets[0],
                    verifiably_provides(NewIIsDeactivatedFilterSet))
        assert_that(filter_set.filter_sets[0].filter_sets[0],
                    is_(NewDeactivatedFilterSet))
        assert_that(filter_set.filter_sets[0].filter_sets[0].Deactivated,
                    is_(False))

        # Verify site two segment
        assert_that(site_two_segments, has_length(1))
        filter_set = site_two_segments['seg.one'].filter_set
        assert_that(filter_set.filter_sets[0].filter_sets, has_length(2))
        assert_that(filter_set.filter_sets[0].filter_sets[1],
                    verifiably_provides(NewIIsDeactivatedFilterSet))
        assert_that(filter_set.filter_sets[0].filter_sets[1],
                    is_(NewDeactivatedFilterSet))
        assert_that(filter_set.filter_sets[0].filter_sets[1].Deactivated,
                    is_(False))

        # Verify site three segment
        assert_that(site_three_segments, has_length(1))

        filter_set = site_three_segments['seg.one'].filter_set
        assert_that(filter_set.filter_sets[0].filter_sets[0],
                    verifiably_provides(ILastActiveFilterSet))
        assert_that(filter_set.filter_sets[0].filter_sets[0],
                    is_(LastActiveFilterSet))

        # Verify expected migration totals
        assert_that(captured_logs, has_length(1))
        assert_that(captured_logs[0], has_length(5))
        assert_that(captured_logs[0], contains(
            not_none(),
            2,  # Generation
            3,  # Segments updated
            2,  # Sites updated
            3   # Total sites
        ))
