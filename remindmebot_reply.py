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
            "RemindMeBot here!" 
            "\n\n**Your message:** \n\n>{message}"
            "\n\n**Your original comment:** \n\n>{original}"
            "\n\n**The parent comment from your original comment or its submission:** \n\n>{parent}"
            "\n\n_____\n\n"
            "[^([FAQs])](http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/) ^| "
            "[^([Custom Reminder])](http://www.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message="
            "[LINK INSIDE SQUARE BRACKETS else default to FAQs]%0A%0ANOTE: Don't forget to add the time options after the command."
            "%0A%0ARemindMe!) ^| "
            "[^([Feedback])](http://www.reddit.com/message/compose/?to=RemindMeBotWrangler&subject=Feedback) ^| "
            "[^([Code])](https://github.com/SIlver--/remindmebot-reddit)"
            )

    def parent_comment(self, dbPermalink):
        """
        Returns the parent comment or if it's a top comment
        return the original submission
        """
        try:
            commentObj = reddit.get_submission(dbPermalink).comments[0]
            if commentObj.is_root:
                return str(commentObj.submission.permalink)
            else:
                return str(reddit.get_info(thing_id=commentObj.parent_id).permalink)
        except IndexError as err:
            print "parrent_comment error"
            return "It seems your original comment was deleted, unable to return parent comment."

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
            # checks to make sure ID hasn't been commented already
            # For situtations where errors happened
            if row[0] not in alreadyCommented:
                flagDelete = False
                # MySQl- permalink, message, reddit user
                flagDelete = self.new_reply(row[1],row[2], row[4])
                # removes row based on flagDelete
                if flagDelete:
                    cmd = "DELETE FROM message_date WHERE id = %s" 
                    self._queryDB.cursor.execute(cmd, [row[0]])
                    self._queryDB.connection.commit()
                alreadyCommented.append(row[0])

        self._queryDB.connection.commit()
        self._queryDB.connection.close()

    def new_reply(self, permalink, message, author):
        """
        Replies a second time to the user after a set amount of time
        """ 
        """
        print self._replyMessage.format(
                message,
                permalink
            )
        """
        print "---------------"
        print author
        print permalink
        try:
            reddit.send_message(author, 'Hello, ' + author + ' RemindMeBot Here!', 
                self._replyMessage.format(
                    message=message,
                    original=permalink,
                    parent=self.parent_comment(permalink)
                ))
            print "Did It"
            return True
        except APIException as err:
            print "APIException", err
            return False
        except IndexError as err:
            print "IndexError", err
            return False
        except (HTTPError, ConnectionError, Timeout, timeout) as err:
            print "HTTPError", err
            return False
        except RateLimitExceeded as err:
            print "RateLimitExceeded", err
            time.sleep(10)

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
        time.sleep(5)
        #except Exception as err:
           # print err 


# =============================================================================
# RUNNER
# =============================================================================
print "start"
if __name__ == '__main__':
    main()