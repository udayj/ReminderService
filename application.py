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
import multiprocessing
from werkzeug import secure_filename
import os

SECRET_KEY='SECRET'


SALT='123456789passwordsalt'

app = Flask(__name__)
app.config.from_envvar('CONFIG')
app.debug=app.config['DEBUG']

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = u"Please log in to access this page."

mail=Mail(app)
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'xls', 'doc', 'xlsx','docx'])
ACCOUNT_SID=app.config['ACCOUNT_SID']
AUTH_TOKEN=app.config['AUTH_TOKEN']

class User(UserMixin):
    def __init__(self, name, _id, password,email,activation_hash=None,active=True):
        self.name = name
        self.id = _id
        self.active = active
        self.password=password
        self.email=email
        self.activation_hash=activation_hash
        
    def is_active(self):
        return self.active


@app.route('/')
def front():
	
	return render_template('front.html',active='front')

@app.route('/new_task')
@login_required
def new_task():
	
	return render_template('new_task.html',active='new_task')

@app.route('/new_user_task')
def new_user_task():
	
	return render_template('new_user_task.html',active='new_user_task')

@app.route('/admin')
def admin():
	def sorter(task):
		return task['state']+str(task['time'])

	password=request.args.get('password')
	if password==app.config['ADMIN_PASSWORD']:

		client=MongoClient()
		db=client[app.config['DATABASE']]
		
		tasks=db.reminders.find()
		output=[]
		for task in tasks:
			output.append(task)
		output.sort(key=sorter)
		return render_template('list.html',tasks=output)
	else:
		return redirect(url_for('front'))		

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

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

def validComponents(task):
	keys=['message','time','type','method','details','datepicker']
	for key in keys:
		if key not in task:
			return False

	return True

@login_manager.user_loader
def load_user(_id):
	client=MongoClient()
	db=client[app.config['DATABASE']]
	user=db.users.find({'_id':ObjectId(_id)})
	try:
		user=user.next()
		
		ret_user=User(name=user['name'],email=user['email'],password="",active=user['active'],_id=str(user['_id']))
		return ret_user
	except StopIteration:
		return None

login_manager.setup_app(app)



@app.route('/activate')
def activate():
	activation_hash=request.args.get('hash')
	if not activation_hash:
		return render_template('activate_error.html')
	client=MongoClient()
	db=client[app.config['DATABASE']]
	user=db.users.find({'activation_hash':activation_hash})
	try:
		user=user.next()
		user['active']=True
		db.users.save(user)
		ret_user=User(name=user['name'],email=user['email'],password="",active=user['active'],_id=str(user['_id']))
		login_user(ret_user)
		return render_template('activate.html')
	except StopIteration:
		return render_template('activate_error.html')


@app.route('/signup',methods=['GET','POST'])
def signup():
	def send_mail(data,files):
		result=requests.post(
        "https://api.mailgun.net/v2/remindica.com/messages",
        auth=("api", "key-1b9979216cd5d2f065997d3d53852cd6"),
        files=files,
        data=data)

	if request.method=='GET':
		return render_template('signup.html',active='signup')
	else:
		
		data={}
		for name,value in dict(request.form).iteritems():
			data[name]=value[0]
		username=None
		if 'username' in data:
			username=data['username']
		client=MongoClient()
		db=client[app.config['DATABASE']]
		salt='reminderserviceactivateusingtoken'
		activation_hash=hashlib.sha512(salt+data['email']).hexdigest()[10:30]
		
		exist_user=db.users.find({'email':data['email']})
		try:
			exist_user.next()
			return render_template('signup.html',active='signup',signup_error='Email already exists',username=username,email=data['email'])
		except StopIteration:
			pass

		_id=db.users.save({'name':username,
					   'email':data['email'],
					   'password':hashlib.sha512(SALT+data['password']).hexdigest(),
					   'activation_hash':activation_hash,
					   'active':False})
		#user=User(name=username,email=data['email'],password=data['password'],active=False,id=str(_id))
		msg = Message('Welcome to Reminder Service', sender = app.config['MAIL_SENDER'], recipients = [data['email']])
		
		
		msg.body = 'Click this link to activate your account '+app.config['HOST']+'/activate?hash='+activation_hash
		app.logger.debug('Sending activation email to:'+data['email'])
		html_content=render_template("activate_email.html",name=username, url=app.config['HOST']+'/activate?hash='+activation_hash)
		data={"from": "Remindica <admin@remindica.com>",
              "to": [data['email']],
              "subject": 'Welcome to Remindica',
              "text": 'Click this link to activate your account '+app.config['HOST']+'/activate?hash='+activation_hash,
              "html":html_content}
		#app.logger.debug(activation_hash)
		#app.logger.debug(str(app.extensions['mail'].server))
		try:
			p=multiprocessing.Process(target=send_mail,args=(data,None,))
			p.start()
		except Exception:
			db.users.remove({'_id':_id})
			return render_template('signup.html',signup_error='Problem sending email. Account not created. Try again later.',
									username=username,email=data['email'])
		return render_template('checkmail.html')

