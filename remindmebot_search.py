#!/usr/bin/env python2.7

# =============================================================================
# IMPORTS
# =============================================================================

import praw
import re
import MySQLdb
import ConfigParser
import time
from datetime import datetime, timedelta
from requests.exceptions import HTTPError, ConnectionError, Timeout
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded
from socket import timeout
from pytz import timezone

# =============================================================================
# GLOBALS
# =============================================================================

# Reads the config file
config = ConfigParser.ConfigParser()
config.read("remindmebot.cfg")

#Reddit info
user_agent = ("RemindMeBot v2.0 by /u/RemindMeBotWrangler")
reddit = praw.Reddit(user_agent = user_agent)
USER = config.get("Reddit", "username")
PASS = config.get("Reddit", "password")

DB_USER = config.get("SQL", "user")
DB_PASS = config.get("SQL", "passwd")
DB_TABLE = config.get("SQL", "table")
# =============================================================================
# CLASSES
# =============================================================================

class Connect(object):
    """
    DB connection class
    """
    connection = None
    cursor = None

    def __init__(self):
        self.connection = MySQLdb.connect(
            host="localhost", user=DB_USER, passwd=DB_PASS, db="bot"
        )
        self.cursor = self.connection.cursor()

    def execute(self, command):
        self.cursor.execute(command)

    def fetchall(self):
        return self.cursor.fetchall()

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

class Search(object):
    commented = [] # comments already replied to
    subId = [] # reddit threads already replied in

    def __init__(self, comment):
        self.comment = comment # Reddit comment Object
        self._messageInput = '"Hello, I\'m here to remind you to see the parent comment!"'
        self._totalTime = 0
        self._replyMessage = ""
        self._replyDate = None

    def parse_comment(self):
        """
        Parse comment looking for the message and time
        """
        # Default Times
        timeDayInt = 1
        timeHourInt = 0

        # check for hours
        # regex: 4.0 or 4 "hour | hours" ONLY
        timeHourTemp = re.search("(?:\d+)?\.*(?:\d+ [hH][oO][uU][rR]([sS]|))", self.comment.body)

        if timeHourTemp:
            # regex: ignores ".0" and non numbers
            timeHourTemp = re.search("\d*", timeHourTemp.group(0))
            timeHourInt = int(timeHourTemp.group(0))

        # check for days
        # regex 4.0 or 4 "day | days" ONLY
        timeDayTemp = re.search("(?:\d+)?\.*(?:\d+ [dD][aA][yY]([sS]|))", self.comment.body)
        if timeDayTemp:
            timeDayTemp = re.search("\d*", timeDayTemp.group(0))
            timeDayInt= int(timeDayTemp.group(0))
        # cases where the user inputs hours but not days
        elif not timeDayTemp and timeHourTemp > 0:
            timeDayInt = 0

        # convert into hours
        self._totalTime = (timeDayInt * 24) + timeHourInt

        # check for user message
        # regex: Only text around quotes, avoids long messages
        messageInputTemp = re.search('(["].{0,10000}["])', self.comment.body)
        if messageInputTemp:
            self._messageInput = messageInputTemp.group(0)


    def save_to_db(self):
        """
        Saves the permalink comment, the time, and the message to the DB
        """

        # connection
        addToDB = Connect()

        # Converting time
        self._replyDate = datetime.now(timezone('UTC')) + timedelta(hours=self.hours)
        #9999/12/31 HH/MM/SS
        self._replyDate = format(self._replyDate, '%Y-%m-%d %H:%M:%S')

        addToDB.execute("INSERT INTO %s VALUES ('%s', %s, '%s', '%s')" %(
                        DB_TABLE, 
                        self.comment.permalink, 
                        self._messageInput, 
                        self._replyDate, 
                        self.comment.author))
        addToDB.commit()
        addToDB.close()
        # Info is added to DB, user won't be bothered a second time
        self.commented.append(self.comment.id)

    def build_message(self):
        """
        Buildng message for user
        """
        self._replyMessage = "I'll message you on {0} UTC to remind you of this post."
                            "\n\n_____\n ^(Hello, I'm RemindMeBot, I will PM you a message"
                            " so you don't forget about the comment or thread later on!) "
                            "[^(More Info Here)]"
                            "(http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)"
                            "\n\n^(NOTE: Only days and hours. Max wait is one year. Default is a day."
                            " **Only first confirmation in the unique thread is shown.**)"


    def reply(self):
        """
        Messages the user letting as a confirmation
        """
        sub = reddit.get_submission(comment.permalink)
        author = comment.author
        """
        try:
            # First message will be a reply in a thread
            # afterwards are PM in the same thread
            if (sub.id not in self.subId):
                self.comment.reply(self._replyMessage.format(
                                    self.__replyDate, 
                                    self._replyMessage))
            else:
                reddit.send_message(author, 'RemindMeBot Reminder!', self._replyMessage.format(
                                    self.__replyDate, 
                                    self._replyMessage))
        except (HTTPError, ConnectionError, Timeout, timeout) as err:
            print err
            # PM instead if the banned from the subreddit
            if str(e) == "403 Client Error: Forbidden":
                reddit.send_message(author, 'RemindMeBot Reminder!', self._replyMessage.format(
                                    self.__replyDate, 
                                    self._replyMessage))
        except RateLimitExceeded as err:
            print err
            # PM when I message too much
            reddit.send_message(author, 'RemindMeBot Reminder!', self._replyMessage.format(
                    self.__replyDate, 
                    self._replyMessage))
            time.sleep(10)
        except APIException as err: # Catch any less specific API errors
            print err
        else:
            # only message the thread once
            self.subId.append(sub.id)
        """
        print self._replyMessage.format(
                        self.__replyDate, 
                        self._replyMessage))
# =============================================================================
# MAIN
# =============================================================================

def main():
    while True:
        try:
            reddit.login(USER, PASS)
            # Grab all the new comments from /r/all
            comments = praw.helpers.comment_stream(reddit, 'all', limit=1000, verbosity=0)

            # loop through each comment
            for comment in comments:
                redditCall = Search(comment)
                if "RemindMe!" in comment.body and 
                    redditCall.comment.id not in redditCall.commented:
                        print "in"
                        redditCall.parse_comment()
                        redditCall.save_to_db()
                        redditCall.build_message()
                        redditCall.reply()

        except Exception err:
            print err
# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()
