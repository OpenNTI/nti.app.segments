#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import time

from hamcrest import assert_that
from hamcrest import contains
from hamcrest import described_as
from hamcrest import has_entries
from hamcrest import has_length
from hamcrest import is_
from hamcrest import is_not
from hamcrest import none
from hamcrest import not_none

from nti.app.segments.tests import SiteAdminTestMixin

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.base import TestBaseMixin

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.tests import mock_dataserver as mock_ds

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.segments.model import UserSegment


class WorkspaceTestMixin(TestBaseMixin):

    WORKSPACE_NAME = None

    def get_workspace(self, ws_name, kwargs):
        path = b'/dataserver2/service'
        res = self.testapp.get(path, **kwargs)
        workspace = [ws for ws in res.json_body['Items']
                     if ws['Title'] == ws_name]

        return workspace[0] if workspace else None

    def get_workspace_collection(self, ws_name, collection_name, **kwargs):
        workspace = self.get_workspace(ws_name, kwargs)
        assert_that(workspace, not_none())

        collection = [c for c in workspace.get('Items', ())
                      if c.get('Class') == 'Collection' and c.get('Title') == collection_name]

        collection = collection[0] if collection else None
        assert_that(collection, described_as("A collection named",
                                             is_not(none()),
                                             collection_name))

        return collection.get('href')

    def forbid_workspace(self, ws_name, **kwargs):
        workspace = self.get_workspace(ws_name, kwargs)
        assert_that(workspace, is_(none()), ws_name)


