#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import copy
import json
import os
import time
from itertools import chain

from hamcrest import assert_that
from hamcrest import contains
from hamcrest import described_as
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_item
from hamcrest import has_length
from hamcrest import is_
from hamcrest import is_not
from hamcrest import none
from hamcrest import not_none

from webob.cookies import parse_cookie

from zope import lifecycleevent

from nti.app.segments.tests import SiteAdminTestMixin

from nti.app.site.hostpolicy import create_site

from nti.app.testing.application_webtest import ApplicationLayerTest
from nti.app.testing.application_webtest import AppTestBaseMixin

from nti.app.testing.base import TestBaseMixin

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.users.utils import set_user_creation_site

from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.tests import mock_dataserver as mock_ds

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.externalization.datetime import date_from_string

from nti.identifiers.interfaces import IUserExternalIdentityContainer

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.segments.model import IntersectionUserFilterSet
from nti.segments.model import IsDeactivatedFilterSet
from nti.segments.model import UnionUserFilterSet
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


class SegmentManagementMixin(AppTestBaseMixin,
                             WorkspaceTestMixin):

    def _create_segment(self,
                        title,
                        filter_set=None,
                        simple_filter_set=None,
                        created_time=None,
                        last_modified=None,
                        **kwargs):
        workspace_kwargs = dict()
        if 'extra_environ' in kwargs:
            workspace_kwargs['extra_environ'] = kwargs['extra_environ']
        create_path = self.get_workspace_collection('SiteAdmin',
                                                    'Segments',
                                                    **workspace_kwargs)

        if simple_filter_set is not None and not filter_set:
            filter_set = {
                "MimeType": IntersectionUserFilterSet.mime_type,
                "filter_sets": [{
                    "MimeType": UnionUserFilterSet.mime_type,
                    "filter_sets": [simple_filter_set]
                }]
            }

        data = {
            "MimeType": UserSegment.mime_type,
            "title": title,
            "filter_set": filter_set,
        }

        res = self.testapp.post_json(create_path, data, **kwargs)

        if created_time is not None or last_modified is not None:
            with mock_ds.mock_db_trans():
                segment = find_object_with_ntiid(res.json_body['NTIID'])

                if created_time is not None:
                    segment.createdTime = created_time

                if last_modified is not None:
                    segment.lastModified = last_modified

        return res

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


class SegmentManagementTest(SegmentManagementMixin,
                            ApplicationLayerTest,
                            WorkspaceTestMixin):

    WORKSPACE_NAME = 'Segments'

    default_origin = 'http://alpha.nextthought.com'


class TestCreateSegments(SegmentManagementTest,
                         SiteAdminTestMixin):

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


