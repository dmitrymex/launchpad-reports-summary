#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import collections
import json
import os

import flask

from flask import (Flask, request, render_template, json as flask_json,
                   redirect, session, url_for)
from launchpadlib.credentials import Credentials, AccessToken
from launchpadlib.uris import LPNET_WEB_ROOT


from launchpad_reporting import sla_reports
from launchpad_reporting.db import db
from launchpad_reporting.launchpad import (LaunchpadClient,
                                           LaunchpadAnonymousClient)
from launchpad_reporting.launchpad.lpdata import (authorization_url,
                                                  SimpleLaunchpad)


path_to_data = "/".join(os.path.abspath(__file__).split('/')[:-1])

with open('{0}/data.json'.format(path_to_data)) as data_file:
    data = json.load(data_file)

with open('{0}/file.json'.format(path_to_data)) as teams_file:
    teams_data = json.load(teams_file, object_pairs_hook=collections.OrderedDict)


launchpad = LaunchpadAnonymousClient()

app = Flask(__name__)

app.secret_key = "lei3raighuequic3Pephee8duwohk8"


def print_select(dct, param, val):
    if param not in dct or val not in dct[param]:
        return ""
    return "selected=\"selected\""


def filter(request, bugs):

    filters = {
        'status': request.args.getlist('status'),
        'importance': request.args.getlist('importance'),
        'assignee': request.args.getlist('assignee'),
        'criteria': request.args.getlist('criteria')
    }

    teams_data['Unknown'] = {'unknown': []}

    if 'tab_name' in request.args and request.args['tab_name'] in teams_data:
        filters['assignee'] = teams_data[request.args['tab_name']]


    bugs = launchpad.lpdata.filter_bugs(bugs, filters, teams_data)

    return bugs, filters


app.jinja_env.globals.update(print_select=print_select)

KEY_MILESTONE = "6.1"
MILESTONES = db.bugs.milestones.find_one()["Milestone"]
flag = False

launchpad_user = None


def process_launchpad_authorization():
    global launchpad_user
    # FIXME: store keys in session for every user (probably uuids)
    # then retrieve launchpad instance from App-level dict
    credentials = Credentials()
    SimpleLaunchpad.set_credentials_consumer(credentials,
                                             "launchpad-reporting-www")
    if 'request_token_parts' in session:
        credentials._request_token = AccessToken.from_params(
            session['request_token_parts'])
        credentials.exchange_request_token_for_access_token(LPNET_WEB_ROOT)
        launchpad_user = LaunchpadClient(credentials)
        session['access_token_parts'] = {
            'oauth_token': credentials.access_token.key,
            'oauth_token_secret': credentials.access_token.secret,
            'lp.context': credentials.access_token.context
        }
        del session['request_token_parts']
        return (False, None)
    elif 'access_token_parts' in session:
        if launchpad_user is None:
            credentials.access_token = AccessToken.from_params(
                session['access_token_parts'])
            launchpad_user = LaunchpadClient(credentials)
        return (False, None)
    else:
        credentials.get_request_token(
            web_root=LPNET_WEB_ROOT)
        request_token_key = credentials._request_token.key
        request_token_secret = credentials._request_token.secret
        request_token_context = credentials._request_token.context
        session['request_token_parts'] = {
            'oauth_token': request_token_key,
            'oauth_token_secret': request_token_secret,
            'lp.context': request_token_context
        }
        auth_url = authorization_url(LPNET_WEB_ROOT,
                                     request_token=request_token_key)
        return (True, auth_url)


@app.route('/project/<project_name>/bug_table_for_status/<bug_type>/'
           '<milestone_name>/bug_list/')
def bug_list(project_name, bug_type, milestone_name):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    project = launchpad.get_project(project_name)
    tags = None

    if 'tags' in request.args:
        tags = request.args['tags'].split(',')
    if bug_type == "New":
        milestone_name = None

    bugs = launchpad.get_bugs(
        project_name=project_name,
        statuses=launchpad.BUG_STATUSES[bug_type],
        milestone_name=milestone_name, tags=tags)

    return render_template("bug_list.html",
                                 project=project,
                                 bugs=bugs,
                                 bug_type=bug_type,
                                 milestone_name=milestone_name,
                                 selected_bug_table=True,
                                 prs=list(db.prs),
                                 key_milestone=KEY_MILESTONE,
                                 update_time=launchpad.get_update_time())



@app.route('/project/<project_name>/bug_list_for_sbpr/<milestone_name>/'
           '<bug_type>/<sbpr>')