class TestCreateSegments(ApplicationLayerTest,
                         WorkspaceTestMixin,
                         SiteAdminTestMixin):

    WORKSPACE_NAME = 'Segments'

    default_origin = 'http://alpha.nextthought.com'

    def _create_segment(self,
                        title,
                        created_time=None,
                        last_modified=None,
                        **kwargs):
        workspace_kwargs = dict()
        if 'extra_environ' in kwargs:
            workspace_kwargs['extra_environ'] = kwargs['extra_environ']
        create_path = self.get_workspace_collection('SiteAdmin',
                                                    'Segments',
                                                    **workspace_kwargs)

        res = self.testapp.post_json(create_path,
                                     {
                                         "MimeType": UserSegment.mime_type,
                                         "title": title
                                     },
                                     **kwargs)

        if created_time is not None or last_modified is not None:
            with mock_ds.mock_db_trans():
                segment = find_object_with_ntiid(res.json_body['NTIID'])

                if created_time is not None:
                    segment.createdTime = created_time

                if last_modified is not None:
                    segment.lastModified = last_modified

        return res

    @WithSharedApplicationMockDS(users=('site.admin.one',
                                        'site.admin.two',
                                        'joe.user'),
                                 testapp=True,
                                 default_authenticate=True)
    def test_crud(self):
        joe_env = self._make_extra_environ(username='joe.user')
        site_admin_one_env = self._make_extra_environ(username='site.admin.one')
        site_admin_two_env = self._make_extra_environ(username='site.admin.two')
        with mock_ds.mock_db_trans(site_name='alpha.nextthought.com'):
            self.make_site_admins('site.admin.one', 'site.admin.two')

        # Only (site) admins can create/list
        self.forbid_workspace('SiteAdmin', extra_environ=joe_env)

        # Create
        create_path = u'/dataserver2/++etc++hostsites/alpha.nextthought.com/++etc++site/default/segments-container'
        self.testapp.post_json(create_path,
                               dict(title=u'my segment'),
                               extra_environ=joe_env,
                               status=403)

        res = self._create_segment('my segment',
                                   extra_environ=site_admin_one_env,
                                   status=201).json_body

        assert_that(res, has_entries({
            "title": u"my segment",
            "filter_set": none(),
            "Creator": u"site.admin.one",
            "CreatedTime": not_none(),
            "Last Modified": not_none(),
            "href": not_none(),
        }))

        # Retrieve (can be retrieved by any site admin)
        segment_url = res['href']
        res = self.testapp.get(segment_url,
                               extra_environ=site_admin_two_env).json_body
        assert_that(res, has_entries({
            "title": u"my segment",
            "filter_set": none(),
            "Creator": u"site.admin.one",
            "CreatedTime": not_none(),
            "Last Modified": not_none(),
            "href": not_none(),
        }))

        # Update
        edit_url = self.require_link_href_with_rel(res, 'edit')
        res = self.testapp.put_json(edit_url,
                                    dict(title='updated segment')).json_body
        assert_that(res, has_entries({
            "title": u"updated segment",
            "filter_set": none(),
            "Creator": u"site.admin.one",
            "CreatedTime": not_none(),
            "Last Modified": not_none(),
            "href": not_none(),
        }))

        #       Other site admins can also update
        res = self.testapp.put_json(edit_url, dict(title='my segment'),
                                    extra_environ=site_admin_two_env).json_body
        assert_that(res, has_entries({
            "title": u"my segment",
            "filter_set": none(),
            "Creator": u"site.admin.one",
            "CreatedTime": not_none(),
            "Last Modified": not_none(),
            "href": not_none(),
        }))

        # Delete
        delete_url = self.require_link_href_with_rel(res, 'delete')
        self.testapp.delete(delete_url, extra_environ=site_admin_two_env,
                            status=204)

        self.testapp.get(delete_url, extra_environ=site_admin_one_env,
                         status=404)

    def _list_segments(self, via_workspace=True, **kwargs):
        if via_workspace:
            workspace_kwargs = dict()
            if 'extra_environ' in kwargs:
                workspace_kwargs['extra_environ'] = kwargs['extra_environ']
            list_path = self.get_workspace_collection('SiteAdmin',
                                                      'Segments',
                                                      **workspace_kwargs)
        else:
            list_path = os.path.join('/dataserver2',
                                     '++etc++hostsites',
                                     'alpha.nextthought.com',
                                     '++etc++site',
                                     'default',
                                     'segments-container')

        res = self.testapp.get(list_path, **kwargs)

        return res

    @WithSharedApplicationMockDS(users=('site.admin.one',
                                        'site.admin.two',
                                        'nti.admin',
                                        'non.admin'),
                                 testapp=True,
                                 default_authenticate=True)
    def test_list(self):
        site_admin_one_env = self._make_extra_environ(username='site.admin.one')
        site_admin_two_env = self._make_extra_environ(username='site.admin.two')
        nti_admin_env = self._make_extra_environ(username='nti.admin')
        non_admin_env = self._make_extra_environ(username='non.admin')
        with mock_ds.mock_db_trans(site_name='alpha.nextthought.com'):
            self.make_site_admins('site.admin.one', 'site.admin.two')

            self._assign_role(ROLE_ADMIN, username=u'nti.admin')

            IFriendlyNamed(self._get_user('site.admin.one')).realname = u'One'
            IFriendlyNamed(self._get_user('site.admin.two')).realname = u'Two'
            IFriendlyNamed(self._get_user('nti.admin')).realname = u'Three'

        # Non-admins have no access
        self.forbid_workspace('SiteAdmin', extra_environ=non_admin_env)
        self._list_segments(via_workspace=False,
                            extra_environ=non_admin_env,
                            status=403)

        created_time = 0
        last_modified = time.time() + 10
        res = self._create_segment("sa one segment",
                                   extra_environ=site_admin_one_env,
                                   created_time=created_time,
                                   last_modified=last_modified)
        title_one = res.json_body['title']

        # Site admins should see all segments for the site
        res = self._list_segments(extra_environ=site_admin_one_env).json_body
        assert_that(res, has_entries({
            "Items": has_length(1)
        }))

        assert_that(res["Items"][0], has_entries({
            "MimeType": UserSegment.mime_type,
            "title": "sa one segment",
            "Creator": "site.admin.one",
            "filter_set": none(),
        }))

        created_time += 1
        last_modified -= 2
        res = self._create_segment("sa two segment",
                                   extra_environ=site_admin_two_env,
                                   created_time=created_time,
                                   last_modified=last_modified)
        title_two = res.json_body['title']

        res = self._list_segments(extra_environ=site_admin_two_env).json_body
        assert_that(res, has_entries({
            "Items": has_length(2)
        }))

        # NTI Admins should see all segments for the site
        res = self._list_segments().json_body
        assert_that(res, has_entries({
            "Items": has_length(2)
        }))

        # Check site.admin.one access
        res = self._list_segments(extra_environ=site_admin_one_env).json_body
        assert_that(res, has_entries({
            "Items": has_length(2)
        }))

        # Create a third subscription to test paging
        created_time += 1
        last_modified += 1
        res = self._create_segment("admin segment one",
                                   extra_environ=nti_admin_env,
                                   created_time=created_time,
                                   last_modified=last_modified)
        title_three = res.json_body['title']

        # Paging
        #   First page
        res = self._list_segments(params={'batchSize': '2'}).json_body
        assert_that(res['Total'], is_(3))
        self.require_link_href_with_rel(res, 'batch-next')
        self.forbid_link_with_rel(res, 'batch-prev')

        #   Middle page
        res = self._list_segments(params={'batchStart': '1', 'batchSize': '1'}).json_body
        assert_that(res['Total'], is_(3))
        self.require_link_href_with_rel(res, 'batch-next')
        self.require_link_href_with_rel(res, 'batch-prev')

        #   Last page
        res = self._list_segments(params={'batchStart': '1', 'batchSize': '2'}).json_body
        assert_that(res['Total'], is_(3))
        self.forbid_link_with_rel(res, 'batch-next')
        self.require_link_href_with_rel(res, 'batch-prev')

        # Test sorting
        def assert_order(params, expected, key='title'):
            res_ = self._list_segments(params=params).json_body
            assert_that(res_['ItemCount'], is_(len(expected)))
            values = [item[key]
                      for item in res_['Items']]
            assert_that(values, contains(*expected))

        assert_order({},
                     (title_three, title_one, title_two))
        assert_order({'sortOn': 'name'},
                     (title_three, title_one, title_two))
        assert_order({'sortOn': 'name', 'sortOrder': 'invalid'},
                     (title_three, title_one, title_two))
        assert_order({'sortOn': 'name', 'sortOrder': 'ascending'},
                     (title_three, title_one, title_two))
        assert_order({'sortOn': 'name', 'sortOrder': 'descending'},
                     (title_two, title_one, title_three))
        assert_order({'sortOn': 'creator'},
                     (title_one, title_three, title_two))
        assert_order({'sortOn': 'createdtime'},
                     (title_one, title_two, title_three))
        assert_order({'sortOn': 'lastmodified'},
                     (title_two, title_three, title_one))
