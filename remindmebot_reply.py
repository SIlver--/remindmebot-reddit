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

# DB Info
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

class Reply(object):

    def __init__(self):
        self._queryDB = Connect()
        self._replyMessage =(
            "RemindMeBot here!\n\n**{0}**\n\n {1} \n\n_____\n"
            " ^(Hello, I'm RemindMeBot, I will PM you a message so "
            "you don't forget about the comment or thread later on!) "
            "[^(More Info Here)]"
            "(http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)"
            "\n\n^(NOTE: Only days and hours. Max wait is one year. Default is a day.)"
            )

    def time_to_reply(self):
        """
        Checks to see through SQL if net_date is < current time
        """

        # get current time to compare
        currentTime = datetime.now(timezone('UTC'))
        currentTime = format(currentTime, '%Y-%m-%d %H:%M:%S')
        self._queryDB.execute("SELECT * FROM %s WHERE new_date < '%s'" %(DB_TABLE, currentTime))

    def search_db(self):
        """
        Loop through data looking for which comments are old
        """

        data = self._queryDB.fetchall()
        alreadyCommented = []
        for row in data:
            # checks to make sure permalink hasn't been commented already
            if row[0] not in alreadyCommented:
                flag = 0
                # MySQl- permalink, message, reddit user
                flag = self.new_reply(row[0],row[1], row[3])
                # removes row based on flag
                if flag == 1 or flag == 2:
                    self._queryDB.execute("DELETE FROM %s WHERE permalink = '%s'" %(DB_TABLE, row[0]))
                    self._queryDB.commit()
                alreadyCommented.append(row[0])

        self._queryDB.commit()
        self._queryDB.close()
    def new_reply(self, permalink, message, author):
        """
        Replies a second time to the user after a set amount of time
        """
        print self._replyMessage.format(
                message,
                permalink
            )
        try:
            reddit.send_message(author, 'RemindMeBot Reminder!', 
                self._replyMessage.format(
                    message,
                    permalink
                ))
            return 1
        except APIException as err:
            print err
            return 2
        except IndexError as err:
            return 2
        except (HTTPError, ConnectionError, Timeout, timeout) as err:
            print err
            pass
        except RateLimitExceeded as err:
            print err
            time.sleep(10)
            pass

# =============================================================================
# MAIN
# =============================================================================

def main():
    while True:
        try:
            reddit.login(USER, PASS)
            checkReply = Reply()
            checkReply.time_to_reply()
            checkReply.search_db()
            print "sleep"
            time.sleep(60*2)
        except Exception as err:
            print err 


# =============================================================================
# RUNNER
# =============================================================================
print "start"
if __name__ == '__main__':
    main()
