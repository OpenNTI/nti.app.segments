#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import fudge

from hamcrest import assert_that
from hamcrest import has_length
from hamcrest import is_
from hamcrest import none
from hamcrest import not_
from hamcrest import same_instance

from z3c.baseregistry.baseregistry import BaseComponents

from zope.component import globalSiteManager as BASE

from zope.interface.interfaces import IComponents

from zope.site.interfaces import INewLocalSite

from nti.app.authentication.subscribers import install_site_authentication

from nti.app.segments.generations.install import evolve

from nti.appserver.policies.sites import BASEADULT

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.tests.mock_dataserver import DataserverLayerTest
from nti.dataserver.tests.mock_dataserver import mock_db_trans

from nti.segments.interfaces import ISegmentsContainer

from nti.site.hostpolicy import synchronize_host_policies

from nti.site.interfaces import IHostPolicySiteManager

from nti.site.site import get_site_for_site_names

__docformat__ = "restructuredtext en"

TEST_BASE = BaseComponents(BASEADULT,
                           name='test.nextthought.com',
                           bases=(BASEADULT,))

TEST_CHILD = BaseComponents(TEST_BASE,
                            name='test-child.nextthought.com',
                            bases=(TEST_BASE,))

SITES = (TEST_BASE,
         TEST_CHILD)


class TestFunctionalInstall(DataserverLayerTest):

    def setUp(self):
        super(TestFunctionalInstall, self).setUp()
        for bc in SITES:
            bc.__init__(bc.__parent__, name=bc.__name__, bases=bc.__bases__)
            BASE.registerUtility(bc, name=bc.__name__, provided=IComponents)

        # We want to test sites that were created prior to this handler
        # being in place, so disable it for the test
        BASE.unregisterHandler(install_site_authentication, (IHostPolicySiteManager, INewLocalSite))

    def tearDown(self):
        for bc in SITES:
            BASE.unregisterUtility(bc, name=bc.__name__, provided=IComponents)
        BASE.registerHandler(install_site_authentication, (IHostPolicySiteManager, INewLocalSite))
        super(TestFunctionalInstall, self).tearDown()

    def get_segments_container(self, site):
        sm = site.getSiteManager()
        authentication_utils = [reg for reg in sm.registeredUtilities()
                                if (reg.provided.isOrExtends(ISegmentsContainer)
                                    and reg.name == '')]
        return authentication_utils

    @mock_dataserver.WithMockDS
    def test_installed(self):

        with mock_db_trans(self.ds) as conn:
            context = fudge.Fake().has_attr(connection=conn)
            synchronize_host_policies()

            # Verify we don't have the container yet
            test_base_site = get_site_for_site_names(('test.nextthought.com',))
            base_container = self.get_segments_container(test_base_site)
            assert_that(base_container, has_length(0))
            test_base_sm = test_base_site.getSiteManager()
            assert_that(test_base_sm.get('default', {}).get('segments-container'),
                        is_(none()))

            test_child_site = get_site_for_site_names(('test-child.nextthought.com',))
            child_container = self.get_segments_container(test_child_site)
            assert_that(child_container, has_length(0))
            test_child_sm = test_child_site.getSiteManager()
            assert_that(test_child_sm.get('default', {}).get('segments-container'),
                        is_(none()))

            evolve(context)

            # Ensure site container was added
            base_container = self.get_segments_container(test_base_site)
            assert_that(base_container, has_length(1))
            assert_that(test_base_sm.get('default', {}).get('segments-container'),
                        not_(none()))

            child_container = self.get_segments_container(test_child_site)
            assert_that(child_container, has_length(1))
            assert_that(child_container, not_(same_instance(base_container[0])))
            assert_that(test_child_sm.get('default', {}).get('segments-container'),
                        not_(none()))
