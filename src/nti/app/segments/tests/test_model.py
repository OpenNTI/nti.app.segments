#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time
from contextlib import contextmanager
from datetime import timedelta

from unittest import TestCase

import fudge
from hamcrest import assert_that
from hamcrest import calling
from hamcrest import contains_inanyorder
from hamcrest import has_entries
from hamcrest import has_key
from hamcrest import has_length
from hamcrest import has_properties
from hamcrest import is_
from hamcrest import not_
from hamcrest import not_none
from hamcrest import raises

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite
from zope.interface.interfaces import IComponents

from zope.intid import IIntIds

from zope.lifecycleevent import modified

from zope.schema.interfaces import ConstraintNotSatisfied


from nti.app.segments.interfaces import ICreatedTimeFilterSet
from nti.app.segments.interfaces import IIsDeactivatedFilterSet
from nti.app.segments.interfaces import ILastActiveFilterSet
from nti.app.segments.interfaces import IStringProfileFieldFilterSet
from nti.app.segments.interfaces import MATCH_OP_EQUAL
from nti.app.segments.interfaces import MATCH_OP_NOT_EQUAL
from nti.app.segments.interfaces import MATCH_OP_NOT_SET
from nti.app.segments.interfaces import MATCH_OP_SET
from nti.app.segments.interfaces import RANGE_OP_AFTER
from nti.app.segments.interfaces import RANGE_OP_BEFORE

from nti.app.segments.model import CreatedTimeFilterSet
from nti.app.segments.model import IsDeactivatedFilterSet
from nti.app.segments.model import LastActiveFilterSet
from nti.app.segments.model import RelativeOffset
from nti.app.segments.model import StringProfileFieldFilterSet

from nti.app.segments.tests import SharedConfiguringTestLayer

from nti.app.site.hostpolicy import create_site

from nti.appserver.policies.sites import BASEADULT

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import WithMockDS

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import ICompleteUserProfile

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


class IsDeactivatedModelTest(TestCase):

    layer = SharedConfiguringTestLayer

    def _internalize(self, external):
        factory = find_factory_for(external)
        assert_that(factory, is_(not_none()))
        new_io = factory()
        if new_io is not None:
            update_from_external_object(new_io, external)
        return new_io

    def test_valid_interface(self):
        assert_that(IsDeactivatedFilterSet(Deactivated=True),
                    verifiably_provides(IIsDeactivatedFilterSet))

    def test_internalize(self):
        ext_obj = {
            "MimeType": IsDeactivatedFilterSet.mime_type,
            "Deactivated": True,
        }
        filter_set = self._internalize(ext_obj)
        assert_that(filter_set, is_(IsDeactivatedFilterSet))
        assert_that(filter_set, has_properties(
            Deactivated=True,
        ))

    def test_externalize(self):
        filter_set = IsDeactivatedFilterSet(Deactivated=False)

        ext_filterset = to_external_object(filter_set)
        assert_that(ext_filterset,
                    has_entries({
                        'MimeType': IsDeactivatedFilterSet.mime_type,
                        "Deactivated": False
                    }))


class StringProfileFieldFilterSetModelTest(TestCase):

    layer = SharedConfiguringTestLayer

    def _internalize(self, external):
        factory = find_factory_for(external)
        assert_that(factory, is_(not_none()))
        new_io = factory()
        if new_io is not None:
            update_from_external_object(new_io, external)
        return new_io

    def test_valid_interface(self):
        assert_that(StringProfileFieldFilterSet(fieldName='alias',
                                                operator=MATCH_OP_EQUAL,
                                                value=u'test_value'),
                    verifiably_provides(IStringProfileFieldFilterSet))

    def test_interface_invariant(self):
        ext_obj = {
            "MimeType": StringProfileFieldFilterSet.mime_type,
            "fieldName": "alias",
            "operator": MATCH_OP_EQUAL
        }
        assert_that(calling(self._internalize).with_args(ext_obj),
                    raises(ConstraintNotSatisfied,
                           u"Must supply a value for the chosen operator."))

    def test_internalize(self):
        ext_obj = {
            "MimeType": StringProfileFieldFilterSet.mime_type,
            "fieldName": "alias",
            "operator": MATCH_OP_EQUAL,
            "value": u"test_value"
        }
        filter_set = self._internalize(ext_obj)
        assert_that(filter_set, is_(StringProfileFieldFilterSet))
        assert_that(filter_set, has_properties(
            fieldName="alias",
            operator=MATCH_OP_EQUAL,
            value=u"test_value"
        ))

    def test_externalize(self):
        filter_set = StringProfileFieldFilterSet(fieldName='alias',
                                                 operator=MATCH_OP_EQUAL,
                                                 value=u'test_value')

        ext_filterset = to_external_object(filter_set)
        assert_that(ext_filterset,
                    has_entries({
                        'MimeType': "application/vnd.nextthought.segments.stringprofilefieldfilterset",
                        "fieldName": "alias",
                        "operator": MATCH_OP_EQUAL,
                        "value": u"test_value"
                    }))


