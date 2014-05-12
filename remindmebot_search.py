#! /usr/bin/python -O
"""
    Sends a message to the Reddit user after a specified amount of time

"""
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

#Reads the config file
config = ConfigParser.ConfigParser()
config.read("remindmebot.cfg")


user_agent = ("RemindMeBot v1.0 by /u/RemindMeBotWrangler")
reddit = praw.Reddit(user_agent = user_agent)

#Reddit info
reddit_user = config.get("Reddit", "username")
reddit_pass = config.get("Reddit", "password")
reddit.login(reddit_user, reddit_pass)

#Database info, SQLite used
host = config.get("SQL", "host")
user = config.get("SQL", "user")
passwd = config.get("SQL", "passwd")
db = config.get("SQL", "db")
table = config.get("SQL", "table")

#commented already messaged are appended to avoid messaging again
commented = []


class Connect:
	"""
	DB connection class
	"""
	connection = None
	cursor = None

	def __init__(self):
		self.connection = MySQLdb.connect(host= host, user = user, passwd= passwd, db= db)
		self.cursor = self.connection.cursor()

	def execute(self, command):
		self.cursor.execute(command)

	def fetchall(self):
		return self.cursor.fetchall()

	def commit(self):
		self.connection.commit()

	def close(self):
		self.connection.close()

		
def parse_comment(comment):
	"""
	Parses through the comment looking for the message and time
	Calls save_to_db() to save the values
	"""
	if (comment not in commented):

		#defaults
		time_day_int = 1
		time_hour_int = 0
		message_input = '"Hello, I\'m here to remind you to see the parent comment!"'


		#check for hours
		#regex: 4.0 or 4 "hour | hours" ONLY
		time_hour = re.search("(?:\d+)?\.*(?:\d+ [hH][oO][uU][rR]([sS]|))", comment.body)
		if time_hour:
			#regex: ignores ".0" and non numbers
			time_hour = re.search("\d*", time_hour.group(0))
			time_hour_int = int(time_hour.group(0))


		#check for days
		#regex: 4.0 or 4 "day | days" ONLY
		time_day = re.search("(?:\d+)?\.*(?:\d+ [dD][aA][yY]([sS]|))", comment.body)
		if time_day:
			time_day = re.search("\d*", time_day.group(0))
			time_day_int = int(time_day.group(0))
		#cases where the user inputs hours but not days
		elif not time_day and time_hour_int > 0 :
			time_day_int = 0

		#no longer than 365 days
		hours_and_days = (time_day_int * 24) + time_hour_int
		if hours_and_days >= 8760:
			hours_and_days = 8760

		#check for comments
		#regex: Only text around quotes, avoids long messages
		message_user = re.search('(["].{0,10000}["])', comment.body)
		if message_user:
			message_input = message_user.group(0)


		save_to_db(comment, hours_and_days, message_input)

		
def save_to_db(comment, hours, message):
	"""
	Saves the permalink comment, the time, and the message to the database
	"""
	#connect to DB
	save_to_db = Connect()

	
	#setting up time and adding
	reply_date = datetime.now(timezone('UTC')) + timedelta(hours=hours)
	#9999/12/31 HH/MM/SS
	reply_date = format(reply_date, '%Y-%m-%d %H:%M:%S')

	save_to_db.execute("INSERT INTO %s VALUES ('%s', %s, '%s', '%s')" %(table, comment.permalink, message , reply_date, comment.author))
	save_to_db.commit()
	save_to_db.close()
	reply_to_original(comment, reply_date, message)

	
def reply_to_original(comment, reply_date, message):
	"""
	Messages the user letting them know when they will be messaged a second time
	"""
	try:
		comment_to_user = "I'll message you on {0} UTC to remind you of this post.\n\n_____\n ^(Hello, I'm RemindMeBot, I will PM you a message so you don't forget about the comment or thread later on!) [^(More Info Here)](http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)\n\n^(NOTE: Only days and hours. Max wait is one year. Default is a day.)" 
		comment.reply(comment_to_user.format(reply_date, message))
		commented.append(comment)
	except (HTTPError, ConnectionError, Timeout, timeout), e:
		#PM instead if the banned from the subreddit
		if str(e) == "403 Client Error: Forbidden":
			comment_to_user = "I'll message you on {0} UTC to remind you of this post.\n\n_____\n ^(Hello, I'm RemindMeBot, I will PM you a message so you don't forget about the comment or thread later on!) [^(More Info Here)](http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)\n\n^(NOTE: Only days and hours. Max wait is one year. Default is a day.)" 
			author = comment.author
			reddit.send_message(author, 'RemindMeBot Reminder!', comment_to_user.format(reply_date, message))
			commented.append(comment)
		print e
	except APIException, e:
		print e
	except RateLimitExceeded, e:
		print e
		time.sleep(10)
		
		

def main():
	#continuous loop
	while True:
		try:
			#grab all the new comments from /r/all
			comments = praw.helpers.comment_stream(reddit, 'all', limit=None, verbosity=0)
			comment_count = 0
			#loop through each comment
			for comment in comments:
				comment_count += 1
				if "RemindMe!" in comment.body:
					parse_comment(comment)
				#end loop after 1000
				if comment_count == 1000:
					break
			time.sleep(25)
		except Exception, e:
			print e     

main()


