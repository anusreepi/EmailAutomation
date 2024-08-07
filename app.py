from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_mail import Mail, Message
import pandas as pd
import schedule
import time
import threading
import datetime
import os

from gen import generate_email

app = Flask(__name__)
app.config.update(
    DEBUG=True,
    MAIL_SERVER='arkaconsultancy.xyz',
    MAIL_PORT=465,
    MAIL_USE_SSL=True,
    MAIL_USERNAME='anushree@arkaconsultancy.xyz',
    MAIL_PASSWORD='&hZRM;$i]ha#',
    SERVER_NAME='127.0.0.1:5000',
    APPLICATION_ROOT='/',
    PREFERRED_URL_SCHEME='http'
)

mail = Mail(app)

email_status = {}
email_data = {}

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_email', methods=['POST'])
def generate_email_api():
    prompt = request.form['prompt']
    file = request.files['file']
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    recipients_df = pd.read_excel(file_path)
    subject, body = generate_email(prompt)
    
    responses = []
    for _, row in recipients_df.iterrows():
        recipient = row['Email']
        name = row['Name']
        
        # Generate a unique tracking link
        tracking_url = url_for('track_click', email=recipient, redirect_url='http://google.com', _external=True)
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{subject}</title>
        </head>
        <body>
            <h1>Dear {name}</h1>
            <p>{body}</p>
            <p>For more information or to make a purchase, <a href="{tracking_url}">click here</a>.</p>
            <p>Thank you for your attention!</p>
            <p>Best regards,<br>Your Company</p>
        </body>
        </html>
        """
        responses.append({
            "recipient": recipient,
            "subject": subject,
            "body": body
        })
    
    global email_data
    email_data = {
        'subject': subject,
        'body': body,
        'recipients': recipients_df,
        'file_path': file_path
    }
    
    return jsonify(responses)

@app.route('/send_email', methods=['POST'])
def send_email_api():
    subject = request.form['subject']
    body = request.form['body']
    send_time = request.form['sendTime']
    
    recipients_df = email_data['recipients']
    
    if send_time:
        send_time = datetime.datetime.strptime(send_time, '%H:%M').time()
        now = datetime.datetime.now().time()
        delay = (datetime.datetime.combine(datetime.date.today(), send_time) - datetime.datetime.combine(datetime.date.today(), now)).seconds
        
        schedule.every().day.at(send_time.strftime('%H:%M')).do(send_email_to_recipients, subject, body, recipients_df)
        
        threading.Thread(target=run_scheduler).start()
    else:
        send_email_to_recipients(subject, body, recipients_df)
    
    return redirect(url_for('follow_up'))

@app.route('/follow_up', methods=['GET', 'POST'])
def follow_up():
    if request.method == 'POST':
        opened_subject = request.form['openedSubject']
        opened_body = request.form['openedBody']
        not_opened_subject = request.form['notOpenedSubject']
        not_opened_body = request.form['notOpenedBody']
        opened_time = request.form['openedTime']
        not_opened_time = request.form['notOpenedTime']
        
        # Schedule follow-up emails
        schedule_follow_up_emails(opened_subject, opened_body, not_opened_subject, not_opened_body, opened_time, not_opened_time)
        
        return redirect(url_for('index'))
    
    return render_template('follow_up.html')

@app.route('/track_click', methods=['GET'])
def track_click():
    email = request.args.get('email')
    redirect_url = request.args.get('redirect_url')
    
    # Log the click
    email_status[email] = True
    
    # Redirect to the final destination
    return redirect(redirect_url)

def send_email_to_recipients(subject, body, recipients_df):
    with app.app_context():
        for _, row in recipients_df.iterrows():
            recipient = row['Email']
            email_status[recipient] = False
            
            # Generate a unique tracking link
            tracking_url = url_for('track_click', email=recipient, redirect_url='http://google.com', _external=True)
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{subject}</title>
            </head>
            <body>
                <h1>Dear {row['Name']}</h1>
                <p>{body}</p>
                <p>For more information or to make a purchase, <a href="{tracking_url}">click here</a>.</p>
                <p>Thank you for your attention!</p>
                <p>Best regards,<br>Your Company</p>
            </body>
            </html>
            """
            
            msg = Message(subject, sender="anushree@arkaconsultancy.xyz", recipients=[recipient])
            msg.body = body
            msg.html = html_body
            mail.send(msg)

def schedule_follow_up_emails(opened_subject, opened_body, not_opened_subject, not_opened_body, opened_time, not_opened_time):
    recipients_df = email_data['recipients']
    
    if opened_time:
        opened_time = datetime.datetime.strptime(opened_time, '%H:%M').time()
        for _, row in recipients_df.iterrows():
            recipient = row['Email']
            # Schedule the follow-up for opened emails
            schedule.every().day.at(opened_time.strftime('%H:%M')).do(check_and_send_follow_up, recipient, opened_subject, opened_body, True)
    
    if not_opened_time:
        not_opened_time = datetime.datetime.strptime(not_opened_time, '%H:%M').time()
        for _, row in recipients_df.iterrows():
            recipient = row['Email']
            # Schedule the follow-up for not opened emails
            schedule.every().day.at(not_opened_time.strftime('%H:%M')).do(check_and_send_follow_up, recipient, not_opened_subject, not_opened_body, False)

def check_and_send_follow_up(recipient, subject, body, opened):
    if email_status.get(recipient) == opened:
        follow_up_subject = subject
        follow_up_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{follow_up_subject}</title>
        </head>
        <body>
            <h1>Dear {recipient}</h1>
            <p>This is a follow-up email.</p>
            <p>Original Message:</p>
            <blockquote>{body}</blockquote>
            <p>Best regards,<br>Your Company</p>
        </body>
        </html>
        """
        
        msg = Message(follow_up_subject, sender="anushree@arkaconsultancy.xyz", recipients=[recipient])
        msg.body = follow_up_body
        msg.html = follow_up_body
        mail.send(msg)

def run_scheduler():
    with app.app_context():
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == '__main__':
    app.run(debug=True)
