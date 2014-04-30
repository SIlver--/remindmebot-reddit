#! /usr/bin/python -O
import praw
import re
import MySQLdb
from datetime import datetime, timedelta
import time
import ConfigParser

config = ConfigParser.ConfigParser()
config.read("remindmebot.cfg")

print "start"
user_agent = ("RemindMeBot v1.0 by /u/RemindMeBotWrangler")
reddit = praw.Reddit(user_agent = user_agent)
reddit_user = config.get("Reddit", "username")
reddit_pass = config.get("Reddit", "password")
reddit.login(reddit_user, reddit_pass)

commented = []
def parse_comment(comment):
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
	#connection to DB
	host = config.get("SQL", "host")
	user = config.get("SQL", "user")
	password = config.get("SQL", "passwd")
	db = config.get("SQL", "db")
	
	connection = MySQLdb.connect(host= host,
						user = user,
						passwd= password,
						db= db)
						
	query = connection.cursor()
	
	#setting up time and adding
	reply_date = datetime.utcnow() + timedelta(days=day) + timedelta(hours=hour)
	#9999/12/31 HH/MM/SS
	reply_date = format(reply_date, '%Y-%m-%d %H:%M:%S')
	
	 
	command = "INSERT INTO messages_table VALUES(%s, %s, %s)"
	query.execute(command, (comment.permalink , message , reply_date))
	#connection.commit()
	reply_to_original(comment, reply_date, message)
	
	
def reply_to_original(comment, reply_date, message):
	comment_to_user = "Hello, I'll message you on {0} UTC to remind you about this post with the message {1}"
	print comment_to_user.format(reply_date, message)
	#comment.reply(comment_to_user.format(reply_date, message))

for comment in reddit.get_comments("all", limit=None):
    if "RemindMeBot!" in comment.body:
		parse_comment(comment)


print "Done"
