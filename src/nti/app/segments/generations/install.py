#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.generations.generations import SchemaManager as BaseSchemaManager

from zope.generations.interfaces import IInstallableSchemaManager

from nti.coremetadata.interfaces import IDataserver

from nti.dataserver.interfaces import IOIDResolver

from nti.segments.model import install_segments_container

from nti.site import get_all_host_sites

generation = 1

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IInstallableSchemaManager)
class _SchemaManager(BaseSchemaManager):
    """
    A schema manager that we can register as a utility in ZCML.
    """

    def __init__(self):
        super(_SchemaManager, self).__init__(
                generation=generation,
                minimum_generation=generation,
                package_name='nti.app.segments.generations')

    def install(self, context):
        evolve(context)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warning("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator)
        return None


def do_evolve(context, generation=generation):  # pylint: disable=redefined-outer-name
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
            "Hooks not installed?"

        for site in get_all_host_sites():
            install_segments_container(site)
            logger.info('Installed segments container for site %s',
                        site.__name__)


def evolve(context):
    """
    Ensure a segment container is installed in all host sites.
    """
    do_evolve(context, generation)
