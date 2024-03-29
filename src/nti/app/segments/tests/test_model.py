#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time
from contextlib import contextmanager
from datetime import timedelta

from unittest import TestCase

from hamcrest import assert_that
from hamcrest import contains_inanyorder
from hamcrest import has_entries
from hamcrest import has_key
from hamcrest import has_length
from hamcrest import has_properties
from hamcrest import is_
from hamcrest import not_
from hamcrest import not_none

from zope import component

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite
from zope.interface.interfaces import IComponents

from zope.intid import IIntIds

from zope.lifecycleevent import modified

from nti.app.segments.interfaces import ICreatedTimeFilterSet
from nti.app.segments.interfaces import IIsDeactivatedFilterSet
from nti.app.segments.interfaces import ILastActiveFilterSet
from nti.app.segments.interfaces import RANGE_OP_AFTER
from nti.app.segments.interfaces import RANGE_OP_BEFORE

from nti.app.segments.model import CreatedTimeFilterSet
from nti.app.segments.model import IsDeactivatedFilterSet
from nti.app.segments.model import LastActiveFilterSet
from nti.app.segments.model import RelativeOffset

from nti.app.segments.tests import SharedConfiguringTestLayer

from nti.app.site.hostpolicy import create_site

from nti.appserver.policies.sites import BASEADULT

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDS

from nti.dataserver.users import User

from nti.dataserver.users.utils import intids_of_users_by_site

from nti.externalization import to_external_object
from nti.externalization import update_from_external_object

from nti.externalization.internalization import find_factory_for

from nti.segments.model import IntIdSet

from nti.testing.matchers import verifiably_provides


class TimeRangeFilterSetModelTestMixin(object):

    layer = SharedConfiguringTestLayer

    factory = None
    iface = None

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
        assert_that(self.factory(period=offset),
                    verifiably_provides(self.iface))

    def test_internalize(self):
        ext_obj = {
            "MimeType": self.factory.mime_type,
            "period": {
                "MimeType": RelativeOffset.mime_type,
                "duration": "P20D",
                "operator": RANGE_OP_BEFORE,
                # This should just get ignored
                "range_tuple": [0, 1]
            }
        }
        filter_set = self._internalize(ext_obj)
        assert_that(filter_set, is_(self.factory))
        assert_that(filter_set, has_properties(
            period=has_properties(
                duration=timedelta(days=20),
                operator=RANGE_OP_BEFORE
            )
        ))

    def test_externalize(self):
        offset = RelativeOffset(duration=timedelta(days=30),
                                operator=RANGE_OP_AFTER)
        filter_set = self.factory(period=offset)

        ext_filterset = to_external_object(filter_set)
        assert_that(ext_filterset,
                    has_entries({
                        'MimeType': self.factory.mime_type,
                        "period": has_entries({
                            "MimeType": RelativeOffset.mime_type,
                            "duration": "P30D",
                            "operator": RANGE_OP_AFTER,
                        })
                    }))

        assert_that(ext_filterset['period'], not_(has_key('range_tuple')))


class TestLastActiveFilterSet(TimeRangeFilterSetModelTestMixin, TestCase):

    layer = SharedConfiguringTestLayer

    factory = LastActiveFilterSet
    iface = ILastActiveFilterSet


class TestCreatedTimeFilterSet(TimeRangeFilterSetModelTestMixin, TestCase):

    layer = SharedConfiguringTestLayer

    factory = CreatedTimeFilterSet
    iface = ICreatedTimeFilterSet


@contextmanager
def _provide_utility(util, iface, **kwargs):
    gsm = component.getGlobalSiteManager()

    gsm.registerUtility(util, iface, **kwargs)
    try:
        yield
    finally:
        gsm.unregisterUtility(util, iface, **kwargs)


