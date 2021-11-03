#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from nti.app.segments.model import IsDeactivatedFilterSet

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.segments.interfaces import IIsDeactivatedFilterSet
from nti.segments.interfaces import ISegmentsContainer

from nti.site.hostpolicy import get_all_host_sites

generation = 2

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def migrated_filterset(filter_set):
    result_fs = filter_set
    if IIsDeactivatedFilterSet.providedBy(filter_set):
        result_fs = IsDeactivatedFilterSet(Deactivated=filter_set.Deactivated)
        return True, result_fs

    modified = False
    filter_sets = getattr(filter_set, 'filter_sets', None)
    if filter_sets:
        for i, fs in enumerate(filter_sets):
            child_modified, child_fs = migrated_filterset(fs)
            if child_modified:
                filter_sets[i] = child_fs
                modified = True

    return modified, result_fs


def process_site(updated):
    site_modified = False
    segments_container = component.getUtility(ISegmentsContainer)
    for segment in segments_container.values():
        modified, result_fs = migrated_filterset(segment.filter_set)
        if modified:
            segment.filter_set = result_fs
            site_modified = True
            segment._p_changed = True
            updated.add(segment)

    return site_modified


def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
            "Hooks not installed?"

        sites = get_all_host_sites()
        updated = set()
        sites_updated = 0
        for site in sites:
            with current_site(site):
                if process_site(updated):
                    sites_updated += 1

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.  Updated %s segments in %d/%d sites',
                generation, len(updated), sites_updated, len(sites))


def evolve(context):
    """
    Evolve to generation 2 by migrating all deactivated user filtersets to the
    new class in nti.app.segments (from nti.segments)
    """
    do_evolve(context, generation)
