#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component

from zope.site.interfaces import INewLocalSite

from nti.segments.model import install_segments_container

from nti.site.interfaces import IHostPolicyFolder
from nti.site.interfaces import IHostPolicySiteManager

from nti.traversal.traversal import find_interface


@component.adapter(IHostPolicySiteManager, INewLocalSite)
def install_site_segments_container(site_manager, _unused_event=None):
    container_site = find_interface(site_manager, IHostPolicyFolder)
    install_segments_container(container_site)
