#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from operator import attrgetter

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from zc.displayname.interfaces import IDisplayNameGenerator

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.base.abstract_views import download_cookie_decorator

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.renderers.interfaces import IUncacheableInResponse

from nti.app.segments import VIEW_MEMBERS

from nti.app.segments.interfaces import ISegmentsCollection

from nti.app.users.views.view_mixins import AbstractEntityViewMixin
from nti.app.users.views.view_mixins import UsersCSVExportMixin

from nti.appserver.ugd_edit_views import UGDPutView

from nti.coremetadata.interfaces import IX_ALIAS
from nti.coremetadata.interfaces import IX_DISPLAYNAME
from nti.coremetadata.interfaces import IX_LASTSEEN_TIME
from nti.coremetadata.interfaces import IX_REALNAME

from nti.dataserver.authorization import ACT_CREATE
from nti.dataserver.authorization import ACT_DELETE
from nti.dataserver.authorization import ACT_LIST
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ACT_SEARCH

from nti.dataserver.metadata import get_metadata_catalog

from nti.dataserver.metadata.index import IX_CREATEDTIME

from nti.dataserver.users import get_entity_catalog
from nti.dataserver.users import User

from nti.dataserver.users.utils import intids_of_users_by_site

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.namedfile.file import safe_filename

from nti.segments.interfaces import ISegment
from nti.segments.interfaces import ISegmentsContainer
from nti.segments.interfaces import IUserSegment

from nti.segments.model import IntIdSet

from nti.site.interfaces import IHostPolicyFolder

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

    @property
    def _container(self):
        return self.context

    def _do_call(self):
        creator = self.remoteUser
        segment = self.readCreateUpdateContentObject(creator)
        segment.creator = creator.username
        segment = self._container.add(segment)

        self.request.response.status_int = 201

        return segment


@view_config(route_name='objects.generic.traversal',
             request_method='POST',
             renderer='rest',
             permission=ACT_CREATE,
             context=ISegmentsCollection)
class CreateSegmentInCollectionView(CreateSegmentView):

    @property
    def _container(self):
        return self.context.container


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
             context=ISegment,
             name=VIEW_MEMBERS,
             accept='application/json',
             permission=ACT_SEARCH)
class SegmentMembersView(AbstractEntityViewMixin):

    # TODO: Consider extracting sorting/externalization logic to a mixin,
    #  e.g. `nti.app.users.view_mixins.ListUsersMixin`
    _ALLOWED_SORTING = AbstractEntityViewMixin._ALLOWED_SORTING + (IX_LASTSEEN_TIME,)

    _NUMERIC_SORTING = AbstractEntityViewMixin._NUMERIC_SORTING + (IX_LASTSEEN_TIME,)

    def check_access(self):
        # We're using a permission check on the context of the view
        pass

    def get_externalizer(self, user):
        # pylint: disable=no-member
        result = 'summary'
        if user == self.remoteUser:
            result = 'personal-summary'
        elif self.is_admin:
            result = 'admin-summary'
        elif    self.is_site_admin \
                and self.site_admin_utility.can_administer_user(self.remoteUser, user):
            result = 'admin-summary'
        return result

    @Lazy
    def sortMap(self):
        return {
            IX_ALIAS: get_entity_catalog(),
            IX_REALNAME: get_entity_catalog(),
            IX_DISPLAYNAME: get_entity_catalog(),
            IX_CREATEDTIME: get_metadata_catalog(),
            IX_LASTSEEN_TIME: get_metadata_catalog(),
        }

    def search_include(self, doc_id):
        # Users only
        return self.mime_type(doc_id) == 'application/vnd.nextthought.user'

    @Lazy
    def site_name(self):
        # obtained from the nearest IHostPolicyFolder
        return find_interface(self.context, IHostPolicyFolder).__name__

    def get_entity_intids(self, site=None):
        # The parent class will handle any deactivated entity filtering.
        initial_intids = intids_of_users_by_site(site, filter_deactivated=False)

        if self.context.filter_set is not None:
            rs = IntIdSet(initial_intids)
            initial_intids = self.context.filter_set.apply(rs).intids()

        return initial_intids

    def __call__(self):
        result = self._do_call()
        interface.alsoProvides(result, IUncacheableInResponse)
        return result


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             context=IUserSegment,
             accept='text/csv',
             name=VIEW_MEMBERS,
             decorator=download_cookie_decorator,
             permission=ACT_SEARCH)
class SegmentMembersCSVView(SegmentMembersView,
                            UsersCSVExportMixin):

    def _get_filename(self):
        return safe_filename(u'users_export-%s.csv' % (self.context.title,))

    def __call__(self):
        self.check_access()
        return self._create_csv_response()


class SegmentSummary(object):

    def __init__(self, segment, request):
        self.segment = segment
        self.request = request

    @property
    def creator_display_name(self):
        segment = self.segment
        user = User.get_user(segment.creator)
        display_name_generator = component.queryMultiAdapter((user, self.request),
                                                             IDisplayNameGenerator)
        if display_name_generator is None:
            return segment.creator

        return display_name_generator()

    def __getattr__(self, item):
        return getattr(self.segment, item)


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
        'creator': attrgetter('creator_display_name'),
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

    @property
    def _container(self):
        return self.context

    def _get_items(self, result_dict):
        """
        Sort and batch records.
        """
        search = self.request.params.get('filter')
        filter_param = search and search.lower()

        items = [SegmentSummary(segment, self.request)
                 for segment in self._container.values()]
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


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             renderer='rest',
             permission=ACT_LIST,
             context=ISegmentsCollection)
class SiteSegmentsInCollectionView(SiteSegmentsView):

    @property
    def _container(self):
        return self.context.container