class SegmentMembersViewMixin(SegmentManagementMixin,
                              SiteAdminTestMixin):

    def _segment_members(self, href, **kwargs):
        return self.testapp.get(href, **kwargs)

    @WithSharedApplicationMockDS(users=('site.admin.one',
                                        'site.admin.two',
                                        'non.admin',
                                        'diff.site.admin'),
                                 testapp=True,
                                 default_authenticate=True)
    def test_access(self):
        site_admin_one_env = self._make_extra_environ(username='site.admin.one')
        site_admin_two_env = self._make_extra_environ(username='site.admin.two')
        non_admin_env = self._make_extra_environ(username='non.admin')

        # User with a different site
        diff_site_admin_env = self._make_extra_environ(
            username='diff.site.admin',
            HTTP_ORIGIN='http://alderaan')

        with mock_ds.mock_db_trans():
            create_site('alderaan')

        with mock_ds.mock_db_trans(site_name='alderaan'):
            self.make_site_admins('diff.site.admin',)

        with mock_ds.mock_db_trans(site_name='alpha.nextthought.com'):
            self.make_site_admins('site.admin.one', 'site.admin.two')

            non_admin = self._get_user('non.admin')
            set_user_creation_site(non_admin)
            lifecycleevent.modified(non_admin)

        # Only admins and site admins should have access
        segment = self._create_segment('Null Filter',
                                       extra_environ=site_admin_one_env).json_body

        members_url = self._members_url(segment)
        self._segment_members(members_url)
        self._segment_members(members_url, extra_environ=site_admin_one_env)
        self._segment_members(members_url, extra_environ=site_admin_two_env)

        self._segment_members(members_url, extra_environ=non_admin_env, status=403)
        self._segment_members(members_url, extra_environ=diff_site_admin_env, status=403)

    @WithSharedApplicationMockDS(users=('site.admin.one',
                                        'site.admin.two',
                                        'non.admin',
                                        'diff.site'),
                                 testapp=True,
                                 default_authenticate=True)
    def test_no_filter(self):
        with mock_ds.mock_db_trans():
            create_site('alderaan')
            diff_site_user = self._get_user('diff.site')
            set_user_creation_site(diff_site_user, 'alderaan')
            lifecycleevent.modified(diff_site_user)

        with mock_ds.mock_db_trans(site_name='alpha.nextthought.com'):
            self.make_site_admins('site.admin.one', 'site.admin.two')

            non_admin = self._get_user('non.admin')
            set_user_creation_site(non_admin)
            lifecycleevent.modified(non_admin)

        res = self._create_segment('Null Filter',
                                   status=201).json_body

        members_url = '%s?sortOn=displayname' % (self._members_url(res),)
        res = self._segment_members(members_url).json_body
        assert_that(res['Items'], has_length(3))
        usernames = [user['Username'] for user in res['Items']]
        assert_that(usernames, contains(
            'non.admin',
            'site.admin.one',
            'site.admin.two',
        ))

    @WithSharedApplicationMockDS(users=True,
                                 testapp=True,
                                 default_authenticate=True)
    def test_is_deactivated(self):
        test_username = 'deactivated.user.three'
        with mock_ds.mock_db_trans(site_name='alpha.nextthought.com'):
            self._create_user('user.one',
                              external_value={'realname': u'user one'})
            self._create_user('user.two',
                              external_value={'realname': u'user two'})
            self._create_user(test_username,
                              external_value={'realname': u'user three'})

        deactivated_filter_set = {
            "MimeType": IsDeactivatedFilterSet.mime_type,
            "Deactivated": True
        }
        deactivated_seg = self._create_segment(
            'Deactivated Users',
            simple_filter_set=deactivated_filter_set).json_body

        activated_filter_set = {
            "MimeType": IsDeactivatedFilterSet.mime_type,
            "Deactivated": False
        }
        activated_seg = self._create_segment(
            'Activated Users',
            simple_filter_set=activated_filter_set).json_body

        # Matches prior to deactivation
        deactivated_members_url = self._members_url(deactivated_seg)
        deactivated_res = self._segment_members(deactivated_members_url).json_body
        assert_that(deactivated_res['Items'], has_length(0))

        activated_members_url = self._members_url(activated_seg)
        activated_res = self._segment_members(activated_members_url).json_body
        assert_that(activated_res['Items'], has_length(3))

        # Deactivate user
        self._deactivate_user(test_username)

        # Matches post deactivation
        deactivated_res = self._segment_members(deactivated_members_url).json_body
        assert_that(deactivated_res['Items'], has_length(1))
        assert_that(deactivated_res['Items'][0], has_entries(Username=test_username))

        activated_res = self._segment_members(activated_members_url).json_body
        assert_that(activated_res['Items'], has_length(2))

    def _members_url(self, ext_segment):
        return self.require_link_href_with_rel(ext_segment, 'members')

    def _deactivate_user(self, test_username):
        resolve_user_url = '/dataserver2/ResolveUser/%s' % test_username
        res = self.testapp.get(resolve_user_url).json_body
        assert_that(res['Items'], has_length(1))

        deactivate_url = self.require_link_href_with_rel(res['Items'][0], 'Deactivate')
        self.testapp.post(deactivate_url)