def bug_list_for_sbpr(project_name, bug_type, milestone_name, sbpr):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    subprojects = [sbpr]

    if sbpr == 'all':
        subprojects = list(db.subprs)

    bug_importance = []
    bug_statuses = ""
    bugs_type_to_print = ""

    if bug_type == "done":
        bugs_type_to_print = "Closed"
        bug_statuses = "Closed"

    if bug_type == "total":
        bugs_type_to_print = "Total"
        bug_statuses = "All"

    if bug_type == "high":
        bugs_type_to_print = "High and Critical"
        bug_statuses = "NotDone"
        bug_importance = ["High", "Critical"]

    if bug_type == "incomplete":
        bugs_type_to_print = "Incomplete"
        bug_statuses = "Incomplete"

    bugs = list(set(launchpad.get_bugs(project_name=project_name,
                                       statuses=launchpad.
                                       BUG_STATUSES[bug_statuses],
                                       milestone_name=milestone_name,
                                       tags=subprojects,
                                       importance=bug_importance)))

    return render_template("bug_table_sbpr.html",
                           project=project_name,
                           prs=list(db.prs),
                           bugs=bugs,
                           sbpr=sbpr,
                           key_milestone=KEY_MILESTONE,
                           milestone_name=milestone_name,
                           milestones=MILESTONES,
                           update_time=launchpad.get_update_time(),
                           bugs_type_to_print=bugs_type_to_print)


@app.route('/project/<project_name>/api/release_chart_trends/'
           '<milestone_name>/get_data')
def bug_report_trends_data(project_name, milestone_name):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    data = launchpad.release_chart(
        project_name,
        milestone_name
    ).get_trends_data()

    return flask_json.dumps(data)


@app.route('/project/<project_name>/api/release_chart_incoming_outgoing/'
           '<milestone_name>/get_data')
def bug_report_get_incoming_outgoing_data(project_name, milestone_name):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    data = launchpad.release_chart(
        project_name,
        milestone_name
    ).get_incoming_outgoing_data()
    return flask_json.dumps(data)


@app.route('/project/<project_name>/bug_table_for_status/'
           '<bug_type>/<milestone_name>')
def bug_table_for_status(project_name, bug_type, milestone_name):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    project = launchpad.get_project(project_name)

    if bug_type == "New":
        milestone_name = None

    return render_template("bug_table.html",
                           project=project,
                           prs=list(db.prs),
                           key_milestone=KEY_MILESTONE,
                           milestone_name=milestone_name,
                           update_time=launchpad.get_update_time())


@app.route('/project/<project_name>/bug_trends/<milestone_name>/')
def bug_trends(project_name, milestone_name):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    project = launchpad.get_project(project_name)

    return render_template("bug_trends.html",
                           project=project,
                           milestone_name=milestone_name,
                           selected_bug_trends=True,
                           prs=list(db.prs),
                           key_milestone=KEY_MILESTONE,
                           update_time=launchpad.get_update_time())


@app.route('/hcf_report/<milestone_name>')
def bugs_hcf_report(milestone_name):
    bugs = sla_reports.get_reports_data('hcf-report', ['mos', 'fuel'],
                                        milestone_name)
    bugs, filters = filter(request, bugs)

    return render_template(
        "bugs_lifecycle_report.html",
        report="hcf",
        milestone_name=milestone_name,
        milestones=MILESTONES,
        all_bugs=bugs,
        teams=teams_data,
        filters=filters,
    )


@app.route('/sla_report/<milestone_name>')
def bugs_lifecycle_report(milestone_name):
    bugs = sla_reports.get_reports_data('sla-report', ['mos', 'fuel'],
                                        milestone_name)

    bugs, filters = filter(request, bugs)

    return render_template(
        "bugs_lifecycle_report.html",
        report="sla",
        milestone_name=milestone_name,
        milestones=MILESTONES,
        all_bugs=bugs,
        teams=teams_data,
        filters=filters,
    )


@app.route('/triage_queue/<project>')
def triage_queue(project):
    bugs = sla_reports.get_reports_data('non-triaged-in-time', [project])

    bugs, filters = filter(request, bugs)

    return flask.render_template(
        "bugs_lifecycle_report.html",
        report="triage",
        all_bugs=bugs,
        teams=teams_data,
        filters=filters,
    )

@app.route('/project/<project_name>/<milestone_name>/project_statistic/<tag>/')
def statistic_for_project_by_milestone_by_tag(project_name, milestone_name,
                                              tag):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    display = True
    project = launchpad.get_project(project_name)

    project.display_name = project.display_name.capitalize()

    page_statistic = launchpad.common_statistic_for_project(
        project_name=project_name,
        tag=tag,
        milestone_name=[milestone_name])

    milestone = dict.fromkeys(["name", "id"])
    milestone["name"] = milestone_name
    milestone["id"] = data[project_name][milestone_name]
    if project_name == "fuel":
        milestone["id"] = data[project_name][milestone_name]

    return render_template("project.html",
                           project=project,
                           key_milestone=KEY_MILESTONE,
                           selected_overview=True,
                           display_subprojects=display,
                           prs=list(db.prs),
                           subprs=list(db.subprs),
                           page_statistic=page_statistic,
                           milestone=milestone,
                           flag=True,
                           tag=tag,
                           update_time=launchpad.get_update_time())