class StringProfileFieldFilterSetApplyTest(TestCase):

    layer = SharedConfiguringTestLayer

    def _create_filterset(self, fieldName, operator, value=None):
        kwargs = dict(value=value) if value is not None else dict()
        filter_set = StringProfileFieldFilterSet(fieldName=fieldName,
                                                 operator=operator,
                                                 **kwargs)

        return filter_set

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    def apply(self, filter_set):
        initial_intids = intids_of_users_by_site(getSite(), filter_deactivated=False)

        rs = IntIdSet(initial_intids)
        result_intids = filter_set.apply(rs).intids()

        return [self.intids.getObject(uid).username for uid in result_intids]

    @WithMockDS
    def test_apply_no_index(self):

        site_name = 'string-profile-field-test-site'
        with mock_dataserver.mock_db_trans():
            create_site(site_name)

        with _provide_utility(BASEADULT, IComponents, name='genericadultbase'):
            with mock_dataserver.mock_db_trans(site_name=site_name):
                user_one = User.create_user(username=u'user.one')
                user_two = User.create_user(username=u'user.two')
                User.create_user(username=u'user.three')

                ICompleteUserProfile(user_one).role = u'user one role'
                ICompleteUserProfile(user_one).location = u'user one location'
                modified(user_one)

                ICompleteUserProfile(user_two).role = u'user two role'
                modified(user_two)

            with mock_dataserver.mock_db_trans(site_name=site_name):
                filter_set_equal = self._create_filterset(u'role',
                                                          MATCH_OP_EQUAL,
                                                          u'user one role')
                filter_set_nequal = self._create_filterset(u'role',
                                                           MATCH_OP_NOT_EQUAL,
                                                           u'user one role')

                users = self.apply(filter_set_equal)
                assert_that(users, contains_inanyorder(u'user.one'))

                users = self.apply(filter_set_nequal)
                assert_that(users, contains_inanyorder(u'user.two',
                                                       u'user.three'))

            with mock_dataserver.mock_db_trans(site_name=site_name):
                filter_set_equal = self._create_filterset(u'location',
                                                          MATCH_OP_EQUAL,
                                                          None)
                filter_set_nequal = self._create_filterset(u'location',
                                                           MATCH_OP_NOT_EQUAL,
                                                           None)

                users = self.apply(filter_set_equal)
                assert_that(users, contains_inanyorder(u'user.two',
                                                       u'user.three'))

                users = self.apply(filter_set_nequal)
                assert_that(users, contains_inanyorder(u'user.one'))

            with mock_dataserver.mock_db_trans(site_name=site_name):
                filter_set_set = self._create_filterset(u'role',
                                                        MATCH_OP_SET)
                filter_set_nset = self._create_filterset(u'role',
                                                         MATCH_OP_NOT_SET)

                users = self.apply(filter_set_set)
                assert_that(users, contains_inanyorder(u'user.one',
                                                       u'user.two'))

                users = self.apply(filter_set_nset)
                assert_that(users, contains_inanyorder(u'user.three'))

            with mock_dataserver.mock_db_trans(site_name=site_name):
                filter_set_equal = self._create_filterset(u'role',
                                                          MATCH_OP_EQUAL,
                                                          u'unmatched value')

                users = self.apply(filter_set_equal)
                assert_that(users, has_length(0))

    @WithMockDS
    @fudge.patch('nti.app.segments.model.StringProfileFieldFilterSet.intids')
    def test_apply_index(self, filter_set_intids):
        @interface.implementer(IIntIds)
        class CallTrackingIntIds(object):
            count = 0

            @Lazy
            def _intids(self):
                return component.getUtility(IIntIds)

            def getObject(self, obj):
                self.count += 1
                return self._intids.getObject(obj)

        call_tracking_intids = CallTrackingIntIds()
        filter_set_intids.provides('getObject').calls(call_tracking_intids.getObject)

        site_name = 'string-profile-field-test-site'
        with mock_dataserver.mock_db_trans():
            create_site(site_name)

        with _provide_utility(BASEADULT, IComponents, name='genericadultbase'):
            with mock_dataserver.mock_db_trans(site_name=site_name):
                User.create_user(username=u'user.one')
                user_two = User.create_user(username=u'user.two')
                user_three = User.create_user(username=u'user.three')

                ICompleteUserProfile(user_two).alias = u'user.two'
                modified(user_two)

                ICompleteUserProfile(user_three).alias = u'user.three'
                modified(user_three)

            with mock_dataserver.mock_db_trans(site_name=site_name):
                filter_set_equal = self._create_filterset(u'alias',
                                                          MATCH_OP_EQUAL,
                                                          u'user.three')
                filter_set_nequal = self._create_filterset(u'alias',
                                                           MATCH_OP_NOT_EQUAL,
                                                           u'user.three')

                users = self.apply(filter_set_equal)
                assert_that(users, contains_inanyorder(u'user.three'))

                users = self.apply(filter_set_nequal)
                assert_that(users, contains_inanyorder(u'user.one',
                                                       u'user.two'))

            with mock_dataserver.mock_db_trans(site_name=site_name):
                filter_set_equal = self._create_filterset(u'alias',
                                                          MATCH_OP_EQUAL,
                                                          None)
                filter_set_nequal = self._create_filterset(u'alias',
                                                           MATCH_OP_NOT_EQUAL,
                                                           None)

                users = self.apply(filter_set_equal)
                assert_that(users, contains_inanyorder(u'user.one'))

                users = self.apply(filter_set_nequal)
                assert_that(users, contains_inanyorder(u'user.two',
                                                       u'user.three'))

            with mock_dataserver.mock_db_trans(site_name=site_name):
                filter_set_set = self._create_filterset(u'alias',
                                                        MATCH_OP_SET)
                filter_set_nset = self._create_filterset(u'alias',
                                                         MATCH_OP_NOT_SET)

                users = self.apply(filter_set_set)
                assert_that(users, contains_inanyorder(u'user.two',
                                                       u'user.three'))

                users = self.apply(filter_set_nset)
                assert_that(users, contains_inanyorder(u'user.one'))

            with mock_dataserver.mock_db_trans(site_name=site_name):
                filter_set_equal = self._create_filterset(u'alias',
                                                          MATCH_OP_EQUAL,
                                                          u'unmatched value')

                users = self.apply(filter_set_equal)
                assert_that(users, has_length(0))

            # Should have entirely used the index, hence no getObject calls
            # via IIntIds
            assert_that(call_tracking_intids.count, is_(0))
