#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import zope.i18nmessageid

MessageFactory = zope.i18nmessageid.MessageFactory('nti.dataserver')

#: Segments workspace
SEGMENTS = u'Segments'

#: View name for returning segment membership
VIEW_MEMBERS = u'members'

#: View name for previewing membership after segment changes
VIEW_MEMBERS_PREVIEW = u'members_preview'
