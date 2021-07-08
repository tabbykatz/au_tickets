import requests
import os
from collections import Counter
from datetime import datetime, timedelta, date, time
import json
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


class Scheduler:
    def __init__(self):
        self.cal_name = "Golden Tickets"
        self.token = os.environ.get('GITHUB_TOKEN')
        self.service = self.cal_setup()
        self.deleted_events = []
        # make sure g-t cal exists, and if so get the id
        self.ensure_cal()
        # get closed issues from github so we can remove future cal events tied
        # to them if needed
        self.closed_issues = self.get_closed_issues()
        # a list of events already on g-t cal:
        self.events = self.cleanup_events(self.get_events())
        # get open issues and make them Issue objects
        self.open_issues = self.cleanup_issues(self.get_open_issues())
        # make a list of hours not to schedule (booked_windows)
        self.booked_windows = self.check_avail(self.events)
        # get github activities and make them activity opjects
        self.activities = self.get_activities()
        self.goldenhours = self.golden_hours(self.activities)
        self.timestamps = self.timestamper(self.goldenhours)
        self.push_events(self.eventify_issues(self.open_issues))

    def cal_setup(self):
        ''' set up for calls to the google cal api'''
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json',
                    ['https://www.googleapis.com/auth/calendar']
                )
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return build('calendar', 'v3', credentials=creds)

    def ensure_cal(self):
        ''' call the google cal api and create golden tickets calendar,
        harvesting its id, if it doesnt already exist'''
        id = self.get_cal_id()
        if not id:
            calendar = {
            'summary': self.cal_name,
            }

            created_calendar = self.service.calendars().insert(body=calendar).execute()

            id = created_calendar['id']
        self.cal_id = id

    def get_cal_id(self):
        '''call the google cal api to get golden tickets id if it already
        exists'''
        calendars_result = self.service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        for calendar in calendars:
            if calendar['summary'] == self.cal_name:
               return calendar['id']

    def get_events(self):
        '''retrieve cal events and make them objects'''
        events_list = []
        events = self.service.events().list(calendarId=self.cal_id).execute()
        for event in events['items']:
            currentEvent = Event(event['start']['dateTime'][:-1], event['end']['dateTime'][:-1])
            currentEvent.id = event['id']
            currentEvent.location = event['location']
            currentEvent.summary = event['summary']
            events_list.append(currentEvent)
            # print(currentEvent)
        return events_list

    def cleanup_events(self, events):
        ''' remove cal events that are tied to prematurely closed issues'''
        events_copy = events.copy()
        closed_issue_ids = [issue.id for issue in self.closed_issues]
        # print(closed_issue_ids)
        for event in events_copy:
            if event.location in closed_issue_ids:
                events.remove(event)
                self.delete_event(event.id)
        return events


    def check_avail(self, events):
        '''booked windows is a list of datetime objects denoting the starting
        hour of the event already on the cal'''
        booked_windows = []
        for event in events:
            booked_windows.append(event.datetime)
        return booked_windows

    def get_open_issues(self):
        ''' call the github api for open issues and make them objects '''
        open_issues_list = []
        token = os.getenv('GITHUB_TOKEN', self.token)
        owner = "tabbykatz"
        repo = "goldentickets"
        query_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {
            "state": "open",
        }
        headers = {'Authorization': f'token {token}'}
        r = requests.get(query_url, headers=headers, params=params)

        issues = json.loads(r.text)
        for issue in issues:
            currentIssue = Issue(issue["html_url"], issue["id"], issue["number"], issue["title"])
            open_issues_list.append(currentIssue)
            # print(currentIssue)
        return open_issues_list

    def cleanup_issues(self, issues):
        ''' weed out issues already on the calendar '''
        issues_copy = issues.copy()
        event_location_list = [event.location for event in self.events]
        # print(event_location_list)
        for issue in issues_copy:
            # print(issue.id)
            if issue.id in event_location_list:
                issues.remove(issue)
                # print("removing issue {}".format(issue.number))
            #else:
                # print("this is issue # {} id # {}".format(issue.number, issue.id))
        # for issue in issues:
            #print(issue)
        return issues

    def get_closed_issues(self):
        '''get closed gh issues and make them objects'''
        closed_issues_list = []
        token = os.getenv('GITHUB_TOKEN', self.token)
        owner = "tabbykatz"
        repo = "goldentickets"
        query_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {
            "state": "closed",
        }
        headers = {'Authorization': f'token {token}'}
        r = requests.get(query_url, headers=headers, params=params)
        issues = json.loads(r.text)
        for issue in issues:
            currentIssue = Issue(issue["html_url"], issue["id"], issue["number"], issue["title"])
            # print(currentIssue)
            closed_issues_list.append(currentIssue)
        return closed_issues_list

    def delete_event(self, event_id):
        '''delete a cal event if the issue has been closed'''
        event_result = self.service.events().delete(calendarId=self.cal_id, eventId=event_id).execute()


    def eventify_issues(self, issues):
        '''make an event from an Issue object '''
        if len(self.timestamps) < len(issues):
            dif = len(issues) - len(self.timestamps)
            issues = issues[:-(dif)]
        events_to_post = []
        i = 0
        for issue in issues:
            start = self.timestamps[i].isoformat()
            end = (self.timestamps[i] + timedelta(hours=1)).isoformat()
            currentEvent = Event(start, end)
            currentEvent.body = {
                "summary": "Today you're working on Github Issue #{} (id:{})\n".format(issue.number, issue.id),
                "description": "Title: {} \n".format(issue.title) + "Look at the issue on Github: {}\n".format(issue.html_url),
                "location": "{}".format(issue.id),
                "creator": {"id": issue.id,
                            "email": "tomelay@gmail.com",
                            "displayName": "Golden Tickets",
                            "self": False,
                            },
                "start": {"dateTime": start, "timeZone": "UTC"},
                "end": {"dateTime": end, "timeZone": "UTC"},
            }
            events_to_post.append(currentEvent)
            # event_result = self.service.events().insert(calendarId = self.cal_id, body = event).execute()
            i += 1
        return events_to_post

    def push_events(self, events_to_post):
        '''POSTs events to cal'''
        for event in events_to_post:
            event_result = self.service.events().insert(calendarId = self.cal_id, body = event.body).execute()
            self.deleted_events.append(event_result)

    def get_activities(self):
        ''' call the github Events api to get activities and make them objects '''
        activities_list = []
        token = os.getenv('GITHUB_TOKEN', self.token)
        owner = "tabbykatz"
        query_url = f"https://api.github.com/users/{owner}/events"
        params = {
            "per_page": "100",
        }
        headers = {'Authorization': f'token {token}'}
        r = requests.get(query_url, headers=headers, params=params)

        activities = json.loads(r.text)
        for activity in activities:
            currentActivity = Activity(activity['type'], activity['created_at'])
            activities_list.append(currentActivity)
            # print(activity['created_at'])
        return activities_list

    def golden_hours(self, activities):
        auHours = Counter()
        for activity in activities:
            auHours[(activity.datetime.weekday(), activity.datetime.hour)] += 1
        return auHours

    def timestamper(self, goldenhours):
        timestamps = []
        fullday_offset = timedelta(days=1)
        tomorrow = date.today() + fullday_offset
        goldenhours = goldenhours.most_common(10)
        goldenhours.reverse()
        while goldenhours:
            current_slot = goldenhours.pop()
            cur_weekday = current_slot[0][0]
            cur_hour = current_slot[0][1]
            opportunity = datetime.combine(tomorrow, time(hour = cur_hour))
            while opportunity.weekday() != cur_weekday:
                opportunity = opportunity + fullday_offset
            timestamps.append(opportunity)
        timestamps = [x for x in timestamps if x not in self.booked_windows]
        return timestamps


