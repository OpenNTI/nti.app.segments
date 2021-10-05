#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from nti.app.site.workspaces.interfaces import ISiteAdminCollection


class ISegmentsCollection(ISiteAdminCollection):
    """
    Collection of segments supplied as a collection in the site admin workspace.
    """