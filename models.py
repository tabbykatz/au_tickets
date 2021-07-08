from flask_login import UserMixin
from __init__ import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    #github_user = db.Column(db.String(1000))  
    #github_repo = db.Column(db.String(1000))  
    #google_user = db.Column(db.String(1000))
    #google_cal_id = db.Column(db.String(1000))  
