#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.app.segments import VIEW_MEMBERS

from nti.appserver.pyramid_authorization import has_permission

from nti.dataserver.authorization import ACT_DELETE
from nti.dataserver.authorization import ACT_SEARCH

from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.interfaces import StandardExternalFields

from nti.links import Link

from nti.segments.interfaces import ISegment

from pyramid.interfaces import IRequest

LINKS = StandardExternalFields.LINKS


@component.adapter(ISegment, IRequest)
@interface.implementer(IExternalMappingDecorator)
class SegmentLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _do_decorate_external(self, context, result):
        links = []
        if has_permission(ACT_DELETE, context, self.request):
            links.append(Link(context,
                              rel='delete',
                              method='DELETE'))

        if has_permission(ACT_SEARCH, context, self.request):
            links.append(Link(context,
                              rel='members',
                              elements=(VIEW_MEMBERS,),
                              method='GET'))

        if links:
            result.setdefault(LINKS, []).extend(links)
