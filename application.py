from flask import Flask, flash, redirect, render_template, request, session
import os
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from pytz import timezone
import json
import requests
import time

from helpers import apology, login_required
from lightHelpers import Converter

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# New database configuration

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    hash = db.Column(db.String(255), unique=True, nullable=False)
    alarm_hours = db.Column(db.Numeric(precision=8, asdecimal=False, decimal_return_scale=None), unique=False, nullable=True, default=None)
    alarm_minutes = db.Column(db.Numeric(precision=8, asdecimal=False, decimal_return_scale=None), unique=False, nullable=True, default=None)
    sleep_hours = db.Column(db.Numeric(precision=8, asdecimal=False, decimal_return_scale=None), unique=False, nullable=True, default=None)
    sleep_minutes = db.Column(db.Numeric(precision=8, asdecimal=False, decimal_return_scale=None), unique=False, nullable=True, default=None)
    light_x = db.Column(db.Numeric(precision=8, asdecimal=True, decimal_return_scale=None), unique=False, nullable=False, default=0.3127159072215825)
    light_y = db.Column(db.Numeric(precision=8, asdecimal=True, decimal_return_scale=None), unique=False, nullable=False, default=0.3290014805066623)

# , light_x=0.3127159072215825, light_y=0.3290014805066623
    # def __init__(self, name):
    #     self.name = name`

