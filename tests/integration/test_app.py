import unittest

import requests


ENDPOINTS = [
    '/'
    '/common_statistic',
    '/project/fuel/',
    '/project/fuel/bug_table_for_status/New/None',
    '/project/fuel/6.1/project_statistic/',
    '/project/fuel/bug_trends/6.1/',
    '/project/fuel/bug_table_for_status/Open/6.1',
    '/project/fuel/bug_table_for_status/Closed/6.1',
    '/project/mos/bug_table_for_status/New/None',
    '/project/mos/6.1/project_statistic/',
    '/project/mos/bug_trends/6.1/',
    '/project/mos/bug_table_for_status/Open/6.1',
    '/project/mos/bug_table_for_status/Closed/6.1',
    '/project/fuelplusmos/6.1/',
    '/project/fuel/bug_list_for_sbpr/6.1/total/all',
    '/project/mos/bug_list_for_sbpr/6.1/high/all',
    '/project/ceilometer/',
    '/project/ceilometer/bug_table_for_status/New/None',

    '/sla_report/6.0.1',
    '/sla_report/6.1',
    '/hcf_status/6.0.1',
    '/hcf_status/6.1',
    '/custom_report/6.0.1',
    '/custom_report/6.1',
    '/triage_queue/mos',
    '/triage_queue/fuel'
]


class TestApp(unittest.TestCase):
    def setUp(self):
        super(TestApp, self).setUp()
        self.host = 'localhost'
        self.port = 1111
        self.host = 'lp-reports-staging.vm.mirantis.net'
        self.port = 80
        self.host = 'lp-reports.vm.mirantis.net'
        self.port = 80

        # do print to separate output of different tests
        print

    def make_url(self, endpoint):
        return 'http://%s:%d%s' % (self.host, self.port, endpoint)


class TestEndpoints(TestApp):
    def test_endpoints(self):
        for endpoint in ENDPOINTS:
            url = self.make_url(endpoint)
            resp = requests.get(url)

            if resp.status_code != 200:
                self.fail('Got %i status code on endpoint %s' %
                          resp.status_code, url)
