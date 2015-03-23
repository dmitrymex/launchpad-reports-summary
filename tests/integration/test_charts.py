import bs4
import requests

import test_app


CLASS_LST = [
    'statusNEW',
    'statusINCOMPLETE',
    'statusOPINION',
    'statusINVALID',
    'statusWONTFIX',
    'statusCONFIRMED',
    'statusTRIAGED',
    'statusINPROGRESS',
    'statusFIXCOMMITTED',
    'statusFIXRELEASED'
]


def map_class_name(name):
    return name[len('status'):].lower()


class TestCharts(test_app.TestApp):
    def _compare(self, state, a, b):
        if a != b:
            self.diff_counter += abs(a - b)
            print "%s: expected %d, but got %d" % (state, b, a)

    def _find_real_numbers(self, project, milestone):
        resp = requests.get('https://launchpad.net/%s/+milestone/%s' %
                            (project, milestone))
        doc = bs4.BeautifulSoup(resp.text)
        activities = doc.find('div', attrs={'id': 'milestone-activities'})

        real_numbers = {}

        for class_name in CLASS_LST:
            status_name = map_class_name(class_name)

            elem = activities.find('span', attrs={'class': class_name}).strong
            real_numbers[status_name] = int(elem.text)

        return real_numbers

    def _get_chart_last_day_data(self, chart_url, *args):
        url = self.make_url(chart_url % args)

        resp = requests.get(url)

        chart_numbers = {}
        for dct in resp.json():
            chart_numbers[dct['key']] = dct['values'][-1][1]

        return chart_numbers

    def _verify_numbers(self, real_numbers, chart_numbers):
        self.diff_counter = 0

        self._compare('Incomplete',
                     chart_numbers['Incomplete'],
                     real_numbers['incomplete'])

        self._compare('Open',
                     chart_numbers['Open'],
                     real_numbers['confirmed'] + real_numbers['triaged'])

        self._compare('In Progress',
                     chart_numbers['In Progress'],
                     real_numbers['inprogress'])

        self._compare('Resolved',
                     chart_numbers['Resolved'],
                     real_numbers['fixcommitted'] +
                     real_numbers['wontfix'] +
                     real_numbers['invalid'] +
                     real_numbers['opinion'])

        self._compare('Verified',
                     chart_numbers['Verified'],
                     real_numbers['fixreleased'])

        print 'Total sum of differences: %d' % self.diff_counter

    def _verify_fuel_chart(self, milestone):
        print "Testing charts for %s" % milestone

        real_numbers = self._find_real_numbers('fuel', milestone)

        chart_numbers = self._get_chart_last_day_data(
            '/project/fuel/api/release_chart_trends/%s/get_data', milestone)

        self._verify_numbers(real_numbers, chart_numbers)

    def test_fuel_61_chart(self):
        self._verify_fuel_chart('6.1')

    def test_fuel_601_chart(self):
        self._verify_fuel_chart('6.0.1')

    def test_fuelmos_61_chart(self):
        print "Testing Fuel+MOS charts for 6.1"

        real_numbers = self._find_real_numbers('fuel', '6.1')
        real_numbers_mos = self._find_real_numbers('mos', '6.1')

        for key in real_numbers.keys():
            real_numbers[key] += real_numbers_mos[key]

        chart_numbers = self._get_chart_last_day_data(
            '/product/api/release_chart_trends/6.1/get_data')

        self._verify_numbers(real_numbers, chart_numbers)