class ApplyTimeRangeFilterSetTestMixin(object):

    layer = SharedConfiguringTestLayer

    factory = None
    attribute_name = None

    def _create_filterset(self, duration, operator):
        offset = RelativeOffset(duration=duration,
                                operator=operator)
        filter_set = self.factory(period=offset)

        return filter_set

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    def apply(self, filter_set, site=None):
        site = site if site is not None else getSite()
        initial_intids = intids_of_users_by_site(site, filter_deactivated=False)

        rs = IntIdSet(initial_intids)
        result_intids = filter_set.apply(rs).intids()

        return [self.intids.getObject(uid).username for uid in result_intids]

    @WithMockDS
    def test_apply(self):

        with mock_dataserver.mock_db_trans():
            create_site('last-active-test-site')

        with _provide_utility(BASEADULT, IComponents, name='genericadultbase'):
            with mock_dataserver.mock_db_trans(site_name='last-active-test-site'):
                user_one = User.create_user(username=u'user.one')
                user_two = User.create_user(username=u'user.two')
                user_three = User.create_user(username=u'user.three')

                now = time.time()
                setattr(user_one, self.attribute_name, now)
                modified(user_one)

                setattr(user_two, self.attribute_name,
                        now - timedelta(days=10).total_seconds())
                modified(user_two)

                setattr(user_three, self.attribute_name,
                        now - timedelta(days=30).total_seconds())
                modified(user_three)

            with mock_dataserver.mock_db_trans(site_name='last-active-test-site'):
                filter_set_before = self._create_filterset(timedelta(days=0),
                                                           RANGE_OP_BEFORE)
                filter_set_after = self._create_filterset(timedelta(days=0),
                                                          RANGE_OP_AFTER)

                users = self.apply(filter_set_before)
                assert_that(users, contains_inanyorder(u'user.two',
                                                       u'user.three'))

                users = self.apply(filter_set_after)
                assert_that(users, contains_inanyorder(u'user.one'))

            with mock_dataserver.mock_db_trans(site_name='last-active-test-site'):
                filter_set_before = self._create_filterset(timedelta(days=-11),
                                                           RANGE_OP_BEFORE)
                filter_set_after = self._create_filterset(timedelta(days=-11),
                                                          RANGE_OP_AFTER)

                users = self.apply(filter_set_before)
                assert_that(users, contains_inanyorder(u'user.three'))

                users = self.apply(filter_set_after)
                assert_that(users, contains_inanyorder(u'user.one', u'user.two'))

            with mock_dataserver.mock_db_trans(site_name='last-active-test-site'):
                filter_set_before = self._create_filterset(timedelta(days=-31),
                                                           RANGE_OP_BEFORE)
                filter_set_after = self._create_filterset(timedelta(days=-31),
                                                          RANGE_OP_AFTER)

                users = self.apply(filter_set_before)
                assert_that(users, has_length(0))

                users = self.apply(filter_set_after)
                assert_that(users, contains_inanyorder(u'user.one',
                                                       u'user.two',
                                                       u'user.three'))


class TestApplyLastActiveFilterSet(ApplyTimeRangeFilterSetTestMixin, TestCase):

    layer = SharedConfiguringTestLayer

    factory = LastActiveFilterSet
    attribute_name = u'lastSeenTime'


class TestApplyCreatedTimeFilterSet(ApplyTimeRangeFilterSetTestMixin, TestCase):

    layer = SharedConfiguringTestLayer

    factory = CreatedTimeFilterSet
    attribute_name = u'createdTime'


class IsDeactivatedModelTest(object):

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
        assert_that(IsDeactivatedFilterSet(period=offset),
                    verifiably_provides(IIsDeactivatedFilterSet))

    def test_internalize(self):
        ext_obj = {
            "MimeType": IsDeactivatedFilterSet.mime_type,
            "period": {
                "MimeType": RelativeOffset.mime_type,
                "Deactivated": "true",
            }
        }
        filter_set = self._internalize(ext_obj)
        assert_that(filter_set, is_(IsDeactivatedFilterSet))
        assert_that(filter_set, has_properties(
            period=has_properties(
                Deactivated=True,
            )
        ))

    def test_externalize(self):
        filter_set = IsDeactivatedFilterSet(Deactivated=False)

        ext_filterset = to_external_object(filter_set)
        assert_that(ext_filterset,
                    has_entries({
                        'MimeType': IsDeactivatedFilterSet.mime_type,
                        "Deactivated": "false"
                    }))
