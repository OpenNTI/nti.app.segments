#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from operator import attrgetter

from pyramid import httpexceptions as hexc
from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.ugd_edit_views import UGDPutView

from nti.dataserver.authorization import ACT_CREATE
from nti.dataserver.authorization import ACT_DELETE
from nti.dataserver.authorization import ACT_LIST
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.segments.interfaces import ISegment
from nti.segments.interfaces import ISegmentsContainer

from nti.traversal.traversal import find_interface

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE
TOTAL = StandardExternalFields.TOTAL


@view_config(route_name='objects.generic.traversal',
             request_method='POST',
             renderer='rest',
             permission=ACT_CREATE,
             context=ISegmentsContainer)
class CreateSegmentView(ModeledContentUploadRequestUtilsMixin,
                        AbstractAuthenticatedView):

    def _do_call(self):
        creator = self.remoteUser
        segment = self.readCreateUpdateContentObject(creator)
        segment = self.context.add(segment)

        self.request.response.status_int = 201

        return segment


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ISegment,
             request_method='GET',
             permission=ACT_READ)
class GetSegmentView(AbstractAuthenticatedView):

    def __call__(self):
        return self.context


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ISegment,
             request_method='PUT',
             permission=ACT_UPDATE)
class UpdateSegmentView(UGDPutView):
    pass


@view_config(route_name='objects.generic.traversal',
             request_method='DELETE',
             renderer='rest',
             permission=ACT_DELETE,
             context=ISegment)
class DeleteSegmentView(AbstractAuthenticatedView):

    def __call__(self):
        segments_container = find_interface(self.context, ISegmentsContainer)
        segments_container.remove(self.context)
        self.request.response.status_int = 204
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             renderer='rest',
             permission=ACT_LIST,
             context=ISegmentsContainer)
class SiteSegmentsView(BatchingUtilsMixin,
                       AbstractAuthenticatedView):
    """
    Return the list of segments for the site.

    batchSize
            The size of the batch.  Defaults to 50.

    batchStart
            The starting batch index.  Defaults to 0.

    sortOn
            The case insensitive field to sort on. Options are ``title``,
            ``creator``, ``createdtime``, and ``lastmodified``.
            The default is ``name``.

    sortOrder
            The sort direction. Options are ``ascending`` and
            ``descending``. Sort order is ascending by default.

    filter
            String to use for searching by segment title.
    """

    _DEFAULT_BATCH_SIZE = 30
    _DEFAULT_BATCH_START = 0

    _default_sort = 'title'
    _sort_keys = {
        'title': attrgetter('title'),
        'creator': attrgetter('creator'),
        'createdtime': attrgetter('createdTime'),
        'lastmodified': attrgetter('lastModified'),
    }

    def _get_sorted_result_set(self, items, sort_key, sort_desc=False):
        """
        Get the sorted result set.
        """
        items = sorted(items, key=sort_key, reverse=sort_desc)
        return items

    def _get_sort_params(self):
        sort_on = self.request.params.get('sortOn') or ''
        sort_on = sort_on.lower()
        sort_on = sort_on if sort_on in self._sort_keys else self._default_sort
        sort_key = self._sort_keys.get(sort_on)

        # Ascending is default
        sort_order = self.request.params.get('sortOrder')
        sort_descending = bool(
            sort_order and sort_order.lower() == 'descending')

        return sort_key, sort_descending

    def _search_items(self, filter_param, items):
        """
        The search_param param currently searches only for titles
        containing the given string.
        """

        def matches(item):
            return filter_param in item.name

        results = [x for x in items if matches(x)]

        return results

    def _get_items(self, result_dict):
        """
        Sort and batch records.
        """
        search = self.request.params.get('filter')
        filter_param = search and search.lower()

        items = self.context.values()
        if filter_param:
            items = self._search_items(filter_param, items)

        sort_key, sort_descending = self._get_sort_params()

        result_set = self._get_sorted_result_set(items,
                                                 sort_key,
                                                 sort_descending)

        total_items = result_dict[TOTAL] = len(result_set)
        self._batch_items_iterable(result_dict,
                                   result_set,
                                   number_items_needed=total_items)

        return [record for record in result_dict.get(ITEMS)]

    def __call__(self):
        result_dict = LocatedExternalDict()

        result_dict[MIMETYPE] = 'application/vnd.nextthought.segments.sitesegments'
        result_dict[CLASS] = 'SiteSegments'
        result_dict[ITEMS] = self._get_items(result_dict)

        return result_dict
