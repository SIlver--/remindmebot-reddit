#!/usr/bin/env python2.7

# =============================================================================
# IMPORTS
# =============================================================================
import traceback
import praw
import OAuth2Util
import re
import MySQLdb
import ConfigParser
import time
import urllib
import requests
import parsedatetime.parsedatetime as pdt
from datetime import datetime, timedelta
from requests.exceptions import HTTPError, ConnectionError, Timeout
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded, Forbidden
from socket import timeout
from pytz import timezone
from threading import Thread

# =============================================================================
# GLOBALS
# =============================================================================

# Reads the config file
config = ConfigParser.ConfigParser()
config.read("remindmebot.cfg")

#Reddit info
reddit = praw.Reddit(user_agent= "RemindMes")
o = OAuth2Util.OAuth2Util(reddit, print_log = True)
o.refresh(force=True)

DB_USER = config.get("SQL", "user")
DB_PASS = config.get("SQL", "passwd")

# Time when program was started
START_TIME = time.time()
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

class Search(object):
    commented = [] # comments already replied to
    subId = [] # reddit threads already replied in
    endMessage = (
        "\n\n_____\n\n"
        "|[^([FAQs])](http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)"
        "|[^([Custom])](http://www.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message="
            "[LINK INSIDE SQUARE BRACKETS else default to FAQs]%0A%0A"
            "NOTE: Don't forget to add the time options after the command.%0A%0ARemindMe!)"
        "|[^([Your Reminders])](http://www.reddit.com/message/compose/?to=RemindMeBot&subject=List Of Reminders&message=MyReminders!)"
        "|[^([Feedback])](http://www.reddit.com/message/compose/?to=RemindMeBotWrangler&subject=Feedback)"
        "|[^([Code])](https://github.com/SIlver--/remindmebot-reddit)"
        "\n|-|-|-|-|-|"
        )

    def __init__(self, comment):
        self._addToDB = Connect()
        self.comment = comment # Reddit comment Object
        self._messageInput = '"Hello, I\'m here to remind you to see the parent comment!"'
        self._storeTime = None
        self._replyMessage = ""
        self._replyDate = None
        self._privateMessage = False

    def run(self, privateMessage=False):
        if privateMessage == True:
            self._privateMessage = True
        self.parse_comment()
        self.save_to_db()
        self.build_message()
        self.reply()
    def parse_comment(self):
        """
        Parse comment looking for the message and time
        """

        if self._privateMessage == True:
            permalinkTemp = re.search('\[(.*?)\]', self.comment.body)
            if permalinkTemp:
                self.comment.permalink = permalinkTemp.group()[1:-1]
                # Makes sure the URL is real
                try:
                    urllib.urlopen(self.comment.permalink)
                except IOError:
                    self.comment.permalink = "http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/"
            else:
                # Defaults when the user doesn't provide a link
                self.comment.permalink = "http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/"

        # remove RemindMe! or !RemindMe (case insenstive)
        match = re.search(r'(?i)(!*)RemindMe(!*)', self.comment.body)
        # and everything before
        tempString = self.comment.body[match.start():]

        # remove all format breaking characters IE: [ ] ( ) newline
        tempString = tempString.split("\n")[0]
        #tempString = re.sub('\([^)]*\)','', tempString)

        # Use message default if not found
        messageInputTemp = re.search('(["].{0,9000}["])', tempString)
        if messageInputTemp:
            self._messageInput = messageInputTemp.group()

        # Remove RemindMe!
        self._storeTime = re.sub('(["].{0,9000}["])', '', tempString)[9:]
    def save_to_db(self):
        """
        Saves the permalink comment, the time, and the message to the DB
        """

        cal = pdt.Calendar()
        if cal.parse(self._storeTime)[1] == 0:
            # default time
            holdTime = cal.parse("1 day", datetime.now(timezone('UTC')))
        else:
            holdTime = cal.parse(self._storeTime, datetime.now(timezone('UTC')))
        # Converting time
        #9999/12/31 HH/MM/SS
        self._replyDate = time.strftime('%Y-%m-%d %H:%M:%S', holdTime[0])
        cmd = "INSERT INTO message_date (permalink, message, new_date, userID) VALUES (%s, %s, %s, %s)"
        self._addToDB.cursor.execute(cmd, (
                        self.comment.permalink.encode('utf-8'), 
                        self._messageInput.encode('utf-8'), 
                        self._replyDate, 
                        self.comment.author))
        self._addToDB.connection.commit()
        self._addToDB.connection.close()
        # Info is added to DB, user won't be bothered a second time
        self.commented.append(self.comment.id)

    def build_message(self):
        """
        Buildng message for user
        """
        permalink = self.comment.permalink
        self._replyMessage =(
            "Messaging you on [**{0} UTC**](http://www.wolframalpha.com/input/?i={0} UTC To Local Time)"
            " to remind you of [**this.**]({commentPermalink})"
            "{remindMeMessage}")

        try:
            self.sub = reddit.get_submission(self.comment.permalink)
        except Exception as err:
            print "link had http"
        if self._privateMessage == False and self.sub.id not in self.subId:
            remindMeMessage = (
                "\n\n[**CLICK THIS LINK**](http://www.reddit.com/message/compose/?to=RemindMeBot&subject=Reminder&message="
                "[{permalink}]%0A%0ARemindMe! {time}) to send a PM to also be reminded and to reduce spam."
                "\n\n^(Parent commenter can ) [^(delete this message to hide from others.)]"
                "(http://www.reddit.com/message/compose/?to=RemindMeBot&subject=Delete Comment&message=Delete! ____id____)").format(
                    permalink=permalink,
                    time=self._storeTime.replace('\n', '')
                )
        else:
            remindMeMessage = ""

        self._replyMessage = self._replyMessage.format(
                self._replyDate,
                remindMeMessage=remindMeMessage,
                commentPermalink=permalink)
        self._replyMessage += Search.endMessage

    def reply(self):
        """
        Messages the user letting as a confirmation
        """

        author = self.comment.author
        def send_message():
            reddit.send_message(author, 'Hello, ' + str(author) + ' RemindMeBot Confirmation Sent', self._replyMessage)

        try:
            if self._privateMessage == False:
                # First message will be a reply in a thread
                # afterwards are PM in the same thread
                if (self.sub.id not in self.subId):
                    newcomment = self.comment.reply(self._replyMessage)
                    self.subId.append(self.sub.id)
                    # grabbing comment just made
                    reddit.get_info( 
                            thing_id='t1_'+str(newcomment.id)
                            # edit comment with self ID so it can be deleted
                        ).edit(self._replyMessage.replace('____id____', str(newcomment.id))) 
                else:
                    send_message()
            else:
                print str(author)
                send_message()
        except RateLimitExceeded as err:
            print err
            # PM when I message too much
            send_message()
            time.sleep(10)
        except Forbidden as err:
            send_message()
        except APIException as err: # Catch any less specific API errors
            print err
        #else:
            #print self._replyMessage