@app.route('/faq')
def faq():
	return render_template('faq.html',active='faq')

@app.route('/change-password',methods=['GET','POST'])
def change_password():
	def send_mail(data,files):
		result=requests.post(
        "https://api.mailgun.net/v2/remindica.com/messages",
        auth=("api", "key-1b9979216cd5d2f065997d3d53852cd6"),
        files=files,
        data=data)
	if request.method=='GET':
		forgot_password_hash=request.args.get('hash')
		client=MongoClient()
		db=client[app.config['DATABASE']]
		user=db.users.find({'forgot_password_hash':forgot_password_hash})
		try:
			user=user.next()
			if user['forgot_password']==True:
				return render_template('change-password.html',email=user['email'])
			else:
				return render_template('change-password.html',
					error="Password already changed using this link - please request another password reset",email=user['email'])
		except StopIteration:
			return render_template('change-password.html',error='Problem with this link - please contact support@remindica.com')

	else:
		data={}
		for name,value in dict(request.form).iteritems():
			data[name]=value[0]
		client=MongoClient()
		db=client[app.config['DATABASE']]
		
		email=None
		if 'email' in data and 'password' in data:
			email=data['email']
			password=data['password']
		else:
			app.logger.debug('Change password form submitted without email/password')
			return render_template('change-password.html',error="Please re-enter details to reset password")

		user=db.users.find({'email':email})
		
		try:
			user=user.next()
			if user['forgot_password']!=True:
				return render_template('change-password.html',error='Please request another password reset link')	
			user['password']=hashlib.sha512(SALT+password).hexdigest()
			user['forgot_password']=False
			db.users.save(user)
			return render_template('change-password.html',success='Password changed successfully')
		except StopIteration:
			return render_template('change-password.html',error='Please request another password reset link')


@app.route('/forgot-password',methods=['GET','POST'])
def forgot_password():
	def send_mail(data,files):
		result=requests.post(
        "https://api.mailgun.net/v2/remindica.com/messages",
        auth=("api", "key-1b9979216cd5d2f065997d3d53852cd6"),
        files=files,
        data=data)
	if request.method=='GET':
		return render_template('forgot-password.html')
	else:
		data={}
		for name,value in dict(request.form).iteritems():
			data[name]=value[0]
		client=MongoClient()
		db=client[app.config['DATABASE']]
		salt='remindicaforgotpassword'
		email=None
		if 'email' in data:
			email=data['email']
		else:
			app.logger.debug('Forgot password form submitted without email')
			return render_template('forgot-password.html',error="Please enter correct email id to reset password")	

		user=db.users.find({'email':email})
		forgot_password_hash=hashlib.sha512(salt+data['email']).hexdigest()[10:30]
		try:
			user=user.next()
			user['forgot_password_hash']=forgot_password_hash
			user['forgot_password']=True
			db.users.save(user)
			data={"from": "Remindica <admin@remindica.com>",
	              "to": email,
	              "subject": 'Reset your password',
	              "text": 'Click this link to change your password '+app.config['HOST']+'/change-password?hash='+forgot_password_hash,
	              "html":'Click this link to change your password '+app.config['HOST']+'/change-password?hash='+forgot_password_hash}
			try:
				p=multiprocessing.Process(target=send_mail,args=(data,None,))
				p.start()
				
				return render_template('forgot-password.html',success="Password reset instructions sent to your email id")
			except:
				return render_template('forgot-password.html',error="Could not send password reset instructions - please try again")
		except StopIteration:
			return render_template('forgot-password.html',error="Please enter correct email id to reset password")			



