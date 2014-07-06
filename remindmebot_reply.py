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

class Reply(object):

    def __init__(self):
        self._queryDB = Connect()
        self._replyMessage =(
            "RemindMeBot here! Don't forget to click the parent comment.\n\n**{0}**\n\n {1} "
            "\n\n_____\n ^(I will PM you a message so you don't forget about the comment"
            " or thread later on. Just use the **RemindMe!** command and optional date formats. "
            "Subsequent confirmations in this unique thread will be sent through PM to avoid spam."
            " Default wait is a day.)\n\n"
            "[^([PM Reminder])](http://www.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message="
            "[LINK HERE else default to FAQs]%0A%0ANOTE: Don't forget to add time options after RemindMe command!"
            "%0A%0ARemindMe!) ^| "
            "[^([FAQs])](http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/) ^| "
            "[^([Time Options])](http://www.reddit.com/r/RemindMeBot/comments/2862bd/remindmebot_date_options/) ^| "
            "[^([Suggestions])](http://www.reddit.com/message/compose/?to=RemindMeBotWrangler&subject=Suggestion) ^| "
            "[^([Code])](https://github.com/SIlver--/remindmebot-reddit)"
            )

    def time_to_reply(self):
        """
        Checks to see through SQL if net_date is < current time
        """

        # get current time to compare
        currentTime = datetime.now(timezone('UTC'))
        currentTime = format(currentTime, '%Y-%m-%d %H:%M:%S')
        cmd = "SELECT * FROM message_date WHERE new_date < %s"
        self._queryDB.cursor.execute(cmd, [currentTime])

    def search_db(self):
        """
        Loop through data looking for which comments are old
        """

        data = self._queryDB.cursor.fetchall()
        alreadyCommented = []
        for row in data:
            # checks to make sure permalink hasn't been commented already
            if row[0] not in alreadyCommented:
                flag = 0
                # MySQl- permalink, message, reddit user
                flag = self.new_reply(row[0],row[1], row[3])
                # removes row based on flag
                if flag == 1 or flag == 2:
                    cmd = "DELETE FROM message_date WHERE permalink = %s" 
                    self._queryDB.cursor.execute(cmd, [row[0]])
                    self._queryDB.connection.commit()
                alreadyCommented.append(row[0])

        self._queryDB.connection.commit()
        self._queryDB.connection.close()
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
    reddit.login(USER, PASS)
    while True:
        #try:
        checkReply = Reply()
        checkReply.time_to_reply()
        checkReply.search_db()
        print "sleep"
        time.sleep(60*2)
        #except Exception as err:
           # print err 


# =============================================================================
# RUNNER
# =============================================================================
print "start"
if __name__ == '__main__':
    main()