def grab_list_of_reminders(username):
    """
    Grabs all the reminders of the user
    """
    database = Connect()
    query = "SELECT permalink, message, new_date, id FROM message_date WHERE userid = %s ORDER BY new_date"
    database.cursor.execute(query, [username])
    data = database.cursor.fetchall()
    table = ("|Permalink|Message|Date|Remove|\n"
                "|-|-|-|:-:|")
    for row in data:
        date = str(row[2])
        table += (
            "\n|" + row[0] + "|" +   row[1] + "|" + 
            "[" + date  +"](http://www.wolframalpha.com/input/?i=" + str(row[2]) + ")|"
            "[[X]](https://www.reddit.com/message/compose/?to=RemindMeBot&subject=Remove&message=Remove!%20"+ str(row[3]) + ")|"
            )
    if len(data) == 0: 
        table = "Looks like you have no reminders. Click the [Custom] button below to make one!"
    elif len(table) > 9000:
        table = "Sorry the comment was too long to display. Message /u/RemindMeBotWrangler as this was his lazy error catching."
    table += Search.endMessage
    return table

def remove_reminder(username, idnum):
    """
    Deletes the reminder from the database
    """
    database = Connect()
    query = "SELECT userid FROM message_date WHERE id = %s"
    database.cursor.execute(query, [idnum])
    data = database.cursor.fetchall()
    deleteFlag = False
    for row in data:
        userid = str(row[0])
        if userid == username:
            cmd = "DELETE FROM message_date WHERE id = %s" 
            database.cursor.execute(cmd, [idnum])
            database.connection.commit()
            deleteFlag = True

    return deleteFlag

