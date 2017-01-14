#!/usr/bin/env python2.7

# =============================================================================
# IMPORTS
# =============================================================================

import praw
import OAuth2Util
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
reddit = praw.Reddit("RemindMeB0tReply")
o = OAuth2Util.OAuth2Util(reddit, print_log=True)
o.refresh(force=True)
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
            "RemindMeBot private message here!" 
            "\n\n**The message:** \n\n>{message}"
            "\n\n**The original comment:** \n\n>{original}"
            "\n\n**The parent comment from the original comment or its submission:** \n\n>{parent}"
            "{origin_date_text}"
            "\n\n#Would you like to be reminded of the original comment again? Just set your time again after the RemindMe! command. [CLICK HERE]"
            "(http://np.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message=[{original}]"
            "%0A%0ARemindMe!)"
            "\n\n_____\n\n"
            "|[^(FAQs)](http://np.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)"
            "|[^(Custom)](http://np.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message="
                "[LINK INSIDE SQUARE BRACKETS else default to FAQs]%0A%0A"
                "NOTE: Don't forget to add the time options after the command.%0A%0ARemindMe!)"
            "|[^(Your Reminders)](http://np.reddit.com/message/compose/?to=RemindMeBot&subject=List Of Reminders&message=MyReminders!)"
            "|[^(Feedback)](http://np.reddit.com/message/compose/?to=RemindMeBotWrangler&subject=Feedback)"
            "|[^(Code)](https://github.com/SIlver--/remindmebot-reddit)"
            "|[^(Browser Extensions)](https://np.reddit.com/r/RemindMeBot/comments/4kldad/remindmebot_extensions/)"
            "\n|-|-|-|-|-|-|"
            )

    def parent_comment(self, dbPermalink):
        """
        Returns the parent comment or if it's a top comment
        return the original submission
        """
        try:
            commentObj = reddit.get_submission(_force_utf8(dbPermalink)).comments[0]
            if commentObj.is_root:
                return _force_utf8(commentObj.submission.permalink)
            else:
                return _force_utf8(reddit.get_info(thing_id=commentObj.parent_id).permalink)
        except IndexError as err:
            print "parrent_comment error"
            return "It seems your original comment was deleted, unable to return parent comment."
        # Catch any URLs that are not reddit comments
        except Exception  as err:
            print "HTTPError/PRAW parent comment"
            return "Parent comment not required for this URL."

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
                # MySQl- permalink, message, origin date, reddit user
                flagDelete = self.new_reply(row[1],row[2], row[4], row[5])
                # removes row based on flagDelete
                if flagDelete:
                    cmd = "DELETE FROM message_date WHERE id = %s" 
                    self._queryDB.cursor.execute(cmd, [row[0]])
                    self._queryDB.connection.commit()
                    alreadyCommented.append(row[0])

        self._queryDB.connection.commit()
        self._queryDB.connection.close()

    def new_reply(self, permalink, message, origin_date, author):
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

        origin_date_text = ""
        # Before feature was implemented, there are no origin dates stored
        if origin_date is not None:
            origin_date_text =  ("\n\nYou requested this reminder on: " 
                                "[**" + _force_utf8(origin_date) + " UTC**](http://www.wolframalpha.com/input/?i="
                                + _force_utf8(origin_date) + " UTC To Local Time)")

        try:
            reddit.send_message(
                recipient=str(author), 
                subject='Hello, ' + _force_utf8(str(author)) + ' RemindMeBot Here!', 
                message=self._replyMessage.format(
                    message=_force_utf8(message),
                    original=_force_utf8(permalink),
                    parent= self.parent_comment(permalink),
                    origin_date_text = origin_date_text
                ))
            print "Did It"
            return True    
        except InvalidUser as err:
            print "InvalidUser", err
            return True
        except APIException as err:
            print "APIException", err
            return False
        except IndexError as err:
            print "IndexError", err
            return False
        except (HTTPError, ConnectionError, Timeout, timeout) as err:
            print "HTTPError", err
            time.sleep(10)
            return False
        except RateLimitExceeded as err:
            print "RateLimitExceeded", err
            time.sleep(10)
            return False
        except praw.errors.HTTPException as err:
            print"praw.errors.HTTPException"
            time.sleep(10)
            return False

"""
From Reddit's Code 
https://github.com/reddit/reddit/blob/master/r2/r2/lib/unicode.py
Brought to attention thanks to /u/13steinj
"""
def _force_unicode(text):

    if text == None:
        return u''

    if isinstance(text, unicode):
        return text

    try:
        text = unicode(text, 'utf-8')
    except UnicodeDecodeError:
        text = unicode(text, 'latin1')
    except TypeError:
        text = unicode(text)
    return text


def _force_utf8(text):
    return str(_force_unicode(text).encode('utf8'))


# =============================================================================
# MAIN
# =============================================================================

def main():
    while True:
        checkReply = Reply()
        checkReply.time_to_reply()
        checkReply.search_db()
        time.sleep(10)


# =============================================================================
# RUNNER
# =============================================================================
print "start"
if __name__ == '__main__':
    main()