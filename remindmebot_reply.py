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
	query_db.execute("SELECT * FROM %s WHERE new_date < '%s'" %(table, current_time))

	data = query_db.fetchall()
	#row[0] is the permalink to reply to
	#flag states: 0 is different error, 
	#1 means comment was succesful, 
	#2 means comment was deleted
	already_commented = []
	for row in data:
		#checks to make sure permalink hasn't been commented already
		if row[0] not in already_commented:
			flag = 0
			flag = new_reply(row[0],row[1])
			#removes row based on flag
			if flag == 1 or flag == 2:
				query_db.execute("DELETE FROM %s WHERE permalink = '%s'" %(table, row[0]))
				query_db.commit()
			already_commented.append(row[0])
	
	query_db.commit()
	query_db.close()

def new_reply(permalink, message):
	"""
	Replies a second time to the user after a set amount of time
	"""
	try:
		comment_to_user = "RemindMeBot here!\n\n**{0}**\n\n {1} \n\n_____\n ^(Hello, I'm RemindMeBot, I will PM you a message so you don't forget about the comment or thread later on!) [^(More Info Here)](http://www.reddit.com/r/RemindMeBot/comments/24duzp/remindmebot_info/)\n\n^(**NOTE: Only days and hours work for now.**)"
		s = reddit.get_submission(permalink)
		comment = s.comments[0]
		author = comment.author
		reddit.send_message(author, 'RemindMeBot Reminder!', comment_to_user.format(message, permalink))
		return 1
	except APIException, e:
		print e
		if str(e) == "(DELETED_COMMENT) `that comment has been deleted` on field `parent`":
			return 2
		return 2
	except IndexError, e:
		print e
		return 2
	except (HTTPError, ConnectionError, Timeout, timeout), e:
		print e
		pass
	except RateLimitExceeded, e:
		print e
		time.sleep(10)
		pass

		
def main():
	while True:
		try:
			time_to_reply()
			time.sleep(60)
		except Exception, e:
			print e	
main()