def read_pm():
    try:
        for message in reddit.get_unread(unset_has_mail=True, update_user=True):
            prawobject = isinstance(message, praw.objects.Message)
            if (("remindme!" in message.body.lower() or "!remindme" in message.body.lower()) and prawobject):
                redditPM = Search(message)
                redditPM.run(privateMessage=True)
                message.mark_as_read()
            elif (("delete!" in message.body.lower() or "!delete" in message.body.lower()) and prawobject):  
                givenid = re.findall(r'delete!\s(.*?)$', message.body.lower())[0]
                givenid = 't1_'+givenid
                comment = reddit.get_info(thing_id=givenid)
                try:
                    parentcomment = reddit.get_info(thing_id=comment.parent_id)
                    if message.author.name == parentcomment.author.name:
                        comment.delete()
                        submissionId = reddit.get_submission(comment.permalink).id
                        Search.subId.remove(submissionId)
                except ValueError as err:
                    # comment wasn't inside the list
                    pass
                except AttributeError as err:
                    # comment might be deleted already
                    pass
                message.mark_as_read()
            elif (("myreminders!" in message.body.lower() or "!myreminders" in message.body.lower()) and prawobject):
                listOfReminders = grab_list_of_reminders(message.author.name)
                message.reply(listOfReminders)
                message.mark_as_read()
            elif (("remove!" in message.body.lower() or "!remove" in message.body.lower()) and prawobject):
                givenid = re.findall(r'remove!\s(.*?)$', message.body.lower())[0]
                deletedFlag = remove_reminder(message.author.name, givenid)
                listOfReminders = grab_list_of_reminders(message.author.name)
                # This means the user did own that reminder
                if deletedFlag == True:
                    message.reply("Reminder deleted. Your current Reminders:\n\n" + listOfReminders)
                else:
                    message.reply("Try again with the current IDs that belong to you below. Your current Reminders:\n\n" + listOfReminders)
                message.mark_as_read()
        o.refresh()
    except Exception as err:
        print traceback.format_exc()

def check_comment(comment):
    redditCall = Search(comment)
    if (("remindme!" in comment.body.lower() or
        "!remindme" in comment.body.lower()) and 
        redditCall.comment.id not in redditCall.commented and
        'RemindMeBot' != str(comment.author) and
        START_TIME < redditCall.comment.created_utc):
            print "in"
            t = Thread(target=redditCall.run())
            t.start()

# =============================================================================
# MAIN
# =============================================================================

def main():
    print "start"
    read_pm()

    while True:
        try:
            # grab the request
            request = requests.get('https://api.pushshift.io/reddit/search?q=%22RemindMe%22&limit=100')
            json = request.json()
            comments =  json["data"]        
            for rawcomment in comments:
                # object constructor requires empty attribute
                rawcomment['_replies'] = ''
                comment = praw.objects.Comment(reddit, rawcomment)
                check_comment(comment)
            read_pm()
            print "----"
            time.sleep(30)
        except Exception as err:
            print traceback.format_exc()           
            time.sleep(30)
        """
        Will add later if problem with api.pushshift
        hence why check_comment is a function
        try:
            for comment in praw.helpers.comment_stream(reddit, 'all', limit = 1, verbosity = 0):
                check_comment(comment)
        except Exception as err:
           print err
        """
# =============================================================================
# RUNNER
# =============================================================================

if __name__ == '__main__':
    main()
