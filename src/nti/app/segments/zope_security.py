#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from zope.securitypolicy.interfaces import IPrincipalPermissionManager

from zope.securitypolicy.rolepermission import AnnotationRolePermissionManager

from nti.dataserver.authorization import ACT_CREATE
from nti.dataserver.authorization import ACT_DELETE
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ROLE_ADMIN

from nti.segments.interfaces import ISegmentsContainer


@component.adapter(ISegmentsContainer)
@interface.implementer(IPrincipalPermissionManager)
class SegmentsContainerRolePermissionManager(AnnotationRolePermissionManager):

    ADMIN_PERMS = (ACT_CREATE, ACT_READ, ACT_UPDATE, ACT_DELETE)

    def __init__(self, context):
        super(SegmentsContainerRolePermissionManager, self).__init__(context)
        # We must call this here so that permissions are updated if the state changes
        self.initialize()

    def initialize(self):
        # Initialize with perms for the enrollment record owner
        for permission in self.ADMIN_PERMS:
            self.grantPermissionToRole(permission.id, ROLE_ADMIN.id)
