#===          Import packages      ===#
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from models import User
from flask_login import login_user, logout_user, login_required, current_user
from __init__ import db
from emails import send_email


auth = Blueprint('auth', __name__) # create Blueprint object 'auth'

@auth.route('/login', methods=['GET', 'POST']) # define login page path
def login(): # define login page fucntion
    if request.method=='GET': # if the request is a GET we return the login page
        return render_template('login.html')
    else: # if the request is POST check user/password
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        user = User.query.filter_by(email=email).first()
        # check if the user exists
        # take the password, hash it, compare it to the hashed password in the
        # db
        if not user:
            flash('Please sign up before logging in.')
            return redirect(url_for('auth.signup'))
        elif not check_password_hash(user.password, password):
            flash('Wrong login details.')
            return redirect(url_for('auth.login')) # if !user or password is bad, reload page
        # if the above check passes the user has good credentials
        login_user(user, remember=remember)
        return redirect(url_for('main.profile'))

@auth.route('/signup', methods=['GET', 'POST'])# sign up path
def signup(): # sign up function
    if request.method=='GET': # If request = GET we return the sign up page and forms
        return render_template('signup.html')
    else: # if the request = POST, then we check if the email doesn't already exist and then we save data
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first() # if this returns a user, email already exists in database
        if user: # if a user is found, redirect back to signup page so user can try again
            flash('Email address already exists')
            return redirect(url_for('auth.signup'))
        # create a new user hash password so the plain text version isn't saved.
        new_user = User(email=email, name=name, password=generate_password_hash(password, method='sha256')) #
        # add new user to db
        db.session.add(new_user)
        db.session.commit()
        # this is broken 
        # send_email('Golden Tickets Admin <tomelay@gmail.com>', 'New User',
          #                 'mail/new_user', user=user)
        return redirect(url_for('auth.login'))

@auth.route('/logout') # define logout path
@login_required
def logout(): #define the logout function
    logout_user()
    return redirect(url_for('main.index'))