class TestSegmentMembersView(SegmentManagementTest, SegmentMembersViewMixin):

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_export_members(self):
        with mock_ds.mock_db_trans():
            create_site('alderaan')
            diff_site_user = self._create_user('diff.site')
            set_user_creation_site(diff_site_user, 'alderaan')
            lifecycleevent.modified(diff_site_user)

        with mock_ds.mock_db_trans(site_name='alpha.nextthought.com'):
            user = self._create_user('user.one',
                                     external_value={'realname': u'user one',
                                                     'email': u'one@user.org'})
            self._create_user('user.two',
                              external_value={'realname': u'user two',
                                              'email': u'two@user.org'})
            self._create_user('user.three.deactivated',
                              external_value={'realname': u'user three',
                                              'email': u'three@user.org'})
            self._create_user('site.admin',
                              external_value={'realname': u'admin one',
                                              'email': u'site.admin@user.org'})
            self.make_site_admins('site.admin')

            identity_container = IUserExternalIdentityContainer(user)
            identity_container.add_external_mapping('ext id1', 'aaaaaaa')
            lifecycleevent.modified(user)

        activated_filter_set = {
            "MimeType": IsDeactivatedFilterSet.mime_type,
            "Deactivated": False
        }
        segment = self._create_segment(
            'Activated Users',
            simple_filter_set=activated_filter_set).json_body

        # Deactivate user
        self._deactivate_user('user.three.deactivated')

        # CSV
        params = {'sortOn': 'createdTime'}
        headers = {'accept': str('text/csv')}

        # Call without download-token param works
        members_url = self.require_link_href_with_rel(segment, 'members')
        members = self.testapp.get(members_url, params=params, headers=headers)
        assert_that(members.content_disposition,
                    is_('attachment; filename="users_export-Activated_Users.csv"'))

        _, rows = self.normalize_userinfo_csv(members.body)

        assert_that(rows, has_length(4))
        assert_that(rows[0], is_('username,realname,alias,email,createdTime,lastLoginTime,ext id1'))
        assert_that(rows[1], is_('user.one,User One,User One,one@user.org,,,aaaaaaa'))
        assert_that(rows[2], is_('user.two,User Two,User Two,two@user.org,,,'))
        assert_that(rows[3], is_('site.admin,Admin One,Admin One,site.admin@user.org,,,'))

        # Check filtering
        params['filterAdmins'] = True
        members = self.testapp.get(members_url, params=params, headers=headers)
        csv_contents, rows = self.normalize_userinfo_csv(members.body)
        assert_that(rows, has_length(3))

        params['filter'] = "One"
        members = self.testapp.get(members_url, params=params, headers=headers)
        _, rows = self.normalize_userinfo_csv(members.body)
        assert_that(rows, has_length(2))
        assert_that(rows[1], is_('user.one,User One,User One,one@user.org,,,aaaaaaa'))
        del params['filter']

        # As does call with empty string
        params['download-token'] = ''
        members = self.testapp.get(members_url, params, status=200, headers=headers)
        _, rows = self.normalize_userinfo_csv(members.body)
        assert_that(rows, has_length(3))

        params['download-token'] = 1234
        members = self.testapp.get(members_url, params, status=200, headers=headers)
        _, rows = self.normalize_userinfo_csv(members.body)
        assert_that(rows, has_length(3))
        cookies = dict(parse_cookie(members.headers['Set-Cookie']))
        assert_that(cookies, has_item('download-1234'))
        cookie_res = json.loads(cookies['download-1234'])
        assert_that(cookie_res, has_entry('success', True))

        normalized_body, _ = self.normalize_userinfo_csv(members.body)
        assert_that(normalized_body, is_(csv_contents))

    @staticmethod
    def normalize_userinfo_csv(csv_contents):
        """
        Removes any trailing rows and, after checking for a parseable created
        time in the fifth column, sets that column as empty
        """
        # Removing any trailing empty rows and split into rows
        rows = csv_contents.rstrip().split('\r\n')

        def normalize_row(row):
            cols = row.split(',')
            assert_that(cols, has_length(7), "Expected 7 columns: %s" % (row,))

            # Ensure it parses as a date
            date_from_string(cols[4])
            cols[4] = ''

            return ','.join(cols)

        # We only want to normalize the data rows (not the header)
        header = rows[:1]
        data = [normalize_row(r) for r in rows[1:]]
        rows = tuple(chain(header, data))
        csv_contents = '\r\n'.join(rows)

        return csv_contents, rows


class TestSegmentMembersPreviewView(SegmentManagementTest,
                                    SegmentMembersViewMixin):

    def _segment_members(self, href, params=None, **kwargs):
        params = params if params is not None else {}
        return self.testapp.put_json(href, params=params, **kwargs)

    def _members_url(self, ext_segment):
        return self.require_link_href_with_rel(ext_segment, 'members_preview')

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_updated_preview(self):
        test_username = 'deactivated.user.three'
        with mock_ds.mock_db_trans(site_name='alpha.nextthought.com'):
            self._create_user('user.one',
                              external_value={'realname': u'user one'})
            self._create_user('user.two',
                              external_value={'realname': u'user two'})
            self._create_user(test_username,
                              external_value={'realname': u'user three'})

        deactivated_filter_set = {
            "MimeType": IsDeactivatedFilterSet.mime_type,
            "Deactivated": True
        }
        deactivated_seg = self._create_segment(
            'Deactivated Users',
            simple_filter_set=deactivated_filter_set).json_body

        # Matches prior to deactivation
        preview_url = self._members_url(deactivated_seg)
        deactivated_res = self._segment_members(preview_url).json_body
        assert_that(deactivated_res['Items'], has_length(0))

        # Deactivate user
        self._deactivate_user(test_username)

        # Matches post deactivation
        deactivated_res = self._segment_members(preview_url).json_body
        assert_that(deactivated_res['Items'], has_length(1))
        assert_that(deactivated_res['Items'][0], has_entries(Username=test_username))

        # Preview with deactivated changed
        updated_filter_set = copy.deepcopy(deactivated_seg)
        updated_filter_set['filter_set']['filter_sets'][0]['filter_sets'][0]['Deactivated'] = False
        activated_res = self._segment_members(preview_url, params=updated_filter_set).json_body
        assert_that(activated_res['Items'], has_length(2))

        # Ensure change wasn't persisted
        activated_res = self._segment_members(preview_url, params=None).json_body
        assert_that(activated_res['Items'], has_length(1))
        assert_that(deactivated_res['Items'][0], has_entries(Username=test_username))