@app.route("/")
@login_required
def home():
    # alarm_hours = db.execute("SELECT alarm_hours FROM users WHERE id = :id", id=session["user_id"])[0]["alarm_hours"]
    user_data = User.query.filter_by(id=session["user_id"]).first()

    alarm_hours = user_data.alarm_hours
    alarm_minutes = user_data.alarm_minutes



    #alarm_minutes = db.execute("SELECT alarm_minutes FROM users WHERE id = :id", id=session["user_id"])[0]["alarm_minutes"]
    # alarm_minutes = User.query.filter_by(id=session["user_id"]).first().alarm_minutes

    if alarm_hours != None and alarm_minutes != None:

        # Calculate remaining things for wake up time and sleep hours
        sleep_hours = user_data.sleep_hours
        sleep_minutes = user_data.sleep_minutes
        # sleep_hours = db.execute("SELECT sleep_hours FROM users WHERE id = :id", id=session["user_id"])[0]["sleep_hours"]
        # sleep_minutes = db.execute("SELECT sleep_minutes FROM users WHERE id = :id", id=session["user_id"])[0]["sleep_minutes"]
        am_pm = "AM"
        if alarm_hours > 12:
            alarm_hours -= 12
            am_pm = "PM"

        # Calculate what time user needs to go to sleep to achieve both of the above

        tosleep_hours = alarm_hours
        tosleep_am_pm = am_pm
        tosleep_minutes = alarm_minutes - sleep_minutes
        if tosleep_minutes < 0:
            tosleep_minutes += 60
            tosleep_hours -= 1
        tosleep_hours -= sleep_hours
        if tosleep_hours <= 0:
            if tosleep_hours < 0:
                if tosleep_am_pm == "AM":
                    tosleep_am_pm = "PM"
                else:
                    tosleep_am_pm = "AM"
            tosleep_hours += 12

        return render_template("home-alarm.html", alarm_hours=alarm_hours, alarm_minutes=alarm_minutes, sleep_hours=sleep_hours,
                                sleep_minutes=sleep_minutes, am_pm=am_pm, tosleep_hours=tosleep_hours, tosleep_minutes=tosleep_minutes,
                                tosleep_am_pm=tosleep_am_pm)
    else:
        return render_template("home.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("login.html", error_code=1)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("login.html", error_code=2)

        # Query database for username
        # rows = db.execute("SELECT * FROM users WHERE username = :username",
        #                   username=request.form.get("username"))
        user_data = User.query.filter_by(username=request.form.get("username")).first()
        rows = current_info = [{"alarm_hours":user_data.alarm_hours, "alarm_minutes":user_data.alarm_minutes, "sleep_hours":user_data.sleep_hours, "sleep_minutes":user_data.sleep_minutes, "hash":user_data.hash, "id":user_data.id}]

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("login.html", error_code=3)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html", error_code=0)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("register.html", error_code=1)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("register.html", error_code=2)

        # Ensure password was submitted for a second time
        elif not request.form.get("confirmation"):
            return render_template("register.html", error_code=3)

        # Ensure password and confirmation password match
        elif request.form.get("password") != request.form.get("confirmation"):
            return render_template("register.html", error_code=4)

        # Add user to database
        hashed_password = generate_password_hash(request.form.get("password"))
        #result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                            #username=request.form.get("username"), hash=hashed_password)

        user_data = User.query.filter_by(username=request.form.get("username")).first()

        # Check for insertion failures
        if user_data is not None:
            return render_template("register.html", error_code=5)
        else:
            new_user = User(username=request.form.get("username"), hash=hashed_password)
            db.session.add(new_user)
            db.session.commit()

        # automatic login (and redirection to home page)
        session["user_id"] = new_user.id
        return redirect("/")

    else:
        return render_template("register.html", error_code=0)

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/set", methods=["GET", "POST"])
@login_required
def set_alarm():
    if request.method == "POST":
        # Do the stuff that's supposed to happen after the form is submitted
        alarm_hours = int(request.form.get("clock-hour"))
        alarm_minutes = int(request.form.get("clock-minute"))
        sleep_hours = int(request.form.get("sleep-hours"))
        sleep_minutes = int(request.form.get("sleep-minutes"))

        if request.form.get("clock-am-pm") == "PM":
            alarm_hours += 12

        # db.execute("UPDATE users SET alarm_hours=:alarm_hours, alarm_minutes=:alarm_minutes, sleep_hours=:sleep_hours, sleep_minutes=:sleep_minutes WHERE id=:id",
        #            alarm_hours=alarm_hours, alarm_minutes=alarm_minutes, sleep_hours=sleep_hours, sleep_minutes=sleep_minutes, id=session["user_id"])
        # # https://stackoverflow.com/questions/6699360/flask-sqlalchemy-update-a-rows-information

        user_data = User.query.filter_by(id=session["user_id"]).first()
        user_data.alarm_hours = alarm_hours
        user_data.alarm_minutes = alarm_minutes
        user_data.sleep_hours = sleep_hours
        user_data.sleep_minutes = sleep_minutes
        db.session.commit()

        return redirect("/")
    else:
        user_data = User.query.filter_by(id=session["user_id"]).first()
        # current_info = db.execute("SELECT alarm_hours, alarm_minutes, sleep_hours, sleep_minutes FROM users WHERE id=:id", id=session["user_id"])[0]
        # if current_info["alarm_hours"] == None and current_info["alarm_minutes"] == None and current_info["sleep_minutes"] == None and current_info["sleep_hours"] == None:
        if user_data.alarm_hours == None and user_data.alarm_minutes == None and user_data.sleep_hours == None and user_data.sleep_minutes == None:
            new_haven = timezone('EST')
            time = datetime.now(new_haven)
            return render_template("set-alarm.html", load_time=time.minute)
        else:
            return redirect("/edit")

@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit_alarm():
    if request.method == "POST":
        # Do the stuff that's supposed to happen after the form is submitted
        alarm_hours = int(request.form.get("clock-hour"))
        alarm_minutes = int(request.form.get("clock-minute"))
        sleep_hours = int(request.form.get("sleep-hours"))
        sleep_minutes = int(request.form.get("sleep-minutes"))

        if request.form.get("clock-am-pm") == "PM":
            alarm_hours += 12

        # db.execute("UPDATE users SET alarm_hours=:alarm_hours, alarm_minutes=:alarm_minutes, sleep_hours=:sleep_hours, sleep_minutes=:sleep_minutes WHERE id=:id",
        #            alarm_hours=alarm_hours, alarm_minutes=alarm_minutes, sleep_hours=sleep_hours, sleep_minutes=sleep_minutes, id=session["user_id"])

        user_data = User.query.filter_by(id=session["user_id"]).first()
        user_data.alarm_hours = alarm_hours
        user_data.alarm_minutes = alarm_minutes
        user_data.sleep_hours = sleep_hours
        user_data.sleep_minutes = sleep_minutes
        db.session.commit()

        return redirect("/")
    else:
        # current_info = db.execute("SELECT alarm_hours, alarm_minutes, sleep_hours, sleep_minutes FROM users WHERE id=:id", id=session["user_id"])[0]

        user_data = User.query.filter_by(id=session["user_id"]).first()
        current_info = {"alarm_hours":user_data.alarm_hours, "alarm_minutes":user_data.alarm_minutes, "sleep_hours":user_data.sleep_hours, "sleep_minutes":user_data.sleep_minutes}

        if current_info["alarm_hours"] != None and current_info["alarm_minutes"] != None and current_info["sleep_minutes"] != None and current_info["sleep_hours"] != None:
            am_pm = "AM"
            if current_info["alarm_hours"] > 12:
                am_pm = "PM"
            new_haven = timezone('EST')
            time = datetime.now(new_haven)
            return render_template("edit-alarm.html", current_info=current_info, am_pm=am_pm, load_time=time.minute)
        else:
            return redirect("/set")

@app.route("/alarm", methods=["GET", "POST"])
@login_required
def sound_alarm():
    if request.method == "POST":
        return redirect("/")
    else:
        return render_template("sound-alarm.html")

@app.route("/snooze", methods=["GET", "POST"])
@login_required
def snooze():
    # Change the alarm_hours and alarm_minutes variables so the alarm gets set for 5 minutes later
    # current_info = db.execute("SELECT alarm_hours, alarm_minutes FROM users WHERE id=:id", id=session["user_id"])[0]
    current_info = User.query.filter_by(id=session["user_id"]).first()
    new_minutes = current_info.alarm_minutes + 5
    new_hours = current_info.alarm_hours
    if new_minutes >= 60:
        new_minutes -= 60
        new_hours += 1

    # Update the database with this information (so alarm itself changes)
    # db.execute("UPDATE users SET alarm_hours=:alarm_hours, alarm_minutes=:alarm_minutes WHERE id=:id",
    #            alarm_hours=new_hours, alarm_minutes=new_minutes, id=session["user_id"])

    user_data = User.query.filter_by(id=session["user_id"]).first()
    user_data.alarm_hours = new_hours
    user_data.alarm_minutes = new_minutes
    db.session.commit()

    return redirect("/")



@app.route("/cancel", methods=["GET", "POST"])
@login_required
def cancel_alarm():
    # db.execute("UPDATE users SET alarm_hours=NULL, alarm_minutes=NULL, sleep_hours=NULL, sleep_minutes=NULL WHERE id=:id", id=session["user_id"])

    user_data = User.query.filter_by(id=session["user_id"]).first()
    user_data.alarm_hours = None
    user_data.alarm_minutes = None
    user_data.sleep_hours = None
    user_data.sleep_minutes = None
    db.session.commit()

    return redirect("/")

@app.route("/set-light", methods=["GET", "POST"])
@login_required
def set_light():
    if request.method == "POST":
        converter = Converter()
        red_value = int(request.form.get("red"))
        green_value = int(request.form.get("green"))
        blue_value = int(request.form.get("blue"))
        xy_value = converter.rgb_to_xy(red_value, green_value, blue_value)
        print(xy_value)
        return redirect("/")
    else:
        return render_template("set-lights.html")

def errorhandler(e):
    """Handle error"""
    #return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