@app.route('/login',methods=['GET','POST'])
def login():
	if request.method=='GET':
		return render_template('login.html',active='login')
	data={}
	for name,value in dict(request.form).iteritems():
		data[name]=value[0]
	username=None
	if 'username' in data and 'password' in data:
		username=data['username']
		password=data['password']
	else:
		app.logger.debug('Login Form submitted without fields')
		return render_template('login.html',active='login')
	client=MongoClient()
	db=client[app.config['DATABASE']]
	password=hashlib.sha512(SALT+password).hexdigest()
	user=db.users.find({'email':username,'password':password})
	try:
		user=user.next()
		ret_user=User(name=user['name'],email=user['email'],password="",active=user['active'],_id=str(user['_id']))
		if login_user(ret_user):
			flash('Logged in!')
			return redirect(url_for('task_list'))
		else:
			return render_template('login.html',error='Cannot login. Account still inactive',active='login')
	except StopIteration:
		return render_template('login.html',error='Cannot login. Wrong credentials',
								active='login')
@app.route("/logout")
@login_required
def logout():
	logout_user()
	flash("Logged out!")
	return redirect(url_for('front'))

@app.route("/task")
@login_required
def task():
	def sorter(task):
		if('time_performed' in task):
			epoch=datetime.utcfromtimestamp(0)
			delta=task['time_performed']-epoch
			return 10000000000000-delta.total_seconds()
		else:
			return 1
	suffix=['st','nd','rd','th','th','th','th','th','th','th','th','th','th','th','th','th','th','th','th',
			'th','st','nd','rd','th','th','th','th','th','th','th','st']
	_id=request.args.get('id')
	instant=request.args.get('instant')
	client=MongoClient()
	db=client[app.config['DATABASE']]

	if instant=='true':
		task=db.reminders.find({'_id':ObjectId(_id)})
		task=task.next()
		if str(task['creator_id'])==current_user.id:
			result=task_worker(_id,True)
			if result!=1:
				app.logger.error('ERROR in performing task: '+_id)

	
	try:
		task=db.reminders.find({'_id':ObjectId(_id)})
		task=task.next()
		if task['type']=='one-time':
			task['timing']='Once at '+task['time'].strftime('%b %d, %Y %I:%M %p')
		if task['type']=='daily':
			task['timing']='Daily at '+task['time'].strftime('%I:%M %p')
		if task['type']=='weekly':
			task['timing']='Weekly on '+task['day_of_week'].title()+' at '+task['time'].strftime('%I:%M %p')
		if task['type']=='monthly':
			task['timing']='Monthly on - '+str(task['day_of_month'])+suffix[task['day_of_month']-1] +' day at ' +\
								task['time'].strftime('%I:%M %p')

		app.logger.debug('inside task function')
		display_sub_tasks=[]
		intermediate_sub_tasks=[]
		for sub_task in db.status.find({'task_id':ObjectId(_id)}):
			
			if(sub_task==None):
				break

			intermediate_sub_tasks.append(sub_task)
		app.logger.debug('working till here')
		intermediate_sub_tasks=sorted(intermediate_sub_tasks,key=sorter)
		for sub_task in intermediate_sub_tasks:
			
			if(sub_task==None):
				break

			display_sub_tasks.append({'time':sub_task['time_performed'].strftime('%b %d, %Y %I:%M %p'),'status':sub_task['status'],
				'method':task['method']})

		app.logger.debug('inside task function - after aggregating tasks')
		
		return render_template('task.html',task=task,sub_tasks=display_sub_tasks)
	except:
		return render_template('task_error.html')



