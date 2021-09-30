#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component

from zope.component.hooks import getSite

from zope.security import checkPermission

from zope.securitypolicy.interfaces import IRolePermissionManager

from zope.securitypolicy.settings import Allow

from hamcrest import assert_that
from hamcrest import greater_than
from hamcrest import has_item
from hamcrest import has_length
from hamcrest import is_

from nti.app.segments.tests import SiteAdminTestMixin

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.authorization import ACT_CREATE
from nti.dataserver.authorization import ACT_DELETE
from nti.dataserver.authorization import ACT_LIST
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.authorization_utils import zope_interaction

from nti.dataserver.tests import mock_dataserver as mock_ds

from nti.dataserver.users.common import set_user_creation_site

from nti.segments.interfaces import ISegmentsContainer


class TestSegmentsContainerPermissions(ApplicationLayerTest,
                                       SiteAdminTestMixin):

    @WithSharedApplicationMockDS(users=("site.admin",
                                        "nti.admin",
                                        "regular.joe"))
    def test_permissions(self):
        with mock_ds.mock_db_trans(self.ds,
                                   site_name="alpha.nextthought.com"):
            # Site admins should be able to manage all segments
            site_admin = self._get_user(u"site.admin")
            self.make_site_admins('site.admin')

            # Nti admins should also be able to manage all segments
            nti_admin = self._get_user('nti.admin')
            self._assign_role(ROLE_ADMIN, username='nti.admin')

            # Non admin user
            joe = self._get_user('regular.joe')
            set_user_creation_site(joe, getSite())

            container = component.getUtility(ISegmentsContainer)

            with zope_interaction(joe.username):
                self.forbid_permissions(container)

            with zope_interaction(site_admin.username):
                self.require_permissions(container)

            with zope_interaction(nti_admin.username):
                self.require_permissions(container)

            rpm = IRolePermissionManager(container)
            for perm in (ACT_CREATE, ACT_READ, ACT_UPDATE, ACT_DELETE, ACT_LIST):
                roles = rpm.getRolesForPermission(perm.id)
                assert_that(roles, has_length(greater_than(0)))
                assert_that(roles, has_item((ROLE_ADMIN.id, Allow)))

    @staticmethod
    def require_permissions(container):
        assert_that(checkPermission(ACT_CREATE.id, container), is_(True))
        assert_that(checkPermission(ACT_READ.id, container), is_(True))
        assert_that(checkPermission(ACT_UPDATE.id, container), is_(True))
        assert_that(checkPermission(ACT_DELETE.id, container), is_(True))
        assert_that(checkPermission(ACT_LIST.id, container), is_(True))

    @staticmethod
    def forbid_permissions(container):
        assert_that(checkPermission(ACT_CREATE.id, container), is_(False))
        assert_that(checkPermission(ACT_READ.id, container), is_(False))
        assert_that(checkPermission(ACT_UPDATE.id, container), is_(False))
        assert_that(checkPermission(ACT_DELETE.id, container), is_(False))
        assert_that(checkPermission(ACT_LIST.id, container), is_(False))
