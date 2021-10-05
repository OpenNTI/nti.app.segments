#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.dataserver.authorization import ACT_DELETE

from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.interfaces import StandardExternalFields

from nti.links import Link

from nti.segments.interfaces import ISegment

from pyramid.interfaces import IRequest

LINKS = StandardExternalFields.LINKS


@component.adapter(ISegment, IRequest)
@interface.implementer(IExternalMappingDecorator)
class DeleteLinkSegmentDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, result):
        super_instance = super(DeleteLinkSegmentDecorator, self)
        return (super_instance._predicate(context, result)
                and has_permission(ACT_DELETE, context, self.request))

    def _do_decorate_external(self, context, result):
        links = result.setdefault(LINKS, [])
        links.append(Link(context,
                          rel='delete',
                          method='DELETE'))