@app.route('/task_list',methods=['GET','POST'])
@login_required
def task_list():
	suffix=['st','nd','rd','th','th','th','th','th','th','th','th','th','th','th','th','th','th','th','th',
			'th','st','nd','rd','th','th','th','th','th','th','th','st']
	country_code='+91'
	timezone='IST'
	def sorter(task):
		if('creation_time' in task):
			epoch=datetime.utcfromtimestamp(0)
			delta=task['creation_time']-epoch
			return task['state']+str(1000000000000-delta.total_seconds())+task['type']+str(task['time'])
		else:
			return task['state']+task['type']+str(task['time'])
	client=MongoClient()
	db=client[app.config['DATABASE']]
	_id=current_user.id
	tasks=db.reminders.find({'creator_id':ObjectId(_id)})
	output=[]
	for task in tasks:
		task['time_output']=''
		if task['type']=='one-time':
			task['time_output']='Once at '+task['time'].strftime('%b %d, %Y %I:%M %p')
		elif task['type']=='daily':
			task['time_output']='Daily at '+task['time'].strftime('%I:%M %p')
		elif task['type']=='weekly':
			task['time_output']='Weekly on '+task['day_of_week'].title()+' at '+task['time'].strftime('%I:%M %p')
		else:

			task['time_output']='Monthly on - '+str(task['day_of_month'])+suffix[task['day_of_month']-1] +' day at ' +\
								task['time'].strftime('%I:%M %p')


		output.append(task)
	
	if request.method=='POST':
		data={}
		for name,value in dict(request.form).iteritems():
			data[name]=value[0].strip()
		app.logger.debug(str(data))
		

		task={}
		if not validComponents(data):
			app.logger.error('Problem with task form data. Cannot submit task')
			output.sort(key=sorter)
			return render_template('list.html',tasks=output,error='Problem submitting task. Try again later')
		try:
			year=2013
			month=7
			day=7
			try:
				date=data['datepicker'].split("/")
				year=int(date[2])
				month=int(date[0])
				day=int(date[1])
			except:
				pass



			time_components=data['time'].split(":")
			hours=0
			hours=int(time_components[0])

			"""if time_components[2]=='AM' or time_components[0]=='12':
				hours=int(time_components[0])
			else:
				hours=int(time_components[0])+12"""


			minutes=int(time_components[1])
			task['message']=data['message']
			if('subject' in data and data['method'].lower()=='email'):
				task['subject']=data['subject']
			

			app.logger.debug('reminder message:'+task['message'])
			task['type']=data['type'].lower()
			task['time']=datetime(year,month,day,hours,minutes)
			task['state']='active'
			task['timezone']=timezone
			task['method']=data['method'].lower()
			task['details']=data['details'].lower()
			task['creator']='admin'
			task['day_of_week']=data['week-type'].lower()
			task['day_of_month']=int(data['month-type'].lower())
			task['creator_id']=ObjectId(current_user.id)
			task['creation_time']=datetime.now()

			if task['method']=='sms' or task['method']=='voice':
				task['details']=country_code+task['details']

			_id=db.reminders.save(task)
			task['_id']=_id
			attachment=request.files['attachment']
			if attachment:
				if allowed_file(attachment.filename):
					attachment_name='attachment_'+str(_id)+'.'+attachment.filename.rsplit('.', 1)[1]
					attachment.save(os.path.join(app.config['UPLOAD_FOLDER'],attachment_name))
					task['attachment']=os.path.join(app.config['UPLOAD_FOLDER'],attachment_name)
					task['attachment_name']=attachment_name
					task['attachment_original_name']=attachment.filename
					db.reminders.save(task)


			if task['method']=='voice':
				task['voice_response']=os.path.join(app.config['UPLOAD_FOLDER'],'response_'+str(_id)+'.xml')
				output_file=codecs.open('static/data/response_'+str(_id)+'.xml','w','utf-8')
				response='<?xml version="1.0" encoding="UTF-8"?>\
					<Response>\
					    <Say voice="alice" language="en-IN">'+task['message']+'</Say>\
					</Response>'
				output_file.write(response)
				output_file.close()
				db.reminders.save(task)

			task['time_output']=''
			if task['type']=='one-time':
				task['time_output']='Once at '+task['time'].strftime('%b %d, %Y %I:%M %p')
			elif task['type']=='daily':
				task['time_output']='Daily at '+task['time'].strftime('%I:%M %p')
			elif task['type']=='weekly':
				task['time_output']='Weekly on '+task['day_of_week'].title()+' at '+task['time'].strftime('%I:%M %p')
			else:

				task['time_output']='Monthly on - '+str(task['day_of_month'])+suffix[task['day_of_month']-1] +' day at ' +\
								task['time'].strftime('%I:%M %p')
			output.append(task)
		except Exception as inst:
			app.logger.debug(inst)
			app.logger.error('Problem submitting task')
			output.sort(key=sorter)
			return render_template('new_task.html',tasks=output,error='Problem submitting task. Try again later',active='new_task')
			
	output.sort(key=sorter)
	return render_template('list.html',tasks=output,active='task_list')