class Issue:
    def __init__(self, html_url="", id="", number="", title=""):
        self.html_url = html_url
        self.id = str(id)
        self.number = number
        self.title = title

    def __str__(self):
        return "Issue #{} contains:\nTitle: {}\n Url: {}\n Id: {}\n Number: {}\n".format(self.number, self.title, self.html_url, self.id, self.number)

class Activity:
    def __init__(self, type="", created_at=""):
        self.type = type
        self.created_at = created_at
        self.datetime = self.get_datetime()

    def __str__(self):
        return "Activity:\n(type: {}\n, created_at: {}\n)".format(self.type, self.created_at)

    def get_datetime(self):
        '''get datetime obj for activity'''
        return datetime.strptime(self.created_at[:-1], "%Y-%m-%dT%H:%M:%S")

class Event:
    def __init__(self, start="", end=""):
        self.start = start
        self.end = end
        self.datetime = self.get_datetime()

    def __str__(self):
        return("\n\nSummary = {}\nStart = {}\nEnd = {}\nLocation = {}\nID = {}\n Datetime obj = {}".format(self.summary, self.start, self.end, self.location, self.id, self.datetime))

    def get_datetime(self):
        ''' get datetime obj for event'''
        return datetime.strptime(self.start, "%Y-%m-%dT%H:%M:%S")

def main():
    sch = Scheduler()
    # print(sch.goldenhours)

if __name__ == '__main__':
    main()
