#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import lifecycleevent

from zope.component.hooks import getSite
from zope.component.hooks import setHooks

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from zope.testing import cleanup as z_cleanup

from nti.app.users.utils import set_user_creation_site

from nti.coremetadata.interfaces import IUser

from nti.dataserver.authorization import ROLE_SITE_ADMIN

from nti.testing.layers import ConfiguringLayerMixin

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