@app.route('/project/<project_name>/<milestone_name>/project_statistic/')
def statistic_for_project_by_milestone(project_name, milestone_name):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    display = False
    project = launchpad.get_project(project_name)
    if project_name in ("mos", "fuel"):
        display = True
    project.display_name = project.display_name.capitalize()

    page_statistic = launchpad.common_statistic_for_project(
        project_name=project_name,
        tag=None,
        milestone_name=[milestone_name])

    milestone = dict.fromkeys(["name", "id"])
    milestone["name"] = milestone_name
    milestone["id"] = data[project_name][milestone_name]
    if project_name == "fuel":
        milestone["id"] = data[project_name][milestone_name]

    return render_template("project.html",
                           key_milestone=KEY_MILESTONE,
                           project=project,
                           selected_overview=True,
                           display_subprojects=display,
                           prs=list(db.prs),
                           subprs=list(db.subprs),
                           page_statistic=page_statistic,
                           milestone=milestone,
                           flag=True,
                           update_time=launchpad.get_update_time())


@app.route('/project/fuelplusmos/<milestone_name>/')
def fuel_plus_mos_overview(milestone_name):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    milestones = db.bugs.milestones.find_one()["Milestone"]

    subprojects = list(db.subprs)
    page_statistic = dict.fromkeys(subprojects)

    for sbpr in subprojects:
        page_statistic["{0}".format(sbpr)] = dict.fromkeys(["fuel", "mos"])
        for pr in ("fuel", "mos"):
            page_statistic["{0}".format(sbpr)]["{0}".format(pr)] = \
                dict.fromkeys(["done", "total", "high"])

            page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["done"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["Closed"],
                    milestone_name=milestone_name,
                    tags=[sbpr]))

            page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["total"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["All"],
                    milestone_name=milestone_name,
                    tags=[sbpr]))

            page_statistic["{0}".format(sbpr)]["{0}".format(pr)]["high"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["NotDone"],
                    milestone_name=milestone_name,
                    tags=[sbpr],
                    importance=["High", "Critical"]))

    fuel_plus_mos = dict.fromkeys(subprojects)
    for subpr in subprojects:
        fuel_plus_mos["{0}".format(subpr)] = dict.fromkeys(["done",
                                                            "total",
                                                            "high"])
    for subpr in subprojects:
        tag = ["{0}".format(subpr)]
        summary = launchpad.bugs_ids(tag, milestone_name)
        fuel_plus_mos["{0}".format(subpr)]["done"] = summary["done"]
        fuel_plus_mos["{0}".format(subpr)]["total"] = summary["total"]
        fuel_plus_mos["{0}".format(subpr)]["high"] = summary["high"]

    summary_statistic = dict.fromkeys("summary")
    summary_statistic["summary"] = dict.fromkeys(["tags", "others"])
    for criterion in ["tags", "others"]:
        summary_statistic["summary"][criterion] = dict.fromkeys(
            ["fuel", "mos", "fuel_mos"])

    for criterion in ["tags", "others"]:

        if criterion == "others":
            condition = True
        else:
            condition = False

        for pr in ("fuel", "mos"):
            summary_statistic["summary"][criterion]["{0}".format(pr)] = \
                dict.fromkeys(["done", "total", "high"])

            summary_statistic[
                "summary"][criterion]["{0}".format(pr)]["done"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["Closed"],
                    milestone_name=milestone_name,
                    tags=subprojects,
                    condition=condition))

            summary_statistic[
                "summary"][criterion]["{0}".format(pr)]["total"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["All"],
                    milestone_name=milestone_name,
                    tags=subprojects,
                    condition=condition))

            summary_statistic[
                "summary"][criterion]["{0}".format(pr)]["high"] = \
                len(launchpad.get_bugs(
                    project_name=pr,
                    statuses=launchpad.BUG_STATUSES["NotDone"],
                    milestone_name=milestone_name,
                    tags=subprojects,
                    importance=["High", "Critical"],
                    condition=condition))

    for criterion in ["tags", "others"]:
        summary_statistic["summary"][criterion]["fuel_mos"] = \
            dict.fromkeys(["done", "total", "high"])
        for state in ["done", "total", "high"]:
            summary_statistic[
                "summary"][criterion]["fuel_mos"]["{0}".format(state)] = 0

    for state in ["done", "total", "high"]:
        for subpr in subprojects:
            summary_statistic[
                "summary"]["tags"]["fuel_mos"]["{0}".format(state)] +=\
                fuel_plus_mos["{0}".format(subpr)]["{0}".format(state)]

        summary_statistic[
            "summary"]["others"]["fuel_mos"]["{0}".format(state)] = \
            summary_statistic[
                "summary"]["others"]["fuel"]["{0}".format(state)] + \
            summary_statistic["summary"]["others"]["mos"]["{0}".format(state)]

    incomplete = dict.fromkeys("fuel", "mos")
    for pr in ("fuel", "mos"):
        incomplete['{0}'.format(pr)] = \
            len(launchpad.get_bugs(
                project_name=pr,
                statuses=["Incomplete"],
                milestone_name=milestone_name,
                tags=subprojects))

    return render_template("project_fuelmos.html",
                           milestones=milestones,
                           key_milestone=KEY_MILESTONE,
                           current_milestone=milestone_name,
                           prs=list(db.prs),
                           subprs=list(db.subprs),
                           fuel_milestone_id=data["fuel"][
                               milestone_name],
                           mos_milestone_id=data["mos"][milestone_name],
                           page_statistic=page_statistic,
                           summary_statistic=summary_statistic,
                           fuel_plus_mos=fuel_plus_mos,
                           all_tags="+".join(db.subprs),
                           incomplete=incomplete,
                           update_time=launchpad.get_update_time())


