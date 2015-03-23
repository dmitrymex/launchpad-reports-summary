import bs4
import requests

import test_app


class TextCustomReport(test_app.TestApp):
    def _get_lst_from_project(self, project_name):
        resp = requests.get('https://launchpad.net/%s/+milestone/6.1' %
                            project_name)

        doc = bs4.BeautifulSoup(resp.text)

        table = doc.find(id='milestone_bugtasks')

        result = []
        for tr in table.tbody.find_all('tr'):
            tds = tr.find_all('td')
            bug_id = tds[1].text[1:]
            bug_name = tds[2].a.text

            self.id_map[bug_id] = bug_name
            result.append(bug_id)

        return result

    def _get_lst_from_app(self):
        url = self.make_url('/custom_report/6.1')
        resp = requests.get(url)
        doc = bs4.BeautifulSoup(resp.text)

        tables = doc.find_all('tbody')
        result = []
        for table in tables:
            trs = table.find_all('tr')

            for tr in trs:
                tds = tr.find_all('td')
                bug_id = tds[0].a.text.split('\n')[0]
                bug_name = tds[1].span.text.strip()

                self.id_map[bug_id] = bug_name
                result.append(bug_id)

        return result

    def _print_bug(self, msg, bug_id):
        bug_name = self.id_map[bug_id]
        print '%-14s #%s "%s"' % (msg, bug_id, bug_name)

    def test_61_report(self):
        self.id_map = {}

        lp = set(self._get_lst_from_project('mos') +
                 self._get_lst_from_project('fuel'))

        app = set(self._get_lst_from_app())

        for bug_id in lp - app:
            self._print_bug('Missing bug:', bug_id)

        for bug_id in app - lp:
            self._print_bug('Excessive bug:', bug_id)