#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import lifecycleevent

from zope.component.hooks import getSite
from zope.component.hooks import setHooks

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from zope.testing import cleanup as z_cleanup

from nti.app.users.utils import set_user_creation_site

from nti.app.testing.application_webtest import AppCreatingLayerHelper
from nti.app.testing.application_webtest import Library

from nti.app.testing.layers import PyramidLayerMixin

from nti.coremetadata.interfaces import IUser

from nti.dataserver.authorization import ROLE_SITE_ADMIN

from nti.dataserver.tests import DSInjectorMixin

from nti.testing.layers import ConfiguringLayerMixin
from nti.testing.layers import find_test

from nti.testing.layers import GCLayerMixin

from nti.testing.layers import ZopeComponentLayer


class SharedConfiguringTestLayer(ZopeComponentLayer,
                                 GCLayerMixin,
                                 ConfiguringLayerMixin):

    set_up_packages = ('nti.dataserver', 'nti.app.segments')

    @classmethod
    def setUp(cls):
        setHooks()
        cls.setUpPackages()

    @classmethod
    def tearDown(cls):
        cls.tearDownPackages()
        z_cleanup.cleanUp()

    @classmethod
    def testSetUp(cls, unused_test=None):
        setHooks()

    @classmethod
    def testTearDown(cls):
        pass


class SegmentApplicationTestLayer(ZopeComponentLayer,
                                  PyramidLayerMixin,
                                  GCLayerMixin,
                                  ConfiguringLayerMixin,
                                  DSInjectorMixin):

    features = ('devmode', 'testmode', 'segments',)

    set_up_packages = ()  # None, because configuring the app will do this
    APP_IN_DEVMODE = True
    # We have no packages, but we will set up the listeners ourself when
    # configuring the app
    configure_events = False

    @classmethod
    def _setup_library(cls, *unused_args, **unused_kwargs):
        return Library()

    @classmethod
    def _extra_app_settings(cls):
        return {}

    @classmethod
    def setUp(cls):
        z_cleanup.cleanUp()  # Make sure we're starting fresh.
        AppCreatingLayerHelper.appSetUp(cls)

    @classmethod
    def tearDown(cls):
        AppCreatingLayerHelper.appTearDown(cls)
        setHooks()

    @classmethod
    def setUpPackages(cls):
        super(SegmentApplicationTestLayer, cls).setUpPackages()

    @classmethod
    def testSetUp(cls, test=None):
        # At the beginning of every test, we should have a library in place;
        # if we don't something has gone very wrong.
        try:
            from nti.contentlibrary.interfaces import IContentPackageLibrary
            lib = component.getGlobalSiteManager().queryUtility(IContentPackageLibrary)
            if lib is None:
                raise AssertionError("Library gone", find_test())
        except ImportError:
            pass
        AppCreatingLayerHelper.appTestSetUp(cls, test)

    @classmethod
    def testTearDown(cls, test=None):
        AppCreatingLayerHelper.appTestTearDown(cls, test)
        # At the end of every test, we should have a library in place;
        # if we don't something's gone very wrong. Optionally, would could verify
        # that it's the same instance we had when we started the test.
        # This protects us from bugs in a unit test's tearDown method that gets too
        # aggressive.
        try:
            from nti.contentlibrary.interfaces import IContentPackageLibrary
            lib = component.getGlobalSiteManager().queryUtility(IContentPackageLibrary)
            if lib is None:
                raise AssertionError("Library gone", find_test())
        except ImportError:
            pass


class SiteAdminTestMixin(object):

    def make_site_admins(self, *users):
        prm = IPrincipalRoleManager(getSite())
        for user in users:
            if IUser.providedBy(user):
                username = user.username
            else:
                username = user
                user = self._get_user(username=user)

            set_user_creation_site(user, getSite())
            prm.assignRoleToPrincipal(ROLE_SITE_ADMIN.id, username)
            lifecycleevent.modified(user)
