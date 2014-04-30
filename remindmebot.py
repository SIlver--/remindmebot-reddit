#! /usr/bin/python -O
"""
    Sends a message to the Reddit user after a specified amount of time
    Copyright (C) 2014 Giuseppe Ranieri

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
import praw
import re
import sqlite3
import ConfigParser
import time
from datetime import datetime, timedelta
from praw.errors import ExceptionList, APIException, InvalidCaptcha, InvalidUser, RateLimitExceeded
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
		self.connection = sqlite3.connect(db)
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
			#no longer than a 24 hour day
			if time_hour_int >= 24:
				time_hour_int = 24



		#check for days
		#regex: 4.0 or 4 "day | days" ONLY
		time_day = re.search("(?:\d+)?\.*(?:\d+ [dD][aA][yY]([sS]|))", comment.body)
		if time_day:
			time_day = re.search("\d*", time_day.group(0))
			time_day_int = int(time_day.group(0))
			#no longer than a seven day week
			if time_day_int >= 7.0:
				time_day_int = 7
				time_hour_int = 0
		#cases where the user inputs hours but not days
		elif not time_day and time_hour_int > 0 :
			time_day_int = 0



		#check for comments
		#regex: Only text around quotes, avoids long messages
		message_user = re.search('(["].{0,10000}["])', comment.body)
		if message_user:
			message_input = message_user.group(0)


		save_to_db(comment, time_day_int, time_hour_int, message_input)

		
def save_to_db(comment, day, hour, message):
	"""
	Saves the permalink comment, the time, and the message to the database
	"""
	#connect to DB
	save_to_db = Connect()

	
	#setting up time and adding
	reply_date = datetime.now(timezone('UTC')) + timedelta(days=day) + timedelta(hours=hour)
	#9999/12/31 HH/MM/SS
	reply_date = format(reply_date, '%Y-%m-%d %H:%M:%S')

	save_to_db.execute("INSERT INTO '%s' VALUES ('%s', %s, '%s')" %(table, comment.permalink , message , reply_date))
	save_to_db.commit()
	save_to_db.close()
	reply_to_original(comment, reply_date, message)

	
def reply_to_original(comment, reply_date, message):
	"""
	Messages the user letting them know when they will be messaged a second time
	"""
	try:
		comment_to_user = "I'll message you on **{0} UTC** to remind you of this post with the message\n\n**{1}**\n\n_____\n ^(Hello, I'm RemindMeBot, I send you a message if you ask so you don't forget about the parent comment or thread later on!)[^(More Info Here)](http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)" 
		comment.reply(comment_to_user.format(reply_date, message))
		commented.append(comment)
	except (HTTPError, ConnectionError, Timeout, timeout) as e:
		print e
		pass
	except APIException as e:
		print e
		pass
	except RateLimitExceeded as e:
		print e
		time.sleep(10)
		pass
		
		
def time_to_reply():
	"""
	Checks to see through SQL if new_date is < current time
	Once done will send a message to the user
	"""
	#connection to DB
	query_db = Connect()
	
	#get current time to compare
	current_time = datetime.now(timezone('UTC'))
	current_time = format(current_time, '%Y-%m-%d %H:%M:%S')
	query_db.execute("SELECT * FROM '%s' WHERE new_date < '%s'" %(table, current_time))

	data = query_db.fetchall()
	#row[0] is the permalink to reply to
	#flag states: 0 is different error, 
	#1 means comment was succesful, 
	#2 means comment was deleted

	for row in data:
		flag = 0
		flag = new_reply(row[0],row[1])
		#removes row based on flag
		if flag == 1 or flag == 2:
			query_db.execute("DELETE FROM '%s' WHERE permalink = '%s'" %(table, row[0]))

	query_db.commit()
	query_db.close()
	

def new_reply(permalink, message):
	"""
	Replies a second time to the user after a set amount of time
	"""
	try:
		comment_to_user = "RemindMeBot here!\n\n**{0}**\n\n_____\n ^(Hello, I'm RemindMeBot, I send you a message if you ask so you don't forget about the parent comment or thread later on!)[^(More Info Here)](http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)"
		s = reddit.get_submission(permalink)
		comment = s.comments[0]
		comment.reply(comment_to_user.format(message))
		return 1
	except APIException as e:
		print e
		if str(e) == "(DELETED_COMMENT) `that comment has been deleted` on field `parent`":
			return 2
	except IndexError:
		print e
		return 2
	except (HTTPError, ConnectionError, Timeout, timeout) as e:
		print e
		pass
	except RateLimitExceeded as e:
		print e
		time.sleep(10)
		pass
		
		
def main():
	while True:
		try:
			print "Start loop"
			#looks to be called for
			for comment in reddit.get_comments("all", limit=None):
				if "RemindMe!" in comment.body:
					parse_comment(comment)
			print "End Loop"
			time_to_reply()
		except Exception, e:
			print e
			pass



main()