@app.route('/project/<project_name>/')
def project_overview(project_name):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    project_name = project_name.lower()

    if project_name == "fuelplusmos":
        return redirect(
            "/project/fuelplusmos/{0}/".format(KEY_MILESTONE), code=302)

    project = launchpad.get_project(project_name)
    project.display_name = project.display_name.capitalize()
    page_statistic = launchpad.common_statistic_for_project(
        project_name=project_name,
        milestone_name=project.active_milestones,
        tag=None)

    return render_template("project.html",
                           project=project,
                           key_milestone=KEY_MILESTONE,
                           selected_overview=True,
                           prs=list(db.prs),
                           subprs=list(db.subprs),
                           page_statistic=page_statistic,
                           milestone=[],
                           update_time=launchpad.get_update_time())


@app.route('/project/<global_project_name>/<tag>/')
def mos_project_overview(global_project_name, tag):
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    global_project_name = global_project_name.lower()
    tag = tag.lower()

    project = launchpad.get_project(global_project_name)
    page_statistic = launchpad.common_statistic_for_project(
        project_name=global_project_name,
        milestone_name=project.active_milestones,
        tag=tag)

    return render_template("project.html",
                           project=project,
                           key_milestone=KEY_MILESTONE,
                           tag=tag,
                           page_statistic=page_statistic,
                           selected_overview=True,
                           display_subprojects=True,
                           prs=list(db.prs),
                           subprs=list(db.subprs),
                           milestone=[],
                           update_time=launchpad.get_update_time())


@app.route('/logout')
def logout():
    del session['request_token_parts']
    del session['access_token_parts']
    return redirect(url_for('main_page'))


@app.route('/')
def main_page():
    should_redirect, lp_url = process_launchpad_authorization()
    if should_redirect:
        return redirect(lp_url)
    global_statistic = dict.fromkeys(db.prs)
    for pr in global_statistic.keys()[:]:
        types = dict.fromkeys(["total", "critical", "unresolved"])
        types["total"] = len(launchpad.get_bugs(
            project_name=pr, statuses=launchpad.BUG_STATUSES["All"]))
        types["critical"] = len(launchpad.get_bugs(
            project_name=pr,
            statuses=launchpad.BUG_STATUSES["NotDone"],
            importance=["Critical"]))
        types["unresolved"] = len(launchpad.get_bugs(
            project_name=pr,
            statuses=launchpad.BUG_STATUSES["NotDone"]))
        global_statistic['{0}'.format(pr)] = types

    return render_template("main.html",
                           key_milestone=KEY_MILESTONE,
                           statistic=global_statistic,
                           prs=list(db.prs),
                           update_time=launchpad.get_update_time())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="action", help='actions'
    )
    run_parser = subparsers.add_parser(
        'run', help='run application locally'
    )
    run_parser.add_argument(
        '-p', '--port', dest='port', action='store', type=str,
        help='application port', default='80'
    )
    run_parser.add_argument(
        '-H', '--host', dest='host', action='store', type=str,
        help='application host', default='0.0.0.0'
    )

    params, args = parser.parse_known_args()
    app.run(
        debug=True,
        host=params.host,
        port=int(params.port),
        use_reloader=True,
        threaded=True
    )

