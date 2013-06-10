 # -*- coding: utf-8 -*-
from flask import Flask, request, render_template, Response, redirect, url_for,flash 
from pymongo import MongoClient
from bson.objectid import ObjectId
import json
import random
from flask.ext.login import (LoginManager, current_user, login_required,
                            login_user, logout_user, UserMixin, AnonymousUser,
                            confirm_login, fresh_login_required,login_url)
from flask.ext.mail import Message, Mail
import hashlib
import requests
import urllib
import cgi
import ast
import base64
import codecs
import urllib2
import datetime
import re
from twilio.rest import TwilioRestClient
import thread
import time
from datetime import datetime,timedelta


app = Flask(__name__)
app.config.from_envvar('CONFIG')
app.debug=app.config['DEBUG']


mail=Mail(app)

@app.route('/')
def front():
	
	return render_template('front.html')

def poller():
	#note current time, year,month,day,hour,minute - calculate using offset value from config
	#go through list and compare timestamp using offset value based on timezone(supported - IST,GMT)
	#create separate list for acceptable tasks
	#send to separate function to implement tasks - mark as done
	#write any errors to log
	#sleep for 1 minute
	while True:
		system_time=datetime.now()+timedelta(hours=app.config['SYSTEM_OFFSET_HOURS'],minutes=app.config['SYSTEM_OFFSET_MINUTES'])
		app.logger.debug(system_time.minute)
		client=MongoClient()
		db=client[app.config['DATABASE']]
		tasks=db.reminders.find()
		acceptable=[]
		for task in tasks:
			if task['state']=='active' and isEqual(task['time'],system_time,task['timezone']):
				acceptable.append(task)
		app.logger.debug(str(acceptable))
		for task in acceptable:
			app.logger.debug(task['message'])
			execute(task)
		app.logger.debug('done with the loop')
		time.sleep(60)


def execute(task):
	result=requests.get(app.config['HOST']+'/perform_task?id='+str(task['_id']))
	client=MongoClient()
	db=client[app.config['DATABASE']]
	if result.status_code!=200:
		app.logger.debug('Problem executing task with id:'+str(task['_id']))

		


def isEqual(task_time,system_time,task_timezone):
	components=['year','month','day','hour','minute']
	timezone={'IST':0,'GMT':1}
	offset_hour={0:-5,1:0}
	offset_minutes={0:-30,1:0}
	app.logger.debug('task_time:'+str(task_time))
	task_time=task_time+timedelta(hours=offset_hour[timezone[task_timezone]],minutes=offset_minutes[timezone[task_timezone]])
	app.logger.debug('Comparing timestamps')
	app.logger.debug('task_time:'+str(task_time))
	app.logger.debug('system_time'+str(system_time))
	if task_time.year!=system_time.year:
		return False
	if task_time.month!=system_time.month:
		return False
	if task_time.day!=system_time.day:
		return False
	if task_time.hour!=system_time.hour:
		return False
	if task_time.minute!=system_time.minute:
		return False
	return True


@app.route('/task_list',methods=['GET','POST'])
def task_list():
	def sorter(task):
		return task['state']+str(task['time'])
	client=MongoClient()
	db=client[app.config['DATABASE']]
	if request.method=='POST':
		data={}
		for name,value in dict(request.form).iteritems():
			data[name]=value[0].strip()
		app.logger.debug(str(data))

		task={}
		date=data['datepicker'].split("/")
		year=int(date[2])
		month=int(date[0])
		day=int(date[1])

		time_components=data['time'].split(":")
		hours=0
		if time_components[2]=='AM' or time_components[0]=='12':
			hours=int(time_components[0])
		else:
			hours=int(time_components[0])+12
		minutes=int(time_components[1])
		task['message']=data['message']
		task['type']='one-time'
		task['time']=datetime(year,month,day,hours,minutes)
		task['state']='active'
		task['timezone']=data['timezone']
		task['method']=data['method'].lower()
		task['details']=data['details'].lower()
		task['creator']='admin'
		db.reminders.save(task)
	tasks=db.reminders.find()
	output=[]
	for task in tasks:
		output.append(task)
	output.sort(key=sorter)
	return render_template('list.html',tasks=output)

@app.route('/delete_task')
def delete_task():
	_id=request.args.get('id')
	client=MongoClient()
	db=client[app.config['DATABASE']]
	app.logger.debug(_id)
	db.reminders.remove({'_id':ObjectId(_id)})
	return redirect(url_for('task_list'))
	



@app.route('/perform_task')
def perform_task():
	_id=request.args.get('id')
	client=MongoClient()
	db=client[app.config['DATABASE']]
	app.logger.debug(_id)
	task=db.reminders.find({'_id':ObjectId(_id)})
	task=task.next()
	if task['method']=='sms' and task['state']=='active':
		account_sid = "ACbb51060d0fb44e38bccbde905f0781ae"
		auth_token = "7c4e788704bc432a8c7ed2ae72404e12"
		client = TwilioRestClient(account_sid, auth_token)
		message = client.sms.messages.create(body=task['message'],
	    		to="+"+task['details'],
				from_="+14157499397")

		app.logger.debug(message.sid)
		task['state']='done'
		db.reminders.save(task)
		return render_template('task_completion.html')	
	if task['method']=='email' and task['state']=='active':
		msg = Message('Reminder', sender = app.config['MAIL_SENDER'], recipients =[task['details']])

		msg.body = task['message']
		mail.send(msg)
		app.logger.debug('Sending reminder email to:'+task['details'])
		task['state']='done'
		db.reminders.save(task)
		return render_template('task_completion.html')
	else:
		return render_template('task_completion.html')
	
thread.start_new_thread(poller,())
if app.debug is None or app.debug is False or app.debug is True:   
	    import logging
	    from logging.handlers import RotatingFileHandler
	    file_handler = RotatingFileHandler('/home/uday/code/reminder_service/logs/application.log', maxBytes=1024 * 1024 * 100, backupCount=20)
	    file_handler.setLevel(logging.DEBUG)
	    formatter = logging.Formatter("%(asctime)s - %(funcName)s - %(levelname)s - %(message)s")
	    file_handler.setFormatter(formatter)
	    app.logger.addHandler(file_handler)
	    app.logger.error(str(app.config))

if __name__=='__main__':
	app.run()
	