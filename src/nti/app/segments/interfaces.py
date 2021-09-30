#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from nti.appserver.workspaces.interfaces import IWorkspace


class ISegmentsWorkspace(IWorkspace):
    """
    A workspace containing data for segments.
    """