@app.route('/delete_task')
def delete_task():
	_id=request.args.get('id')
	client=MongoClient()
	db=client[app.config['DATABASE']]
	app.logger.debug(_id)
	db.reminders.remove({'_id':ObjectId(_id)})
	app.logger.debug('Deleted task:'+_id)
	return redirect(url_for('task_list'))
	

@app.route('/perform_task')
def perform_task():
	
	_id=request.args.get('id')
	result=task_worker(_id)	
	if result==1:
		return render_template('task_completion.html')	
	else:
		app.logger.error("ERROR in performing task: "+_id)
		return render_template('task_completion.html')

def task_worker(_id,instant=False):
	def send_mail(data,files):
		result=requests.post(
        "https://api.mailgun.net/v2/remindica.com/messages",
        auth=("api", "key-1b9979216cd5d2f065997d3d53852cd6"),
        files=files,
        data=data)
		
		app.logger.debug(result)


	client=MongoClient()
	db=client[app.config['DATABASE']]
	app.logger.debug(_id)
	task=db.reminders.find({'_id':ObjectId(_id)})
	task=task.next()
	timezone='IST'
	if task['method']=='http' and task['state']=='active':
		account_sid = ACCOUNT_SID
		auth_token = AUTH_TOKEN
		client = TwilioRestClient(account_sid, auth_token)
		if ('sms_id' in task):

			message=client.sms.messages.get(task['sms_id'])
			task_status_id=task['details']
			reminder_task=db.status.find({'_id':task_status_id})
			reminder_task=reminder_task.next()
			reminder_task['status']=message.status

			db.status.save(reminder_task)

			task['state']='done'
			db.reminders.save(task)
			return 1

		if('call_id' in task):
			call=client.calls.get(task['call_id'])
			task_status_id=task['details']
			reminder_task=db.status.find({'_id':task_status_id})
			reminder_task=reminder_task.next()
			reminder_task['status']=call.status
			db.status.save(reminder_task)
			task['state']='done'
			db.reminders.save(task)
			return 1


	if task['method']=='sms' and (task['state']=='active' or instant==True):
		account_sid = ACCOUNT_SID
		auth_token = AUTH_TOKEN
		client = TwilioRestClient(account_sid, auth_token)
		message = client.sms.messages.create(body=task['message'],
	    		to=task['details'],
				from_="+14157499397")

		
		if(task['type']=='one-time'):
			task['state']='done'
		task_status={}
		task_status['task_id']=task['_id']
		task_status['method']=task['method']
		task_status['time_performed']=datetime.now()+timedelta(hours=9,minutes=30)
		task_status['status']='-'
		task_status['sms_id']=message.sid
		
		task_status_id=db.status.save(task_status)

		url_task={}
		url_task['type']='one-time'
		url_task['time']=datetime.now()+timedelta(hours=9,minutes=32)
		url_task['state']='active'
		url_task['timezone']='IST'
		url_task['method']='http'
		url_task['message']='http task'
		url_task['details']=task_status_id
		url_task['creator']='admin'
		url_task['day_of_week']=1
		url_task['day_of_month']=1
		url_task['creator_id']='admin'
		url_task['creation_time']=datetime.now()
		url_task['sms_id']=message.sid


		db.reminders.save(url_task)
		db.reminders.save(task)
		return 1

	if task['method']=='voice' and (task['state']=='active' or instant==True):
		account_sid = ACCOUNT_SID
		auth_token = AUTH_TOKEN
		client = TwilioRestClient(account_sid, auth_token)
		response_file=''
		if ('voice_response' in task):
			response_file=task['voice_response']
		else:
			response_file="static/data/response_"+_id+".xml"
		call = client.calls.create(to=task['details'],  # Any phone number
                                  #from_="+16065474465", # Must be a valid Twilio number
                                   from_="+14157499397",
                                   url=app.config['HOST']+'/'+response_file,
                                   method='get',
                                   record="true",
                                   timeout="30")
		app.logger.debug('Checking voice reminders')
		if(task['type']=='one-time'):
			task['state']='done'
		task_status={}
		task_status['task_id']=task['_id']
		task_status['method']=task['method']
		task_status['time_performed']=datetime.now()+timedelta(hours=9,minutes=30)
		task_status['status']='-'
		task_status['call_id']=call.sid
		
		task_status_id=db.status.save(task_status)

		url_task={}
		url_task['type']='one-time'
		url_task['time']=datetime.now()+timedelta(hours=9,minutes=32)
		url_task['state']='active'
		url_task['timezone']='IST'
		url_task['method']='http'
		url_task['message']='http task'
		url_task['details']=task_status_id
		url_task['creator']='admin'
		url_task['day_of_week']=1
		url_task['day_of_month']=1
		url_task['creator_id']='admin'
		url_task['creation_time']=datetime.now()
		url_task['call_id']=call.sid

		db.reminders.save(url_task)
		db.reminders.save(task)
		return 1

	if task['method']=='email' and (task['state']=='active' or instant==True):

		

		subject='Reminder: '+task['message']
		if('subject' in task):
			subject=task['subject']

		text=task['message']
		html=task['message']
		creator_id=task['creator_id']
		user=db.users.find({'_id':creator_id})
		user=user.next()
		files=None
		if ('attachment' in task):
			files=[("attachment",open(task['attachment']))]
		from_name='Remindica'
		if 'name' in user:
			from_name=user['name']
		recipient=task['details']
		data={"from": from_name + " <admin@remindica.com>",
              "to": [recipient],
              "subject": subject,
              "text": text,
              "html":html}
		p=multiprocessing.Process(target=send_mail,args=(data,files,))
		p.start()
		
		app.logger.debug('Sending reminder email to:'+task['details'])
		if(task['type']=='one-time'):
			task['state']='done'
		task_status={}
		task_status['task_id']=task['_id']
		task_status['type']=task['type']
		task_status['time_performed']=datetime.now()
		task_status['status']='sent'
		db.status.save(task_status)


		db.reminders.save(task)
		return 1
	return 1

if app.debug is None or app.debug is False or app.debug is True:   
	    import logging
	    from logging.handlers import RotatingFileHandler
	    file_handler = RotatingFileHandler('/home/uday/code/reminder_service/logs/application.log', maxBytes=1024 * 1024 * 100, backupCount=20)
	    file_handler.setLevel(logging.DEBUG)
	    formatter = logging.Formatter("%(asctime)s - %(funcName)s - %(levelname)s - %(message)s")
	    file_handler.setFormatter(formatter)
	    app.logger.addHandler(file_handler)
	    app.logger.error(str(app.config))
	    #pool=Pool(1)
	    #pool.map(poller,[3])
	    #thread.start_new_thread(poller,())

if __name__=='__main__':
	app.run()
	