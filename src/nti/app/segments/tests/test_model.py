#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from datetime import timedelta

from unittest import TestCase

from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_key
from hamcrest import has_properties
from hamcrest import is_
from hamcrest import not_
from hamcrest import not_none

from nti.app.segments.interfaces import ILastActiveFilterSet
from nti.app.segments.interfaces import RANGE_OP_AFTER
from nti.app.segments.interfaces import RANGE_OP_BEFORE

from nti.app.segments.model import LastActiveFilterSet
from nti.app.segments.model import RelativeOffset

from nti.app.segments.tests import SharedConfiguringTestLayer
from nti.externalization import to_external_object

from nti.externalization import update_from_external_object

from nti.externalization.internalization import find_factory_for

from nti.externalization.tests import externalizes

from nti.testing.matchers import verifiably_provides


class TestLastActiveFilterSet(TestCase):

    layer = SharedConfiguringTestLayer

    def _internalize(self, external):
        factory = find_factory_for(external)
        assert_that(factory, is_(not_none()))
        new_io = factory()
        if new_io is not None:
            update_from_external_object(new_io, external)
        return new_io

    def test_valid_interface(self):
        offset = RelativeOffset(duration=timedelta(days=30),
                                operator=RANGE_OP_AFTER)
        assert_that(LastActiveFilterSet(period=offset),
                    verifiably_provides(ILastActiveFilterSet))

    def test_internalize(self):
        ext_obj = {
            "MimeType": LastActiveFilterSet.mime_type,
            "period": {
                "MimeType": RelativeOffset.mime_type,
                "duration": "P20D",
                "operator": RANGE_OP_BEFORE,
                # This should just get ignored
                "range_tuple": [0, 1]
            }
        }
        filter_set = self._internalize(ext_obj)
        assert_that(filter_set, has_properties(
            period=has_properties(
                duration=timedelta(days=20),
                operator=RANGE_OP_BEFORE
            )
        ))

    def test_externalize(self):
        offset = RelativeOffset(duration=timedelta(days=30),
                                operator=RANGE_OP_AFTER)
        filter_set = LastActiveFilterSet(period=offset)

        ext_filterset = to_external_object(filter_set)
        assert_that(ext_filterset,
                    has_entries({
                        'MimeType': LastActiveFilterSet.mime_type,
                        "period": has_entries({
                            "MimeType": RelativeOffset.mime_type,
                            "duration": "P30D",
                            "operator": RANGE_OP_AFTER,
                        })
                    }))

        assert_that(ext_filterset['period'], not_(has_key('range_tuple')))
